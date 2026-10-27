from fastapi import APIRouter

from app.config import get_settings

router = APIRouter(tags=["health"])


@router.get("/healthz", summary="健康检查")
def healthz() -> dict[str, str]:
    """当前阶段只证明应用本身存活；数据库和 Redis 检查会在后续模块加入。"""
    settings = get_settings()
    return {
        "status": "ok",
        "app": settings.app_name,
        "env": settings.app_env,
    }
