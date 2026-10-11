import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from unittest.mock import patch, MagicMock
import pandas as pd
import pytest

from market_data import _market_symbol, fetch_etf_quotes


@pytest.fixture(autouse=True)
def block_fallback_network(monkeypatch):
    """Fallback sources must never hit the real network in unit tests."""
    def blocked(*args, **kwargs):
        raise ConnectionError("network disabled in tests")
    monkeypatch.setattr("market_data.requests.get", blocked)


def _make_etf_df(rows):
    """Helper to create a DataFrame mimicking ak.fund_etf_spot_em() output."""
    return pd.DataFrame(rows)


def _response(text):
    resp = MagicMock()
    resp.content = text.encode("gbk")
    resp.raise_for_status.return_value = None
    return resp


def _tencent_line(code, name, price, prev_close):
    fields = ["0"] * 50
    fields[0], fields[1], fields[2] = "51", name, code
    fields[3], fields[4], fields[6] = str(price), str(prev_close), "123456"
    fields[33], fields[34] = str(max(price, prev_close)), str(min(price, prev_close))
    return f'v_{_market_symbol(code)}="' + "~".join(fields) + '";\n'


def _sina_line(code, name, price, prev_close):
    fields = [name, "1.0", str(prev_close), str(price), "2.0", "0.5", "1.0", "1.0", "12345600"]
    fields += ["0"] * 23
    return f'var hq_str_{_market_symbol(code)}="' + ",".join(fields) + '";\n'


class TestFetchEtfQuotesNetworkError:
    """TC-06: when every source fails, return an empty dict without crashing."""

    @patch("market_data.ak.fund_etf_spot_em")
    def test_network_exception_returns_empty(self, mock_ak):
        mock_ak.side_effect = ConnectionError("Network unreachable")
        result = fetch_etf_quotes(["159941"])
        assert result == {}

    @patch("market_data.ak.fund_etf_spot_em")
    def test_timeout_returns_empty(self, mock_ak):
        mock_ak.side_effect = TimeoutError("Request timed out")
        result = fetch_etf_quotes(["159941"])
        assert result == {}

    @patch("market_data.ak.fund_etf_spot_em")
    def test_generic_exception_returns_empty(self, mock_ak):
        mock_ak.side_effect = RuntimeError("Unexpected error")
        result = fetch_etf_quotes(["159941"])
        assert result == {}


class TestFetchEtfQuotesSuccess:
    """Mock AkShare returning normal data, verify parsing logic."""

    @patch("market_data.ak.fund_etf_spot_em")
    def test_single_fund_parsed_correctly(self, mock_ak):
        mock_ak.return_value = _make_etf_df([
            {
                "代码": "159941",
                "名称": "纳指ETF",
                "最新价": 1.856,
                "昨收": 1.917,
                "涨跌幅": -3.18,
                "最高": 1.920,
                "最低": 1.850,
                "成交量": 12345678,
            }
        ])
        result = fetch_etf_quotes(["159941"])
        assert "159941" in result
        q = result["159941"]
        assert q["name"] == "纳指ETF"
        assert q["price"] == 1.856
        assert q["prev_close"] == 1.917
        assert q["change_pct"] == -3.18
        assert q["high"] == 1.920
        assert q["low"] == 1.850
        assert q["volume"] == 12345678

    @patch("market_data.ak.fund_etf_spot_em")
    def test_multiple_funds(self, mock_ak):
        mock_ak.return_value = _make_etf_df([
            {"代码": "159941", "名称": "纳指ETF", "最新价": 1.9, "昨收": 2.0,
             "涨跌幅": -5.0, "最高": 2.0, "最低": 1.85, "成交量": 100},
            {"代码": "513500", "名称": "标普500ETF", "最新价": 1.5, "昨收": 1.55,
             "涨跌幅": -3.23, "最高": 1.56, "最低": 1.48, "成交量": 200},
            {"代码": "000001", "名称": "其他基金", "最新价": 3.0, "昨收": 3.0,
             "涨跌幅": 0.0, "最高": 3.0, "最低": 3.0, "成交量": 999},
        ])
        result = fetch_etf_quotes(["159941", "513500"])
        assert len(result) == 2
        assert "159941" in result
        assert "513500" in result
        assert "000001" not in result

    @patch("market_data.ak.fund_etf_spot_em")
    def test_fund_not_found_in_data(self, mock_ak):
        mock_ak.return_value = _make_etf_df([
            {"代码": "000001", "名称": "其他", "最新价": 3.0, "昨收": 3.0,
             "涨跌幅": 0.0, "最高": 3.0, "最低": 3.0, "成交量": 999},
        ])
        result = fetch_etf_quotes(["159941"])
        assert result == {}

    @patch("market_data.ak.fund_etf_spot_em")
    def test_empty_dataframe_returns_empty(self, mock_ak):
        mock_ak.return_value = pd.DataFrame()
        result = fetch_etf_quotes(["159941"])
        assert result == {}

    @patch("market_data.ak.fund_etf_spot_em")
    def test_none_dataframe_returns_empty(self, mock_ak):
        mock_ak.return_value = None
        result = fetch_etf_quotes(["159941"])
        assert result == {}

    def test_empty_fund_codes_returns_empty(self):
        result = fetch_etf_quotes([])
        assert result == {}


