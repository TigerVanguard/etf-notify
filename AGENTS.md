# AGENTS.md — etf-notify

## Project Overview

PWA 应用：工作日 10:00~14:30 监控国内场内纳指和标普 ETF 跌幅，达门限时推送通知。

## Goal

构建完整的 ETF 跌幅监控 + 推送通知系统。

## Architecture

- **Python Worker** (`worker/`): AkShare 获取行情 → 门限判断 → FCM + PushDeer 推送
- **Next.js PWA** (`web/`): 仪表盘展示 + 配置管理界面
- **GitHub Actions** (`.github/workflows/`): 每10分钟 cron 调度 Worker
- **Firestore**: 配置存储 + 行情快照 + 通知记录

## Constraints

- 零成本：只用免费服务（GitHub Actions、Firebase Spark、PushDeer）
- 中文界面
- 移动端优先
- 单用户，无认证

## Done When

- [ ] Python Worker 能通过 AkShare 获取行情数据
- [ ] 门限判断逻辑正确（多级：提醒/警告/紧急）
- [ ] 冷却时间机制生效
- [ ] FCM 推送通知到达手机
- [ ] PushDeer 推送通知到达手机
- [ ] GitHub Actions cron 在工作日 10:00~14:30 正常触发
- [ ] PWA 仪表盘正确展示行情和门限状态
- [ ] PWA 可安装到手机主屏幕
- [ ] 端到端流程跑通：行情变动 → 检测 → 推送 → 手机收到通知

## Stop If

- 需要用户提供外部凭证（Firebase service account、PushDeer Key 等）
- 设计决策有歧义无法自行判断
- 关键测试失败且无法自行修复
- 外部 API（AkShare、Firebase、PushDeer）不可用且无替代方案

## File Structure

```
etf-notify/
├── AGENTS.md                          # 本文件 — 项目指南
├── TODO.md                            # 任务跟踪
├── docs/
│   └── superpowers/specs/
│       └── 2026-05-30-etf-notify-design.md  # 设计文档
├── worker/                            # Python 监控服务
│   ├── main.py                        # 入口
│   ├── config.py                      # Firestore 配置读取
│   ├── market_data.py                 # AkShare 行情获取
│   ├── threshold.py                   # 门限计算
│   ├── notifier.py                    # FCM + PushDeer 推送
│   ├── cooldown.py                    # 冷却时间管理
│   ├── requirements.txt               # Python 依赖
│   └── tests/                         # 单元测试
├── web/                               # Next.js PWA 前端
│   ├── app/                           # App Router 页面
│   ├── components/                    # UI 组件
│   ├── lib/                           # Firebase SDK 封装
│   └── public/                        # 静态资源 + SW
├── .github/workflows/
│   └── monitor.yml                    # GitHub Actions cron
└── firebase.json                      # Firebase Hosting 配置
```

## Agent Guidelines

### For Implementation Agents
- 先读设计文档 `docs/superpowers/specs/2026-05-30-etf-notify-design.md`
- 遵循已定义的模块拆分，不要合并模块
- Python Worker 每个模块职责单一，通过函数参数通信
- 前端使用 Tailwind CSS，移动端优先（min-width breakpoints）
- 所有用户可见文本使用中文

### For Test Agents
- 端到端测试是核心验收标准
- 使用 pytest + mock 做单元/集成测试
- 测试计划详见设计文档 Section 7
- Mock AkShare 返回数据以避免真实 API 调用
- 测试通知推送时 mock HTTP 请求，验证请求参数

### Key Decisions Already Made
- 数据源: AkShare（Python）
- 跌幅计算: 相对昨日收盘价
- 门限: 多级（提醒-1%、警告-2%、紧急-3%），可配置
- 去重: 冷却时间（可配置分钟数）
- 推送: FCM + PushDeer 双通道
- 存储: Firestore
- 调度: GitHub Actions cron（每10分钟）
- 节假日: chinese-calendar 库
