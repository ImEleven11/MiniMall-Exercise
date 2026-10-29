from fastapi import APIRouter

from app.deps import CurrentUser
from app.schemas import UserOut # UserOut 是 Pydantic 响应模型，定义"返回给客户端的用户数据长什么样"

# prefix：这个 router 下注册的所有接口，路径前面都自动加上prefix（这个路径）
router = APIRouter(prefix="/api/v1/users", tags=["users"])


@router.get("/me", response_model=UserOut, summary="当前用户")
def read_me(current_user: CurrentUser) -> UserOut: # 依赖注入
    return UserOut.model_validate(current_user)
