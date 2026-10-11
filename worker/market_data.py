import logging
import math

import akshare as ak
import requests

logger = logging.getLogger(__name__)

TENCENT_URL = "https://qt.gtimg.cn/q="
SINA_URL = "https://hq.sinajs.cn/list="
# Sina rejects requests without a finance.sina.com.cn referer.
SINA_HEADERS = {"Referer": "https://finance.sina.com.cn"}
HTTP_TIMEOUT = 10


def _parse_float(value) -> float | None:
    """Parse a numeric cell; return None when missing/NaN/unparseable."""
    if value is None:
        return None
    try:
        result = float(value)
    except (TypeError, ValueError):
        return None
    if math.isnan(result):
        return None
    return result


def _market_symbol(code: str) -> str:
    """Prefix a fund code with its exchange: Shanghai codes start with 5/6, the rest are Shenzhen."""
    return ("sh" if code.startswith(("5", "6")) else "sz") + code


def _make_quote(code, *, name, price, prev_close, source,
                change_pct=None, high=None, low=None, volume=None) -> dict | None:
    """Validate one quote and build the common quote dict; return None if unusable."""
    # Bad price data must not silently become zeros in Firestore
    # (zeros can suppress alerts); exclude the fund instead.
    if price is None or prev_close is None or price <= 0 or prev_close <= 0:
        logger.warning(
            "基金 %s 行情数据无效（来源=%s, price=%s, prev_close=%s），跳过该基金",
            code, source, price, prev_close,
        )
        return None

    if change_pct is None:
        change_pct = (price - prev_close) / prev_close * 100

    return {
        "name": name,
        "price": price,
        "prev_close": prev_close,
        "change_pct": change_pct,
        "high": high or 0,
        "low": low or 0,
        "volume": int(volume) if volume is not None else 0,
        "source": source,
    }


def _fetch_from_akshare(fund_codes: list[str]) -> dict:
    """Primary source: AkShare's full ETF list (backed by Eastmoney)."""
    try:
        df = ak.fund_etf_spot_em()
    except Exception as exc:
        logger.warning("AkShare 获取 ETF 行情失败: %s: %s", type(exc).__name__, exc)
        return {}

    if df is None or df.empty:
        logger.warning("AkShare 返回数据为空")
        return {}

    result = {}
    for code in fund_codes:
        try:
            row = df[df["代码"] == code]
            if row.empty:
                logger.warning("AkShare 未找到基金 %s 的行情数据", code)
                continue

            row = row.iloc[0]
            quote = _make_quote(
                code,
                name=str(row.get("名称", "")),
                price=_parse_float(row.get("最新价")),
                prev_close=_parse_float(row.get("昨收")),
                change_pct=_parse_float(row.get("涨跌幅")),
                high=_parse_float(row.get("最高")),
                low=_parse_float(row.get("最低")),
                volume=_parse_float(row.get("成交量")),
                source="akshare",
            )
            if quote:
                result[code] = quote
        except Exception:
            logger.exception("解析基金 %s 行情数据失败", code)
    return result


def _fetch_from_tencent(fund_codes: list[str]) -> dict:
    """Fallback source: Tencent quote API, one request for all codes.

    Response lines look like v_sz159941="51~name~code~price~prev_close~open~volume~...";
    """
    url = TENCENT_URL + ",".join(_market_symbol(code) for code in fund_codes)
    resp = requests.get(url, timeout=HTTP_TIMEOUT)
    resp.raise_for_status()
    text = resp.content.decode("gbk", errors="replace")

    result = {}
    for line in text.split(";"):
        if '"' not in line or "~" not in line:
            continue
        fields = line.split('"')[1].split("~")
        if len(fields) < 35 or fields[2] not in fund_codes:
            continue
        code = fields[2]
        quote = _make_quote(
            code,
            name=fields[1],
            price=_parse_float(fields[3]),
            prev_close=_parse_float(fields[4]),
            high=_parse_float(fields[33]),
            low=_parse_float(fields[34]),
            volume=_parse_float(fields[6]),
            source="tencent",
        )
        if quote:
            result[code] = quote
    return result


def _fetch_from_sina(fund_codes: list[str]) -> dict:
    """Fallback source: Sina quote API, one request for all codes.

    Response lines look like var hq_str_sz159941="name,open,prev_close,price,high,low,bid,ask,volume,...";
    """
    url = SINA_URL + ",".join(_market_symbol(code) for code in fund_codes)
    resp = requests.get(url, headers=SINA_HEADERS, timeout=HTTP_TIMEOUT)
    resp.raise_for_status()
    text = resp.content.decode("gbk", errors="replace")

    result = {}
    for line in text.splitlines():
        if '="' not in line:
            continue
        code = line.split("=", 1)[0][-6:]
        fields = line.split('"')[1].split(",")
        if code not in fund_codes or len(fields) < 9:
            continue
        volume = _parse_float(fields[8])
        quote = _make_quote(
            code,
            name=fields[0],
            price=_parse_float(fields[3]),
            prev_close=_parse_float(fields[2]),
            high=_parse_float(fields[4]),
            low=_parse_float(fields[5]),
            # Sina reports volume in shares; the other sources report lots of 100.
            volume=volume / 100 if volume is not None else None,
            source="sina",
        )
        if quote:
            result[code] = quote
    return result


def fetch_etf_quotes(fund_codes: list[str]) -> dict:
    """Fetch real-time ETF quotes for the given fund codes.

    AkShare is the primary source; any fund it fails to return is retried
    via Tencent, then Sina. Returns a dict keyed by fund code, e.g.:
    {
        "159941": {
            "name": "纳指ETF",
            "price": 1.856,
            "prev_close": 1.917,
            "change_pct": -3.18,
            "high": 1.920,
            "low": 1.850,
            "volume": 12345678,
            "source": "akshare",
        }
    }
    """
    if not fund_codes:
        return {}

    result = _fetch_from_akshare(fund_codes)

    for source_name, fetch in (("腾讯", _fetch_from_tencent), ("新浪", _fetch_from_sina)):
        missing = [code for code in fund_codes if code not in result]
        if not missing:
            break
        logger.warning("%d 只基金暂无行情，改用%s行情: %s", len(missing), source_name, missing)
        try:
            result.update(fetch(missing))
        except Exception as exc:
            logger.warning("%s行情获取失败: %s: %s", source_name, type(exc).__name__, exc)

    logger.info("成功获取 %d/%d 只基金行情", len(result), len(fund_codes))
    return result
