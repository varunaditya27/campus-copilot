from typing import Annotated

from fastapi import APIRouter, Query

from app.api.deps import AdminUser
from app.services import usage_service

router = APIRouter(prefix="/api/admin/analytics", tags=["admin"])


@router.get("")
def analytics(admin: AdminUser, days: Annotated[int, Query(ge=1, le=365)] = 30) -> dict:
    """Usage over the last `days` days (UTC): active students per day, tool and document use,
    popular words, how often proposed actions are approved, and how often nothing relevant was retrieved."""
    return usage_service.summary(days)
