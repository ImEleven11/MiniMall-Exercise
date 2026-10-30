import logging

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app import cache
from app.exceptions import ProductNotFoundError
from app.models import Product

logger = logging.getLogger(__name__)


def list_products(
    db: Session,
    page: int,
    page_size: int,
    keyword: str | None = None,
) -> tuple[list[Product], int]:
    """返回当前页的商品和满足条件的总数。"""
    conditions = [Product.is_active.is_(True)] # 条件列表，用来存放 WHERE 子句的各个条件
    if keyword:
        # SQLAlchemy 会把 keyword 作为参数传给数据库，不会被当成 SQL 拼接。
        # 生成 SQL 的 name LIKE '%关键字%'，即"名称包含关键字"，也就是说包含这个关键字的商品都会被检索
        conditions.append(Product.name.like(f"%{keyword}%"))

    # db.scalar(query) ：执行查询，只取结果的第一行第一列，返回这一个值
    total = db.scalar(select(func.count(Product.id)).where(*conditions)) or 0 # 满足条件的共有多少条

    items = list(
        db.scalars(
            select(Product)
            .where(*conditions)
            .order_by(Product.id)
            .offset((page - 1) * page_size) # 分页公式，跳过前面多少条
            .limit(page_size)
        ).all() # 把结果全部取出，返回一个列表
    )
    return items, total


def get_product(db: Session, product_id: int) -> dict[str, object]:
    """Cache-Aside：先查 Redis，未命中再查 SQLite 并回填缓存。"""
    cached = cache.get_product_cache(product_id)
    if cached is not None:
        logger.info("商品详情命中缓存 | product_id=%s", product_id)
        return cached

    logger.info("商品详情缓存未命中，查询数据库 | product_id=%s", product_id)

    product = db.get(Product, product_id)
    if product is None or not product.is_active:
        raise ProductNotFoundError()

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
    cache.set_product_cache(product_id, data)
    return data