class TestFetchEtfQuotesInvalidData:
    """Bad rows (missing/NaN/zero prices) must be excluded, not returned as zeros."""

    @patch("market_data.ak.fund_etf_spot_em")
    def test_renamed_price_column_excludes_fund(self, mock_ak):
        mock_ak.return_value = _make_etf_df([
            {"代码": "159941", "名称": "纳指ETF", "现价": 1.9, "昨收": 2.0,
             "涨跌幅": -5.0, "最高": 2.0, "最低": 1.85, "成交量": 100},
        ])
        result = fetch_etf_quotes(["159941"])
        assert result == {}

    @patch("market_data.ak.fund_etf_spot_em")
    def test_nan_price_excludes_fund(self, mock_ak):
        mock_ak.return_value = _make_etf_df([
            {"代码": "159941", "名称": "纳指ETF", "最新价": float("nan"), "昨收": 2.0,
             "涨跌幅": -5.0, "最高": 2.0, "最低": 1.85, "成交量": 100},
        ])
        result = fetch_etf_quotes(["159941"])
        assert result == {}

    @patch("market_data.ak.fund_etf_spot_em")
    def test_zero_prev_close_excludes_fund(self, mock_ak):
        mock_ak.return_value = _make_etf_df([
            {"代码": "159941", "名称": "纳指ETF", "最新价": 1.9, "昨收": 0,
             "涨跌幅": -5.0, "最高": 2.0, "最低": 1.85, "成交量": 100},
        ])
        result = fetch_etf_quotes(["159941"])
        assert result == {}

    @patch("market_data.ak.fund_etf_spot_em")
    def test_negative_price_excludes_fund(self, mock_ak):
        mock_ak.return_value = _make_etf_df([
            {"代码": "159941", "名称": "纳指ETF", "最新价": -1.9, "昨收": 2.0,
             "涨跌幅": -5.0, "最高": 2.0, "最低": 1.85, "成交量": 100},
        ])
        result = fetch_etf_quotes(["159941"])
        assert result == {}

    @patch("market_data.ak.fund_etf_spot_em")
    def test_bad_row_does_not_block_valid_funds(self, mock_ak):
        mock_ak.return_value = _make_etf_df([
            {"代码": "159941", "名称": "纳指ETF", "最新价": float("nan"), "昨收": 2.0,
             "涨跌幅": -5.0, "最高": 2.0, "最低": 1.85, "成交量": 100},
            {"代码": "513500", "名称": "标普500ETF", "最新价": 1.5, "昨收": 1.55,
             "涨跌幅": -3.23, "最高": 1.56, "最低": 1.48, "成交量": 200},
        ])
        result = fetch_etf_quotes(["159941", "513500"])
        assert "159941" not in result
        assert "513500" in result

    @patch("market_data.ak.fund_etf_spot_em")
    def test_missing_change_pct_derived_from_prices(self, mock_ak):
        mock_ak.return_value = _make_etf_df([
            {"代码": "159941", "名称": "纳指ETF", "最新价": 1.9, "昨收": 2.0,
             "涨跌幅": float("nan"), "最高": 2.0, "最低": 1.85, "成交量": 100},
        ])
        result = fetch_etf_quotes(["159941"])
        assert result["159941"]["change_pct"] == pytest.approx(-5.0)


class TestMarketSymbol:
    def test_shanghai_and_shenzhen_prefixes(self):
        assert _market_symbol("513100") == "sh513100"
        assert _market_symbol("159941") == "sz159941"


