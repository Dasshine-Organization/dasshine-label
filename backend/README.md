# Dasshine Label 后端

## 技术栈

- **框架**: FastAPI 0.104+
- **数据库**: PostgreSQL 14+ + SQLAlchemy 2.0+
- **迁移**: Alembic
- **认证**: JWT (python-jose)
- **任务队列**: Celery + Redis
- **测试**: Pytest

## 目录结构

```
backend/
├── app/
│   ├── __init__.py
│   ├── main.py              # FastAPI入口
│   ├── core/                # 核心配置
│   │   ├── __init__.py
│   │   ├── config.py        # 配置管理
│   │   ├── security.py      # 安全工具
│   │   └── exceptions.py    # 自定义异常
│   ├── api/                 # API路由
│   │   ├── __init__.py
│   │   ├── deps.py          # 依赖注入
│   │   └── v1/
│   │       ├── __init__.py
│   │       ├── auth.py
│   │       ├── projects.py
│   │       ├── tasks.py
│   │       ├── annotations.py
│   │       ├── users.py
│   │       └── export.py
│   ├── models/              # 数据库模型
│   │   ├── __init__.py
│   │   ├── base.py
│   │   ├── user.py
│   │   ├── project.py
│   │   ├── task.py
│   │   ├── annotation.py
│   │   └── quality.py
│   ├── schemas/             # Pydantic模型
│   │   ├── __init__.py
│   │   ├── user.py
│   │   ├── project.py
│   │   ├── task.py
│   │   └── annotation.py
│   ├── services/            # 业务逻辑
│   │   ├── __init__.py
│   │   ├── auto_label.py    # 自动标注
│   │   ├── task_dispatch.py # 任务分发
│   │   ├── quality_control.py # 质量控制
│   │   ├── export.py
│   │   └── prelabel/        # 2D 预标注（YOLO/HF/HTTP）
│   └── db/                  # 数据库（转发 core.database）
│       ├── __init__.py
│       └── session.py
├── alembic/                 # 数据库迁移
├── tests/
├── Dockerfile
└── requirements.txt
```

## 快速开始

```bash
# 安装依赖
pip install -r requirements.txt

# 配置环境变量
export DATABASE_URL="postgresql://user:password@localhost/dasshine_label"
export SECRET_KEY="your-secret-key"
export REDIS_URL="redis://localhost:6379"

# 运行迁移
alembic upgrade head

# 启动服务
uvicorn app.main:app --reload
```

## API文档

启动后访问：
- Swagger UI: http://localhost:8000/docs
- ReDoc: http://localhost:8000/redoc
