import logging
import os
from datetime import datetime, timedelta, timezone

from config import init_firebase, load_config
from market_data import fetch_etf_quotes
from notifier import send_pushdeer
from threshold import check_threshold

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("system-test")

TZ_BEIJING = timezone(timedelta(hours=8))


def run_system_test() -> None:
    """Run a production-safe external integration test."""
    logger.info("=== 系统测试开始 ===")
    now = datetime.now(TZ_BEIJING)
    run_id = os.environ.get("GITHUB_RUN_ID") or now.strftime("%Y%m%d%H%M%S")

    db = init_firebase()
    config = load_config(db)
    funds = [fund for fund in config.get("funds", []) if fund.get("enabled", True)]
    if not funds:
        raise RuntimeError("系统测试失败: 没有启用的基金配置")

    fund_codes = [fund["code"] for fund in funds]
    quotes = fetch_etf_quotes(fund_codes)
    if not quotes:
        raise RuntimeError("系统测试失败: AkShare 未返回行情")

    levels = config.get("levels", [])
    triggered = []
    for code, quote in quotes.items():
        fund_name = quote.get("name", code)
        change_pct = quote.get("change_pct", 0)
        result = check_threshold(change_pct, levels)
        logger.info("%s(%s): 涨跌幅 %.2f%% 门限=%s", fund_name, code, change_pct, result)
        if result:
            triggered.append({"code": code, "name": fund_name, "level": result["name"]})

    snapshot = {
        "run_id": run_id,
        "created_at": now.isoformat(),
        "quotes": quotes,
        "triggered": triggered,
    }
    db.collection("test_snapshots").document(run_id).set(snapshot)

    pushdeer_key = os.environ.get("PUSHDEER_KEY") or config.get("pushdeer_key", "")
    if not pushdeer_key:
        raise RuntimeError("系统测试失败: PUSHDEER_KEY 未配置")

    title = "[系统测试] ETF Notify 全流程验证"
    body = (
        f"AkShare 数据获取成功: {len(quotes)} 只基金\n"
        "Firestore 测试快照写入成功\n"
        f"触发门限数量: {len(triggered)}\n"
        f"测试时间: {now.strftime('%Y-%m-%d %H:%M:%S')}"
    )
    if not send_pushdeer(pushdeer_key, title, body):
        raise RuntimeError("系统测试失败: PushDeer 推送失败")

    result_doc = {
        "run_id": run_id,
        "created_at": now.isoformat(),
        "status": "passed",
        "quotes_count": len(quotes),
        "triggered_count": len(triggered),
    }
    db.collection("system_tests").document(run_id).set(result_doc)
    logger.info("=== 系统测试完成: PASS ===")


if __name__ == "__main__":
    run_system_test()
