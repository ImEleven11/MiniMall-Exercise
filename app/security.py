from datetime import datetime, timedelta, timezone

import jwt # 用于生成和验证 JWT
from pwdlib import PasswordHash # 密码哈希库

from app.config import get_settings

# argon2 的推荐配置；哈希结果中自带盐，同一个密码每次哈希结果都不同。
# 模块级创建一个哈希器实例，全局复用
# 变量名带下划线前缀，是 Python 约定，表示"模块内部使用，外部不要直接引用"
_password_hash = PasswordHash.recommended()


def hash_password(password: str) -> str:
    return _password_hash.hash(password)


def verify_password(password: str, hashed_password: str) -> bool:
    return _password_hash.verify(password, hashed_password)

# JWT 签发
def create_access_token(user_id: int) -> str:
    settings = get_settings()
    now = datetime.now(timezone.utc)
    payload = {
        "sub": str(user_id), # subject：这个token代表谁，这里放用户 ID
        "iat": now, # issued at：什么时候签发的
        "exp": now + timedelta(minutes=settings.jwt_expire_minutes), # expiration time：什么时候过期
    }
    # 返回的是编码后的 JWT 字符串，交给客户端保存
    return jwt.encode(
        payload,
        settings.jwt_secret, # 签名密钥，只能放在环境变量/密钥管理里，绝不能提交到代码仓库
        # 泄露了密钥，攻击者就能伪造任意用户的 token
        algorithm=settings.jwt_algorithm, # 签名算法
    )

# JWT 解码
def decode_access_token(token: str) -> dict:
    settings = get_settings()
    return jwt.decode(
        token,
        settings.jwt_secret,
        algorithms=[settings.jwt_algorithm],
    )
