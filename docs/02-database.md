# 02 · 数据库接入模块

> 所属阶段：Phase 0.2
> 完成日期：2026-10-27
> 对应代码：`app/database.py`、`app/config.py`、`app/main.py`、`app/routers/health.py`

---

## 1. 这个模块做了什么

把「应用」和「数据库」这条线接通：

1. 增加 `DATABASE_URL` 配置。
2. 创建 SQLAlchemy `engine`、`SessionLocal`、`Base`。
3. 提供 `get_db` 依赖，为每个请求创建并关闭一个 Session。
4. 应用启动时创建 `data/app.db` 并检查连接。
5. `/healthz` 增加数据库检查。

**还没有建业务表。** 这一版只验证连接和会话管理；用户表、商品表、订单表会在后续模块逐步加入。

---

## 2. 文件变化

| 文件 | 变化 |
| --- | --- |
| `app/database.py` | 新增：engine、SessionLocal、Base、get_db、init_db |
| `app/config.py` | 新增 `database_url` 配置 |
| `app/main.py` | 启动时调用 `init_db()`，关闭时 `engine.dispose()` |
| `app/routers/health.py` | 增加数据库连通性检查 |
| `.env` / `.env.example` | 增加 `DATABASE_URL` |
| `requirements.txt` | 增加 `sqlalchemy==2.1.6` |
| `data/app.db` | 首次启动自动生成（不提交 Git） |

---

## 3. SQLite 到底是什么

SQLite 不需要 Docker 镜像，也不需要启动服务。

```text
其他数据库：应用 → 网络连接 → 数据库服务（MySQL 容器）
SQLite：   应用 → sqlite3 模块 → 本地的 app.db 文件
```

Python 自带 `sqlite3`，SQLAlchemy 只是把 ORM 和 SQL 翻译成 SQLite 能执行的语句。

数据库连接地址：

```text
sqlite:///./data/app.db
```

拆开看：

| 部分 | 含义 |
| --- | --- |
| `sqlite` | 数据库类型（方言） |
| `///` | SQLite 固定写法，后面接文件路径 |
| `./data/app.db` | 相对于「启动目录」的文件路径 |

这也是为什么启动应用要在项目根目录：路径是相对的。

---

## 4. SQLAlchemy 的四个核心对象

```text
engine          → 管理连接和连接池，是数据库的入口
SessionLocal    → 生产 Session 的工厂
Session         → 一次请求内的工作单元，负责查询、事务、身份映射
Base            → 所有 ORM 模型的基类，同时也是「表结构登记处」
```

### 4.1 engine

```python
connect_args = (
    {"check_same_thread": False}
    if settings.database_url.startswith("sqlite")
    else {}
)

engine = create_engine(settings.database_url, connect_args=connect_args)
```

- `engine` 是进程级的，应用启动时创建一次。
- 它不是「一个连接」，而是连接池的管理者；需要时从池里取连接。
- SQLite 的 `check_same_thread=False` 是必须的：FastAPI 的同步路由会在线程池的不同线程里执行，默认设置会拒绝跨线程使用连接。
- 如果以后换成 MySQL/PostgreSQL，这段 `connect_args` 会自动不生效，主要改 `DATABASE_URL` 和驱动。

### 4.2 SessionLocal

```python
SessionLocal = sessionmaker(
    bind=engine,
    autoflush=False,
    autocommit=False,
    expire_on_commit=False,
)
```

- `autoflush=False`：查询前不自动把未提交的改动刷到数据库，事务行为更可控。
- `autocommit=False`：必须显式 `commit()`，避免「以为没提交，其实提交了」。
- `expire_on_commit=False`：commit 后对象属性不会立刻失效，返回响应时更省心。

### 4.3 Session 与请求的关系

```python
def get_db() -> Generator[Session, None, None]:
    db = SessionLocal()
    try:
        yield db
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()
```

执行过程：

```text
请求进入
  → FastAPI 发现路由参数依赖 get_db
  → 调用 get_db()，创建 Session
  → yield 把 Session 交给路由函数
  → 路由/Service 使用 Session
  → 请求结束
      正常：finally → close()
      异常：except → rollback() → finally → close()
```

为什么不是全局一个 Session？

- Session 会缓存对象、维护事务状态，不是线程安全的。
- 每个请求一个 Session，事务边界清楚，互不干扰。
- 连接池负责复用底层连接，Session 只是「工作单元」。

### 4.4 Base

```python
class Base(DeclarativeBase):
    pass
```

所有模型都继承它：

```python
class User(Base):
    __tablename__ = "users"
    ...
```

`Base.metadata` 记录所有已注册的表结构，`create_all()` 根据它建表。

**重要坑**：只有被 Python 导入过的模型类才会注册到 `Base.metadata`。如果模型文件没有被 import，`create_all()` 根本不知道它的存在，表不会创建。下一模块加 User 模型时，必须确保 `app/models.py` 在 `init_db()` 之前被导入。

---

## 5. 启动时发生了什么

```python
@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("应用启动 ...")
    init_db()
    yield
    engine.dispose()
    logger.info("应用关闭")
```

`init_db()`：

```python
Base.metadata.create_all(bind=engine)

with engine.connect() as connection:
    connection.execute(text("SELECT 1"))
```

两步：

1. `create_all()`：根据 `Base.metadata` 创建缺失的表。当前没有模型，所以什么都不建。
2. 主动连接并执行 `SELECT 1`：确保 `data/app.db` 文件被创建，同时验证连接真的可用。

