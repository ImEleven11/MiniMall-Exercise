from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.exceptions import InvalidCredentialsError, UsernameAlreadyExistsError
from app.models import User
from app.security import create_access_token, hash_password, verify_password


def register_user(db: Session, username: str, password: str) -> User:
    """创建用户并提交事务。"""
    # 先查重，等价于"按用户名查用户，取一个"
    existing = db.scalar(select(User).where(User.username == username))
    if existing is not None:
        raise UsernameAlreadyExistsError()

    user = User(username=username, hashed_password=hash_password(password))
    db.add(user)

    # 提交事务、写库
    try:
        db.commit()
    except IntegrityError:
        # 并发注册同名用户时，唯一索引会在这里兜底。
        db.rollback()
        raise UsernameAlreadyExistsError() from None

    db.refresh(user)
    return user

# 该函数职责：
# 查重（友好报错）
#   → 哈希密码
#   → 构造对象、加入 Session
#   → commit（写库）
#       └─ 唯一索引兜底并发 → rollback + 抛业务异常
#   → refresh（补齐数据库生成字段）
#   → 返回 User

def login_user(db: Session, username: str, password: str) -> str:
    """校验用户名和密码，成功时返回 JWT。"""
    # 按用户名查用户
    user = db.scalar(select(User).where(User.username == username))

    # 用户不存在和密码错误返回同一个异常，避免暴露用户名是否存在。
    if user is None or not verify_password(password, user.hashed_password):
        raise InvalidCredentialsError()

    # 签发 token
    return create_access_token(user.id)

# 函数职责：
# 按用户名查用户
#   → 不存在 或 密码不匹配 → 同一个异常（防枚举）
#   → 通过 → 签发 JWT → 返回