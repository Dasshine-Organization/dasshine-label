# P14 · Automerge · NFS/FUSE · 逐点/像素 CRDT · Connect/税务

P13 交付了订阅门户、虚拟挂载、点云/具身粗粒度共编。本迭代收口此前全部延后项，**不再延后**。

## 范围

| ID | 交付 | 状态 |
|----|------|------|
| **P14-1** | 共编引擎换为 Automerge；对象级 Map + 稀疏像素/点标签 CRDT | ✅ |
| **P14-2** | `fuse` / `nfs` 挂载种类；内核挂载探测/挂载；用户态 FUSE 文件系统 + CLI | ✅ |
| **P14-3** | Stripe Tax（Checkout `automatic_tax`）+ Connect Express 入驻与 destination charge | ✅ |

## 共编（Automerge）

- 前端：`useCollab`（`useYjsCollab` 兼容再导出）
- 文档：`objects`（`a:{id}` / `b:{id}`）+ `pixels`（`x,y` → label）+ `pointLabels`（点索引 → label）+ `payload`
- WS 仍中继二进制；`engine=automerge`；旧 Yjs 快照加载失败则新建空文档
- 2D 画笔写入稀疏像素；点云 `point` 工具写入逐点标签

## NFS / FUSE

```
STORAGE_OS_MOUNT_ENABLED=false
STORAGE_OS_MOUNT_ALLOW_ROOTS=/mnt/dasshine,/Volumes/dasshine
```

- `kind=nfs|fuse` + `options.nfs_export` / `os_mount_point`
- `GET /storage/os-mounts` 列内核挂载
- `POST /orgs/{id}/storage-mounts/{id}/os-attach` 绑定已有挂载点
- `POST …/os-mount` 仅当 `STORAGE_OS_MOUNT_ENABLED=true` 时执行 `mount`
- CLI：`python -m app.cli.fuse_mount --root uploads/projects --mountpoint /tmp/dasshine-fuse`

## Stripe Connect / Tax

```
STRIPE_TAX_ENABLED=true
STRIPE_CONNECT_ENABLED=true
STRIPE_CONNECT_COUNTRY=US
STRIPE_CONNECT_RETURN_URL=http://localhost:3000/projects?billing=connect
STRIPE_APPLICATION_FEE_BPS=1000
```

- Checkout / 订阅：`automatic_tax` + `tax_id_collection`
- `POST /orgs/{id}/billing/connect/onboard` → Account Link
- destination charge / `application_fee_percent`（Connect 账户 `charges_enabled` 后）
- Webhook：`account.updated`

## 迁移

```bash
cd backend && .venv/bin/alembic upgrade head
# 20260818_p14_fuse_connect
cd frontend && npm install
```
