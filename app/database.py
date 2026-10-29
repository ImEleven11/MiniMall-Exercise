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

# 创建 Session 工厂
SessionLocal = sessionmaker(
    bind=engine, # 把 Session 绑定到上面创建的 engine
    autoflush=False, # 关闭自动刷新：关掉后，查询前不会偷偷发 SQL，行为更可预期
    autocommit=False, # 关闭自动提交：一个请求一个 Session，成功则 commit
    expire_on_commit=False, # 关闭过期时间：提交后不让对象属性过期
)


class Base(DeclarativeBase):
    """所有 ORM 模型的基类。"""


def get_db() -> Generator[Session, None, None]:
    """每个请求打开一个 Session，请求结束或异常时关闭。"""
    db = SessionLocal() # 每个请求创建一个独立的 Session
    try:
        yield db # 返回 Session，让调用者使用
    except Exception:
        db.rollback() # 如果请求过程中发生异常，回滚事务
        raise
    finally:
        db.close() # 请求结束后关闭 Session

# 请求进来
#   → SessionLocal() 创建 db
#   → yield db，交给路由函数
#   → 路由函数执行
#        ├─ 正常返回 → finally: db.close()
#        └─ 抛异常   → except: db.rollback() → raise → finally: db.close()

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
