# P13 · 订阅门户 · 虚拟挂载 · 点云/具身共编

P12 交付了一次性 Checkout、多模态 Yjs、浏览硬化。本迭代落地此前延后的三块可交付切片；后续 Automerge / FUSE / 逐点 CRDT / Connect 见 P14。

## 范围

| ID | 交付 | 状态 |
|----|------|------|
| **P13-1** | Stripe Subscriptions + Customer Portal；`invoice.paid` / `customer.subscription.*` webhook；计划月积分 | ✅ |
| **P13-2** | 组织级虚拟挂载注册表 `storage_mounts`；按挂载浏览/导入（仍非 OS FUSE） | ✅ |
| **P13-3** | 点云 / 具身工作台粗粒度 Yjs（`boxes3d` / embodied draft JSON）+ presence | ✅ |

**P14 已交付：** Automerge、内核 NFS/FUSE、逐点 CRDT、Stripe Connect/税务。见 `docs/p14_automerge_fuse_connect.md`。

## 订阅

配置：

```
STRIPE_PRICE_PLANS=[{"id":"plan_pro","price_id":"price_xxx","credits_per_month":5000,"label":"Pro"}]
STRIPE_PORTAL_RETURN_URL=http://localhost:3000/projects?billing=portal
```

组织 `quota` 扩展键：`stripe_customer_id` / `subscription_status` / `subscription_plan_id` / `subscription_id`。

API：

- `GET /billing/plans`
- `POST /orgs/{id}/billing/subscribe` — Checkout `mode=subscription`
- `POST /orgs/{id}/billing/portal` — Customer Portal
- Webhook：`invoice.paid` 月积分（幂等 `stripe_invoice`）；`customer.subscription.updated|deleted` 更新状态

## 虚拟挂载

- 表 `storage_mounts`：`org_id, name, root_prefix, kind, read_only, enabled`
- `GET/POST/DELETE /orgs/{id}/storage-mounts`
- `GET /storage/mounts/{id}/browse`；导入可用 `mount_id` + 相对 path

## 共编

- `PointCloudAnnotation` / `EmbodiedAnnotation` 接入 `useYjsCollab` + `CollabPresenceBar`
- 同步对象级 JSON，非逐点 CRDT

## 迁移

```bash
cd backend && .venv/bin/alembic upgrade head
# 20260817_p13_mounts
```
