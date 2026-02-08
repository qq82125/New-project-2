# PR2 Worker 框架与数据同步骨架

## 范围
- 仅包含下载、校验、解压、`source_runs` 记录、调度入口。
- 不包含字段映射/upsert/change_log。

## 入口
- 单次执行（cron-compatible）：
  - `python -m app.workers.cli --once --package-url https://example.com/mock.zip`
- 常驻循环：
  - `python -m app.workers.cli`

## 关键函数
- `sync_nmpa_ivd(...)`：`/Users/GY/Documents/New project 2/api/app/workers/sync.py`
- `prepare_staging_dirs(...)`：清理/复用 staging

## 行为
1. 创建/复用 staging 目录（downloads/extracted）
2. 获取包信息（支持 `--package-url` 占位 URL）
3. 下载文件
4. 校验 MD5/SHA256
5. 解压到 staging
6. 写入 `source_runs`：
   - 成功：`status=success`
   - 失败：`status=failed`

## 配置
- `STAGING_DIR`
- `SYNC_INTERVAL_SECONDS`
