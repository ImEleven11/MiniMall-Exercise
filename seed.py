from sqlalchemy import func, select

from app.database import SessionLocal, init_db
from app.models import Product

SAMPLE_PRODUCTS = [
    {
        "name": "机械键盘",
        "description": "87 键，青轴",
        "price_cents": 19900,
        "stock": 10,
    },
    {
        "name": "无线鼠标",
        "description": "2.4G 无线，静音按键",
        "price_cents": 5900,
        "stock": 20,
    },
    {
        "name": "显示器支架",
        "description": "单臂，可升降",
        "price_cents": 12900,
        "stock": 5,
    },
]


def main() -> None:
    init_db()

    with SessionLocal() as db:
        count = db.scalar(select(func.count(Product.id))) or 0
        if count > 0:
            print(f"已有 {count} 件商品，跳过插入。")
            return

        db.add_all(Product(**item) for item in SAMPLE_PRODUCTS)
        db.commit()
        print(f"已插入 {len(SAMPLE_PRODUCTS)} 件示例商品。")


if __name__ == "__main__":
    main()
