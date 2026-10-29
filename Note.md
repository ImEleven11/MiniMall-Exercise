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

