"""Request and response schemas, mirroring ``components/schemas`` in ``api/openapi.yaml``."""

import unicodedata
from enum import StrEnum
from typing import Annotated, Literal

from pydantic import AfterValidator, BaseModel, ConfigDict, Field, StrictStr

ITEM_ID_PATTERN = r"^[A-Za-z0-9_-]{1,64}$"
ITEM_NAME_MAX_LENGTH = 100
BATCH_MAX_ITEMS = 20


def _normalize_item_name(value: str) -> str:
    value = value.strip()
    if not value:
        raise ValueError("must not be empty")
    if len(value) > ITEM_NAME_MAX_LENGTH:
        raise ValueError(f"must be at most {ITEM_NAME_MAX_LENGTH} characters long")
    if any(unicodedata.category(char) == "Cc" for char in value):
        raise ValueError("must not contain control characters")
    return value


# Strict: only JSON strings are accepted, numbers etc. are not coerced.
ItemName = Annotated[StrictStr, AfterValidator(_normalize_item_name)]


class ItemSource(StrEnum):
    MANUAL = "manual"
    AI_RECOMMENDATION = "ai_recommendation"


class _RequestModel(BaseModel):
    """Base for request bodies: unknown fields are rejected."""

    model_config = ConfigDict(extra="forbid")


class NewItem(_RequestModel):
    name: ItemName
    source: ItemSource = ItemSource.MANUAL


class NewItemBatch(_RequestModel):
    items: Annotated[list[NewItem], Field(min_length=1, max_length=BATCH_MAX_ITEMS)]


class RecommendationRequest(_RequestModel):
    # Length and emptiness are checked by the recommendation pipeline, because those
    # cases have their own error codes (PROMPT_EMPTY, PROMPT_TOO_LONG).
    prompt: StrictStr


class Item(BaseModel):
    id: str
    name: str
    source: ItemSource


class ItemList(BaseModel):
    items: list[Item]


class Recommendation(BaseModel):
    name: str


class RecommendationResponse(BaseModel):
    recommendations: list[Recommendation]
    disclaimer: str


class HealthResponse(BaseModel):
    status: Literal["ok"] = "ok"
