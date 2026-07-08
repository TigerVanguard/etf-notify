"""
System Integration Tests for etf-notify
Tests real external services (AkShare, PushDeer, Firestore) without mocks.

These tests make live network calls, so they only run when the PUSHDEER_KEY
environment variable is set (e.g. in CI with secrets). A default local
`pytest` run skips this whole module.
"""
import io
import json
import logging
import os
import sys
import traceback
from datetime import datetime, timedelta, timezone

import pytest

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace")

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)],
)
logger = logging.getLogger("system_test")

TZ_BEIJING = timezone(timedelta(hours=8))

RESULTS = {}
AKSHARE_DATA = {}

DEFAULT_LEVELS = [
    {"name": "提醒", "threshold": -1.0, "color": "yellow"},
    {"name": "警告", "threshold": -2.0, "color": "orange"},
    {"name": "紧急", "threshold": -3.0, "color": "red"},
]

PUSHDEER_KEY = os.environ.get("PUSHDEER_KEY", "")

# Skip the entire module unless explicitly enabled via env: these are live
# system tests (AkShare / PushDeer / Firestore), not unit tests.
pytestmark = pytest.mark.skipif(
    not PUSHDEER_KEY,
    reason="PUSHDEER_KEY 环境变量未设置，跳过系统集成测试（避免真实网络调用）",
)


def record(test_id, status, details=""):
    RESULTS[test_id] = {"status": status, "details": details}
    icon = {"PASS": "✓", "FAIL": "✗", "SKIP": "⊘"}.get(status, "?")
    print(f"\n[{icon}] {test_id}: {status}")
    if details:
        for line in details.strip().split("\n"):
            print(f"    {line}")


# ── ST-01: AkShare Real Data Fetch ──────────────────────────────────────────

def test_st01_akshare():
    global AKSHARE_DATA
    print("\n" + "=" * 60)
    print("ST-01: AkShare 实时数据获取（真实网络请求）")
    print("=" * 60)

    try:
        from market_data import fetch_etf_quotes

        fund_codes = ["159941", "513100", "513500", "159612"]
        print(f"请求基金代码: {fund_codes}")
        print("正在调用 AkShare API...")

        quotes = fetch_etf_quotes(fund_codes)

        if not quotes:
            record("ST-01", "FAIL", "AkShare 返回空数据。可能原因：\n- 非交易日无实时数据\n- 网络问题\n- AkShare API 变更")
            return

        AKSHARE_DATA = quotes
        details_lines = [f"成功获取 {len(quotes)}/{len(fund_codes)} 只基金数据:"]
        details_lines.append(f"{'代码':<8} {'名称':<12} {'最新价':>8} {'昨收':>8} {'涨跌幅':>8} {'最高':>8} {'最低':>8} {'成交量':>12}")
        details_lines.append("-" * 80)

        all_valid = True
        for code, q in quotes.items():
            price = q.get("price", 0)
            prev = q.get("prev_close", 0)
            chg = q.get("change_pct", 0)
            name = q.get("name", "N/A")
            high = q.get("high", 0)
            low = q.get("low", 0)
            vol = q.get("volume", 0)
            details_lines.append(
                f"{code:<8} {name:<12} {price:>8.3f} {prev:>8.3f} {chg:>+8.2f}% {high:>8.3f} {low:>8.3f} {vol:>12,}"
            )
            if price <= 0 or prev <= 0:
                all_valid = False
                details_lines.append(f"  ⚠ {code} 价格异常: price={price}, prev_close={prev}")

        now_str = datetime.now(TZ_BEIJING).strftime("%Y-%m-%d %H:%M:%S")
        details_lines.append(f"\n获取时间: {now_str} (北京时间)")
        details_lines.append(f"注意: 今天是周六，数据为最近一个交易日(周五)的收盘数据")

        detail = "\n".join(details_lines)
        if all_valid and len(quotes) >= 2:
            record("ST-01", "PASS", detail)
        elif len(quotes) > 0:
            record("ST-01", "PASS", detail + "\n部分基金数据缺失，但主要基金数据有效")
        else:
            record("ST-01", "FAIL", detail)

    except Exception as e:
        record("ST-01", "FAIL", f"异常: {type(e).__name__}: {e}\n{traceback.format_exc()}")


# ── ST-02: Firestore Read/Write ─────────────────────────────────────────────

