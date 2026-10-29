# 03 · 用户与 JWT 登录模块

> 所属阶段：Phase 1
> 完成日期：2026-10-27
> 对应代码：`app/models.py`、`app/schemas.py`、`app/security.py`、`app/exceptions.py`、`app/deps.py`、`app/services/auth_service.py`、`app/routers/auth.py`、`app/routers/users.py`

---

## 1. 这个模块做了什么

第一张业务表、第一组业务接口、第一套鉴权流程：

1. 创建 `users` 表。
2. 注册接口：校验参数、哈希密码、写入数据库。
3. 登录接口：校验密码、签发 JWT。
4. `get_current_user` 依赖：解析 Bearer Token、查用户。
5. `GET /api/v1/users/me`：受保护接口。
6. 统一的业务异常处理。

现在项目第一次有了「业务链路」：

```text
注册 → 登录 → 拿到 Token → 带 Token 访问受保护接口
```

---

## 2. 文件变化


| 文件                             | 职责                         |
| ------------------------------ | -------------------------- |
| `app/models.py`                | `User` ORM 模型              |
| `app/schemas.py`               | 注册/登录请求、用户响应、Token 响应      |
| `app/security.py`              | 密码哈希、JWT 签发/解码             |
| `app/exceptions.py`            | 业务异常基类与具体异常                |
| `app/deps.py`                  | `get_current_user` 依赖      |
| `app/services/auth_service.py` | 注册、登录的业务逻辑                 |
| `app/routers/auth.py`          | `/register`、`/login`       |
| `app/routers/users.py`         | `/users/me`                |
| `app/main.py`                  | 注册路由、注册异常处理器               |
| `app/database.py`              | 启动时导入模型，让 `create_all` 能建表 |
| `app/config.py`                | 增加 JWT 配置                  |
| `.env` / `.env.example`        | 增加 JWT 密钥与有效期              |


---



## 3. users 表

```text
users
├── id               INTEGER 主键，自增
├── username         VARCHAR(32) 唯一，非空
├── hashed_password  VARCHAR(255) 非空
└── created_at       DATETIME 服务器默认值
```

对应模型：

```python
class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    username: Mapped[str] = mapped_column(
        String(32), unique=True, index=True, nullable=False
    )
    hashed_password: Mapped[str] = mapped_column(String(255), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
```

`init_db()` 里新增了一行关键代码：

```python
import app.models  # noqa: F401
Base.metadata.create_all(bind=engine)
```

只有被导入的模型类才会注册到 `Base.metadata`。如果不导入，`create_all()` 不知道 `User` 存在，`users` 表就不会创建。

---



## 4. 密码是怎么存的



### 4.1 绝不存明文

注册时，数据库里保存的是 argon2 哈希：

```text
alice  →  $argon2id$v=19$m=65536,t=3,p=4$...
```

哈希的特点：

- **单向**：不能从哈希反推出原密码。
- **带盐**：同一个密码两次哈希，结果完全不同，防止彩虹表。
- **校验方式**：不是解密，而是把用户输入的密码再哈希，然后比对。

```python
hashed = hash_password("secret123")
verify_password("secret123", hashed)  # True
verify_password("wrong", hashed)      # False
```



### 4.2 为什么不用 MD5 / SHA256

普通哈希计算太快，攻击者可以每秒尝试数十亿次。argon2 故意设计得慢且占内存，专门用于密码存储。

### 4.3 响应里为什么没有密码

`UserOut` 只包含：

```python
id, username, created_at
```

`hashed_password` 不在响应模型里，所以即使 ORM 对象有这个属性，也不会被序列化出去。

---



## 5. JWT 在本项目里怎么用



### 5.1 JWT 的三段

```text
eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9 . eyJzdWIiOiIxIiwiZXhwIjoxNzkzMDgwMDQ4fQ . VdJUbC0d...
└──────────── header ────────────────┘   └──────────── payload ───────────────┘   └─ signature ─┘
```


| 部分        | 内容                  | 是否可读 |
| --------- | ------------------- | ---- |
| header    | 算法，例如 HS256         | 可解码  |
| payload   | 业务数据，例如 `sub`、`exp` | 可解码  |
| signature | 用密钥对前两部分签名          | 不可伪造 |


**JWT 不是加密**。任何人都能解码 payload，只是改内容后签名会对不上。所以：

- 不放密码、手机号等敏感信息。
- 只放 `user_id` 这种不敏感、够用的信息。



### 5.2 本项目放了什么

```python
payload = {
    "sub": str(user.id),   # subject：用户 ID
    "iat": now,            # issued at：签发时间
    "exp": now + timedelta(minutes=60),
}
```

`sub` 按规范使用字符串；`exp` 由 PyJWT 在解码时自动校验。

### 5.3 签发

```python
jwt.encode(payload, settings.jwt_secret, algorithm="HS256")
```

`JWT_SECRET` 是签名密钥，来自 `.env`：

```text
JWT_SECRET=<用下面的命令生成>
```

生成方式：

```bash
python -c "import secrets; print(secrets.token_urlsafe(48))"
```

配置里要求至少 32 个字符，缺失或太短时应用启动失败。这是有意的「快速失败」。

### 5.4 携带

登录成功后，客户端保存 `access_token`，之后请求头带上：

```http
Authorization: Bearer eyJhbGciOi...
```

注意 `Bearer` 和 Token 之间有一个空格。

### 5.5 校验

`get_current_user` 是整条鉴权链路的核心：

