## `logging_config.py`

**函数体**

```py
    level = getattr(logging, settings.log_level.upper(), logging.INFO)
```

这行是核心，拆成三步看：

1. `settings.log_level`：从配置里取出日志级别字符串，比如 `"info"`、`"debug"`。
2. `.upper()`：转成大写，得到 `"INFO"`、`"DEBUG"`。因为 `logging` 模块里的级别常量是大写的（`logging.INFO`、`logging.DEBUG`）。
3. `getattr(logging, "INFO", logging.INFO)`：从 `logging` 模块里按名字取出对应的常量。第三个参数 `logging.INFO` 是默认值：如果配置里写了个不存在或不规范的级别名（比如 `"verbose"`），`getattr` 不会报错，而是返回默认的 `logging.INFO`。

最终 `level` 是一个整数常量，比如 `logging.INFO` 实际值是 `20`。

```py
    logging.basicConfig(
        level=level,
        format="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
        force=True,
    )
```

调用 `logging.basicConfig` 做全局日志配置，四个参数：

- `level=level`：设置日志级别。只有级别不低于该值的日志才会输出。例如设为 `INFO`，则 `DEBUG` 日志会被丢弃。
- `format=...`：日志输出格式模板，各占位符含义：
  - `%(asctime)s`：时间
  - `%(levelname)-8s`：日志级别名，`-8` 表示左对齐占 8 个字符宽度，让各级别（INFO、WARNING、ERROR）上下对齐
  - `%(name)s`：日志记录器名称，通常是模块名，方便看出日志来自哪个文件
  - `%(message)s`：日志正文
  - `|` 是普通分隔符
- `datefmt="%Y-%m-%d %H:%M:%S"`：时间的格式，即 `2026-10-28 14:30:00` 这种形式。
- `force=True`：强制重新配置。`basicConfig` 默认只在第一次调用时生效，如果之前已经配置过（比如被其他库或测试代码配置过），后面的调用会被忽略。`force=True` 会先移除已有的 handler 再重新配置，保证这里的配置一定生效。这也正好配合"应用启动时调用一次"的用法。

**输出效果示例**

配置后日志长这样：

```
2026-10-28 14:30:00 | INFO     | app.main | 应用启动
2026-10-28 14:30:01 | ERROR    | app.db   | 数据库连接失败
```

**小结**

- 这个文件的职责单一：从配置里读日志级别，用统一的格式初始化 `logging`。
- 级别名做了容错：配置不合法时回退到 `INFO`，不会让应用启动失败。
- `force=True` 保证配置生效，适合在 `main.py` 启动阶段调用一次。
- 没有使用 `logging.getLogger(__name__)` 去创建具体 logger，是因为 `basicConfig` 配置的是根 logger，各模块用 `logging.getLogger(__name__)` 拿到的 logger 会自动继承这套配置。



## `main.py`

**生命周期**，指的是一个 FastAPI 应用从**启动**到**关闭**的整个存在过程。`lifespan` 就是一个可以在"启动时"和"关闭时"各执行一段代码的**钩子函数**。

一个服务进程大致经历三段：

```
启动 ──────── 运行中（处理请求） ──────── 关闭
  |                  |                    |
lifespan          （应用跑着）          lifespan
yield 之前                              yield 之后
```

`lifespan` 函数就覆盖了首尾两端：`yield` 之前的代码在**启动时**跑一次，`yield` 之后的代码在**关闭时**跑一次。中间"运行中"这段时间，函数就停在 `yield` 那里不动。

```py
@asynccontextmanager
async def lifespan(app: FastAPI):
    """应用启动与关闭时执行一次，用来管理进程级资源。"""
    logger.info("应用启动 | name=%s env=%s", settings.app_name, settings.app_env)
    init_db()
    yield
    # 执行到这里，函数暂停，把控制权交回 FastAPI，应用正式开始运行、处理请求
    # 这一停可能持续几小时甚至几天，直到应用收到关闭信号。
    engine.dispose()
    logger.info("应用关闭")
```



## `database.py`

