# P10 · 规模化运维：异步导入 · 组织配额 · 黄金题轮换

P9 收口了共识裁决与索引。本迭代补齐大规模运维缺口；**完整 Yjs/CRDT 实时共编延后 P11**。

## 范围

| ID | 交付 | 状态 |
|----|------|------|
| **P10-1** | ZIP/YOLO 异步导入：`…/import/{zip\|yolo}/jobs` + `GET /projects/import-jobs/{job_id}` | ✅ |
| **P10-2** | 组织配额：`organizations.quota`；创建项目与导入前校验；`GET/PUT /orgs/{id}/quota` | ✅ |
| **P10-3** | 黄金题轮换：Celery beat + `quality_config.golden_rotation` | ✅ |

**明确不做（P11 已交付切片 / P12 延后）：** Stripe 签约续费、全模态深度 CRDT、NFS/FUSE 内核挂载。见 `docs/p11_collab_billing_mount.md`。

## 配额默认

```json
{ "max_projects": 50, "max_tasks": 100000, "max_members": 200 }
```

## 运维

- Compose **默认**启动 `celery` + `celery-beat`（`./deploy.sh up` / `dev`）
- 异步导出经 `FileStorageService`：local 或 S3（与导入同配置）
- 迁移：`alembic upgrade head`（`20260816_p10_ops`）
