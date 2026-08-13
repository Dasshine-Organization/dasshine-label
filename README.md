# Dasshine Label — 智能标注与分发平台

<div align="center">

![Dasshine Label](https://img.shields.io/badge/Dasshine-Label-00d4ff?style=for-the-badge)
![FastAPI](https://img.shields.io/badge/FastAPI-009688?style=for-the-badge&logo=fastapi&logoColor=white)
![React](https://img.shields.io/badge/React-61DAFB?style=for-the-badge&logo=react&logoColor=black)
![PostgreSQL](https://img.shields.io/badge/PostgreSQL-336791?style=for-the-badge&logo=postgresql&logoColor=white)

**多模态标注 · 项目数据导入 · AI 预标注 · 任务分发与质检**

</div>

---

## 功能概览

### 项目管理

- 创建 / 编辑项目（图像 2D、点云 3D、文本、语音、视频、多模态、具身等类型）
- **本地图片 / 文件夹 / ZIP / YOLO** 导入，文件落盘至可配置文件服务（`UPLOAD_DIR` + `FILE_SERVER_BASE_URL`），或 `STORAGE_BACKEND=s3` 写入 S3 兼容对象存储
- 项目任务网格预览，点击进入对应标注工作台
- 项目 **归档 / 恢复 / 删除**（级联删除任务与数据）

### 标注工作台

| 模态 | 路径示例 | 说明 |
|------|----------|------|
| 图像 2D | `/annotate-image/:taskId` | 矩形框、多帧会话、草稿自动保存、2D 预标注模型 |
| 点云 3D | `/annotate-3d/:taskId` | 3D 框与点标注 |
| 具身 | `/annotate-embodied/:taskId` | 多路视频 + 关节轨迹 |
| 文本 | `/annotate-text/:taskId` | NER 等语料工作区草稿与提交 |
| 语音 | `/annotate-audio/:taskId` | ASR 等语音工作区 |
| 视频 | `/annotate-video/:taskId` | 时序动作片段 |
| 多模态 | `/annotate-multimodal/:taskId` | 图文等多模态工作区 |
| 兼容跳转 | `/annotate/:taskId` | 按任务类型重定向到上述工作台 |

工作台默认从 **项目管理**（`/projects` 或 `/projects?category=…`）进入真实项目任务；硬编码演示 task id 仅在开发演示分区或显式开启 `VITE_ENABLE_DEMO_ENTRIES` 时出现。

### 任务与状态

- 任务领取、开始、提交（API）
- 2D 标注：**服务端草稿**同步，有标注框时自动标记 `annotating`，提交后 `submitted`
- 项目任务列表与标注页 **状态实时同步**（无需手动刷新）
- 顶部栏显示帧进度（已标注帧数 / 总帧数）及项目内上一条 / 下一条任务

### 平台能力

- JWT 登录注册、用户与角色管理
- 智能任务分发（技能 / 质量 / 负载等多维评分）
- 质量控制（交叉验证、审核、黄金题等 API）
- 自动标注与批量预标注（可选 Celery Worker）
- 导出（COCO / YOLO 等）

---

## 系统架构

```
┌──────────────────────────────────────────────────────────────────┐
│  Frontend (React + Vite + Ant Design + Zustand)                  │
│  项目 / 任务列表 · 2D/3D/具身/文本/音视频标注 UI                    │
└────────────────────────────┬─────────────────────────────────────┘
                             │ /api  /uploads
┌────────────────────────────▼─────────────────────────────────────┐
│  Backend (FastAPI)                                               │
│  auth · projects · dataset · tasks · annotations · drafts          │
│  prelabel · modality_workspace · embodied · quality · export     │
└────────────────────────────┬─────────────────────────────────────┘
                             │
        ┌────────────────────┼────────────────────┐
        ▼                    ▼                    ▼
   PostgreSQL              Redis              文件存储
   (业务数据)            (Celery/缓存)        (./uploads)
```

---

## 项目结构

```
dasshine-label/
├── backend/                 # FastAPI
│   ├── app/api/v1/          # REST API
│   ├── app/services/        # 业务逻辑（分发、导入、预标注、图像标注等）
│   ├── alembic/             # 迁移（可选；Docker 默认 init_db 建表）
│   ├── Dockerfile
│   └── docker-entrypoint.sh
├── frontend/                # React SPA
│   ├── src/pages/           # 页面（Projects、ProjectTasks、ImageAnnotation…）
│   ├── Dockerfile           # 生产：构建 + Nginx
│   └── nginx/default.conf
├── deploy/
│   ├── deploy.sh            # 一键部署脚本
│   ├── docker-compose.yml   # 生产栈
│   ├── docker-compose.dev.yml
│   └── .env.example
└── docs/                    # 设计文档
```

### 开发约定（唯一真源）

- **唯一工作副本**：本仓库 `Dashine/dasshine-label`。勿在其它本地分叉（如 `VscodeProject/dasshine-label`）上并行改同一功能。
- **前端真源**：仅 `frontend/src/`（`index.html` → `/src/main.tsx`）。勿再使用根级陈旧 `App.tsx` / `main.tsx`。
- **入口默认**：工作台「业务入口」走 `/projects?category=…` / `/tasks?category=…`；硬编码演示 task 仅出现在「演示入口」，由 `VITE_ENABLE_DEMO_ENTRIES` 控制（开发默认开，生产构建默认关）。
- **分类字段**：`projects.category` / `projects.ann_type` 为一等列，并与 `annotation_schema` 双写；详见 `docs/schema_category.md`。迁移：`cd backend && alembic upgrade head`。
- **类别种子**：`python scripts/seed_category_projects.py`（每类一个真实项目，无硬编码 task id）。
- **P3 闭环**：审核 `/review`；项目任务页导出 COCO；分发日志 `GET /projects/{id}/dispatch-logs`；2D 预标注用 `/tasks/{id}/prelabel/*`。
- **P4**：观测 `/health` `/ready` + JSON 访问日志；`pytest`；React Query（项目/任务/审核）；部署见 `docs/deploy.md`。

---

## 快速开始（Docker 推荐）

### 前置条件

- [Docker](https://docs.docker.com/get-docker/) 20.10+
- [Docker Compose](https://docs.docker.com/compose/) v2

### 生产部署

```bash
cd deploy
cp .env.example .env
# 编辑 .env：至少修改 SECRET_KEY；PUBLIC_URL 改为实际访问地址

chmod +x deploy.sh
./deploy.sh up -d
```

| 服务 | 地址 |
|------|------|
| **Web 前端** | http://localhost:8080 （由 `HTTP_PORT` 控制） |
| **API 文档** | http://localhost:8080/docs |
| PostgreSQL | `localhost:5432`（默认，可按需改端口） |

首次访问请 **注册账号**，登录后创建项目并导入数据。

常用命令：

```bash
./deploy.sh ps              # 查看状态
./deploy.sh logs -f backend # 后端日志
./deploy.sh worker          # 可选：启动 Celery
./deploy.sh down            # 停止
./deploy.sh down -v         # 停止并清空数据卷（慎用）
```

### 开发模式（热重载）

```bash
cd deploy
cp .env.example .env
./deploy.sh dev
```

- 前端：http://localhost:3000  
- 后端：http://localhost:8000  

---

## 本地手动启动（不用 Docker）

### 后端

```bash
cd backend
python -m venv .venv
source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env
# 配置 DATABASE_URL、SECRET_KEY、FILE_SERVER_BASE_URL 等

# PostgreSQL 已就绪后初始化表
python -c "from app.core.database import init_db; init_db()"

uvicorn app.main:app --reload --port 8000
```

### 前端

```bash
cd frontend
npm ci
# 可选 .env：VITE_API_URL=http://localhost:8000/api/v1
npm run dev
```

浏览器打开 http://localhost:3000 。

### Celery（可选）

```bash
cd backend
celery -A app.celery_app worker --loglevel=info
```

---

## 环境变量说明

后端主要配置见 `backend/.env.example`：

| 变量 | 说明 |
|------|------|
| `DATABASE_URL` | PostgreSQL 连接串 |
| `REDIS_URL` | Redis（Celery） |
| `SECRET_KEY` | JWT 密钥，**生产必须修改** |
| `UPLOAD_DIR` | 本地上传目录（`STORAGE_BACKEND=local`） |
| `FILE_SERVER_BASE_URL` | 本地模式下 `data_url` 公网前缀 |
| `STORAGE_BACKEND` | `local` 或 `s3`（MinIO/AWS/OSS 兼容，见 `docs/storage_s3.md`） |
| `BACKEND_CORS_ORIGINS` | 允许的前端源，逗号分隔 |
| `PRELABEL_ENABLE_LOCAL` | 是否启用本地 YOLO 预标注（需安装 ultralytics） |

Docker 部署使用 `deploy/.env`，其中 `PUBLIC_URL` 会同步写入 `FILE_SERVER_BASE_URL` 与 CORS。

---

## 典型工作流（图像 2D）

1. **项目管理** → 新建 `image_2d` 项目  
2. **导入数据** → 拖拽本地图片或 ZIP，可选填写文件服务地址  
3. 进入 **项目任务列表** → 点击缩略图打开标注  
4. 绘制标注框 → 自动保存草稿，状态变为「标注中」  
5. 点击 **提交** → 状态变为「已提交」，返回列表自动更新  

---

## API 文档

本地运行后访问：

- Swagger UI：`/docs`
- ReDoc：`/redoc`

主要路由前缀：`/api/v1`（认证、项目、任务、数据集导入、标注草稿、预标注、多模态工作区等）。

---

## 文档目录

- [任务分发算法](docs/task_dispatch.md)
- [自动标注服务](docs/auto_label.md)
- [质量控制体系](docs/quality_control.md)
- [前端界面说明](docs/frontend.md)

---

## 贡献与许可

欢迎提交 Issue 与 Pull Request。

MIT License

---

<div align="center">
Made with care by Dasshine Team
</div>
