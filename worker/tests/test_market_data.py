import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from unittest.mock import patch, MagicMock
import pandas as pd
import pytest

from market_data import fetch_etf_quotes


def _make_etf_df(rows):
    """Helper to create a DataFrame mimicking ak.fund_etf_spot_em() output."""
    return pd.DataFrame(rows)


class TestFetchEtfQuotesNetworkError:
    """TC-06: AkShare network error should not crash, returns empty dict."""

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
