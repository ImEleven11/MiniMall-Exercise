from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.exceptions import InvalidCredentialsError, UsernameAlreadyExistsError
from app.models import User
from app.security import create_access_token, hash_password, verify_password


def register_user(db: Session, username: str, password: str) -> User:
    """创建用户并提交事务。"""
    existing = db.scalar(select(User).where(User.username == username))
    if existing is not None:
        raise UsernameAlreadyExistsError()

    user = User(username=username, hashed_password=hash_password(password))
    db.add(user)

    try:
        db.commit()
    except IntegrityError:
        # 并发注册同名用户时，唯一索引会在这里兜底。
        db.rollback()
        raise UsernameAlreadyExistsError() from None

    db.refresh(user)
    return user


def login_user(db: Session, username: str, password: str) -> str:
    """校验用户名和密码，成功时返回 JWT。"""
    user = db.scalar(select(User).where(User.username == username))

    # 用户不存在和密码错误返回同一个异常，避免暴露用户名是否存在。
    if user is None or not verify_password(password, user.hashed_password):
        raise InvalidCredentialsError()

    return create_access_token(user.id)
