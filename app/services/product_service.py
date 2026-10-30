from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.exceptions import ProductNotFoundError
from app.models import Product


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


def get_product(db: Session, product_id: int) -> Product:
    product = db.get(Product, product_id)
    if product is None or not product.is_active:
        raise ProductNotFoundError()
    return product
