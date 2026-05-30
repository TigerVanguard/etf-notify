# TODO — etf-notify

## Phase 1: Python Worker 核心逻辑
- [ ] `worker/config.py` — Firestore 配置读取
- [ ] `worker/market_data.py` — AkShare 行情获取封装
- [ ] `worker/threshold.py` — 门限计算 + 触发判断
- [ ] `worker/cooldown.py` — 冷却时间管理
- [ ] `worker/notifier.py` — FCM + PushDeer 推送
- [ ] `worker/main.py` — 入口编排
- [ ] `worker/requirements.txt` — Python 依赖

## Phase 2: GitHub Actions 工作流
- [ ] `.github/workflows/monitor.yml` — cron 调度配置
- [ ] 中国节假日判断集成
- [ ] 交易时间二次校验

## Phase 3: Next.js PWA 前端
- [ ] Next.js 项目初始化（App Router + Tailwind）
- [ ] Firebase 客户端 SDK 集成
- [ ] 仪表盘页面（基金卡片 + 行情展示）
- [ ] 设置页面（基金管理 + 门限配置 + 推送设置）
- [ ] PWA manifest + Service Worker
- [ ] FCM 客户端集成
- [ ] Firebase Hosting 配置

## Phase 4: 测试
- [ ] TC-01: 正常触发通知
- [ ] TC-02: 多级门限逐级触发
- [ ] TC-03: 冷却期去重
- [ ] TC-04: 冷却过期重新触发
- [ ] TC-05: 非交易时间不运行
- [ ] TC-06: 数据源异常降级
- [ ] TC-07: 推送失败不崩溃
- [ ] TC-08: 配置变更即时生效
- [ ] TC-09: PWA 仪表盘数据正确
- [ ] TC-10: 端到端真实环境验证

## Phase 5: 部署上线
- [ ] Firebase 项目创建 + Firestore 初始化
- [ ] GitHub Secrets 配置
- [ ] Firebase Hosting 部署
- [ ] 首次 Firestore 配置写入（预设基金 + 门限）
- [ ] 手动触发 workflow 验证
- [ ] 手机安装 PWA + 确认通知到达
