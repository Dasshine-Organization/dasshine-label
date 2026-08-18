# P12 · Stripe 充值 · 多模态共编 · 存储挂载硬化

P11 交付了账本、2D presence、存储浏览。本迭代落地此前延后的三块可交付切片；**Stripe 订阅续费门户、Automerge、内核 NFS/FUSE、3D/具身逐像素 CRDT 延后**（订阅/门户与点云粗粒度共编已在 P13；Automerge / FUSE / 逐点 CRDT 见 P14）。

## 范围

| ID | 交付 | 状态 |
|----|------|------|
| **P12-1** | Stripe Checkout 一次性积分包 + webhook 入账（幂等）；组织侧「充值」入口 | ✅ |
| **P12-2** | 2D 草稿 Yjs 双向同步；文本/视频/OCR 等模态工作台 presence + payload 共编；Redis 扇出（多 worker） | ✅ |
| **P12-3** | 浏览根白名单 / 禁 symlink；S3 `Delimiter` 真目录；大前缀异步 `from-storage/jobs` | ✅ |

**明确不做（当时）：** 见 P13 / P14；现均已交付。

## Stripe

配置（未配密钥时接口返回 503，管理员 topup 仍可用）：

```
STRIPE_SECRET_KEY=
STRIPE_WEBHOOK_SECRET=
STRIPE_SUCCESS_URL=http://localhost:3000/projects?billing=success
STRIPE_CANCEL_URL=http://localhost:3000/projects?billing=cancel
STRIPE_CREDIT_PACKS=[{"id":"pack_1k","credits":1000,"amount_cents":999,"currency":"usd","label":"1000 积分"}]
```

API：

- `GET /billing/packs` — 可见积分包
- `POST /orgs/{id}/billing/checkout` — 创建 Checkout Session
- `POST /billing/stripe/webhook` — `checkout.session.completed` → `reason=stripe` 入账

## 共编

- 2D：`pushDraft` / 远端合并进 annotation store
- `useModalityWorkspace`：接入 `useYjsCollab`，payload 变更广播
- Collab Hub：有 Redis 时 pub/sub 扇出

## 挂载硬化

- `STORAGE_BROWSE_ALLOW_PREFIXES`（逗号分隔相对前缀；空=仅 `projects/`）
- Local：拒绝 symlink 逃逸
- S3：`Delimiter=/` 列出子目录
- `POST …/import/from-storage/jobs` 大前缀后台导入

## 迁移

无新表（复用 `org_billing_ledger` + `task_collab_docs`）。需安装可选依赖：`pip install stripe`。
