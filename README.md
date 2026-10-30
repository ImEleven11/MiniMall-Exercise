# MiniMall 学习项目

一个用于学习 FastAPI 分层、数据库、Redis 缓存和 Docker 打包的最小后端项目。

当前进度：**Phase 2 商品读取（SQLite）**

## 技术栈

- Python 3.11（conda 环境 `test`）
- FastAPI + Uvicorn
- SQLite + SQLAlchemy
- JWT 鉴权
- Redis（后续模块加入）
- Docker（最后打包）

## 运行

```bash
conda activate test
pip install -r requirements.txt
python seed.py
uvicorn app.main:app --reload --port 8000
```

- Swagger：<http://127.0.0.1:8000/docs>
- 健康检查：<http://127.0.0.1:8000/healthz>

## 文档

- [项目全景：分层与依赖](docs/00-project-map.md)
- [架构蓝图](docs/architecture-blueprint.md)
- [01 · 框架骨架](docs/01-framework.md)
- [02 · 数据库接入](docs/02-database.md)
- [03 · 用户与 JWT 登录](docs/03-auth.md)
- [04 · 商品模块](docs/04-products.md)

## 目录

```text
app/
├── main.py              # 应用入口
├── config.py            # 配置
├── database.py          # engine / Session / get_db / init_db
├── models.py            # User / Product 模型
├── schemas.py           # 请求 / 响应模型
├── security.py          # 密码哈希 / JWT
├── exceptions.py        # 业务异常
├── deps.py              # get_current_user
├── logging_config.py    # 日志
├── services/
│   ├── auth_service.py      # 注册 / 登录
│   └── product_service.py   # 商品列表 / 详情
└── routers/
    ├── health.py        # 健康检查
    ├── auth.py          # 注册 / 登录
    ├── users.py         # 当前用户
    └── products.py      # 商品列表 / 详情
seed.py                  # 插入示例商品
data/
└── app.db               # SQLite 数据文件（自动生成，不提交）
scripts/
└── smoke_test.py        # 可选的启动冒烟检查
```
