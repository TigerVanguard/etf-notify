# etf-notify 设计文档

> 日期: 2026-05-30
> 状态: 已批准

## 1. 项目概述

### Goal
构建一个 PWA 应用，在工作日 10:00~14:30 监控国内场内纳指和标普 ETF 基金的涨跌幅，当跌幅达到指定门限时，通过 Firebase Cloud Messaging 和 PushDeer 推送通知到 Android/iOS 设备。

### Constraints
- **零成本运行**：只使用免费服务（GitHub Actions 免费额度、Firebase Spark plan、PushDeer）
- **中文界面**：所有 UI 文本为中文
- **移动端优先**：响应式设计，主要在手机上使用
- **单用户模式**：无认证系统

### Done When
- 系统能正常监控行情数据（通过 AkShare）
- 达到门限时成功推送通知到手机（FCM + PushDeer 双通道）
- PWA 可安装、仪表盘正确展示行情和门限状态

### Stop If
- 被外部依赖阻塞（需要用户提供 API Key、手动配置 Firebase 等）
- 遇到设计模糊无法自行决策时
- 关键测试失败且无法自行修复时

## 2. 系统架构

```
┌─────────────────────────────────────────────────────────────┐
│                    GitHub Actions (Cron)                      │
│          每10分钟触发 (工作日 10:00~14:30 UTC+8)              │
└─────────────────────┬───────────────────────────────────────┘
                      │ 运行 Python worker
                      ▼
┌─────────────────────────────────────────────────────────────┐
│                    Python Worker                              │
│  1. 读取 Firestore 配置（基金列表、门限、冷却时间）            │
│  2. AkShare 获取实时行情                                     │
│  3. 计算涨跌幅，判断是否触发门限                              │
│  4. 检查冷却时间（读 Firestore 上次通知时间戳）               │
│  5. 触发通知 → FCM + PushDeer                                │
│  6. 写回 Firestore（最新行情快照 + 通知记录）                 │
└─────────────────────────────────────────────────────────────┘
                      │ 写入
                      ▼
┌─────────────────────────────────────────────────────────────┐
│                    Firestore                                  │
│  collections:                                                │
│    /config      → 基金列表、门限级别、冷却时间、PushDeer Key  │
│    /snapshots   → 最新行情快照（供 PWA 仪表盘读取）           │
│    /notifications → 通知历史记录（去重判断 + 前端展示）        │
└─────────────────────┬───────────────────────────────────────┘
                      │ 实时读取
                      ▼
┌─────────────────────────────────────────────────────────────┐
│              Next.js PWA (Firebase Hosting)                   │
│  页面：                                                      │
│    / (仪表盘)    → 当前行情 + 涨跌幅 + 门限状态               │
│    /settings     → 基金管理 + 门限配置 + 推送设置             │
│  特性：                                                      │
│    - Service Worker (离线缓存 + FCM 接收)                    │
│    - 移动端优先响应式布局                                     │
│    - 中文界面                                                │
└─────────────────────────────────────────────────────────────┘
```

### 数据流向
1. GitHub Actions → Python Worker → AkShare（获取数据；失败时回退腾讯/新浪行情）
2. Python Worker → Firestore（写入快照 + 通知记录）
3. Python Worker → FCM + PushDeer（推送通知）
4. PWA → Firestore（读取仪表盘数据 + 读写配置）

## 3. Python Worker 详细设计

### 模块结构

```
worker/
├── main.py              # 入口：编排整体流程
├── config.py            # Firestore 配置读取
├── market_data.py       # 行情获取（AkShare 为主，腾讯/新浪兜底）
├── threshold.py         # 门限计算 + 触发判断
├── notifier.py          # FCM + PushDeer 推送
├── cooldown.py          # 冷却时间管理
├── requirements.txt     # 依赖
└── tests/
    └── test_threshold.py
```

### 运行流程

