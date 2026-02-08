# PR6 聚合指标与订阅推送

## 范围
- `daily_metrics` 每日生成任务
- 订阅命中：`company / product / keyword`
- 每日汇总推送：同一 `subscriber_key` 一天一条（Webhook）

## 关键能力

### 1) daily_metrics 生成（可重跑）
- 入口：`generate_daily_metrics(db, metric_date)`
- 文件：`/Users/GY/Documents/New project 2/api/app/services/metrics.py`
- 行为：按 `metric_date` upsert（`ON CONFLICT (metric_date) DO UPDATE`）

### 2) 订阅与推送
- 文件：`/Users/GY/Documents/New project 2/api/app/services/subscriptions.py`
- 命中类型：
  - `company`：匹配企业名
  - `product`：匹配产品名/UDI/reg_no
  - `keyword`：匹配多字段全文
- 去重：同日同产品仅保留最新变更
- 频控：`daily_digest_runs` 唯一键 `(digest_date, subscriber_key, channel)`
- 可重跑：默认跳过已发送；`force=True` 可强制重发

### 3) 推送渠道
- 支持 `Webhook` 与 `Email`
- `subscriptions.channel` 取值：
  - `webhook`：使用 `webhook_url`
  - `email`：使用 `email_to`（或 `subscriber_key` 为邮箱时回退）
- SMTP 配置（环境变量）：
  - `SMTP_HOST`, `SMTP_PORT`, `SMTP_USER`, `SMTP_PASSWORD`, `SMTP_USE_TLS`, `EMAIL_FROM`

## 调度入口（cron-compatible）
- `python -m app.workers.cli daily-metrics --date YYYY-MM-DD`
- `python -m app.workers.cli daily-digest --date YYYY-MM-DD`
- `python -m app.workers.cli daily-digest --date YYYY-MM-DD --force`
