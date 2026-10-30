from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class RegisterRequest(BaseModel):
    """注册请求：用户名只允许字母、数字和下划线。"""

    # Field定义的这些元信息会进入 FastAPI 自动生成的 /docs 文档
    # 前端可以直接看到
    username: str = Field(
        min_length=3,
        max_length=32,
        pattern=r"^[A-Za-z0-9_]+$",
    )
    password: str = Field(min_length=6, max_length=128)


class LoginRequest(BaseModel):
    username: str
    password: str


class UserOut(BaseModel):
    """用户响应：绝不包含 hashed_password。"""

    # 默认情况下 Pydantic 只认字典和它自己的模型，UserOut.model_validate(user_orm) 会失败
    # 加上 from_attributes=True 之后，Pydantic 就允许按属性名访问：
    # user_orm.id、user_orm.username、user_orm.created_at。

    model_config = ConfigDict(from_attributes=True)

    id: int
    username: str
    created_at: datetime


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    expires_in: int


class ProductOut(BaseModel):
    """商品响应：金额统一用「分」，避免浮点误差。"""

    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    description: str | None
    price_cents: int
    stock: int
    is_active: bool
    created_at: datetime
    updated_at: datetime


class ProductListResponse(BaseModel):
    items: list[ProductOut]
    total: int
    page: int
    page_size: int