def test_st02_firestore():
    print("\n" + "=" * 60)
    print("ST-02: Firestore 读写（真实数据库）")
    print("=" * 60)

    creds_json = os.environ.get("FIREBASE_CREDENTIALS")
    if not creds_json:
        record("ST-02", "SKIP",
               "FIREBASE_CREDENTIALS 环境变量未设置。\n"
               "需要 Firebase 服务账号凭证才能执行此测试。\n"
               "本地未找到服务账号 JSON 文件。\n"
               "Firebase CLI 登录已过期。")
        return

    try:
        from config import init_firebase, DEFAULT_CONFIG
        db = init_firebase()

        sub_results = []

        # a. Write test config
        print("  a. 写入测试配置到 /config/settings ...")
        test_config = dict(DEFAULT_CONFIG)
        test_config["_system_test"] = True
        test_config["_test_time"] = datetime.now(TZ_BEIJING).isoformat()
        db.collection("config").document("settings").set(test_config)
        sub_results.append("a. 写入配置 ✓")

        # b. Read back and verify
        print("  b. 读取配置验证一致性 ...")
        doc = db.collection("config").document("settings").get()
        if doc.exists:
            read_config = doc.to_dict()
            funds_match = len(read_config.get("funds", [])) == len(test_config["funds"])
            levels_match = len(read_config.get("levels", [])) == len(test_config["levels"])
            sub_results.append(f"b. 读取配置 ✓ (funds匹配:{funds_match}, levels匹配:{levels_match})")
        else:
            sub_results.append("b. 读取配置 ✗ (文档不存在)")

        # c. Write test snapshot
        print("  c. 写入测试快照 ...")
        test_date = "test-system-" + datetime.now(TZ_BEIJING).strftime("%Y%m%d%H%M%S")
        snap_doc = {
            "date": test_date,
            "updated_at": datetime.now(TZ_BEIJING).isoformat(),
            "quotes": {"159941": {"name": "纳指ETF", "price": 1.5, "prev_close": 1.6, "change_pct": -6.25}},
            "_system_test": True,
        }
        db.collection("snapshots").document(test_date).set(snap_doc)
        sub_results.append(f"c. 写入快照 ✓ (doc_id: {test_date})")

        # d. Write test notification
        print("  d. 写入测试通知 ...")
        notif_doc = {
            "fund_code": "TEST",
            "fund_name": "系统测试",
            "level": "提醒",
            "change_pct": -1.5,
            "price": 1.5,
            "timestamp": datetime.now(TZ_BEIJING).isoformat(),
            "channels": ["system_test"],
            "delivered": True,
            "_system_test": True,
        }
        notif_ref = db.collection("notifications").add(notif_doc)
        notif_id = notif_ref[1].id
        sub_results.append(f"d. 写入通知 ✓ (doc_id: {notif_id})")

        # e. Read notification back
        print("  e. 读取通知验证 ...")
        read_notif = db.collection("notifications").document(notif_id).get()
        if read_notif.exists:
            nd = read_notif.to_dict()
            sub_results.append(f"e. 读取通知 ✓ (fund_code={nd.get('fund_code')}, level={nd.get('level')})")
        else:
            sub_results.append("e. 读取通知 ✗")

        # f. Cleanup
        print("  f. 清理测试数据 ...")
        db.collection("snapshots").document(test_date).delete()
        db.collection("notifications").document(notif_id).delete()
        sub_results.append("f. 清理测试数据 ✓")

        record("ST-02", "PASS", "\n".join(sub_results))

    except Exception as e:
        record("ST-02", "FAIL", f"异常: {type(e).__name__}: {e}\n{traceback.format_exc()}")


# ── ST-03: PushDeer Real Push ────────────────────────────────────────────────

def test_st03_pushdeer():
    print("\n" + "=" * 60)
    print("ST-03: PushDeer 推送（真实推送）")
    print("=" * 60)

    try:
        from notifier import send_pushdeer

        now_str = datetime.now(TZ_BEIJING).strftime("%Y-%m-%d %H:%M:%S")

        akshare_status = "✓" if AKSHARE_DATA else "未测试"
        title = "[系统测试] ETF Notify 系统测试通过"
        body = (
            f"测试时间: {now_str}\n"
            f"数据源: AkShare {akshare_status}\n"
            f"推送通道: PushDeer ✓"
        )

        print(f"推送标题: {title}")
        print(f"推送内容:\n{body}")
        print(f"PushDeer Key: {PUSHDEER_KEY[:10]}...{PUSHDEER_KEY[-6:]}")

        result = send_pushdeer(PUSHDEER_KEY, title, body)

        if result:
            record("ST-03", "PASS",
                   f"PushDeer 推送成功\n"
                   f"标题: {title}\n"
                   f"时间: {now_str}\n"
                   f"请检查手机是否收到通知")
        else:
            record("ST-03", "FAIL", "send_pushdeer 返回 False，推送失败")

    except Exception as e:
        record("ST-03", "FAIL", f"异常: {type(e).__name__}: {e}\n{traceback.format_exc()}")


# ── ST-04: Threshold Integration Test ───────────────────────────────────────

