# P20 · 规模化硬化

对照：Playwright 每模态冒烟、大视频/大 PCD 分片、Prometheus（claim/export/collab WS）、生产关演示入口。

## 交付

| 能力 | 行为 |
|------|------|
| Playwright | `frontend/e2e/modality-loop.spec.ts`：8 模态 标注→审核→导出（API mock，可无后端） |
| Range 媒体 | `GET /api/v1/media/file/{path}` 支持 `Range` / `206`；Nginx `/uploads` 透传 Range |
| 点云分片 | `GET /api/v1/media/pointcloud?path=&chunk=`；前端 `loadPointCloudAsset` 优先分片 |
| Prometheus | `GET /metrics`：`dasshine_claim_total` / `dasshine_export_*` / `dasshine_collab_ws_*` |
| 演示入口 | 生产 Docker `VITE_ENABLE_DEMO_ENTRIES=false`；`public-config.demo_entries_enabled` 运行时杀开关 |
| 共编代理 | Nginx `/api/v1/ws/` WebSocket Upgrade |

## 观测

```bash
curl -s http://localhost:8000/metrics | head
# 可选：METRICS_TOKEN=secret → Authorization: Bearer secret
```

中间件自动统计 `POST …/claim`、`…/claim-next`、`GET …/export/{id}`、`POST …/export/{id}/jobs`；Celery 导出另打 `kind=celery`；共编 WS 连接 Gauge + 消息 Counter。

## 媒体

```bash
# Range
curl -I -H 'Range: bytes=0-1023' http://localhost:8000/api/v1/media/file/projects/1/video.mp4
# 点云分片
curl 'http://localhost:8000/api/v1/media/pointcloud?path=projects/1/scan.pcd&chunk=0'
```

视频工作台 `preload="metadata"`；点云加载显示进度百分比。

## Playwright

```bash
cd frontend
npm i
npm run test:e2e:install
npm run test:e2e
```

环境：`VITE_ENABLE_DEMO_ENTRIES=true`（webServer 已注入）。对照后端导出冒烟：`pytest tests/test_p20_scale_hardening.py`。

## 配置

| 变量 | 默认 | 说明 |
|------|------|------|
| `METRICS_ENABLED` | true | 关闭后 `/metrics` 404 |
| `METRICS_TOKEN` | 空 | 设置则需 Bearer |
| `DEMO_ENTRIES_ENABLED` | false | 写入 public-config；**不**因 DEBUG 自动打开 |
| `VITE_ENABLE_DEMO_ENTRIES` | 生产 false | 编译期演示入口 |

## 验收

- `pytest tests/test_p20_scale_hardening.py`
- `npm run test:e2e`（8 模态）
- 生产构建 Dashboard 无「演示入口」；`/metrics` 含 claim/export/collab
