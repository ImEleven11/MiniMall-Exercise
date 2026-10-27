import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.config import get_settings
from app.logging_config import setup_logging
from app.routers import health

setup_logging()

logger = logging.getLogger(__name__)
settings = get_settings()


@asynccontextmanager
async def lifespan(app: FastAPI):
    """应用启动与关闭时执行一次，用来管理进程级资源。"""
    logger.info("应用启动 | name=%s env=%s", settings.app_name, settings.app_env)
    yield
    logger.info("应用关闭")


app = FastAPI(
    title=settings.app_name,
    version="0.1.0",
    description="用于学习 FastAPI 分层与业务链路的最小项目",
    lifespan=lifespan,
)

app.include_router(health.router)


@app.get("/", include_in_schema=False)
def root() -> dict[str, str]:
    return {
        "message": f"{settings.app_name} API",
        "docs": "/docs",
        "health": "/healthz",
    }