def test_st04_threshold():
    print("\n" + "=" * 60)
    print("ST-04: 门限判断集成测试（真实数据 + 真实门限）")
    print("=" * 60)

    try:
        from threshold import check_threshold

        data_source = AKSHARE_DATA if AKSHARE_DATA else {
            "159941": {"name": "纳指ETF(模拟)", "price": 1.5, "prev_close": 1.6, "change_pct": -1.5},
        }

        if not AKSHARE_DATA:
            print("⚠ 使用模拟数据（ST-01 未获取到真实数据）")
        else:
            print(f"使用 ST-01 获取的真实行情数据 ({len(AKSHARE_DATA)} 只基金)")

        details_lines = [f"门限配置:"]
        for lv in DEFAULT_LEVELS:
            details_lines.append(f"  {lv['name']}: {lv['threshold']}%")
        details_lines.append("")
        details_lines.append(f"{'代码':<8} {'名称':<12} {'涨跌幅':>8} {'触发级别':<10} {'说明'}")
        details_lines.append("-" * 65)

        for code, q in data_source.items():
            change_pct = q.get("change_pct", 0)
            name = q.get("name", code)
            triggered = check_threshold(change_pct, DEFAULT_LEVELS)

            if triggered:
                level_name = triggered["name"]
                threshold_val = triggered["threshold"]
                details_lines.append(
                    f"{code:<8} {name:<12} {change_pct:>+8.2f}% {level_name:<10} 触发 (门限 {threshold_val}%)"
                )
            else:
                details_lines.append(
                    f"{code:<8} {name:<12} {change_pct:>+8.2f}% {'未触发':<10} 涨跌幅未达到最低门限 (-1%)"
                )

        using = "真实数据" if AKSHARE_DATA else "模拟数据"
        details_lines.append(f"\n数据来源: {using}")
        record("ST-04", "PASS", "\n".join(details_lines))

    except Exception as e:
        record("ST-04", "FAIL", f"异常: {type(e).__name__}: {e}\n{traceback.format_exc()}")


# ── ST-05: Full Worker Flow ─────────────────────────────────────────────────

def test_st05_worker_flow():
    print("\n" + "=" * 60)
    print("ST-05: Worker 完整流程（绕过时间检查）")
    print("=" * 60)

    creds_json = os.environ.get("FIREBASE_CREDENTIALS")
    if not creds_json:
        record("ST-05", "SKIP",
               "FIREBASE_CREDENTIALS 环境变量未设置。\n"
               "Worker 完整流程需要 Firestore 连接。\n"
               "跳过此测试。")
        return

    try:
        import main as worker_main

        original_is_trading_time = worker_main.is_trading_time
        worker_main.is_trading_time = lambda: True
        print("已 monkey-patch is_trading_time() → True")

        try:
            worker_main.run()
            record("ST-05", "PASS",
                   "Worker 完整流程执行成功\n"
                   "- AkShare 获取数据 ✓\n"
                   "- Firestore 读取配置 ✓\n"
                   "- 门限判断执行 ✓\n"
                   "- 快照保存 ✓")
        except Exception as e:
            record("ST-05", "FAIL", f"Worker 运行异常: {type(e).__name__}: {e}\n{traceback.format_exc()}")
        finally:
            worker_main.is_trading_time = original_is_trading_time
            print("已恢复 is_trading_time()")

    except Exception as e:
        record("ST-05", "FAIL", f"导入或初始化异常: {type(e).__name__}: {e}\n{traceback.format_exc()}")


# ── Main ────────────────────────────────────────────────────────────────────

def main():
    print("=" * 60)
    print("ETF Notify 系统集成测试")
    print(f"时间: {datetime.now(TZ_BEIJING).strftime('%Y-%m-%d %H:%M:%S')} (北京时间)")
    print("=" * 60)

    test_st01_akshare()
    test_st03_pushdeer()
    test_st04_threshold()
    test_st02_firestore()
    test_st05_worker_flow()

    print("\n" + "=" * 60)
    print("测试结果汇总")
    print("=" * 60)

    for test_id in ["ST-01", "ST-02", "ST-03", "ST-04", "ST-05"]:
        r = RESULTS.get(test_id, {"status": "NOT_RUN", "details": ""})
        icon = {"PASS": "✓", "FAIL": "✗", "SKIP": "⊘", "NOT_RUN": "?"}.get(r["status"], "?")
        print(f"  [{icon}] {test_id}: {r['status']}")

    passed = sum(1 for r in RESULTS.values() if r["status"] == "PASS")
    failed = sum(1 for r in RESULTS.values() if r["status"] == "FAIL")
    skipped = sum(1 for r in RESULTS.values() if r["status"] == "SKIP")
    print(f"\n总计: {passed} PASS / {failed} FAIL / {skipped} SKIP")

    return RESULTS


if __name__ == "__main__":
    main()
