from typing import Annotated

import jwt
from fastapi import Depends, HTTPException, status
# HTTPAuthorizationCredentials：提取成功后返回的凭证对象，有两个属性：
# .scheme：认证方案名，通常是 "Bearer"。
# .credentials：真正的 token 字符串，也就是请求头里 Bearer 后面的那部分。后续解码就传这个值。
# HTTPBearer：从请求中提取 token，声明"本接口用 Bearer 认证"
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import User
from app.security import decode_access_token

# 创建一个模块级的 HTTPBearer安全方案示例
# 此处提取失败时不报错，返回 None，照常进入依赖函数
bearer_scheme = HTTPBearer(auto_error=False)

# 一个依赖函数，任何路由只要声明依赖它，FastAPI就会在调用路由前先执行它
def get_current_user(
    credentials: Annotated[
        HTTPAuthorizationCredentials | None, Depends(bearer_scheme)
    ],
    db: Annotated[Session, Depends(get_db)],
) -> User:
    """从 Authorization: Bearer <token> 中解析用户。"""
    unauthorized = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="未登录或 Token 无效",
        headers={"WWW-Authenticate": "Bearer"},
    )

    if credentials is None:
        raise unauthorized

    try:
        payload = decode_access_token(credentials.credentials)
        user_id = int(payload["sub"])
    except (jwt.PyJWTError, KeyError, TypeError, ValueError):
        raise unauthorized

    user = db.get(User, user_id)
    if user is None:
        raise unauthorized

    return user


CurrentUser = Annotated[User, Depends(get_current_user)]
