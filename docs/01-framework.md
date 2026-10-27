# 01 · 框架骨架模块

> 所属阶段：Phase 0.1
> 完成日期：2026-10-27
> 对应代码：`app/main.py`、`app/config.py`、`app/logging_config.py`、`app/routers/health.py`

---

## 1. 这个模块做了什么

只做四件事，先把 FastAPI 应用跑起来：

1. 创建 FastAPI 应用对象，并配置标题、版本、描述。
2. 把配置从代码里挪到 `.env`，通过 `pydantic-settings` 读取。
3. 加一个统一的日志格式。
4. 提供一个 `/healthz` 健康检查接口，以及 `/` 根路径提示。

**本模块还没有数据库、Redis、登录和业务逻辑。** 这不是遗漏，而是为了让每一步的依赖关系都清楚：先证明「应用本身能跑」，再往里加数据库，再加 Redis。

---

## 2. 环境说明

| 项目 | 值 |
| --- | --- |
| Conda 环境 | `test` |
| Python | 3.11.15 |
| SQLite | 3.51.2（Python 内置，不需要 Docker 镜像） |
| 已安装 | fastapi 0.162.0、uvicorn 0.54.0、pydantic-settings 2.16.1 |

关于 SQLite 的一个常见误解：

> SQLite 不是需要 Docker 启动的服务，也没有「SQLite 镜像」这个概念。
> 它是一个嵌入式数据库，Python 自带 `sqlite3` 模块，SQLAlchemy 只是把 SQL 发给这个内置库。
> 数据最终就是项目里的一个 `data/app.db` 文件。

Docker Desktop 目前没有启动也不影响本模块。到 Redis 模块时再启动 Docker。

---

## 3. 文件清单

```text
a-little-exercise/
├── app/
│   ├── __init__.py          # 标记 app 是一个 Python 包
│   ├── main.py              # 应用入口：创建 app、注册路由、lifespan
│   ├── config.py            # 配置读取
│   ├── logging_config.py    # 日志格式
│   └── routers/
│       ├── __init__.py
│       └── health.py        # /healthz
├── scripts/
│   └── smoke_test.py        # 可选：临时启动 uvicorn 做冒烟检查
├── .env                     # 本地配置（不提交）
├── .env.example             # 配置模板（提交）
├── .gitignore
├── requirements.txt
└── README.md
```

| 文件 | 负责 | 不负责 |
| --- | --- | --- |
| `app/main.py` | 组装应用：创建 app、挂路由、注册生命周期 | 业务逻辑、数据库查询 |
| `app/config.py` | 读取环境变量和 `.env` | 业务逻辑 |
| `app/logging_config.py` | 设置日志级别和输出格式 | 记录业务事件 |
| `app/routers/health.py` | 健康检查接口 | 真正的数据库/Redis 检查（下一阶段加） |
| `.env` | 本地实际配置 | 被提交到 Git |
| `requirements.txt` | 运行依赖及版本 | 开发工具依赖 |

---

## 4. 一次请求的链路

以 `GET /healthz` 为例：

```text
浏览器 / Swagger / curl
        │  HTTP 请求
        ▼
Uvicorn（ASGI 服务器）
        │  把请求交给 ASGI 应用
        ▼
FastAPI 应用对象 app
        │  匹配路径 /healthz
        ▼
APIRouter 中注册的 healthz 函数
        │  调用 get_settings()
        ▼
返回 Python 字典
        │  FastAPI 自动 JSON 序列化
        ▼
HTTP 200 + JSON
```

### 4.1 Uvicorn 和 FastAPI 的分工

- **Uvicorn**：负责监听端口、解析 HTTP、管理连接，是一个 ASGI 服务器。
- **FastAPI**：负责路由、参数校验、依赖注入、生成文档，是一个 ASGI 应用。

启动命令里的 `app.main:app` 含义是：

```text
app/main.py 文件里的 app 变量
```

所以 `app.main` 不是包名，而是「模块路径」。

