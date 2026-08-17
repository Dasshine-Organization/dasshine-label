# P11 · 共编 · 计费账本 · 存储目录挂载

P10 收口了异步导入与组织配额。本迭代落地此前延后的三块；**完整 Stripe 扣款对接、全模态 Yjs 深度绑定、NFS 内核挂载延后 P12**。

## 范围

| ID | 交付 | 状态 |
|----|------|------|
| **P11-1** | Yjs 文档中继 WebSocket + 任务级共享草稿落库；2D 工作台 presence / 共编同步 | ✅ |
| **P11-2** | 组织积分账本：`quota.credits` + `org_billing_ledger`；导入/导出扣款；管理员充值 | ✅ |
| **P11-3** | 存储前缀浏览 `GET /storage/browse` + `POST …/import/from-storage`（local / S3） | ✅ |

**明确不做（P12 已交付切片 / P13 延后）：** Stripe Subscriptions、Automerge、内核 NFS/FUSE。见 `docs/p12_stripe_collab_mount.md`。

## 共编

- `WS /api/v1/ws/tasks/{task_id}/collab?token=`：中继 Yjs update / awareness；晚加入者收到 `init` 快照
- `GET/PUT /tasks/{id}/collab-doc`：共享草稿快照（无 WS 时兜底）
- 占用锁仍为提交权威；共编用于实时合并草稿与在线 presence

## 计费

默认配额含 `credits: 10000`。扣款：

| 动作 | 默认消耗 |
|------|----------|
| 每成功导入 1 条任务 | `BILLING_CREDIT_PER_IMPORT_TASK`（1） |
| 每次异步导出入队 | `BILLING_CREDIT_PER_EXPORT`（10） |

API：`GET /orgs/{id}/billing`、`POST /orgs/{id}/billing/topup`（管理员）。

## 目录挂载

- `GET /storage/browse?prefix=&limit=` 列出相对键 / 本地路径
- `POST /projects/{id}/import/from-storage` `{ prefix, extensions?, limit? }` 按公网 URL 批量建任务

## 迁移

```bash
cd backend && .venv/bin/alembic upgrade head
# 20260816_p11_collab_billing
```

## 前端

- 导入弹窗新增「存储目录」
- 2D 标注顶栏显示共编在线用户（`useYjsCollab`）
