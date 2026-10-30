# 05 · Redis 商品缓存模块

> 所属阶段：Phase 3
> 完成日期：2026-10-30
> 对应代码：`app/cache.py`、`app/services/product_service.py`、`app/routers/health.py`、`app/main.py`、`app/config.py`

---

## 1. 这个模块做了什么

给商品详情加上 Redis 缓存：

1. 新增 `app/cache.py`，封装 Redis 连接和商品缓存的读、写、删。
2. 商品详情改为 Cache-Aside：先查 Redis，未命中再查 SQLite，然后回填缓存。
3. 缓存 TTL 设为 60 秒。
4. 缓存命中/未命中写日志，方便观察。
5. `/healthz` 增加 Redis 检查。
6. Redis 挂掉时，商品详情降级查数据库，应用不崩溃。

**这一阶段没有商品写接口**，所以还没有真正触发「商品变更后删除缓存」。下一步做订单扣库存时，删除缓存会变成必需动作。

---

## 2. 为什么要加缓存

商品详情是典型的「读多写少」数据：

```text
用户频繁查看商品 → 同样的查询重复执行
商品信息偶尔变化 → 不需要每次都查数据库
```

缓存的作用不是让数据更正确，而是：

- 减少 SQLite 查询。
- 降低响应时间。
- 在数据库压力大时挡一部分请求。

但代价是：**Redis 和数据库之间可能出现短暂不一致**。所以必须明确谁是真相。

```text
SQLite：商品数据的唯一真相
Redis：商品数据的副本，随时可以删除、可以重建
```

---

## 3. Cache-Aside 模式

本项目采用最常用的 Cache-Aside（旁路缓存）：

```text
读：
  1. 查 Redis
  2. 命中 → 直接返回
  3. 未命中 → 查数据库
  4. 把结果写入 Redis
  5. 返回

写：
  1. 更新数据库
  2. 删除 Redis 缓存（不是更新缓存）
```

为什么写操作是删除缓存，而不是更新缓存？

- 更新缓存需要知道缓存里存的是什么结构。
- 并发写时，两个请求可能把旧值写回缓存。
- 删除最简单：下次读自然回源，重新生成最新值。

---

## 4. 环境说明

本机使用**原生 Redis**：

```bash
redis-cli ping
# PONG
```

- 地址：`redis://127.0.0.1:6379/0`
- 版本：Redis 8.4.0
- 连接配置在 `.env`：

  ```text
  REDIS_URL=redis://127.0.0.1:6379/0
  REDIS_PREFIX=minimall:dev
  ```

如果换成 Docker Redis，只需要改 `REDIS_URL`：

```text
应用在宿主机：redis://127.0.0.1:6379/0
应用也在容器：redis://redis:6379/0
```

业务代码不需要改。

---

## 5. 文件变化

| 文件 | 变化 |
| --- | --- |
| `app/cache.py` | 新增：Redis 客户端、缓存读写删、健康检查 |
| `app/services/product_service.py` | 商品详情改为 Cache-Aside，并记录命中/未命中 |
| `app/routers/health.py` | 增加 Redis 组件检查 |
| `app/main.py` | 启动时检查 Redis，关闭时释放连接 |
| `app/config.py` | 增加 `redis_url`、`redis_prefix` |
| `.env` / `.env.example` | 增加 Redis 配置 |
| `requirements.txt` | 增加 `redis==8.1.0` |

---

## 6. 缓存 Key 设计

```text
key:   minimall:dev:product:1
value: {"id": 1, "name": "机械键盘", ...}
TTL:   60 秒
```

Key 结构：

```text
{redis_prefix}:product:{product_id}
```

为什么加前缀？

- 同一个 Redis 可能被多个项目共用。
- `minimall:dev` 能区分项目和環境，避免和别的 key 冲突。
- 以后切到 `minimall:prod` 不会互相污染。

为什么设 TTL？

- 防止缓存永久不一致。
- 即使某次删除缓存失败，最多 60 秒后也会自动过期。
- 这是缓存和数据库一致性的最后一道保险。

为什么只缓存详情，不缓存列表？

- 列表带分页、关键词，组合很多，key 设计更复杂。
- 列表数据变化更频繁。
- 先缓存一个最简单的场景，把机制讲清楚。

---

## 7. 请求链路

### 7.1 第一次请求：未命中

```text
GET /api/v1/products/1
  → routers/products.py
  → Depends(get_db) 创建 Session
  → product_service.get_product(db, 1)
      → cache.get_product_cache(1)
          → Redis GET minimall:dev:product:1
          → 不存在，返回 None
      → 记录日志：缓存未命中，查询数据库
      → db.get(Product, 1)
      → 组装可 JSON 序列化的 dict
      → cache.set_product_cache(1, data)
          → Redis SET key value EX 60
      → 返回 dict
  → ProductOut.model_validate(dict)
  → 200 JSON
```

