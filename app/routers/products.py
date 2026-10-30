from typing import Annotated

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.database import get_db
from app.schemas import ProductListResponse, ProductOut
from app.services import product_service

router = APIRouter(prefix="/api/v1/products", tags=["products"])


@router.get("", response_model=ProductListResponse, summary="商品列表")
def list_products(
    db: Annotated[Session, Depends(get_db)],
    page: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[int, Query(ge=1, le=100)] = 20,
    keyword: Annotated[str | None, Query(max_length=50)] = None,
) -> ProductListResponse:
    items, total = product_service.list_products(db, page, page_size, keyword)
    return ProductListResponse(
        items=[ProductOut.model_validate(item) for item in items],
        total=total,
        page=page,
        page_size=page_size,
    )


@router.get("/{product_id}", response_model=ProductOut, summary="商品详情")
def get_product_detail(
    product_id: int,
    db: Annotated[Session, Depends(get_db)],
) -> ProductOut:
    product = product_service.get_product(db, product_id)
    return ProductOut.model_validate(product)
