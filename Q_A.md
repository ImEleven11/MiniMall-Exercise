# Session、JWT 与 deps 问答记录

> 记录日期：2026-10-29
> 对应阶段：用户与 JWT 登录模块完成后

## 1. 以注册链路为例，`Depends(get_db)` 创建 Session，这里的 Session 是什么？有什么用？有什么性质？

`Session` 是 SQLAlchemy ORM 的核心，你可以把它理解为你与数据库进行**所有交互的“工作台”或“暂存区”**。它并非数据库连接本身，而是连接之上的一层智能管理层。

想象你在处理一批数据：

- **数据库**是仓库。
- `Engine`是通往仓库的**大门**。
- `Session`就是你在大门后设立的**工作台**。

当你需要查询或修改数据时，不是直接冲进仓库，而是在`Session`这个工作台上操作。`Session`会记录你对所有对象所做的修改（新增、修改、删除），这些修改最初只存在于内存中。只有当你明确告诉`Session`“保存”（`commit()`）时，它才会打开大门，把所有积攒的改动高效地、在一个事务里一次性提交给数据库。

Session的核心作用：

1. **身份映射 (Identity Map)**：在同一个`Session`生命周期内，对同一条数据库记录，它只会创建**一个**Python对象。无论你查询多少次，拿到的都是同一个对象，这保证了数据的一致性，避免了混乱。
2. **工作单元 (Unit of Work)**：这是`Session`的核心机制。它会自动跟踪你加载或关联的所有对象的状态变化。在需要时（例如查询前或提交时），它会将所有待处理的变更（`INSERT`, `UPDATE`, `DELETE`）**按正确顺序整理好，一次性批量发送**给数据库，以最小化数据库往返次数。
3. **事务管理**：`Session`的完整生命周期通常封装在一个数据库事务中。你的一系列操作要么通过`commit()`全部成功，要么通过`rollback()`全部撤销，保证了操作的原子性。

```text
请求进入
  → FastAPI 解析 Depends(get_db)
  → SessionLocal() 创建 Session（尚未借连接）
  → yield 交给路由 / Service
  → 查询、写入、commit
  → 正常：finally → close()
  → 异常：rollback() → raise → finally → close()
```



## 2. JWT 是一直存放在客户端的，需要校验的时候就拿出来，我的理解对吗？

大方向对，更准确的说法是：JWT 由客户端保存；每次访问受保护接口时，客户端主动把它放进请求头；服务端不保存 JWT，只验证本次请求头里的 Token。

```text
登录成功
  → 服务端返回 JWT
  → 客户端保存

访问受保护接口
  → 客户端发送：
     Authorization: Bearer eyJ...
  → 服务端从请求头取出 Token
  → 验签 + 检查 exp
  → 取出 payload["sub"] 得到 user_id
  → 查数据库得到 User
```

服务端不是去某个存储里「拿出 JWT」，而是读取这一次请求的 Header。服务端是无状态的，不记录谁登录过，只靠签名判断 Token 是否可信。

## 3. JWT 流的部分：「`user.id` → `create_access_token`（签名）」，这里 `create_access_token` 返回了什么？就是 JWT 吗？

是的，它返回一个字符串，这个字符串就是 JWT 本身。

```python
def create_access_token(user_id: int) -> str:
    payload = {
        "sub": str(user_id),
        "iat": now,
        "exp": now + timedelta(minutes=60),
    }
    return jwt.encode(payload, settings.jwt_secret, algorithm="HS256")
```

`jwt.encode()` 会把 payload 序列化成 JSON，进行 Base64URL 编码，再和 header 一起用密钥签名，最后拼成三段：

```text
header.payload.signature
```

这三段整体就是 access token。`TokenResponse` 里的 `access_token` 放的就是这个字符串，客户端后续把它放进 `Authorization` 请求头。

容易混淆的地方：

- `create_access_token` 返回的是编码后的字符串，不是 payload 字典。
- `decode_access_token` 返回的才是 payload 字典。
- `user.id` 被放进 payload 的 `sub` 字段，不是直接变成 Token。
- `expires_in=3600` 是给客户端看的便利字段，真正的过期时间在 Token 内部的 `exp` 里。
- 签名不是加密，payload 可以被任何人解码，只是修改后签名会失效。



## 4. `deps.py` 在链路的哪些部分起作用？

目前只有 `GET /api/v1/users/me` 会经过 `deps.py`。注册、登录、健康检查都不经过。


| 链路                    | 是否经过 `deps.py` | 原因                |
| --------------------- | -------------- | ----------------- |
| `POST /auth/register` | 否              | 公开接口，只需要 `get_db` |
| `POST /auth/login`    | 否              | 公开接口，只需要 `get_db` |
| `GET /users/me`       | 是              | 需要从 Token 解析当前用户  |
| `GET /healthz`        | 否              | 探活，不需要用户          |
| 未来的下单、购物车             | 是              | 复用 `CurrentUser`  |


注意：`get_db` 定义在 `database.py`，不在 `deps.py`。注册和登录直接依赖 `database.get_db`。

`/users/me` 的依赖树：

```text
routers/users.py 的 read_me()
  └── current_user: CurrentUser
        └── Depends(get_current_user)          ← deps.py
              ├── Depends(bearer_scheme)       ← 取 Authorization 头
              ├── Depends(get_db)              ← database.py
              ├── decode_access_token(token)   ← security.py
              └── db.get(User, user_id)        ← models.py → SQLite
```

FastAPI 会在进入 `read_me()` 之前先解析 `get_current_user`：取 Token、创建 Session、验签、查用户。任何一步失败都直接返回 401，`read_me()` 不会执行；全部成功后才把 User 注入路由函数。

把 `get_current_user` 单独放在 `deps.py`，是为了让未来的受保护接口直接复用 `current_user: CurrentUser`，让 Router 只关心 HTTP 参数和业务调用，也让 Token 解析逻辑可以独立测试。

`deps.py` 不负责签发 Token，不负责密码校验，不负责创建数据库 Session，也不负责业务权限。它只负责「从请求中准备当前用户」这一件事。