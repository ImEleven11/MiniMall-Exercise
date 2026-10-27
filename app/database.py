import logging
from collections.abc import Generator
from pathlib import Path

from sqlalchemy import create_engine, text
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from app.config import get_settings

logger = logging.getLogger(__name__)
settings = get_settings()

# SQLite 不会自动创建父目录，所以先确保 data/ 存在。
DATA_DIR = Path("data")
DATA_DIR.mkdir(parents=True, exist_ok=True)

# SQLite 默认只允许创建连接的那个线程使用连接；FastAPI 的同步路由运行在线程池中，
# 因此需要关闭这个检查。
connect_args = (
    {"check_same_thread": False}
    if settings.database_url.startswith("sqlite")
    else {}
)

engine = create_engine(settings.database_url, connect_args=connect_args)

SessionLocal = sessionmaker(
    bind=engine,
    autoflush=False,
    autocommit=False,
    expire_on_commit=False,
)


class Base(DeclarativeBase):
    """所有 ORM 模型的基类。"""


def get_db() -> Generator[Session, None, None]:
    """每个请求打开一个 Session，请求结束或异常时关闭。"""
    db = SessionLocal()
    try:
        yield db
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


def init_db() -> None:
    """创建数据库文件和表结构。

    只有被导入的模型才会注册到 Base.metadata，所以这里先导入 models。
    """
    # noqa: F401 表示这个导入只为注册模型，变量本身不会被使用。
    import app.models  # noqa: F401

    Base.metadata.create_all(bind=engine)

    # 主动建立一次连接，确保数据库文件被创建，同时验证连接可用。
    with engine.connect() as connection:
        connection.execute(text("SELECT 1"))

    logger.info("数据库初始化完成 | url=%s", settings.database_url)
