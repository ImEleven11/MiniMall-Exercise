from datetime import datetime

from sqlalchemy import DateTime, Integer, String, func
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class User(Base):
    __tablename__ = "users" # 表名

    # 下面都是表的列
    # Mapped[]：Python 侧的类型声明
    # mapped_column()：数据库侧的列定义，定义列的属性
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    username: Mapped[str] = mapped_column(
        String(32), unique=True, index=True, nullable=False
    ) # 唯一约束（防止重复注册），索引（加速查询），非空（用户名必填）
    hashed_password: Mapped[str] = mapped_column(String(255), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