### 7.2 第二次请求：命中

```text
GET /api/v1/products/1
  → product_service.get_product(db, 1)
      → cache.get_product_cache(1)
          → Redis GET 命中
          → json.loads 得到 dict
      → 记录日志：命中缓存
      → 直接返回 dict
  → ProductOut.model_validate(dict)
  → 200 JSON
```

注意：命中缓存时**不会查 SQLite**，但仍然创建了数据库 Session（因为路由声明了 `Depends(get_db)`）。这是当前实现的取舍：Session 创建成本很低，连接是按需借用的。

实际日志：

```text
商品详情缓存未命中，查询数据库 | product_id=1
商品详情命中缓存 | product_id=1
```

---

## 8. 为什么缓存的不是 ORM 对象

SQLAlchemy 的 `Product` 对象不能直接 `json.dumps`：

- 它包含数据库连接、状态、关系等内部结构。
- `created_at` 是 `datetime`，不是 JSON 原生类型。

所以 Service 在写缓存前把它转成普通 dict：

```python
data = {
    "id": product.id,
    "name": product.name,
    "description": product.description,
    "price_cents": product.price_cents,
    "stock": product.stock,
    "is_active": product.is_active,
    "created_at": product.created_at.isoformat(),
    "updated_at": product.updated_at.isoformat(),
}
```

然后：

```python
json.dumps(data, ensure_ascii=False)
```

读出来时：

```python
data = json.loads(raw)
return data
```

Router 仍然执行：

```python
ProductOut.model_validate(product)
```

Pydantic 会把 ISO 字符串重新解析成 `datetime`。所以 Router 代码没有改。

---

## 9. Redis 故障时怎么办

`app/cache.py` 里所有 Redis 操作都捕获 `RedisError`：

```python
try:
    raw = redis_client.get(key)
except RedisError:
    logger.warning("读取商品缓存失败，降级查数据库")
    return None
```

效果：

| 场景 | 商品详情 | `/healthz` |
| --- | --- | --- |
| Redis 正常 | 可能命中缓存 | 200，`redis=ok` |
| Redis 挂掉 | 降级查 SQLite，仍然 200 | 200，`status=degraded`，`redis=error` |
| SQLite 挂掉 | 失败 | 503，`database=error` |

为什么 Redis 挂掉时 `/healthz` 还是 200？

- Redis 在当前项目里只是缓存，不是数据真相。
- 商品详情仍能查数据库，核心功能可用。
- 所以标记为 `degraded`，但不返回 503。
- 数据库挂掉才是真正的不可用，返回 503。

连接超时也设短了：

```python
socket_connect_timeout=1,
socket_timeout=1,
```

Redis 不可用时，最多等 1 秒就失败，不会拖住整个请求。

应用启动时也不会因为 Redis 挂掉而拒绝启动：

```python
if cache.check_redis():
    logger.info("Redis 连接成功")
else:
    logger.warning("Redis 不可用，商品详情将降级为数据库查询")
```

---

## 10. 缓存失效：现在还没真正发生

当前没有商品修改接口，所以「商品数据变化 → 删除缓存」这条路径还没有被触发。

但下一步做订单扣库存时，库存会变化，必须删除缓存：

```python
db.commit()
cache.delete_product_cache(product_id)
```

规则：

1. **先提交数据库，再删除缓存。**
2. 不要更新缓存，直接删除。
3. 不要在数据库事务提交前写缓存。
4. 删除失败只记录日志，接受最多 60 秒的旧数据。

如果忘记删除，用户会看到最长 60 秒的旧库存。这就是 TTL 的意义：即使逻辑漏了，也能自愈。

---

## 11. 实际验证结果

验证前先清空缓存：

```bash
redis-cli DEL minimall:dev:product:1
```

第一次请求商品详情：

```text
商品详情缓存未命中，查询数据库 | product_id=1
GET /api/v1/products/1 → 200
```

第二次请求：

```text
商品详情命中缓存 | product_id=1
GET /api/v1/products/1 → 200
```

检查 Redis：

```bash
redis-cli TTL minimall:dev:product:1
# 60

redis-cli --raw GET minimall:dev:product:1
# {"id": 1, "name": "机械键盘", ..., "stock": 10, ...}
```

健康检查：

```json
{
  "status": "ok",
  "components": {
    "database": "ok",
    "redis": "ok"
  }
}
```

模拟 Redis 故障（把 `REDIS_URL` 指向一个不存在的端口）：

