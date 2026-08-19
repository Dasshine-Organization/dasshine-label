"""
Dasshine Label - 核心配置模块
"""
import os
from pathlib import Path
from typing import List, Optional, Union
from pydantic import PostgresDsn, RedisDsn, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """应用配置"""
    
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=True,
    )
    
    # 应用信息
    APP_NAME: str = "Dasshine Label"
    APP_VERSION: str = "0.1.0"
    DEBUG: bool = False
    
    # 安全
    SECRET_KEY: str = "your-secret-key-change-in-production"
    ALGORITHM: str = "HS256"
    # 访问令牌默认 12 小时（可用环境变量覆盖；生产建议 ≤ 24h）
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60 * 12

    # 限流（每分钟；优先 Redis，不可用则进程内存）
    RATE_LIMIT_ENABLED: bool = True
    RATE_LIMIT_API_PER_MINUTE: int = 180
    RATE_LIMIT_AUTH_PER_MINUTE: int = 20
    RATE_LIMIT_CLAIM_PER_MINUTE: int = 40
    RATE_LIMIT_IMPORT_PER_MINUTE: int = 30

    # P11 共编 / 计费
    COLLAB_ENABLED: bool = True
    BILLING_ENABLED: bool = True
    BILLING_CREDIT_PER_IMPORT_TASK: int = 1
    BILLING_CREDIT_PER_EXPORT: int = 10

    # P12 Stripe（可选；未配置则 Checkout 不可用）
    STRIPE_SECRET_KEY: Optional[str] = None
    STRIPE_WEBHOOK_SECRET: Optional[str] = None
    STRIPE_SUCCESS_URL: str = "http://localhost:3000/projects?billing=success"
    STRIPE_CANCEL_URL: str = "http://localhost:3000/projects?billing=cancel"
    # JSON 数组：[{"id","credits","amount_cents","currency","label"}]
    STRIPE_CREDIT_PACKS: str = (
        '[{"id":"pack_1k","credits":1000,"amount_cents":999,"currency":"usd","label":"1000 积分"},'
        '{"id":"pack_5k","credits":5000,"amount_cents":3999,"currency":"usd","label":"5000 积分"}]'
    )
    # P13 订阅计划：[{"id","price_id","credits_per_month","label"}]
    STRIPE_PRICE_PLANS: str = "[]"
    STRIPE_PORTAL_RETURN_URL: str = "http://localhost:3000/projects?billing=portal"
    # P14 Stripe Tax / Connect
    STRIPE_TAX_ENABLED: bool = False
    STRIPE_CONNECT_ENABLED: bool = False
    STRIPE_CONNECT_COUNTRY: str = "US"
    STRIPE_CONNECT_RETURN_URL: str = "http://localhost:3000/projects?billing=connect"
    STRIPE_APPLICATION_FEE_BPS: int = 0

    # P12 存储浏览白名单（相对 UPLOAD_DIR 或 S3 prefix；空则默认 projects/）
    STORAGE_BROWSE_ALLOW_PREFIXES: str = "projects/"
    # P14 内核 NFS/FUSE（默认不执行 mount；仅登记/探测）
    STORAGE_OS_MOUNT_ENABLED: bool = False
    STORAGE_OS_MOUNT_ALLOW_ROOTS: str = "/mnt/dasshine,/Volumes/dasshine"
    STORAGE_REQUIRE_OS_MOUNT: bool = False
    
    # 数据库
    # DATABASE_URL: PostgresDsn = "postgresql://postgres:postgres@localhost:5432/dasshine_label"
    DATABASE_URL: str = f"postgresql://{os.getenv('USER', 'lijianxiong')}@localhost:5432/dasshine_label"
    DATABASE_POOL_SIZE: int = 20
    DATABASE_MAX_OVERFLOW: int = 10
    
    # Redis
    REDIS_URL: RedisDsn = "redis://localhost:6379/0"
    
    # CORS
    BACKEND_CORS_ORIGINS: List[str] = ["http://localhost:3000", "http://localhost:5173"]
    
    @field_validator("BACKEND_CORS_ORIGINS", mode="before")
    @classmethod
    def assemble_cors_origins(cls, v: Union[str, List[str]]) -> Union[List[str], str]:
        if isinstance(v, str) and not v.startswith("["):
            return [i.strip() for i in v.split(",")]
        elif isinstance(v, (list, str)):
            return v
        raise ValueError(v)
    
    # 文件存储
    UPLOAD_DIR: str = "./uploads"
    # 文件服务对外访问根地址（部署时改为实际域名，默认本机后端）
    FILE_SERVER_BASE_URL: str = "http://localhost:8000"
    MAX_UPLOAD_SIZE: int = 100 * 1024 * 1024  # 100MB
    ALLOWED_EXTENSIONS: List[str] = [".txt", ".pdf", ".jpg", ".jpeg", ".png", ".json", ".csv", ".jsonl"]

    # 存储后端：local（默认）| s3（兼容 MinIO / 阿里云 OSS S3 / AWS S3）
    STORAGE_BACKEND: str = "local"
    S3_ENDPOINT_URL: Optional[str] = None  # 如 http://minio:9000；AWS 可留空
    S3_ACCESS_KEY_ID: Optional[str] = None
    S3_SECRET_ACCESS_KEY: Optional[str] = None
    S3_BUCKET: Optional[str] = None
    S3_REGION: str = "us-east-1"
    S3_PREFIX: str = "dasshine"  # 对象键前缀
    S3_PUBLIC_BASE_URL: Optional[str] = None  # 浏览器可访问前缀；空则按 endpoint/bucket 拼
    S3_FORCE_PATH_STYLE: bool = True  # MinIO / 多数兼容实现需要
    S3_ADDRESSING_STYLE: str = "path"  # path | virtual
    S3_VERIFY_SSL: bool = True
    
    # 自动标注（HTTP 适配器，不在进程内训练）
    AUTO_LABEL_ENABLED: bool = True
    AUTO_LABEL_CONFIDENCE_THRESHOLD: float = 0.8
    AUTO_LABEL_MODEL_PATH: Optional[str] = None
    AUTO_LABEL_LLM_BASE_URL: Optional[str] = None  # OpenAI 兼容，如 https://api.openai.com/v1
    AUTO_LABEL_LLM_API_KEY: Optional[str] = None
    AUTO_LABEL_LLM_MODEL: str = "gpt-4o-mini"
    AUTO_LABEL_WHISPER_ENDPOINT: Optional[str] = None  # POST {audio_url} → text/segments
    AUTO_LABEL_WHISPER_API_KEY: Optional[str] = None
    AUTO_LABEL_OCR_ENDPOINT: Optional[str] = None  # POST {image_url} → texts/bbox
    AUTO_LABEL_OCR_API_KEY: Optional[str] = None
    AUTO_LABEL_HTTP_TIMEOUT: float = 60.0
    AUTO_LABEL_ALLOW_DEMO: bool = False  # 无端点时的启发式；DEBUG 下默认可用
    AUTO_LABEL_AUTO_SUBMIT: bool = False
    AUTO_LABEL_BATCH_SYNC_MAX: int = 20

    # 2D 预标注模型
    PRELABEL_ENABLE_LOCAL: bool = True
    PRELABEL_LOCAL_WEIGHTS_DIR: str = "./models"
    PRELABEL_YOLO_WEIGHTS: str = "yolov8n.pt"
    PRELABEL_HF_API_TOKEN: Optional[str] = None
    PRELABEL_HF_MODEL_ID: str = "hustvl/yolos-tiny"
    PRELABEL_HF_DETR_MODEL_ID: str = "facebook/detr-resnet-50"
    PRELABEL_HTTP_ENDPOINT: Optional[str] = None
    PRELABEL_HTTP_API_KEY: Optional[str] = None

    # 具身 P3：外接策略 / 远端视频打包
    EMBODIED_POLICY_HTTP_ENDPOINT: Optional[str] = None
    EMBODIED_POLICY_HTTP_API_KEY: Optional[str] = None
    EMBODIED_POLICY_HTTP_TIMEOUT: float = 30.0
    EMBODIED_VIDEO_DOWNLOAD: bool = True
    EMBODIED_VIDEO_DOWNLOAD_MAX_MB: float = 32.0
    EMBODIED_VIDEO_DOWNLOAD_TIMEOUT: float = 15.0
    EMBODIED_VIDEO_DOWNLOAD_MAX_STREAMS: int = 8
    EMBODIED_POLICY_WEIGHTS_DIR: Optional[str] = None

    def resolved_yolo_weights_path(self) -> Path:
        """本地 YOLO 权重路径（存在则用自定义，否则交给 Ultralytics 自动下载）"""
        custom = Path(self.PRELABEL_LOCAL_WEIGHTS_DIR) / self.PRELABEL_YOLO_WEIGHTS
        if custom.is_file():
            return custom
        return Path(self.PRELABEL_YOLO_WEIGHTS)
    
    # 任务分发
    TASK_DISPATCH_BATCH_SIZE: int = 100
    TASK_DISPATCH_INTERVAL: int = 60  # 秒
    
    # 质量控制
    QUALITY_GOLDEN_RATIO: float = 0.1  # 黄金标准题比例
    QUALITY_MIN_AGREEMENT: float = 0.8  # 最小一致性阈值
    
    # 分页
    DEFAULT_PAGE_SIZE: int = 20
    MAX_PAGE_SIZE: int = 100
    
    # 日志
    LOG_LEVEL: str = "INFO"
    LOG_FORMAT: str = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"

    # P18 企业接入
    AUTH_REGISTER_ENABLED: bool = True
    OIDC_ENABLED: bool = False
    OIDC_ISSUER: Optional[str] = None  # e.g. https://accounts.google.com
    OIDC_CLIENT_ID: Optional[str] = None
    OIDC_CLIENT_SECRET: Optional[str] = None
    OIDC_REDIRECT_URI: str = "http://localhost:8000/api/v1/auth/oidc/callback"
    OIDC_SCOPES: str = "openid profile email"
    FRONTEND_URL: str = "http://localhost:5173"
    SMTP_HOST: Optional[str] = None
    SMTP_PORT: int = 587
    SMTP_USER: Optional[str] = None
    SMTP_PASSWORD: Optional[str] = None
    SMTP_FROM: str = "noreply@dasshine.local"
    SMTP_USE_TLS: bool = True
    WEBHOOK_TIMEOUT_SEC: float = 10.0
    WEBHOOK_MAX_ATTEMPTS: int = 3
    ORG_INVITE_EXPIRE_DAYS: int = 7


# 全局配置实例
settings = Settings()