### 4.2 应用对象

```python
app = FastAPI(
    title=settings.app_name,
    version="0.1.0",
    description="用于学习 FastAPI 分层与业务链路的最小项目",
    lifespan=lifespan,
)
```

`app` 是整棵路由树的根。后续所有 Router、中间件、异常处理器都会挂到它上面。

### 4.3 Router 的作用

```python
# app/routers/health.py
router = APIRouter(tags=["health"])

@router.get("/healthz", summary="健康检查")
def healthz() -> dict[str, str]:
    ...
```

```python
# app/main.py
app.include_router(health.router)
```

Router 让「接口定义」和「应用组装」分开：

- `health.py` 只关心自己这一组接口。
- `main.py` 决定把哪些 Router 挂到应用上。

后面会按业务拆成 `auth.py`、`products.py`、`orders.py`，`main.py` 只负责 include，不会越来越臃肿。

### 4.4 `/docs` 从哪里来

FastAPI 会根据路由函数和类型注解自动生成 OpenAPI 文档：

- `/docs`：Swagger UI，可以直接在页面上调接口。
- `/openapi.json`：机器可读的接口描述。

当前 OpenAPI 里只有 `/healthz`，因为其他接口还没写。

---

## 5. 关键代码逐段说明

### 5.1 配置：`app/config.py`

```python
class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    app_name: str = "MiniMall"
    app_env: Literal["dev", "test", "prod"] = "dev"
    log_level: str = "INFO"
```

读取优先级：

```text
真实环境变量  >  .env 文件  >  代码里的默认值
```

比如在 PowerShell 里设置 `$env:APP_ENV = "prod"`，它会覆盖 `.env` 中的值。

`@lru_cache` 让配置只解析一次：

```python
@lru_cache
def get_settings() -> Settings:
    return Settings()
```

这样每次请求调用 `get_settings()` 拿到的是同一个对象，不会反复读文件。

### 5.2 日志：`app/logging_config.py`

```python
logging.basicConfig(
    level=level,
    format="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
    force=True,
)
```

- `level` 来自 `.env` 的 `LOG_LEVEL`，方便开发时调成 `DEBUG`。
- `%(name)s` 是 logger 名称，例如 `app.main`，能看出日志来自哪个模块。
- `force=True` 保证重复配置时替换旧的 handler，避免日志重复输出。

日志在 `main.py` 顶部调用一次：

```python
setup_logging()
logger = logging.getLogger(__name__)
```

### 5.3 生命周期：`lifespan`

```python
@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("应用启动 | ...")
    yield
    logger.info("应用关闭")
```

- `yield` 之前：应用启动时执行，适合创建连接池、Redis 客户端。
- `yield` 之后：应用关闭时执行，适合关闭连接、释放资源。
- 一个进程只执行一次，不是每个请求一次。

本阶段还没有需要初始化的资源，所以只打日志。等数据库和 Redis 模块进来，就会把 engine 和 Redis 客户端的创建/关闭放到这里。

> 注意：直接用 `TestClient(app)` 而不进入上下文管理器时，lifespan 不会执行。用 `with TestClient(app) as client:` 或真实运行 `uvicorn` 才会触发。

### 5.4 入口：`app/main.py`

```python
app.include_router(health.router)

@app.get("/", include_in_schema=False)
def root() -> dict[str, str]:
    return {
        "message": f"{settings.app_name} API",
        "docs": "/docs",
        "health": "/healthz",
    }
```

`include_in_schema=False` 表示根路径只是给人看的提示，不放进 OpenAPI 文档。

---

## 6. 如何运行

在项目根目录执行：

```bash
conda activate test
pip install -r requirements.txt
uvicorn app.main:app --reload --port 8000
```

打开：

- Swagger 文档：<http://127.0.0.1:8000/docs>
- 健康检查：<http://127.0.0.1:8000/healthz>
- 根路径：<http://127.0.0.1:8000/>

停止：`Ctrl + C`。

如果不想激活环境，也可以：

