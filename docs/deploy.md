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
| `PUBLIC_URL` | 浏览器入口 | 同时驱动 `BACKEND_CORS_ORIGINS` 与 `FILE_SERVER_BASE_URL` |
| `BACKEND_CORS_ORIGINS` | CORS | Compose 默认等于 `PUBLIC_URL`；多源用逗号分隔 |
| `UPLOAD_DIR` | 上传根目录 | 容器内 `/app/uploads`，需可写 volume |
| `FILE_SERVER_BASE_URL` | 任务 `data_url` 前缀 | 生产应指向经 Nginx 反代后的同源或 CDN |
| `DATABASE_URL` | Postgres | Compose 内用服务名 `db` |
| `DEBUG` | 文档与详细日志 | 生产 `false` |

## 观测

- 访问日志：JSON 行（`dasshine.access`），含 `request_id` / `duration_ms` / `status`
- 响应头：`X-Request-ID`
- 导入失败：`dataset_import_failed` 警告日志，API 返回 `errors[]` + `error_count`

## 冒烟测试

```bash
cd backend
.venv/bin/pytest -q
```
