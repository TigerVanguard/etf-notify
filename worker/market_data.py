import logging
import math

import akshare as ak

logger = logging.getLogger(__name__)


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


def fetch_etf_quotes(fund_codes: list[str]) -> dict:
    """Fetch real-time ETF quotes via AkShare for the given fund codes.

    Returns a dict keyed by fund code with quote details, e.g.:
    {
        "159941": {
            "name": "纳指ETF",
            "price": 1.856,
            "prev_close": 1.917,
            "change_pct": -3.18,
            "high": 1.920,
            "low": 1.850,
            "volume": 12345678,
        }
    }
    """
    if not fund_codes:
        return {}

    try:
        df = ak.fund_etf_spot_em()
    except Exception:
        logger.exception("AkShare 获取 ETF 行情失败")
        return {}

    if df is None or df.empty:
        logger.warning("AkShare 返回数据为空")
        return {}

    result = {}
    for code in fund_codes:
        try:
            row = df[df["代码"] == code]
            if row.empty:
                logger.warning("未找到基金 %s 的行情数据", code)
                continue

            row = row.iloc[0]
            price = _parse_float(row.get("最新价"))
            prev_close = _parse_float(row.get("昨收"))

            # Bad price data must not silently become zeros in Firestore
            # (zeros can suppress alerts); exclude the fund instead.
            if price is None or prev_close is None or price <= 0 or prev_close <= 0:
                logger.warning(
                    "基金 %s 行情数据无效（price=%s, prev_close=%s），跳过该基金",
                    code,
                    row.get("最新价"),
                    row.get("昨收"),
                )
                continue

            change_pct = _parse_float(row.get("涨跌幅"))
            if change_pct is None:
                change_pct = (price - prev_close) / prev_close * 100

            high = _parse_float(row.get("最高")) or 0
            low = _parse_float(row.get("最低")) or 0
            volume_raw = _parse_float(row.get("成交量"))
            volume = int(volume_raw) if volume_raw is not None else 0

            result[code] = {
                "name": str(row.get("名称", "")),
                "price": price,
                "prev_close": prev_close,
                "change_pct": change_pct,
                "high": high,
                "low": low,
                "volume": volume,
            }
        except Exception:
            logger.exception("解析基金 %s 行情数据失败", code)

    logger.info("成功获取 %d/%d 只基金行情", len(result), len(fund_codes))
    return result