ORM 全称 Object-Relational Mapping，**对象关系映射**。作用是**把数据库表和 Python 类对应起来**，让你用操作对象的方式操作数据库，不用手写 SQL。

==一个推荐学习视频==：[为什么不建议直接在 Python 代码里写 sql 语句 | orm | sqlmodel_哔哩哔哩_bilibili](https://www.bilibili.com/video/BV18iEJzNECT/?spm_id_from=333.337.search-card.all.click&vd_source=b536035e35f8eadea1c817dab7b7e892)

对应关系大致是：

| 数据库概念 | ORM 概念             |
| :--------- | :------------------- |
| 表         | Python 类            |
| 表的一行   | 类的一个实例（对象） |
| 表的一列   | 类的属性             |
| 列的类型   | 属性类型注解         |

举个例子，一个 `User` 模型大致长这样：

```py
class User(Base):
    __tablename__ = "users"
    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str]
```

有了它，你就可以写：

```py
user = User(name="张三")   # 相当于准备插入一行
db.add(user)
db.commit()                # 真正执行 INSERT

users = db.query(User).all()   # 相当于 SELECT * FROM users
```

SQLAlchemy 负责把你的对象操作翻译成 SQL 发给数据库，再把结果翻译回对象。好处是代码更贴近业务、少写重复 SQL、换数据库时改动小。



```py
def create_user(db: Session = Depends(get_db)):
    user = User(name="张三")
    db.add(user)
    db.commit()      # 业务里显式提交
    db.refresh(user)
    return user
```

`get_db` 只负责"**创建、回滚、关闭**"，**不负责 commit**。提交由业务代码决定



```py
Base.metadata.create_all(bind=engine)
```

遍历 `metadata` 里登记的所有表，在 `engine` 指向的数据库里创建它们。

几个关键特性：

- **只建不存在的表**。对已存在的表会跳过，不会报错，也不会改动它。所以可以每次启动都执行，是幂等的。
- **不会修改已有表结构**。如果你给模型加了一列，`create_all` 不会给已存在的表 `ALTER TABLE` 加列。它只负责"从无到有"。字段变更、删除列这类结构演进要靠数据库迁移工具（Alembic）。这是初学者最容易踩的坑。
- **不处理删表**。删掉的模型对应的旧表会留在数据库里。

所以 `create_all` 适合开发初期、或者表结构稳定的小项目；正式项目一般用 Alembic 管理迁移。



串起来：

```
Base（基类）
  └─ app.models 里的各模型继承 Base
        └─ 定义时自动登记到 Base.metadata

init_db（启动时，lifespan 里调用一次）
  ├─ import app.models    把模型加载进来、完成登记
  ├─ Base.metadata.create_all   按登记册建表
  └─ 主动连接一次              确保库文件存在、验证可用

get_db（每个请求）
  ├─ SessionLocal()  创建会话
  ├─ yield           交给路由用
  ├─ 异常 rollback
  └─ finally close   归还连接
```



## `security.py`

`jwt.decode` 做三件事：

1. **验证签名**：用同一个密钥重新计算签名，和 token 里的签名比对。对不上说明 token 被篡改或密钥不对，直接抛异常。
2. **验证时间**：检查 `exp` 是否已过期（默认校验），过期抛 `ExpiredSignatureError`。也会校验 `nbf`（生效时间）和 `iat` 的合理性。
3. **返回 payload**：校验全过，返回解码后的字典，即 `{"sub": "...", "iat": ..., "exp": ...}`。

它只负责"验证并解出 payload"，**不负责**：

- 检查用户是否还存在、是否被禁用。要拿 `sub` 里的 id 去查数据库确认。
- 捕获异常。token 过期、格式错误、签名不对都会抛异常（`ExpiredSignatureError`、`InvalidTokenError` 等），需要上层（通常是依赖函数或异常处理器）捕获并转成 401。
- 校验 `aud`（受众）、`iss`（签发者）等，这里 payload 里也没放这些字段，单服务场景一般够用。



四个函数串起来：

```
注册：明文密码 → hash_password() → 存 hashed_password
登录：按 username 查 User
      → verify_password(输入的密码, user.hashed_password)
      → 通过则 create_access_token(user.id) → 返回给客户端
请求：客户端带 token
      → decode_access_token(token) → 得到 {"sub": "3", ...}
      → 用 sub 查数据库确认用户 → 放行
```



注意：

1. **哈希和 JWT 是两套独立的机制**。密码哈希保护"存储的密码"，JWT 保护"会话凭证"，密钥和算法互不相干，不要混为一谈。
2. **密钥管理**：`jwt_secret` 泄露等于鉴权失效；换密钥会导致所有已签发 token 失效，需要权衡。
3. **token 无法主动撤销**。JWT 是**无状态**的，签发后在过期前一直有效。要实现"登出即失效""改密后旧 token 失效"，需要额外机制，比如黑名单、token 版本号、或把过期时间设短配合刷新 token。
4. **`exp` 要短**。access token 一般设 15~60 分钟，泄露后的风险窗口才可控。
5. **异常处理必须补上**。`decode_access_token` 会抛异常，实际项目里一定有一层把它转成 401 响应的代码，否则 token 过期会让请求直接 500。



## `deps.py`

**Bearer Token（译为 “持有者令牌”）**是一种 **HTTP 协议下的轻量级鉴权凭证**，本质是一串无意义的字符串（通常由字母、数字、特殊符号组成），由服务器在用户首次认证（如输入账号密码、扫码登录）后生成并返回给客户端（如浏览器、App）。

“Bearer”（持有者）的核心含义是：**谁持有这串令牌，服务器就认为谁是合法用户**，无需再验证令牌持有者的身份细节（如 “你是谁”），只需验证令牌本身的有效性（如 “令牌是否真实、是否过期”）。

底层原理是这样的：当客户端发送 HTTP 请求时，可以在请求头部中添加 "Authorization" 字段来传递访问令牌。**"Bearer" 是一种认证方案**（authentication scheme）的名称，用于指示后面的令牌是访问令牌。

请求头格式固定：

```http
Authorization: Bearer <你的令牌字符串>
```

注意区分：

- **Bearer Token**：是一种 “鉴权方案”（定义了 “如何用令牌鉴权” 的规则）；
- **JWT**：是 Bearer Token 的一种常见**数据格式**（将用户信息、过期时间等用 JSON 结构存储并加密，便于服务器解析）



`get_current_user` 是一个 **FastAPI 依赖函数**：任何路由只要声明依赖它，FastAPI 就会在调用路由前先执行它。它做四件事：

1. 从请求头取出 token（靠 `bearer_scheme`）
2. 验证 token 并解出用户 id
3. 按 id 查数据库确认用户存在
4. 返回 `User` 对象，或抛 401

路由里拿到的是"已认证的用户"，不用再关心 token 怎么解析。

**函数签名与参数注入：**

```py
def get_current_user(
    credentials: Annotated[
        HTTPAuthorizationCredentials | None, Depends(bearer_scheme)
    ],
    db: Annotated[Session, Depends(get_db)],
) -> User:
```

两个参数都是依赖注入：

- `credentials`：由 `bearer_scheme` 从 `Authorization` 头提取。
- `db`：由 `get_db` 提供，每个请求一个 Session。

**提前构造 unauthorized 异常**

```py
unauthorized = HTTPException(
    status_code=status.HTTP_401_UNAUTHORIZED,
    detail="未登录或 Token 无效",
    headers={"WWW-Authenticate": "Bearer"},
)
```

**判空**

```py
if credentials is None:
    raise unauthorized
```

请求头里没有 `Authorization`，或格式不是 `Bearer ...`，`bearer_scheme` 返回 `None`。直接 401。

这一步能存在，正是因为前面设了 `auto_error=False`。如果是默认的 `True`，请求根本进不到这个函数，框架已经自动报错了，你就失去了统一控制错误响应的机会。

**解析 token 并取用户 id**

```py
try:
    payload = decode_access_token(credentials.credentials)
    user_id = int(payload["sub"])
except (jwt.PyJWTError, KeyError, TypeError, ValueError):
    raise unauthorized
```

`credentials.credentials` 是 token 字符串（Bearer 后面那段）。两行代码都可能失败：

**`decode_access_token(...)` 可能抛的异常**，都归在 `jwt.PyJWTError` 这个基类下：

| 具体异常                | 触发场景                           |
| :---------------------- | :--------------------------------- |
| `ExpiredSignatureError` | token 的 `exp` 已过期              |
| `InvalidSignatureError` | 签名对不上，token 被篡改或密钥不对 |
| `DecodeError`           | token 格式不是合法 JWT             |
| `InvalidAlgorithmError` | 算法不匹配                         |

捕获基类 `PyJWTError` 就能一次覆盖全部，不用逐个列。

**`int(payload["sub"])` 可能抛的异常**：

- `KeyError`：payload 里根本没有 `"sub"` 字段（伪造的 token 或签发时漏放）。
- `TypeError`：`sub` 是 `None` 或不支持转 int 的类型，`int(None)` 抛这个。
- `ValueError`：`sub` 不是数字字符串，比如 `int("abc")`。

`sub` 在 JWT 里按规范是字符串，而数据库主键是整数，所以必须 `int()` 转换。转换本身也是校验：如果不是合法数字，说明 token 不可信。

四种异常统一转成同一个 401，不向客户端区分是过期还是格式错。

**查数据库确认用户：**

```py
user = db.get(User, user_id)
if user is None:
    raise unauthorized

return user
```

**为什么 token 有效还要查库**：JWT 是无状态的，签发后在过期前一直有效。但用户可能已经被删除、被禁用。光验证签名不够，必须以数据库为准。这一步是"token 说你是 3 号用户"到"3 号用户确实存在"的确认。

`user is None` 就 401，同样不区分"用户不存在"和"token 无效"，保持响应统一。

`return user` 把 ORM 对象交给 FastAPI，注入到路由参数。

**`CurrentUser` 类型别名**

```py
CurrentUser = Annotated[User, Depends(get_current_user)]
```

这一行定义了一个**可复用的类型别名**，含义是"一个 `User`，通过 `get_current_user` 依赖获取"。

之后所有需要登录的路由，只写：

```python
@router.get("/me")
def read_me(user: CurrentUser):
    return user
```

不用每个路由都写 `user: User = Depends(get_current_user)`。

**完整执行流程：**

```
请求进入
  → bearer_scheme 解析 Authorization 头
       ├─ 没有/格式错 → credentials = None → 401
       └─ 取到 token 字符串
  → decode_access_token 验证签名和有效期
       ├─ 失败 → 401
       └─ 得到 payload
  → int(payload["sub"]) 取用户 id
       ├─ 缺字段/非数字 → 401
       └─ 得到 user_id
  → db.get(User, user_id) 查库
       ├─ 查不到 → 401
       └─ 得到 User
  → 返回 User，注入路由参数
```



### `Depends()`何时进行调用？

```py
def get_current_user(
    credentials: Annotated[
        HTTPAuthorizationCredentials | None, Depends(bearer_scheme)
    ],
    db: Annotated[Session, Depends(get_db)],
) -> User:
```

FastAPI 在**每次请求**进入时，会在调用路由函数之前，先把这棵"依赖树"解析完。规则是：**先解决子依赖，再解决父依赖，最后调用路由函数**。

对这段代码，依赖树长这样：

```
get_current_user
  ├─ bearer_scheme     （提取 token）
  └─ get_db            （创建 Session）
        │
        ▼
     路由函数
```

执行顺序是**后序遍历**（深度优先，从叶子到根）：

```
1. bearer_scheme()   → 得到 credentials（或 None）
2. get_db()          → 创建 db，执行到 yield 暂停，把 db 交出去
3. get_current_user(credentials, db)  → 执行函数体，返回 User 或抛 401
4. 路由函数(user=User)                → 这时才真正执行业务逻辑
```

所以，当你写：

```py
@router.get("/me")
def read_me(user: CurrentUser):
    return user
```

请求进来时，`read_me` 的函数体**还没开始执行**，`get_db` 和 `bearer_scheme` 已经被调用了，`get_current_user` 也已经跑完并返回了 `User`。`read_me` 拿到的是现成的结果。

以一次带 token 的 `GET /me` 为例：

```
客户端请求
   │
   ▼
路由匹配到 read_me，发现依赖 CurrentUser
   │
   ▼
解析依赖树（后序）
   ├─ 调 bearer_scheme
   │     → 解析 Authorization 头
   │     → 返回 HTTPAuthorizationCredentials 或 None
   │
   ├─ 调 get_db
   │     → SessionLocal() 创建 db
   │     → 执行到 yield db，暂停，把 db 交给上层
   │     （注意：此时 db 还没关闭）
   │
   ├─ 调 get_current_user(credentials, db)
   │     ├─ credentials 为 None → raise 401，到此中断
   │     ├─ decode_access_token 失败 → raise 401
   │     ├─ db.get(User, id) 查不到 → raise 401
   │     └─ 成功 → return user
   │
   ▼
调用 read_me(user=user)
   │
   ▼
read_me 返回结果
   │
   ▼
逆序执行生成器依赖的收尾代码（yield 之后）
   └─ get_db 恢复执行：finally → db.close()
   │
   ▼
返回响应给客户端
```



## `users.py`

```py
@router.get("/me", response_model=UserOut, summary="当前用户")
```

**`response_model=UserOut`**：声明**响应模型**。这是 FastAPI 很重要的机制，作用有三：

1. **序列化**：函数返回的 `UserOut` 对象（或任意兼容对象）会按 `UserOut` 的字段定义转成 JSON。
2. **过滤字段**：`UserOut` 里没定义的字段**不会输出**。即使你返回一个带 `hashed_password` 的对象，响应里也不会出现它。这是防泄露的第二道保险。
3. **文档**：`/docs` 里会展示这个接口的响应结构，客户端能直接看到有哪些字段、什么类型。



```py
def read_me(current_user: CurrentUser) -> UserOut:
```

**`current_user: CurrentUser`**：这是**依赖注入**。`CurrentUser` 展开是 `Annotated[User, Depends(get_current_user)]`，意思是：

> 调用这个函数前，先执行 `get_current_user` 依赖链，把得到的 `User` 对象注入到 `current_user` 参数。

于是 FastAPI 在真正调用 `read_me` 之前，会自动完成：

```
解析 Authorization 头 → 验证 JWT → 取用户 id → 查数据库 → 得到 User
```

任何一步失败（没 token、token 无效、用户不存在），`get_current_user` 抛 401，**`read_me` 根本不会执行**。所以能进入函数体，就意味着"已经有一个通过认证的用户"。



## `auth.py`

**`register`：注册接口**

```
POST /api/v1/auth/register
  │  body: {"username": "...", "password": "..."}
  ▼
RegisterRequest 校验（失败 → 422）
  │
  ▼
get_db 创建 Session
  │
  ▼
auth_service.register_user
  ├─ 重名 → UsernameAlreadyExistsError → 409
  ├─ 哈希密码
  ├─ 插入 + commit（并发兜底）
  └─ 返回 User
  │
  ▼
UserOut.model_validate(user)  → 过滤敏感字段
  │
  ▼
201 Created + UserOut JSON
```

**`login`：登录接口**

```
POST /api/v1/auth/login
  │  body: {"username": "...", "password": "..."}
  ▼
LoginRequest 校验（失败 → 422）
  │
  ▼
get_db 创建 Session
  │
  ▼
auth_service.login_user
  ├─ 查用户 + 校验密码
  ├─ 失败 → InvalidCredentialsError → 401
  └─ 成功 → 签发 JWT
  │
  ▼
get_settings 读过期时间
  │
  ▼
TokenResponse(access_token, expires_in=分钟×60)
  │
  ▼
200 OK + TokenResponse JSON
```

