# 仓库约定 · P0

## 唯一真源

本目录 `Dashine/dasshine-label` 为唯一开发与提交副本。

请勿在以下路径并行修改同一功能后再来回同步：

- `~/Documents/VscodeProject/dasshine-label`（历史分叉，仅作归档参考）

## 前端入口

- 启动：`frontend/index.html` → `frontend/src/main.tsx` → `frontend/src/App.tsx`
- 已删除的陈旧文件：根目录 `App.tsx` / `main.tsx` / `index.css` / `components/` / `contexts/` / `styles/`

## 演示 vs 业务

| 类型 | 行为 |
|------|------|
| 业务入口 | `/projects?category=`、`/tasks?category=`、真实 `project.id` → `/projects/:id/tasks` |
| 演示入口 | 硬编码 task（1001/1002/3001/demo…），仅开发或 `VITE_ENABLE_DEMO_ENTRIES=true` |

`DEMO_TASK_IDS` 仍用于工作台识别离线样例数据，但不再作为 Dashboard 默认跳转目标。

## P1 数据约定

- 分类列：`projects.category` / `projects.ann_type`（与 schema 双写）
- 迁移：`cd backend && .venv/bin/alembic upgrade head`
- 文档：`docs/schema_category.md`
- 种子：`python scripts/seed_category_projects.py`

## P3 产品闭环（2D 验收模板延伸）

- **审核**：`/review` → `GET /quality/queue` + `POST /quality/review`；驳回回流 `annotating`
- **导出**：项目任务页「导出数据」→ 按类别三种主流格式（见 `docs/export_formats.md`）→ `GET /export/{id}?format=…&status=approved`
- **预标注**：2D 工作台 `demo_template` / YOLO（`/tasks/{id}/prelabel/*`）；LLM/OCR auto-label 返回 501
- **分发可观测**：`GET /projects/{id}/dispatch-logs` + 项目任务页最近分发

## P4 平台化

- 观测：`RequestLoggingMiddleware` JSON 访问日志、`/health` + `/ready`、导入失败 `error_count`
- 测试：`cd backend && pytest`
- 前端：Projects / Tasks / Review 使用 React Query
- 部署：`docs/deploy.md`；类别 Hub：`frontend/src/utils/categoryHubs.ts`（侧栏与工作台同源）
- 存储：`STORAGE_BACKEND=local|s3`，S3 兼容见 `docs/storage_s3.md`
- 导出：全模态三种主流格式见 `docs/export_formats.md`
- 具身 P0：指令/成败/区间段、真值关节导出、Episode 导入、提交审核 — `docs/embodied_p0.md`
- 具身 P1：LeRobot dataset ZIP、抓取/轨迹、审核多机位预览 — `docs/embodied_p1.md`
- 具身 P2：力觉/触觉、偏好对、parquet+本地视频打包、HDF5、策略预标注 — `docs/embodied_p2.md`
- 具身 P3：RLDS-lite、远端视频下载、3D 抓取/轨迹面板、外接策略 HTTP — `docs/embodied_p3.md`
