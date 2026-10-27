# MiniMall 学习项目

一个用于学习 FastAPI 分层、数据库、Redis 缓存和 Docker 打包的最小后端项目。

当前进度：**Phase 0.2 数据库接入**

## 技术栈

- Python 3.11（conda 环境 `test`）
- FastAPI + Uvicorn
- SQLite + SQLAlchemy（下一模块加入）
- Redis（后续模块加入）
- Docker（最后打包）

## 运行

```bash
conda activate test
pip install -r requirements.txt
uvicorn app.main:app --reload --port 8000
```

- Swagger：<http://127.0.0.1:8000/docs>
- 健康检查：<http://127.0.0.1:8000/healthz>

## 文档

- [架构蓝图](docs/architecture-blueprint.md)
- [01 · 框架骨架](docs/01-framework.md)
- [02 · 数据库接入](docs/02-database.md)

## 目录

```text
app/
├── main.py              # 应用入口
├── config.py            # 配置
├── database.py          # engine / Session / get_db / init_db
├── logging_config.py    # 日志
└── routers/
    └── health.py        # 健康检查
data/
└── app.db               # SQLite 数据文件（自动生成，不提交）
scripts/
└── smoke_test.py        # 可选的启动冒烟检查
```