```text
请求进入
  → HTTPBearer 从 Authorization 头取出 token
  → decode_access_token：验签、检查 exp
  → 读取 payload["sub"] 得到 user_id
  → 查数据库得到 User
  → 注入到路由函数参数
```

任何一步失败都返回 401，并带 `WWW-Authenticate: Bearer` 响应头。

### 5.6 为什么拿到 user_id 后还要查数据库

因为 Token 里的信息是「签发那一刻」的快照。用户可能被删除、被禁用，或者权限发生变化。每次查库能拿到最新状态，代价是一次主键查询，这个成本很低。

### 5.7 本模块没做的 JWT 功能

- Refresh Token
- 登出黑名单
- 多设备管理
- 角色权限
- 密码重置

这些都不影响先理解「登录 → 签发 → 携带 → 校验」这条主链。

---



## 6. 三条请求链路



### 6.1 注册

```text
POST /api/v1/auth/register
  → Pydantic 校验 username / password
  → get_db 创建 Session
  → auth_service.register_user(db, username, password)
      → 查询用户名是否已存在
         存在 → 抛 UsernameAlreadyExistsError
      → hash_password
      → 创建 User，db.add
      → db.commit
         唯一索引冲突 → rollback，抛 UsernameAlreadyExistsError
      → db.refresh 读取 created_at
  → UserOut 序列化（不含密码）
  → 201
```



### 6.2 登录

```text
POST /api/v1/auth/login
  → Pydantic 校验
  → auth_service.login_user(db, username, password)
      → 按用户名查 User
      → 不存在或 verify_password 失败 → InvalidCredentialsError
      → create_access_token(user.id)
  → Router 组装 TokenResponse
  → 200
```



### 6.3 访问受保护接口

```text
GET /api/v1/users/me
  → 依赖 HTTPBearer 取 Token
  → 依赖 get_db 创建 Session
  → get_current_user
      → decode_access_token
      → db.get(User, user_id)
  → read_me(current_user)
  → UserOut
  → 200
```

依赖是嵌套的：`get_current_user` 自己又依赖 `get_db` 和 `bearer_scheme`。FastAPI 会按依赖链依次解析。

---



## 7. 分层上的几个决定



### 7.1 Service 不依赖 FastAPI

`auth_service.py` 只接收：

```python
def register_user(db: Session, username: str, password: str) -> User
def login_user(db: Session, username: str, password: str) -> str
```

它不导入 `HTTPException`，也不导入 `schemas`。这样业务逻辑可以被测试、被其他入口复用。

### 7.2 业务异常与 HTTP 解耦

`app/exceptions.py`：

```python
class AppError(Exception):
    status_code = 400
    code = "APP_ERROR"
    message = "请求处理失败"
```

具体异常：

- `UsernameAlreadyExistsError` → 409 / `USERNAME_EXISTS`
- `InvalidCredentialsError` → 401 / `INVALID_CREDENTIALS`

`main.py` 里统一翻译：

```python
@app.exception_handler(AppError)
async def handle_app_error(_request, exc):
    return JSONResponse(
        status_code=exc.status_code,
        content={"code": exc.code, "message": exc.message},
    )
```

这样 Service 只表达「业务上出了什么问题」，Router 和处理器决定「用什么 HTTP 状态码」。

### 7.3 谁负责 commit

注册由 `auth_service.register_user` 提交事务。

原因：一次业务操作可能涉及多步数据库写入，事务边界应该由「懂业务的那一层」决定，而不是让每个 Repository 或 Router 各自决定。

### 7.4 错误响应目前有两种形状


| 来源                             | 形状                                  |
| ------------------------------ | ----------------------------------- |
| 业务异常                           | `{"code": "...", "message": "..."}` |
| FastAPI `HTTPException`（如鉴权失败） | `{"detail": "..."}`                 |
| 参数校验失败                         | FastAPI 默认 422 结构                   |


这是当前阶段的简化。后续可以加一个统一的校验异常处理器，把三种形状收敛。先看懂各自由谁产生，比一开始就统一更重要。

---



## 8. 实际验证结果

使用 TestClient 跑完整链路，结果如下：


| 操作                       | 结果                                                   |
| ------------------------ | ---------------------------------------------------- |
| 注册新用户                    | 201，返回 id / username / created_at，没有密码字段             |
| 再次注册同名用户                 | 409 `{"code": "USERNAME_EXISTS", ...}`               |
| 错误密码登录                   | 401 `{"code": "INVALID_CREDENTIALS", ...}`           |
| 正确密码登录                   | 200，返回 `access_token`、`token_type`、`expires_in=3600` |
| 不带 Token 访问 `/users/me`  | 401                                                  |
| 带正确 Token 访问 `/users/me` | 200，返回当前用户                                           |
| 带伪造 Token 访问 `/users/me` | 401                                                  |


数据库检查：

```text
users 表已创建
hashed_password 以 $argon2id$ 开头
```

OpenAPI 路径：

```text
/api/v1/auth/login
/api/v1/auth/register
/api/v1/users/me
/healthz
```

---



## 9. 在 Swagger 里手动测试

1. 打开 `/docs`。
2. 展开 `POST /api/v1/auth/register`，点 **Try it out**，填：
  ```json
   {"username": "alice", "password": "secret123"}
  ```
3. 展开 `POST /api/v1/auth/login`，用同样的账号登录。
4. 复制响应里的 `access_token`。
5. 点击页面右上角的 **Authorize**，粘贴 Token（只粘贴 Token 本身，不要带 `Bearer` ）。
6. 调用 `GET /api/v1/users/me`，应该返回 200。
7. 点 **Authorize → Logout** 后再次调用，应该返回 401。

---

