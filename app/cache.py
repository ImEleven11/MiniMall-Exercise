import json
import logging

import redis
from redis.exceptions import RedisError

from app.config import get_settings

logger = logging.getLogger(__name__)
settings = get_settings()

# 原生 Redis 和 Docker Redis 在这里只差 REDIS_URL。
# 超时设短一些：Redis 挂掉时快速失败，不要拖住请求。
# 缓存核心原则：缓存只是加速手段，不是必需品
# Redis 挂了，正确行为是快速放弃缓存、去查数据库，而不是让请求卡住
redis_client = redis.Redis.from_url(
    settings.redis_url,
    decode_responses=True,
    socket_connect_timeout=1, # 建立 TCP 连接的超时，连不上 Redis 时最多等 1 秒
    socket_timeout=1, # 连接建立后，读写操作的超时，发命令后最多等 1 秒响应
)

PRODUCT_CACHE_TTL_SECONDS = 60


def close_redis() -> None:
    """应用关闭时释放 Redis 连接池。"""
    try:
        redis_client.close()
    except RedisError:
        logger.warning("关闭 Redis 连接失败", exc_info=True)


def check_redis() -> bool:
    try:
        return bool(redis_client.ping())
    except RedisError:
        logger.warning("Redis 不可用")
        return False

# 构造key
def product_cache_key(product_id: int) -> str:
    return f"{settings.redis_prefix}:product:{product_id}"


def get_product_cache(product_id: int) -> dict[str, object] | None:
    """读取商品缓存；Redis 故障或数据异常时返回 None，由调用方回源。"""
    key = product_cache_key(product_id)

    try:
        raw = redis_client.get(key) # 读 key 的值
    except RedisError:
        logger.warning("读取商品缓存失败，降级查数据库 | product_id=%s", product_id)
        return None

    if raw is None:
        return None

    # 反序列化：把字符串反序列化成 Python 对象
    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
        logger.warning("商品缓存不是合法 JSON，删除 | key=%s", key)
        delete_product_cache(product_id) # 主动删除这个坏 key
        return None

    # 结构校验：不是字典就删掉（防御性编程）
    if not isinstance(data, dict):
        logger.warning("商品缓存结构异常，删除 | key=%s", key)
        delete_product_cache(product_id)
        return None

    return data


def set_product_cache(product_id: int, data: dict[str, object]) -> None:
    """写入商品缓存，失败只记录日志，不影响本次请求。"""
    try:
        redis_client.set(
            product_cache_key(product_id),
            json.dumps(data, ensure_ascii=False), # 序列化：把字典序列化成 JSON 字符串
            ex=PRODUCT_CACHE_TTL_SECONDS, # 设置过期时间
        )
    except RedisError:
        logger.warning("写入商品缓存失败 | product_id=%s", product_id)


def delete_product_cache(product_id: int) -> None:
    """商品数据变化后删除缓存，下次读取会重新回源。"""
    try:
        redis_client.delete(product_cache_key(product_id))
    except RedisError:
        logger.warning("删除商品缓存失败 | product_id=%s", product_id)
