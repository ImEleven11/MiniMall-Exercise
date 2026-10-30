import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from app import cache
from app.config import get_settings
from app.database import engine, init_db
from app.exceptions import AppError
from app.logging_config import setup_logging
from app.routers import auth, health, products, users

setup_logging()

logger = logging.getLogger(__name__)
settings = get_settings()


@asynccontextmanager
async def lifespan(app: FastAPI):
    """应用启动与关闭时执行一次，用来管理进程级资源。"""
    logger.info("应用启动 | name=%s env=%s", settings.app_name, settings.app_env)
    init_db()

    if cache.check_redis():
        logger.info("Redis 连接成功")
    else:
        logger.warning("Redis 不可用，商品详情将降级为数据库查询")

    yield

    cache.close_redis()
    engine.dispose()
    logger.info("应用关闭")


app = FastAPI(
    title=settings.app_name,
    version="0.1.0",
    description="用于学习 FastAPI 分层与业务链路的最小项目",
    lifespan=lifespan,
)

app.include_router(health.router)
app.include_router(auth.router)
app.include_router(users.router)
app.include_router(products.router)


@app.exception_handler(AppError)
async def handle_app_error(_request: Request, exc: AppError) -> JSONResponse:
    """把业务异常翻译成统一的 JSON 错误响应。"""
    return JSONResponse(
        status_code=exc.status_code,
        content={
            "code": exc.code,
            "message": exc.message,
        },
    )


@app.get("/", include_in_schema=False)
# schema 指 API 文档
# include_in_schema=False 表示这个接口不包含在 API 文档中
def root() -> dict[str, str]:
    return {
        "message": f"{settings.app_name} API",
        "docs": "/docs",
        "health": "/healthz",
    }
