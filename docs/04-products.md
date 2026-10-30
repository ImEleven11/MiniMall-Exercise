# 04 · 商品模块

> 所属阶段：Phase 2
> 完成日期：2026-10-30
> 对应代码：`app/models.py`、`app/schemas.py`、`app/exceptions.py`、`app/services/product_service.py`、`app/routers/products.py`、`seed.py`

---

## 1. 这个模块做了什么

把「商品」从数据库读到接口：

1. 新增 `Product` 模型和 `products` 表。
2. 用 `seed.py` 插入 3 件示例商品。
3. 商品列表：分页 + 关键词过滤。
4. 商品详情：按 ID 查询，不存在或已下架返回 404。
5. 新增 `ProductNotFoundError` 业务异常。

**这一步还没有接 Redis。** 商品数据完全从 SQLite 读取，目的是先看清「数据库 → Service → Router → JSON」这条链路；下一模块再加缓存，才能对比出缓存到底改变了什么。

---

## 2. 文件变化

| 文件 | 变化 |
| --- | --- |
| `app/models.py` | 新增 `Product` 模型 |
| `app/schemas.py` | 新增 `ProductOut`、`ProductListResponse` |
| `app/exceptions.py` | 新增 `ProductNotFoundError` |
| `app/services/product_service.py` | 新增：商品列表、详情查询 |
| `app/routers/products.py` | 新增：两个商品接口 |
| `app/main.py` | 挂载 `products.router` |
| `seed.py` | 新增：插入示例商品 |

---

## 3. products 表

```text
products
├── id             INTEGER 主键，自增
├── name           VARCHAR(120) 非空，普通索引
├── description    TEXT 可空
├── price_cents    INTEGER 非空
├── stock          INTEGER 非空，默认 0
├── is_active      BOOLEAN 非空，默认 true，普通索引
├── created_at     DATETIME 服务器默认值
└── updated_at     DATETIME 服务器默认值，更新时刷新
```

两个设计点：

1. **金额用整数「分」**：`19900` 表示 199.00 元。避免浮点误差，也不需要处理 `DECIMAL` 和前端精度问题。
2. **下架而不是删除**：`is_active=False` 表示下架。列表和详情都会过滤掉下架商品，但数据还在，未来订单可以继续引用历史商品。

`updated_at` 使用了：

```python
onupdate=func.now()
```

当这一行被 UPDATE 时，SQLAlchemy 会自动把 `updated_at` 设置为当前时间。

---

## 4. 为什么用 seed 脚本，而不是商品创建接口

这一阶段没有管理员角色，也不希望把「谁能创建商品」这个权限问题混进来。

`seed.py` 只负责插入演示数据：

```bash
python seed.py
```

它会：

1. 调用 `init_db()`，确保表存在。
2. 统计 `products` 表行数。
3. 如果已有商品，跳过；否则插入 3 件。

这样你可以反复运行，不会重复插入。

后续如果想练权限，可以再加：

- `is_admin` 字段
- 管理员依赖
- `POST /products`、`PATCH /products/{id}`
- 普通用户访问管理接口返回 403

这些都不影响当前的读取链路。

---

## 5. 请求链路 A：商品列表

```text
GET /api/v1/products?page=1&page_size=2&keyword=键盘
  → routers/products.py 的 list_products()
  → FastAPI 校验 page / page_size / keyword
      page >= 1
      page_size 在 1~100
  → Depends(get_db) 创建 Session
  → product_service.list_products(db, page, page_size, keyword)
      → 构造过滤条件：is_active = true（可选 name LIKE %keyword%）
      → 查询总数：SELECT COUNT(*)
      → 查询当前页：SELECT ... ORDER BY id LIMIT ... OFFSET ...
  → ProductOut.model_validate() 转换每个 ORM 对象
  → ProductListResponse
  → 200 JSON
```

返回结构：

```json
{
  "items": [
    {
      "id": 1,
      "name": "机械键盘",
      "description": "87 键，青轴",
      "price_cents": 19900,
      "stock": 10,
      "is_active": true,
      "created_at": "2026-10-30T02:36:37",
      "updated_at": "2026-10-30T02:36:37"
    }
  ],
  "total": 3,
  "page": 1,
  "page_size": 2
}
```

### 5.1 为什么要查两次

- `total` 告诉前端「一共有多少条」，用于算总页数。
- `items` 只取当前页的数据。

如果只查当前页，前端不知道总数；如果一次查全部，再在 Python 里切片，数据量大时会浪费内存和带宽。

对应的 SQL 大致是：

```sql
SELECT COUNT(products.id) FROM products WHERE is_active = 1;

SELECT * FROM products
WHERE is_active = 1
ORDER BY id
LIMIT 2 OFFSET 0;
```

### 5.2 分页参数

```python
page: Annotated[int, Query(ge=1)] = 1
page_size: Annotated[int, Query(ge=1, le=100)] = 20
```

- `page` 从 1 开始。
- `page_size` 默认 20，最大 100，防止一次拉太多。
- 非法值由 FastAPI 直接返回 422，不会进入 Service。

偏移量：

```python
offset = (page - 1) * page_size
```

第 1 页偏移 0，第 2 页偏移 2（当 `page_size=2` 时）。

### 5.3 关键词过滤

```python
conditions.append(Product.name.like(f"%{keyword}%"))
```

SQLAlchemy 会把 `keyword` 作为参数传给数据库，不是拼接 SQL 字符串，所以不会产生 SQL 注入。

