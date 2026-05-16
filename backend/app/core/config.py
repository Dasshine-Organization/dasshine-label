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
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60 * 24 * 7  # 7天
    
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
    
    # 自动标注
    AUTO_LABEL_ENABLED: bool = True
    AUTO_LABEL_CONFIDENCE_THRESHOLD: float = 0.8
    AUTO_LABEL_MODEL_PATH: Optional[str] = None

    # 2D 预标注模型
    PRELABEL_ENABLE_LOCAL: bool = True
    PRELABEL_LOCAL_WEIGHTS_DIR: str = "./models"
    PRELABEL_YOLO_WEIGHTS: str = "yolov8n.pt"
    PRELABEL_HF_API_TOKEN: Optional[str] = None
    PRELABEL_HF_MODEL_ID: str = "hustvl/yolos-tiny"
    PRELABEL_HF_DETR_MODEL_ID: str = "facebook/detr-resnet-50"
    PRELABEL_HTTP_ENDPOINT: Optional[str] = None
    PRELABEL_HTTP_API_KEY: Optional[str] = None

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


# 全局配置实例
settings = Settings()
