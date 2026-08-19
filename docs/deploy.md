# 部署指南（P4）

## 一键 Compose

```bash
cd deploy
cp .env.example .env
# 必改：SECRET_KEY、PUBLIC_URL（浏览器访问前端的地址，无末尾斜杠）
chmod +x deploy.sh
./deploy.sh up -d
```

- 前端：`http://localhost:8080`（`HTTP_PORT`）
- API 文档：仅 `DEBUG=true` 时开放 `/docs`
- 健康：`GET /health`（存活）、`GET /ready`（DB + 上传目录）

开发栈：

```bash
./deploy.sh dev
# 前端 :3000 · 后端 :8000
```

## 生产必对齐变量

| 变量 | 作用 | 注意 |
|------|------|------|
| `SECRET_KEY` | JWT 签名 | ≥32 随机字符，勿用默认值 |
| `ACCESS_TOKEN_EXPIRE_MINUTES` | 访问令牌有效期 | 默认 `720`（12h）；生产建议 ≤ 1440 |
| `PUBLIC_URL` | 浏览器入口 | 同时驱动 `BACKEND_CORS_ORIGINS` 与 `FILE_SERVER_BASE_URL` |
| `BACKEND_CORS_ORIGINS` | CORS | Compose 默认等于 `PUBLIC_URL`；多源用逗号分隔 |
| `UPLOAD_DIR` | 上传根目录 | 容器内 `/app/uploads`，需可写 volume |
| `FILE_SERVER_BASE_URL` | 任务 `data_url` 前缀 | 生产应指向经 Nginx 反代后的同源或 CDN |
| `DATABASE_URL` | Postgres | Compose 内用服务名 `db` |
| `DEBUG` | 文档与详细日志 | 生产 `false` |
| `RATE_LIMIT_*` | API 限流 | 见下；可设 `RATE_LIMIT_ENABLED=false` 关闭 |

## 限流

中间件对 `/api/*` 做固定窗口限流（优先 Redis，不可用则进程内存）：

| 桶 | 默认（次/分钟） | 路径 |
|----|-----------------|------|
| auth | 20 | `/auth/login`、`/auth/register` |
| claim | 40 | `POST …/claim` |
| import | 30 | `POST …/import/…` |
| api | 180 | 其余 API |

超限返回 `429`，带 `Retry-After` / `X-RateLimit-*`。`/health`、`/ready`、`/docs`、`/uploads` 不限流。

## P11 共编 / 计费 / 目录

见 [`docs/p11_collab_billing_mount.md`](./p11_collab_billing_mount.md)。迁移：`alembic upgrade head`（`20260816_p11_collab_billing`）。

## 观测

- 访问日志：JSON 行（`dasshine.access`），含 `request_id` / `duration_ms` / `status`
- 响应头：`X-Request-ID`；限流响应另含 `X-RateLimit-Limit` / `Remaining`
- 导入失败：`dataset_import_failed` 警告日志，API 返回 `errors[]` + `error_count`
- Prometheus：`GET /metrics`（claim / export / collab WS）；见 `docs/p20_scale_hardening.md`

## Celery（默认启用）

`./deploy.sh up` / `./deploy.sh dev` 会同时启动：

- `celery`：异步导出、异步 ZIP/YOLO 导入
- `celery-beat`：超时任务回收、黄金题轮换

单独重启：`./deploy.sh worker`

异步导出产物经 `FileStorageService` 写入：`STORAGE_BACKEND=local` 落在 `UPLOAD_DIR/projects/{id}/exports/`；`s3` 则 `put_object` 到桶并返回公网 `download_url`。

## 冒烟测试

```bash
cd backend
.venv/bin/pytest -q
```

## S3 兼容存储

见 [`docs/storage_s3.md`](./storage_s3.md)。`STORAGE_BACKEND=s3` 时：

- 数据集导入写入对象桶
- **异步导出**同样写入对象桶（与导入共用 `FileStorageService`）
- `/ready` 会探测 bucket