但要注意：`LIKE '%关键词%'` 前面的 `%` 会导致普通索引无法使用。数据量小的时候没问题；数据量大了要换成前缀匹配、全文索引或搜索引擎。

---

## 6. 请求链路 B：商品详情

```text
GET /api/v1/products/1
  → routers/products.py 的 get_product_detail()
  → Depends(get_db) 创建 Session
  → product_service.get_product(db, 1)
      → db.get(Product, 1)
      ├── 不存在 → 抛 ProductNotFoundError
      ├── is_active = false → 抛 ProductNotFoundError
      └── 正常 → 返回 Product
  → ProductOut.model_validate(product)
  → 200 JSON
```

商品不存在或已下架时：

```json
{
  "code": "PRODUCT_NOT_FOUND",
  "message": "商品不存在或已下架"
}
```

状态码 404 由 `ProductNotFoundError` 的类属性决定，`main.py` 中已有的 `AppError` 处理器负责统一转换。

这就是业务异常分层的好处：Service 只表达「商品找不到」，不关心 HTTP 状态码怎么写。

---

## 7. 实际验证结果

执行：

```bash
python seed.py
```

输出：

```text
已插入 3 件示例商品。
```

接口验证：

| 请求 | 结果 |
| --- | --- |
| `GET /api/v1/products?page=1&page_size=2` | 200，`total=3`，返回前 2 件 |
| `GET /api/v1/products?page=2&page_size=2` | 200，返回第 3 件 |
| `GET /api/v1/products?keyword=键盘` | 200，`total=1`，返回机械键盘 |
| `GET /api/v1/products/1` | 200，返回商品详情 |
| `GET /api/v1/products/99999` | 404，`PRODUCT_NOT_FOUND` |
| `GET /api/v1/products?page=0` | 422，参数校验失败 |

OpenAPI 新增路径：

```text
/api/v1/products
/api/v1/products/{product_id}
```

---

## 8. 如何自己运行

```bash
conda activate test
python seed.py
uvicorn app.main:app --reload --port 8000
```

打开：

- <http://127.0.0.1:8000/docs>
- 展开 **products** 分组
- 先调 `GET /api/v1/products`，再试分页、关键词和详情

商品接口是公开的，不需要 Authorize。

---

## 9. 常见坑

1. **没有先运行 `seed.py`**：列表是空的，不是接口坏了。
2. **列表和详情的过滤条件不一致**：列表过滤 `is_active`，详情也必须过滤，否则下架商品仍能通过 ID 访问。
3. **`total` 和 `items` 用了不同条件**：分页总数会不准。本项目把条件放在同一个 `conditions` 列表里复用。
4. **`LIKE '%x%'` 以为走了索引**：前面的通配符会让普通索引失效。
5. **金额用浮点**：`19.9` 在计算机里可能存成 `19.899999...`，所以统一用分。
6. **分页参数不校验**：`page=0` 或 `page_size=10000` 会带来无意义查询，交给 `Query(ge/le)` 处理。
7. **把 ORM 对象直接返回**：这里用 `ProductOut` 过滤字段、统一序列化。
8. **下架商品用 DELETE**：订单以后可能引用商品，物理删除会丢历史；用 `is_active` 更稳。
9. **忘记 `main.py` 挂载路由**：接口写好了但 `/docs` 里看不到，检查 `include_router`。
10. **数据库已有旧表结构**：本项目用 `create_all`，新增表没问题；如果是改字段，需要手动迁移或删库重建。

---

## 10. 自测问题

1. `GET /api/v1/products` 的 `total` 和 `items` 分别由哪条查询产生？
2. 为什么分页要做两次查询？只查一次会怎样？
3. `page=2&page_size=2` 时，SQL 的 `OFFSET` 是多少？
4. 为什么列表和详情都要过滤 `is_active`？
5. 为什么商品详情返回 404 时，响应体是 `code` / `message`，而不是 FastAPI 默认的 `detail`？
6. `ProductOut.model_validate(product)` 为什么能把 ORM 对象转成响应模型？
7. `LIKE '%键盘%'` 为什么用不上普通索引？
8. 金额为什么不用 `float`？

---

## 11. 动手练习

1. 再插入一件商品，观察 `total` 和分页结果的变化。
2. 用 SQLite 把某件商品改成 `is_active = 0`，再请求列表和详情，观察它是否消失。
3. 请求 `page_size=101`，观察 422 响应。
4. 请求不存在的商品 ID，确认 404 的 `code`。
5. 用 `EXPLAIN QUERY PLAN` 看 `LIKE '%键盘%'` 的查询计划。
6. 思考：如果商品有 100 万条，`COUNT(*)` 每次分页都执行一次，会有什么问题？

---

## 12. 下一个模块：Redis 商品缓存

下一份文档 `docs/05-redis.md` 会给商品详情加缓存：

```text
GET /products/{id}
  → 先查 Redis
     命中 → 直接返回
     未命中 → 查 SQLite → 写入 Redis（TTL 60 秒）→ 返回
```

并加入：

- Redis 客户端与连接管理
- `cache.py` 封装读写删
- 缓存命中/未命中日志
- 商品数据变更后删除缓存
- Redis 挂掉时降级查数据库

**Router、Schema、Product 模型都不需要改。** 缓存只加在 Service 和新增的 `cache.py` 之间，这正好能看出分层的价值。

---

## 13. 本模块边界

- 不做商品创建/修改接口（用 seed 脚本代替）。
- 不做管理员权限。
- 不做 Redis 缓存。
- 不做多分类、图片、SKU、库存流水。

先把「读取商品」这条链路跑通，下一模块再优化它。