```python
def run():
    if not is_trading_time():
        return
    config = load_config()
    for fund in config.funds:
        quote = fetch_quote(fund.code)
        change_pct = calc_change(quote)
        triggered_level = check_threshold(change_pct, config.levels)
        if not triggered_level:
            continue
        if is_in_cooldown(fund.code, triggered_level):
            continue
        send_notification(fund, change_pct, triggered_level)
        record_notification(fund.code, triggered_level)
    save_snapshot(all_quotes)
```

### 预设基金列表

| 代码 | 名称 | 跟踪指数 |
|------|------|---------|
| 159941 | 纳指ETF | 纳斯达克100 |
| 513100 | 纳指ETF | 纳斯达克100 |
| 513500 | 标普500ETF | 标普500 |
| 159612 | 标普500ETF | 标普500 |

### 门限配置

```json
{
  "levels": [
    { "name": "提醒", "threshold": -1.0, "color": "yellow" },
    { "name": "警告", "threshold": -2.0, "color": "orange" },
    { "name": "紧急", "threshold": -3.0, "color": "red" }
  ],
  "cooldown_minutes": 60
}
```

### 通知格式

```
[紧急] 纳指ETF(159941) 跌幅 -3.2%
当前价格: 1.856 | 昨收: 1.917
时间: 2026-05-30 11:20
```

## 4. Next.js PWA 前端设计

### 页面结构

```
web/
├── app/
│   ├── page.tsx           # 仪表盘首页
│   ├── settings/
│   │   └── page.tsx       # 配置页面
│   ├── layout.tsx         # 全局布局（底部导航）
│   └── manifest.json      # PWA manifest
├── components/
│   ├── FundCard.tsx       # 单只基金卡片
│   ├── StatusBadge.tsx    # 门限状态标识
│   ├── ThresholdConfig.tsx # 门限配置组件
│   └── FundManager.tsx    # 基金列表管理
├── lib/
│   ├── firebase.ts        # Firebase 初始化
│   └── firestore.ts       # Firestore 读写封装
├── public/
│   ├── sw.js              # Service Worker
│   └── icons/             # PWA 图标
└── next.config.js
```

### 仪表盘布局

移动端优先的卡片式布局：
- 顶部状态栏：应用名 + 监控状态（监控中/已暂停/非交易时间）
- 基金卡片列表：每只基金一张卡片，显示名称、代码、当前价格、涨跌幅、门限状态
- 卡片颜色根据门限状态变化（正常=绿色/灰色，提醒=黄色，警告=橙色，紧急=红色）
- 最后更新时间
- 底部导航：仪表盘 | 设置

### 配置页面

- 基金管理：添加/删除基金代码
- 门限设置：各级别百分比配置
- 冷却时间：通知冷却分钟数
- 推送设置：PushDeer Key 输入、FCM 权限开关
- 测试推送按钮：一键发送测试通知

### PWA 特性

- manifest.json：应用名称、图标、主题色、启动模式（standalone）
- Service Worker：静态资源离线缓存
- FCM 集成：接收后台推送通知

## 5. GitHub Actions 工作流

```yaml
name: ETF Monitor
on:
  schedule:
    - cron: '*/10 2-6 * * 1-5'
  workflow_dispatch:
jobs:
  monitor:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: '3.11'
          cache: 'pip'
      - run: pip install -r worker/requirements.txt
      - run: python worker/main.py
        env:
          FIREBASE_CREDENTIALS: ${{ secrets.FIREBASE_CREDENTIALS }}
          PUSHDEER_KEY: ${{ secrets.PUSHDEER_KEY }}
```

- cron: UTC 02:00~06:30 = 北京时间 10:00~14:30
- Worker 内部二次校验交易时间（防 cron 延迟）
- 使用 `chinese-calendar` 库判断中国节假日
- `workflow_dispatch` 支持手动触发测试

## 6. Firestore 数据模型

### /config/settings (单文档)

