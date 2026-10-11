# TODO — etf-notify

## Phase 1: Python Worker 核心逻辑
- [x] `worker/config.py` — Firestore 配置读取
- [x] `worker/market_data.py` — AkShare 行情获取封装
- [x] `worker/threshold.py` — 门限计算 + 触发判断
- [x] `worker/cooldown.py` — 冷却时间管理
- [x] `worker/notifier.py` — FCM + PushDeer 推送
- [x] `worker/main.py` — 入口编排
- [x] `worker/requirements.txt` — Python 依赖

## Phase 2: GitHub Actions 工作流
- [x] `.github/workflows/monitor.yml` — cron 调度配置
- [x] 中国节假日判断集成
- [x] 交易时间二次校验

## Phase 3: Next.js PWA 前端
- [x] Next.js 项目初始化（App Router + Tailwind）
- [x] Firebase 客户端 SDK 集成
- [x] 仪表盘页面（基金卡片 + 行情展示）
- [x] 设置页面（基金管理 + 门限配置 + 推送设置）
- [x] PWA manifest + Service Worker
- [x] FCM 客户端集成
- [x] Firebase Hosting 配置

## Phase 4: 测试
- [x] TC-01: 正常触发通知
- [x] TC-02: 多级门限逐级触发
- [x] TC-03: 冷却期去重
- [x] TC-04: 冷却过期重新触发
- [x] TC-05: 非交易时间不运行
- [x] TC-06: 数据源异常降级
- [x] TC-07: 推送失败不崩溃
- [x] TC-08: 配置变更即时生效
- [x] TC-09: PWA 仪表盘数据正确
- [x] TC-10: 端到端真实环境验证
- [x] TC-11: 部署后 Firestore 连通性验证
- [x] TC-12: 部署后路由完整性验证

## Phase 5: 部署上线
- [x] Firebase 项目创建 + Firestore 初始化
- [x] GitHub Secrets 配置
- [x] Firebase Hosting 部署
- [x] 首次 Firestore 配置写入（预设基金 + 门限）
- [x] 手动触发 workflow 验证
- [x] 手机安装 PWA + 确认通知到达

## Phase 6: 运维改进
- [x] 循环容错
- [x] CI 测试
- [x] Firestore 规则收紧
- [x] PushDeer Key 轮换（旧 Key 已作废并验证，Secret 已更新）
- [x] 仓库改为 public（Actions 分钟数不限）
- [x] 行情源兜底：AkShare（东方财富）失败时依次回退腾讯、新浪行情（2026-09-23 起东方财富接口持续 502，交易日监控全部失败）
- [x] 改为短 Job 模式：workflow_dispatch 外部触发 + 每30分钟 cron 兜底（代码侧完成）
- [x] 健康检查改为覆盖率判定（当日成功运行 ≥ 15 次才算健康，对应每15分钟外部触发）
- [x] 注册 cron-job.org 并配置每15分钟调用 workflow_dispatch API（已配置，TEST RUN 返回 204，触发链路验证通过）
