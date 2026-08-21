# Dasshine Label — 智能标注与分发平台

<div align="center">

![Dasshine Label](https://img.shields.io/badge/Dasshine-Label-00d4ff?style=for-the-badge)
![FastAPI](https://img.shields.io/badge/FastAPI-009688?style=for-the-badge&logo=fastapi&logoColor=white)
![React](https://img.shields.io/badge/React-61DAFB?style=for-the-badge&logo=react&logoColor=black)
![PostgreSQL](https://img.shields.io/badge/PostgreSQL-336791?style=for-the-badge&logo=postgresql&logoColor=white)

**多模态标注 · 多租户质检 · Automerge 共编 · Stripe 计费 · 存储挂载**

</div>

---

## 功能概览

### 项目管理

- 创建 / 编辑项目（图像 2D、点云 3D、文本、语音、视频、OCR、多模态、具身等）
- **本地图片 / 文件夹 / ZIP / YOLO / 存储前缀 / 组织挂载** 导入；落盘 `UPLOAD_DIR` 或 `STORAGE_BACKEND=s3`
- 项目任务网格预览，点击进入对应标注工作台
- 项目 **归档 / 恢复 / 删除**（级联删除任务与数据）
- 组织作用域：侧栏切换组织，项目/任务/领取/审核按 `active_org` 隔离

### 标注工作台

| 模态 | 路径示例 | 说明 |
|------|----------|------|
| 图像 2D | `/annotate-image/:taskId` | 框/多边形/画笔像素、草稿、预标注、Automerge 共编 |
| 点云 3D | `/annotate-3d/:taskId` | 3D 框 + 逐点标签、共编 presence |
| 具身 | `/annotate-embodied/:taskId` | 多路视频 / 关节轨迹 / 草稿共编 |
| OCR | `/annotate-ocr/:taskId` | 文本检测与识别工作台 |
| 文本 / 语音 / 视频 / 多模态 | `/annotate-text|audio|video|multimodal/:taskId` | 模态工作区草稿与提交 |
| 兼容跳转 | `/annotate/:taskId` | 按任务类型重定向 |

工作台默认从 **项目管理**（`/projects` 或 `/projects?category=…`）进入真实任务；硬编码演示 task 仅在开发或 `VITE_ENABLE_DEMO_ENTRIES=true` 时出现。

多人同时打开同一任务：占用锁（`TaskLockBanner`）+ Automerge CRDT（对象 / 稀疏像素 / 逐点）+ 在线 presence。

### 任务 · 质检 · 导出

- 领取 / 开始 / 提交；草稿同步后进入 `annotating`，提交后 `submitted`
- 交叉验证、黄金题盲测、审核队列 `/review`（并排版本 + 共识真源）
- 按模态导出三种主流训练格式（见 `docs/export_formats.md`），支持异步作业

### 平台能力

- JWT 登录（默认 12h）+ 分层 API 限流
- 智能任务分发（技能 / 质量 / 负载）与分发日志
- 组织配额与积分账本；Stripe 一次性充值、订阅门户、可选 Tax / Connect
- 存储浏览白名单、组织 `storage_mounts`（含 NFS/FUSE 登记）
- 观测：`/health` `/ready`、JSON 访问日志；Compose 默认 Celery worker + beat

---

## 系统架构

```
┌──────────────────────────────────────────────────────────────────┐
│  Frontend (React + Vite + Ant Design + Zustand + Automerge)      │
│  项目 / 任务 / 审核 · 多模态工作台 · 组织切换 · 充值/订阅           │
└────────────────────────────┬─────────────────────────────────────┘
                             │ HTTP /api  · WS /api/v1/ws/…/collab
┌────────────────────────────▼─────────────────────────────────────┐
│  Backend (FastAPI)                                               │
│  auth · orgs · billing · projects · dataset · storage-mounts     │
│  tasks · collab · quality · export · embodied · prelabel         │
└────────────────────────────┬─────────────────────────────────────┘
                             │
     ┌───────────────┬───────┴────────┬──────────────┐
     ▼               ▼                ▼              ▼
 PostgreSQL        Redis           文件/S3        Stripe
 业务+账本      Celery/共编扇出    uploads/挂载    可选支付
```

---

## 项目结构

```
dasshine-label/
├── backend/                 # FastAPI
│   ├── app/api/v1/          # REST + WebSocket
│   ├── app/services/        # 分发、导入、共编、计费、挂载、FUSE
│   ├── alembic/             # 迁移（开发用 alembic upgrade head）
│   └── tests/
├── frontend/                # React SPA
│   └── src/pages/           # Projects、工作台、Review…
├── deploy/                  # Compose 生产/开发栈
├── scripts/                 # 种子、NFS 挂载辅助
└── docs/                    # 约定与各迭代计划
```

### 开发约定

- **唯一真源**：本仓库。细节见 [`docs/CANONICAL.md`](docs/CANONICAL.md)。
- **前端**：仅 `frontend/src/`（`index.html` → `src/main.tsx`）。
- **分类**：`projects.category` / `projects.ann_type` 与 schema 双写；`cd backend && alembic upgrade head`。
- **测试**：`cd backend && pytest`。

---

## 快速开始（Docker 推荐）

### 生产部署

```bash
cd deploy
cp .env.example .env
# 至少修改 SECRET_KEY；PUBLIC_URL 改为实际访问地址

chmod +x deploy.sh
./deploy.sh up -d
```

| 服务 | 地址 |
|------|------|
| **Web 前端** | http://localhost:8080（`HTTP_PORT`） |
| **API 文档** | http://localhost:8080/docs（仅 `DEBUG=true`） |
| PostgreSQL | `localhost:5432` |

首次访问请 **注册账号**，登录后创建组织/项目并导入数据。

```bash
./deploy.sh ps
./deploy.sh logs -f backend
./deploy.sh worker          # 重启 Celery（up/dev 已默认启动）
./deploy.sh down
```

### 开发模式（热重载）

```bash
cd deploy && cp .env.example .env && ./deploy.sh dev
```

前端 http://localhost:3000 · 后端 http://localhost:8000

---

## 本地手动启动

### 后端

```bash
cd backend
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
# 配置 DATABASE_URL、SECRET_KEY、FILE_SERVER_BASE_URL、REDIS_URL

.venv/bin/alembic upgrade head
# 或：python -c "from app.core.database import init_db; init_db()"

uvicorn app.main:app --reload --port 8000
```

可选：`pip install stripe fusepy`；FUSE 挂载 `python -m app.cli.fuse_mount --root ./uploads/projects --mountpoint /tmp/dasshine-fuse`。

### 前端

```bash
cd frontend
npm ci
npm run dev
```

### Celery

Compose 已默认启用。裸跑：

```bash
cd backend
celery -A app.celery_app worker --loglevel=info
celery -A app.celery_app beat --loglevel=info
```

---

## 环境变量（摘录）

完整列表见 `backend/.env.example`。Docker 用 `deploy/.env`，`PUBLIC_URL` 会写入 CORS 与 `FILE_SERVER_BASE_URL`。

| 变量 | 说明 |
|------|------|
| `DATABASE_URL` / `REDIS_URL` | Postgres / Redis |
| `SECRET_KEY` | JWT 密钥，**生产必须修改** |
| `ACCESS_TOKEN_EXPIRE_MINUTES` | 默认 720（12h） |
| `STORAGE_BACKEND` | `local` 或 `s3`（见 `docs/storage_s3.md`） |
| `COLLAB_ENABLED` / `BILLING_ENABLED` | 共编与积分账本 |
| `STRIPE_SECRET_KEY` | 未配置则 Checkout 返回 503，管理员 topup 仍可用 |
| `STRIPE_PRICE_PLANS` | 订阅计划 JSON |
| `STRIPE_TAX_ENABLED` / `STRIPE_CONNECT_ENABLED` | Stripe Tax / Connect |
| `STORAGE_BROWSE_ALLOW_PREFIXES` | 浏览白名单，默认 `projects/` |
| `STORAGE_OS_MOUNT_ENABLED` | 是否允许 API 执行内核 `mount`（默认关） |

---

## 典型工作流（图像 2D）

1. 注册并切换到目标组织 → 新建 `image_2d` 项目  
2. 导入本地文件，或从存储前缀 / 组织挂载导入  
3. 打开任务：绘制框或画笔 → 草稿自动保存；可与同事共编  
4. 提交 → 审核队列通过后按格式导出  

---

## 文档

| 主题 | 文档 |
|------|------|
| **界面操作指南（含截图）** | [`docs/user-guide/界面操作指南.md`](docs/user-guide/界面操作指南.md) |
| 仓库约定（P0–P14） | [`docs/CANONICAL.md`](docs/CANONICAL.md) |
| 部署 / 限流 | [`docs/deploy.md`](docs/deploy.md) |
| 导出格式 | [`docs/export_formats.md`](docs/export_formats.md) |
| S3 存储 | [`docs/storage_s3.md`](docs/storage_s3.md) |
| 任务分发 | [`docs/task_dispatch.md`](docs/task_dispatch.md) |
| 质控 | [`docs/quality_control.md`](docs/quality_control.md) |
| P11 共编·计费·挂载 | [`docs/p11_collab_billing_mount.md`](docs/p11_collab_billing_mount.md) |
| P12 Stripe·多模态共编 | [`docs/p12_stripe_collab_mount.md`](docs/p12_stripe_collab_mount.md) |
| P13 订阅·虚拟挂载 | [`docs/p13_subscriptions_mounts_collab.md`](docs/p13_subscriptions_mounts_collab.md) |
| P14 Automerge·FUSE·Connect | [`docs/p14_automerge_fuse_connect.md`](docs/p14_automerge_fuse_connect.md) |

API：`/api/v1`（`DEBUG=true` 时 `/docs`、`/redoc`）。

---

## 贡献与许可

欢迎提交 Issue 与 Pull Request。

MIT License

---

<div align="center">
Made with care by Dasshine Team
</div>