```json
{
  "funds": [
    { "code": "159941", "name": "纳指ETF", "index": "纳斯达克100", "enabled": true },
    { "code": "513500", "name": "标普500ETF", "index": "标普500", "enabled": true }
  ],
  "levels": [
    { "name": "提醒", "threshold": -1.0, "color": "yellow" },
    { "name": "警告", "threshold": -2.0, "color": "orange" },
    { "name": "紧急", "threshold": -3.0, "color": "red" }
  ],
  "cooldown_minutes": 60,
  "pushdeer_key": "PDU...",
  "fcm_enabled": true
}
```

### /snapshots/{date} (每天一个文档)

```json
{
  "date": "2026-05-30",
  "updated_at": "2026-05-30T11:20:00+08:00",
  "quotes": {
    "159941": {
      "name": "纳指ETF",
      "price": 1.856,
      "prev_close": 1.917,
      "change_pct": -3.18,
      "high": 1.920,
      "low": 1.850,
      "volume": 12345678
    }
  }
}
```

### /notifications/{auto-id}

```json
{
  "fund_code": "159941",
  "fund_name": "纳指ETF",
  "level": "紧急",
  "change_pct": -3.18,
  "price": 1.856,
  "timestamp": "2026-05-30T11:20:00+08:00",
  "channels": ["pushdeer", "fcm"],
  "delivered": true
}
```

## 7. 端到端测试计划

| ID | 测试用例 | 验证内容 | 方法 |
|----|---------|---------|------|
| TC-01 | 正常触发 | 模拟跌幅超门限，验证通知到达 | Mock AkShare 返回值，检查推送调用 |
| TC-02 | 多级触发 | 跌幅从1%→2%→3%逐级触发 | 连续 mock 不同跌幅 |
| TC-03 | 冷却生效 | 冷却期内不重复推送 | Mock 时间戳验证跳过 |
| TC-04 | 冷却过期 | 冷却期过后重新触发 | Mock 过期时间戳 |
| TC-05 | 非交易时间 | 周末/节假日不运行 | Mock 不同日期，验证 early return |
| TC-06 | 数据源异常 | AkShare 报错时优雅降级 | Mock 网络错误 |
| TC-07 | 推送失败 | FCM/PushDeer 不可用时不崩溃 | Mock HTTP 失败 |
| TC-08 | 配置变更 | 前端修改门限后 Worker 即时生效 | 修改 Firestore → 运行 Worker |
| TC-09 | PWA 仪表盘 | 数据正确展示在前端 | Worker 写入后检查页面 |
| TC-10 | 端到端真实 | 真实环境完整跑通 | 手动触发 workflow，验证手机收到通知 |
| TC-11 | 部署后 Firestore 连通性 | CI 部署后前端能实际连接 Firestore | 部署完成后请求页面，验证 Firebase 配置非 undefined 且 Firestore API 可达 |
| TC-12 | 部署后路由完整性 | 各页面返回正确内容（非 SPA 回退） | 部署后检查 /settings/ 返回内容与 / 不同 |

## 8. 技术依赖

### Python Worker
- akshare: 行情数据获取
- firebase-admin: Firestore + FCM
- requests: PushDeer HTTP 推送
- chinese-calendar: 中国节假日判断

### Next.js PWA
- next: 框架
- firebase (client SDK): Firestore 读写 + FCM 接收
- serwist 或 next-pwa: Service Worker / PWA 支持
- tailwindcss: 样式（移动端优先）

## 9. GitHub Actions 免费额度评估

| 参数 | 数值 |
|------|------|
| 监控时段 | 10:00~14:30 = 270 分钟 |
| 每天触发 | 28 次 |
| 每月工作日 | ~22 天 |
| 每月总触发 | 616 次 |
| 每次运行 | ~1.5 分钟 |
| 每月消耗 | ~924 分钟 |
| 免费额度 | 2000 分钟/月 |
| 使用率 | ~46% |
