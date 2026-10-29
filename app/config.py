from functools import lru_cache
from typing import Literal

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """应用配置：优先读取环境变量，其次读取项目根目录的 .env。"""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    app_name: str = "MiniMall"
    app_env: Literal["dev", "test", "prod"] = "dev"
    log_level: str = "INFO"
    database_url: str = "sqlite:///./data/app.db"

    # JWT 密钥必须由 .env / 环境变量提供，且至少 32 个字符。
    jwt_secret: str = Field(min_length=32)
    jwt_algorithm: str = "HS256"
    jwt_expire_minutes: int = 60

# 用函数的参数作为 key 缓存结果
# get_settings() 没有参数，所以第一次调用时执行 Settings() 并把结果存起来
# 之后每次调用都直接返回缓存的那个对象，不再重新执行 Settings()
# 这样就避免了每次调用都重新读取 .env 文件，提高了性能
# 全局只有一个 Settings 实例，所有地方拿到的都是同一个对象，配置保持一致
@lru_cache
def get_settings() -> Settings:
    """缓存配置对象，避免每次调用都重新读取 .env。"""
    return Settings() # 调用这个类，返回一个装满了配置项的实例对象
