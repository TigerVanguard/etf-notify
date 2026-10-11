# 通知去重规则重构设计

日期：2026-10-10
状态：已确认，待实现

## 1. 背景

现行规则：每 15 分钟检查一次；每只基金取最严重的已触发级别；同一基金 + 同一级别冷却 60 分钟（`cooldown_minutes`）后可再次通知。

问题：通知过多。2026-06-10 至 2026-09-24 共发出 207 条通知，有通知的 22 天平均每天 9.4 条，最多一天 25 条（2026-08-19）。主要来源（有重叠）：

- 127 条（61%）是同一基金、同一级别当天重复发送：跌幅持续停在门限以下，冷却到期即重发。
- 61 条发在午休 11:30–13:00：休市期间价格不变。
- 17 条是回落降级：例如从警告回升到 -1.9% 后又发一条提醒。

目标：只在情况变坏时通知。用同一批历史数据模拟，新规则下 207 条降为 78 条，单日最多从 25 条降为 9 条。

## 2. 通知规则

按基金、按交易日（北京时间）独立判断：

1. 当前级别 = `check_threshold(change_pct, levels)`（现有逻辑，取最严重的已触发级别）。未触发任何级别则不通知。
2. 该基金当天还没有通知记录：通知，原因为 `level_up`。
3. 当前级别的门限比当天已通知的最严重门限更低（更严重）：通知，原因为 `level_up`。
4. 否则，若 `change_pct <= 当天已通知的最深跌幅 - renotify_drop_pct`：通知，原因为 `new_low`。比较时允许 1e-9 的浮点误差，恰好相差一个补发幅度也算满足。
5. 其余情况（同级持续、回落降级、小幅波动）不通知。

补充说明：

- 每只基金单独推送，不合并。
- 跨交易日自动重置，按通知记录的 `date` 区分。
- 盘中回升后又跌回同一级别，当天不再通知，除非满足再跌条件。
- 午休期间价格不变，不会产生新通知。
- 推送全部失败时不写记录，下一轮会重新判断并重试（沿用现有行为）。

示例（`renotify_drop_pct = 1`）：-1.2% 提醒 → -1.8% 不发 → -2.1% 警告 → -1.6% 不发 → -3.3% 紧急 → -3.9% 不发 → -4.3% 再跌补发 → -5.3% 再跌补发。

## 3. 消息格式

- 升级（`level_up`）：沿用现有格式。标题 `[警告] 纳指ETF(159941) 跌幅 -2.10%`；正文为当前价格、昨收、时间。
- 再跌补发（`new_low`）：标题 `[紧急·再跌] 纳指ETF(159941) 跌幅 -4.30%`；正文第一行为 `较上次通知 -3.30% 再跌 1.00%`，其余同上。"上次通知"取当天最深的那次通知；按本规则，同一天的通知跌幅是逐次加深的，所以它就是最近一次通知。

## 4. 数据模型

`notifications` 文档新增字段：

| 字段 | 类型 | 说明 |
|------|------|------|
| `date` | string | 北京时间日期 `YYYY-MM-DD`，用于查询当天记录 |
| `threshold` | number | 触发级别的门限值 |
| `reason` | string | `level_up` 或 `new_low` |

现有字段（`fund_code`、`fund_name`、`level`、`change_pct`、`price`、`timestamp`、`channels`、`delivered`）不变。旧记录没有新字段，它们都属于过去的日期，不参与当天判断。

`config/settings` 新增 `renotify_drop_pct`（number，单位为百分点，默认 1.0）。`cooldown_minutes` 不再读取，保留在文档中不删除。

当天状态：每轮检查查询一次 `notifications where date == 今天`（单字段等值查询，使用自动索引，无需新建复合索引），按 `fund_code` 汇总：

- `worst_threshold`：当天已通知记录中 `threshold` 的最小值
- `deepest_pct`：当天已通知记录中 `change_pct` 的最小值

`firestore.indexes.json` 中 `(fund_code, level, timestamp)` 复合索引不再使用，保留不动（删除需要重新部署，没有收益）。

## 5. 模块改动

Worker：

- `worker/cooldown.py` 重命名为 `worker/dedup.py`，职责是通知去重：
  - `load_today_state(db, date_str) -> dict[str, dict]`：查询并汇总当天状态；查询失败返回 `{}` 并记录 warning。
  - `decide_notification(level, change_pct, fund_state, drop_pct) -> str | None`：纯函数，返回 `"level_up"`、`"new_low"` 或 `None`。
  - `record_notification(...)`：新增 `date`、`threshold`、`reason` 参数并写入记录。
  - 删除 `is_in_cooldown` 及其查询辅助函数。
- `worker/main.py`：
  - 读取 `renotify_drop_pct`，缺失、非数字或不大于 0 时使用 1.0。
  - 每轮开始调用一次 `load_today_state`，逐只基金调用 `decide_notification`。
  - `format_notification` 支持 `new_low`：标题级别后加"·再跌"，正文加"较上次通知"一行。
  - `run_status` 中的 `cooldown_count` 改名为 `suppressed_count`，表示被去重规则拦下的触发次数。
- `worker/config.py`：`DEFAULT_CONFIG` 用 `renotify_drop_pct: 1.0` 替换 `cooldown_minutes: 60`。
- `worker/threshold.py`、`worker/notifier.py`、`worker/market_data.py` 不变。

Web：

- `web/lib/firestore.ts`：`AppConfig` 用可选字段 `renotify_drop_pct` 替换 `cooldown_minutes`；`NotificationRecord` 增加可选字段 `date`、`threshold`、`reason`。
- `web/app/settings/page.tsx`：「冷却时间」区块替换为「再跌补发」区块，包含规则说明和数字输入（单位 %，步长 0.1，最小 0.1）。交互沿用现有做法：失焦保存，输入无效时恢复原值，保存失败时提示。配置中没有该字段时显示 1。

文档：更新 `AGENTS.md`（去重决策、文件结构）、`TODO.md`，并在 `2026-05-30-etf-notify-design.md` 的冷却相关描述处注明已由本设计替代。

## 6. 异常处理

沿用"宁可重复，不可漏报"的原则：

- 当天状态查询失败：视为当天没有通知，可能多发一次，但不会漏报。
- 写通知记录失败：记录错误日志，下一轮可能重复一次（与现状一致）。
- `renotify_drop_pct` 缺失、非数字或不大于 0：使用 1.0。

## 7. 测试

- `worker/tests/test_dedup.py`（替换 `test_cooldown.py`）：
  - `decide_notification`：当天无记录且触发 → `level_up`；未触发 → `None`；同级 → `None`；更严重 → `level_up`；回落 → `None`；同级再跌达到幅度 → `new_low`；未达到幅度 → `None`；恰好等于幅度 → `new_low`；跌破最深门限后连续补发。
  - `load_today_state`：多条记录按基金正确汇总；缺少字段的记录被忽略；查询异常返回 `{}`。
  - `record_notification`：写入 `date`、`threshold`、`reason`。
- `worker/tests/test_main.py`：替换依赖冷却的用例；新增同级持续不重复推送、升级推送、再跌补发的标题与正文、`renotify_drop_pct` 兜底。
- CI：worker 测试与前端构建。
- 上线后：首个交易日收盘后核对 `run_status` 和通知记录，确认没有重复通知。

## 8. 不在本次范围

- 合并多只基金为一条推送、按指数分组
- 回升或解除通知
- 修改门限默认值
