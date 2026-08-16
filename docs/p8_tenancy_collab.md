# P8 · 多租户 Organization + 协同占用锁

P7 已收口质控盲测与点云审核。本迭代落地租户隔离与轻量协同；**完整 CRDT / Yjs 延后 P9**。

## 范围

| ID | 交付 | 状态 |
|----|------|------|
| **P8-1** | `organizations` / `organization_members`；`projects.organization_id`；列表按当前组织过滤 | ✅ |
| **P8-2** | 任务标注占用锁（心跳 + 过期）；工作台提示他人占用 | ✅ |

**明确不做（P10）：** Yjs/Automerge CRDT 实时共编、计费/配额、完整黄金题轮换调度器。

## 数据模型

- `Organization(id, name, slug, created_by_id)`
- `OrganizationMember(org_id, user_id, role)` — owner / admin / member
- `Project.organization_id`（可空；创建时绑当前组织）
- `User.active_org_id`（当前工作组织）
- `TaskAnnotationLock(task_id, user_id, expires_at)` — 唯一 task_id

## API

- `GET/POST /orgs`；`POST /orgs/{id}/members`；`POST /orgs/{id}/activate`
- 项目列表：`?org_id=` 或用户 `active_org_id`
- `POST /tasks/{id}/lock`、`DELETE /tasks/{id}/lock`、`GET /tasks/{id}/lock`

## 验收

- 用户属于不同组织时，项目列表互不可见（非超管）
- 两人打开同任务：后者看到占用提示；锁过期后可抢占

## 迁移

`cd backend && .venv/bin/alembic upgrade head`（`20260816_p8_org`）