如果数据库地址写错、目录不可写，启动会直接报错。这是「快速失败」：与其让应用带病运行，不如在启动阶段暴露问题。

关闭时 `engine.dispose()` 释放连接池。

---

## 6. `/healthz` 的变化

```json
{
  "status": "ok",
  "app": "MiniMall",
  "env": "dev",
  "components": {
    "database": "ok"
  }
}
```

检查逻辑：

```text
GET /healthz
  → 从 engine 取一个连接
  → 执行 SELECT 1
  → 成功：200，database = ok
  → 失败：503，database = error，并记录异常日志
```

注意：健康检查直接使用 `engine`，没有走 `get_db`。健康检查只是「探活」，不需要业务事务，也尽量避免依赖业务 Session。

---

## 7. 实际验证结果

启动应用（TestClient 会触发 lifespan）：

```text
应用启动 | name=MiniMall env=dev
数据库初始化完成 | url=sqlite:///./data/app.db
GET /healthz → 200
```

返回：

```json
{
  "status": "ok",
  "app": "MiniMall",
  "env": "dev",
  "components": {"database": "ok"}
}
```

检查数据库文件：

```text
db exists: True
size: 0
sqlite_master: []
```

解释：

- 文件存在：说明连接成功。
- 大小为 0 且 `sqlite_master` 为空：说明还没有任何表。这是正常的，因为本模块没有定义模型。
- 下一模块创建 `users` 表后，文件会开始有结构。

`get_db` 的查询路径也验证过：

```text
SELECT 1 -> 1
```

异常路径会先 `rollback()` 再 `close()`，然后把异常继续抛给 FastAPI。

---

## 8. 如何自己查看数据库

方式一：Python 标准库

```bash
conda run -n test python -c "import sqlite3; con=sqlite3.connect('data/app.db'); print(con.execute('SELECT name FROM sqlite_master').fetchall()); con.close()"
```

方式二：PyCharm 的 Database 工具

- 新建 SQLite 数据源
- 文件选择 `data/app.db`
- 可以直接看表和运行 SQL

方式三：DB Browser for SQLite（图形化工具，可选）

---

## 9. 为什么现在不用 Alembic

学习阶段使用：

```python
Base.metadata.create_all(bind=engine)
```

优点：简单，启动即建表。

代价：

- 表结构变更不会自动迁移（改字段、加索引需要手动处理）。
- 没有版本历史，无法回滚。
- 生产环境通常使用 Alembic 管理迁移。

所以这是明确的学习简化。等表结构开始频繁变化，再把 Alembic 加回来。

---

## 10. 常见坑

1. **模型没被导入，`create_all` 不建表**：模型必须继承 `Base`，并且模块要被 import。
2. **在错误目录启动**：SQLite 会在别处创建一个新的 `data/app.db`。
3. **SQLite 并发能力弱**：适合学习，不适合高并发写入压测。
4. **忘记关闭 Session**：本项目由 `get_db` 统一关闭；如果绕过依赖直接创建 Session，要自己 `close()`。
5. **用全局 Session**：会导致事务串线、线程安全问题。
6. **在路由里随意 `commit()`**：事务边界会散落各处；本项目的约定是 Service 负责提交。
7. **把 `data/app.db` 提交到 Git**：已在 `.gitignore` 中忽略。
8. **以为 DB 文件 0 字节就是坏了**：没有表时就是 0 字节，能连接、能查询就是正常的。
9. **SQLite 不会自动创建父目录**：代码里已经 `mkdir` 了 `data/`。
10. **生产环境直接沿用 `create_all`**：需要升级为 Alembic 迁移。

---

## 11. 自测问题

1. `engine`、`SessionLocal`、`Session`、`Base` 分别是什么？各自的生命周期多长？
2. 为什么每个请求要一个新的 Session，而不是全局共享一个？
3. `get_db` 里的 `yield` 前后分别做了什么？异常时呢？
4. `check_same_thread=False` 解决了什么问题？为什么 MySQL 不需要它？
5. `create_all()` 是根据什么知道要建哪些表的？
6. 为什么模型文件必须被 import？
7. `/healthz` 为什么直接使用 `engine`，而不是 `get_db`？
8. 现在数据库里有几张表？为什么？

---

## 12. 动手练习

1. 删掉 `data/app.db`，重启应用，确认文件重新生成。
2. 把 `.env` 里的 `DATABASE_URL` 改成 `sqlite:///./data/demo.db`，重启，观察新文件。
3. 把地址改成一个不存在的目录（例如 `sqlite:///./not_exist/app.db`），观察启动报错，理解「快速失败」。
4. 用 Python 的 `sqlite3` 连接 `data/app.db`，执行 `PRAGMA database_list;`。
5. 思考：如果两个请求同时写 SQLite，会发生什么？为什么本阶段不做并发压测？

---

## 13. 下一个模块：用户与 JWT 登录

下一份文档 `docs/03-auth.md` 会加入：

- `User` 模型（`users` 表）
- 注册接口：密码哈希后入库
- 登录接口：校验密码、签发 JWT
- `get_current_user` 依赖：解析 Bearer Token、查用户
- `GET /users/me` 受保护接口
- `Base.metadata.create_all()` 如何真正建出第一张表

到那时，`/healthz` 依然只检查连接，不检查业务表是否存在。

**本模块边界**：只接通连接和会话，不写任何业务表。先把这个基础打牢，后面每张表、每个接口都在同样的模式上扩展。