```bash
conda run -n test uvicorn app.main:app --reload --port 8000
```

注意：

- 必须在项目根目录运行，否则 `.env` 和 `app` 包可能找不到。
- `--reload` 只用于开发，修改代码后自动重启；生产不用。
- 如果 8000 端口被占用，换一个端口，例如 `--port 8001`。

---

## 7. 验证记录

本模块完成后实际验证结果：

```text
GET /healthz       → 200
{"status": "ok", "app": "MiniMall", "env": "dev"}

GET /              → 200
{"message": "MiniMall API", "docs": "/docs", "health": "/healthz"}

GET /openapi.json  → 路径列表：["/healthz"]
```

生命周期日志也验证过：

```text
应用启动 | name=MiniMall env=dev
应用关闭
```

（在 Windows 某些终端里中文日志可能显示乱码，可以设置 `PYTHONUTF8=1` 后再启动。）

`scripts/smoke_test.py` 是可选工具：它会临时启动一个 uvicorn 进程并请求 `/healthz`，适合不想手动开服务时做一次快速检查。

---

## 8. 本模块的边界

现在还没有：

- 数据库连接和建表
- Redis 缓存
- 用户、商品、订单
- Service 层
- JWT 登录
- Docker 打包

所以 `/healthz` 现在只能证明「FastAPI 进程活着」，还不能证明依赖正常。等数据库模块加入后，它会多检查一项 SQLite；Redis 模块加入后再多检查一项 Redis。

这种「先跑通框架，再逐个挂依赖」的顺序，能让你在出问题时快速定位是哪一层引入的。

---

## 9. 常见坑

1. **在错误的目录启动**：找不到 `app` 包或 `.env`。
2. **把 `.env` 提交到 Git**：里面以后会出现 JWT 密钥等敏感信息。
3. **忘记安装依赖**：`ModuleNotFoundError: fastapi`。
4. **端口被占用**：换端口，或找出占用进程。
5. **以为 `/healthz` 已经检查了数据库**：当前没有，后续才加。
6. **`--reload` 用在生产**：会多起进程、增加开销，仅开发使用。
7. **中文日志乱码**：Windows 控制台编码问题，可设置 `PYTHONUTF8=1`。
8. **直接 `TestClient(app)` 看不到启动日志**：lifespan 没触发，要用上下文管理器。

---

## 10. 自测问题

学完这个模块，试着不看代码回答：

1. Uvicorn 和 FastAPI 分别负责什么？
2. `uvicorn app.main:app` 里的 `app.main:app` 分别指什么？
3. `.env`、环境变量、代码默认值，谁的优先级最高？
4. 为什么 `get_settings()` 要加 `@lru_cache`？
5. `lifespan` 适合放什么代码？为什么不能放在每个请求里？
6. `APIRouter` 解决了什么问题？如果所有路由都写在 `main.py` 会怎样？
7. `/docs` 是哪里来的？为什么新增一个路由后文档会自动更新？
8. 现在访问 `/healthz`，能证明数据库正常吗？为什么？

---

## 11. 动手练习

1. 修改 `.env` 里的 `APP_NAME`，重启应用，观察 `/docs` 标题和 `/healthz` 返回值。
2. 新增一个 `GET /ping` 接口，返回 `{"pong": true}`，确认 Swagger 中自动出现。
3. 把 `LOG_LEVEL` 改成 `DEBUG`，重启，观察日志变化。
4. 故意把 `.env` 里的 `APP_ENV` 改成 `abc`，观察配置校验报错。

---

## 12. 下一个模块：数据库

下一份文档 `docs/02-database.md` 会加入：

- `DATABASE_URL` 配置
- SQLAlchemy `engine`、`SessionLocal`、`Base`
- `get_db` 依赖
- 启动时创建 `data/app.db`
- `/healthz` 增加 SQLite 连通性检查
- 为什么数据库 Session 要「每个请求一个」

先不写用户表和业务表，只把「应用 ↔ 数据库」这条线接通。