```text
商品详情 → 200，仍然返回机械键盘
/healthz → 200，status=degraded，redis=error
```

说明降级逻辑生效。

---

## 12. 自己运行

1. 确认 Redis 在运行：

   ```bash
   redis-cli ping
   # PONG
   ```

   如果没有运行，在另一个终端启动：

   ```bash
   redis-server
   ```

2. 启动应用：

   ```bash
   conda activate test
   uvicorn app.main:app --reload --port 8000
   ```

3. 打开 `/docs`，连续调用两次 `GET /api/v1/products/1`。

4. 观察终端日志：第一次「未命中」，第二次「命中」。

5. 用 `redis-cli` 查看：

   ```bash
   redis-cli KEYS "minimall:dev:product:*"
   redis-cli TTL minimall:dev:product:1
   redis-cli --raw GET minimall:dev:product:1
   ```

6. 强制失效：

   ```bash
   redis-cli DEL minimall:dev:product:1
   ```

   再请求一次，日志会重新出现「未命中」。

---

## 13. 常见坑

1. **把 Redis 当数据库**：Redis 里的商品数据可以随时删除，SQLite 才是真相。
2. **更新缓存而不是删除缓存**：并发下容易写入旧值。
3. **在数据库 commit 前写缓存**：可能缓存了最终被回滚的数据。
4. **忘记设置 TTL**：缓存永久不一致。
5. **Key 没有前缀**：多个项目共用一个 Redis 时容易冲突。
6. **缓存 ORM 对象**：`json.dumps` 会失败。
7. **Redis 操作没有 try/except**：Redis 一挂，整个接口 500。
8. **连接没有超时**：Redis 不可用时请求会卡很久。
9. **忘记在库存变化后删缓存**：用户看到旧库存。
10. **只缓存详情就以为缓存万能**：列表、搜索、热点数据需要不同策略。

三个经典缓存问题，当前阶段只做到最基础的处理：

| 问题 | 含义 | 当前应对 | 可选的进阶方案 |
| --- | --- | --- | --- |
| 缓存穿透 | 查询不存在的数据，每次都打数据库 | 暂无 | 缓存空值 30~60 秒、布隆过滤器 |
| 缓存击穿 | 热点 key 过期瞬间大量请求打到数据库 | TTL 60 秒 | 进程内 single-flight、互斥锁 |
| 缓存雪崩 | 大量 key 同时过期或 Redis 故障 | TTL + 降级查库 | TTL 随机抖动、Redis 高可用 |

---

## 14. 自测问题

1. Cache-Aside 的读流程有哪几步？
2. 为什么写操作是删除缓存，而不是更新缓存？
3. 为什么缓存的不是 SQLAlchemy 的 `Product` 对象？
4. 命中缓存时还会查 SQLite 吗？还会创建 Session 吗？
5. 为什么 Redis 挂掉时商品详情还能用？
6. 为什么 Redis 挂掉时 `/healthz` 返回 200 而不是 503？
7. 库存变化后，应该在 commit 前还是 commit 后删除缓存？为什么？
8. 如果删除缓存失败，系统还能自愈吗？靠什么？
9. 缓存穿透、击穿、雪崩分别是什么？
10. 为什么 key 要带 `minimall:dev` 前缀？

---

## 15. 动手练习

1. 连续请求两次商品详情，观察日志中的「未命中」和「命中」。
2. 用 `redis-cli TTL` 观察过期时间，等 60 秒后再请求，观察重新回源。
3. 手动 `DEL` 缓存 key，再请求，观察未命中。
4. 把 `REDIS_URL` 改成一个错误端口，启动应用，验证商品详情仍可用、健康检查为 degraded。
5. 用 SQLite 把商品库存改成 99，但不清缓存，观察 60 秒内接口仍返回旧库存；然后删除缓存，观察恢复。
6. 把 TTL 改成 10 秒，观察过期速度。
7. 思考：如果给 TTL 加 0~30 秒随机抖动，能缓解什么问题？

---

## 16. 下一个模块：订单与事务

下一份文档 `docs/06-orders.md` 会加入：

- `Order` 模型和 `orders` 表
- 下单接口，必须登录（复用 `CurrentUser`）
- 事务内扣库存、写订单
- 条件 UPDATE 防止超卖
- 订单价格和名称快照
- **库存变化后删除商品缓存**，让缓存失效真正发生

到那时，你会看到 Redis 缓存和数据库事务如何配合：

```text
事务内：更新库存 + 写订单 + commit
事务外：删除商品缓存
```

**本模块边界**：只缓存商品详情；不缓存列表；没有商品写接口；不做 TTL 抖动、空值缓存和分布式锁。先把「读缓存 → 未命中 → 回源 → 回填」跑通。
