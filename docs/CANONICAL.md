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
- 具身 P4：TFRecord、6DoF 手柄、相机内外参、策略权重托管、质量摘要 — `docs/embodied_p4.md`

## P5 产线缺口

- 计划：`docs/p5_production_gaps.md`
- OCR 专用工作台 `/annotate-ocr/:taskId`；导出 `coco_text` / `paddleocr`
- 分发消费 `cross_validate_count`，写 `TaskAssignment` + `task_metadata.co_assignee_ids`
- 交叉验证：`POST /quality/cross-validation`，比对 `Annotation.data` / `is_latest`
- 审核预览：`modality_preview`（nlp/audio/video/ocr/multimodal）
- 成员：`GET/POST/DELETE /projects/{id}/members`；平台 `reviewer` 角色可审其所属项目

## P6 产线闭环

- 计划：`docs/p6_production_loop.md`
- 多人共标：满 `cross_validate_count` 才 `SUBMITTED`；`is_task_assignee` 含共标人
- 分发真源：`ProjectService.dispatch`；`POST /tasks/dispatch` / claim 委托同一路径
- 异步导出：`POST /export/{id}/jobs` + `GET /export/jobs/{job_id}`；同步导出仍可用

## P7 质控盲测 + 点云审核

- 计划：`docs/p7_qc_review.md`
- 黄金题：`GET /projects/{id}/golden-tasks`、`PUT /quality/tasks/{id}/golden-answer`；标注侧盲测剥离
- 点云审核：`pointcloud_preview` + `Scene3DWorkspace` `readOnly`

## P8 多租户 + 协同占用锁

- 计划：`docs/p8_tenancy_collab.md`
- 组织：`GET/POST /orgs`、`POST /orgs/{id}/activate`、成员管理；`projects.organization_id`；列表按 `active_org_id`
- 占用锁：`POST/GET/DELETE /tasks/{id}/lock`（TTL 心跳）；工作台 `TaskLockBanner`

## P9 共识裁决 + 规模化硬化

- 计划：`docs/p9_consensus_scale.md`
- 审核：`versions[]` 并排；通过时写 `canonical_annotation_id`；导出 `primary_payload` 优先真源
- 可领任务按组织过滤；任务复合索引；DB pool 读配置；Celery 导出时限 30m
- 轻量黄金题：`quality_config.golden_claim_ratio` 优先插入 available 池

## P10 规模化运维

- 计划：`docs/p10_scale_ops.md`
- 异步导入：`POST …/import/zip|yolo/jobs` + `GET /projects/import-jobs/{id}`（大 ZIP 自动后台）
- 组织配额：`organizations.quota`；`GET/PUT /orgs/{id}/quota`；创建项目/导入前校验
- 黄金题轮换：`quality_config.golden_rotation` + Celery beat `rotate_golden_tasks`
- **P11：** 完整 CRDT / Yjs 共编、计费扣款、目录挂载
