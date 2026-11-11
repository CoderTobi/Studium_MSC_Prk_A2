"""Test doubles: an in-memory item repository and a fake AI client."""

import re
import secrets
from collections.abc import Sequence

from shopping_list.errors import ApiError, ErrorCode
from shopping_list.models import ITEM_ID_PATTERN, Item, NewItem, Recommendation

_ITEM_ID = re.compile(ITEM_ID_PATTERN)


class InMemoryItemRepository:
    """Mirrors the semantics of ``FirestoreItemRepository`` without a database."""

    def __init__(self, item_limit: int = 200) -> None:
        self.item_limit = item_limit
        # uid -> items, kept in insertion order (= oldest first)
        self._items: dict[str, list[Item]] = {}

    @staticmethod
    def _new_id() -> str:
        item_id = secrets.token_urlsafe(15)
        assert _ITEM_ID.match(item_id)
        return item_id

    def list_items(self, uid: str) -> list[Item]:
        return list(self._items.get(uid, []))[: self.item_limit]

    def create_items(self, uid: str, new_items: Sequence[NewItem]) -> list[Item]:
        items = self._items.get(uid, [])
        if len(items) + len(new_items) > self.item_limit:
            raise ApiError(ErrorCode.ITEM_LIMIT_REACHED)
        created = [Item(id=self._new_id(), name=new.name, source=new.source) for new in new_items]
        self._items[uid] = [*items, *created]
        return created

    def delete_item(self, uid: str, item_id: str) -> None:
        items = self._items.get(uid, [])
        remaining = [item for item in items if item.id != item_id]
        if len(remaining) == len(items):
            raise ApiError(ErrorCode.ITEM_NOT_FOUND)
        self._items[uid] = remaining


class FakeAIClient:
    """Returns canned recommendations, or raises ``error``. Remembers the prompts."""

    def __init__(
        self,
        recommendations: Sequence[Recommendation] | None = None,
        error: ApiError | None = None,
    ) -> None:
        self.recommendations = list(recommendations or [])
        self.error = error
        self.prompts: list[str] = []

    def recommend(self, prompt: str) -> list[Recommendation]:
        self.prompts.append(prompt)
        if self.error is not None:
            raise self.error
        return list(self.recommendations)
