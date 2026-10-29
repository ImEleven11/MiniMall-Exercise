import logging

from fastapi import APIRouter, Response, status
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError

from app.config import get_settings
from app.database import engine

logger = logging.getLogger(__name__)

# APIRouter 是 FastAPI 提供的路由分组容器
# 可以理解为迷你FastAPI
# 但它本身不能直接运行，必须被挂到真正的 app 上
# tag 只影响 /docs 文档的展示：Swagger UI 会按 tag 把接口分组折叠显示
router = APIRouter(tags=["health"]) 


@router.get("/healthz", summary="健康检查")
def healthz(response: Response) -> dict[str, object]:
    """检查应用本身和数据库连接；Redis 检查会在下一个模块加入。"""
    settings = get_settings()
    database_ok = True

    try:
        with engine.connect() as connection:
            connection.execute(text("SELECT 1"))
    except SQLAlchemyError:
        database_ok = False
        logger.exception("数据库健康检查失败")
        response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE

    return {
        "status": "ok" if database_ok else "degraded",
        "app": settings.app_name,
        "env": settings.app_env,
        "components": {
            "database": "ok" if database_ok else "error",
        },
    }
