from fastapi import APIRouter

from app.deps import CurrentUser
from app.schemas import UserOut

router = APIRouter(prefix="/api/v1/users", tags=["users"])


@router.get("/me", response_model=UserOut, summary="当前用户")
def read_me(current_user: CurrentUser) -> UserOut:
    return UserOut.model_validate(current_user)