class TestFallbackSources:
    """Eastmoney (behind AkShare) has returned 502 since 2026-09-23; Tencent/Sina must take over."""

    @patch("market_data.ak.fund_etf_spot_em")
    def test_akshare_failure_falls_back_to_tencent(self, mock_ak):
        mock_ak.side_effect = RuntimeError("502 Bad Gateway")
        payload = _tencent_line("159941", "纳指ETF", 1.9, 2.0) + _tencent_line("513100", "纳指ETF国泰", 2.4, 2.374)

        with patch("market_data.requests.get", return_value=_response(payload)) as mock_get:
            result = fetch_etf_quotes(["159941", "513100"])

        url = mock_get.call_args.args[0]
        assert "sz159941" in url and "sh513100" in url
        q = result["159941"]
        assert q["source"] == "tencent"
        assert q["name"] == "纳指ETF"
        assert q["price"] == 1.9
        assert q["prev_close"] == 2.0
        assert q["change_pct"] == pytest.approx(-5.0)
        assert q["high"] == 2.0
        assert q["low"] == 1.9
        assert result["513100"]["change_pct"] == pytest.approx((2.4 - 2.374) / 2.374 * 100)

    @patch("market_data.ak.fund_etf_spot_em")
    def test_tencent_failure_falls_back_to_sina(self, mock_ak):
        mock_ak.side_effect = RuntimeError("502 Bad Gateway")

        def fake_get(url, **kwargs):
            if "gtimg" in url:
                raise ConnectionError("tencent down")
            assert kwargs["headers"]["Referer"] == "https://finance.sina.com.cn"
            return _response(_sina_line("159941", "纳指ETF", 1.9, 2.0))

        with patch("market_data.requests.get", side_effect=fake_get):
            result = fetch_etf_quotes(["159941"])

        q = result["159941"]
        assert q["source"] == "sina"
        assert q["price"] == 1.9
        assert q["prev_close"] == 2.0
        assert q["change_pct"] == pytest.approx(-5.0)
        assert q["volume"] == 123456

    @patch("market_data.ak.fund_etf_spot_em")
    def test_partial_akshare_result_only_fetches_missing_codes(self, mock_ak):
        mock_ak.return_value = _make_etf_df([
            {"代码": "159941", "名称": "纳指ETF", "最新价": 1.9, "昨收": 2.0,
             "涨跌幅": -5.0, "最高": 2.0, "最低": 1.85, "成交量": 100},
        ])
        payload = _tencent_line("513100", "纳指ETF国泰", 2.4, 2.5)

        with patch("market_data.requests.get", return_value=_response(payload)) as mock_get:
            result = fetch_etf_quotes(["159941", "513100"])

        url = mock_get.call_args.args[0]
        assert "sh513100" in url and "159941" not in url
        assert result["159941"]["source"] == "akshare"
        assert result["513100"]["source"] == "tencent"

    @patch("market_data.ak.fund_etf_spot_em")
    def test_complete_akshare_result_skips_fallbacks(self, mock_ak):
        mock_ak.return_value = _make_etf_df([
            {"代码": "159941", "名称": "纳指ETF", "最新价": 1.9, "昨收": 2.0,
             "涨跌幅": -5.0, "最高": 2.0, "最低": 1.85, "成交量": 100},
        ])

        with patch("market_data.requests.get") as mock_get:
            result = fetch_etf_quotes(["159941"])

        mock_get.assert_not_called()
        assert result["159941"]["source"] == "akshare"

    @patch("market_data.ak.fund_etf_spot_em")
    def test_invalid_tencent_price_falls_through_to_sina(self, mock_ak):
        mock_ak.side_effect = RuntimeError("502 Bad Gateway")

        def fake_get(url, **kwargs):
            if "gtimg" in url:
                return _response(_tencent_line("159941", "纳指ETF", 0, 2.0))
            return _response(_sina_line("159941", "纳指ETF", 1.9, 2.0))

        with patch("market_data.requests.get", side_effect=fake_get):
            result = fetch_etf_quotes(["159941"])

        assert result["159941"]["source"] == "sina"

    @patch("market_data.ak.fund_etf_spot_em")
    def test_unknown_codes_in_responses_are_ignored(self, mock_ak):
        mock_ak.side_effect = RuntimeError("502 Bad Gateway")

        def fake_get(url, **kwargs):
            if "gtimg" in url:
                return _response('v_pv_none_match="1";\n')
            return _response('var hq_str_sz159941="";\n')

        with patch("market_data.requests.get", side_effect=fake_get):
            result = fetch_etf_quotes(["159941"])

        assert result == {}
