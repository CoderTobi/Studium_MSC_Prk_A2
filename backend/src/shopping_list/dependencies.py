"""FastAPI dependencies shared by the routers."""

from collections.abc import Awaitable, Callable
from typing import Annotated

from fastapi import Depends, Request
from pydantic import BaseModel, ValidationError

from shopping_list.errors import ApiError, ErrorCode, field_errors
from shopping_list.recommendations import RecommendationService
from shopping_list.repository import ItemRepository


def _is_json(content_type: str | None) -> bool:
    if content_type is None:
        return False
    media_type = content_type.split(";", 1)[0].strip().lower()
    return media_type == "application/json"


def json_body[M: BaseModel](model: type[M]) -> Callable[[Request], Awaitable[M]]:
    """Dependency that reads and validates a JSON request body.

    Used instead of FastAPI's built-in body parameters so that the body is only read
    after authentication and rate limiting (router-level dependencies run first), and
    so that a wrong content type gets ``415`` instead of a validation error.
    """

    async def dependency(request: Request) -> M:
        if not _is_json(request.headers.get("content-type")):
            raise ApiError(ErrorCode.UNSUPPORTED_MEDIA_TYPE)
        body = await request.body()
        try:
            return model.model_validate_json(body)
        except ValidationError as exc:
            raise ApiError(ErrorCode.VALIDATION_ERROR, details=field_errors(exc.errors())) from None

    return dependency


def get_repository(request: Request) -> ItemRepository:
    return request.app.state.repository


def get_recommendation_service(request: Request) -> RecommendationService:
    return request.app.state.recommendation_service


Repository = Annotated[ItemRepository, Depends(get_repository)]
Recommender = Annotated[RecommendationService, Depends(get_recommendation_service)]
