"""Storage of the shopping list items (Firestore schema: see ``database.md``).

    users/{uid}                 itemCount, nextSeq, createdAt, updatedAt
    users/{uid}/items/{itemId}  name, source, seq, createdAt

Every path is built from the authenticated ``uid``, so another user's item simply
does not exist under the caller's path. That gives "foreign item = 404" for free.
"""

from collections.abc import Sequence
from typing import Any, Protocol

from google.cloud import firestore

from shopping_list.config import Settings
from shopping_list.errors import ApiError, ErrorCode
from shopping_list.models import Item, ItemSource, NewItem

USERS = "users"
ITEMS = "items"


class ItemRepository(Protocol):
    def list_items(self, uid: str) -> list[Item]:
        """All items of the user, oldest first."""
        ...

    def create_items(self, uid: str, new_items: Sequence[NewItem]) -> list[Item]:
        """Create all items atomically, in request order.

        Raises ``ITEM_LIMIT_REACHED`` (and creates nothing) if the list would exceed
        the item limit.
        """
        ...

    def delete_item(self, uid: str, item_id: str) -> None:
        """Delete one item. Raises ``ITEM_NOT_FOUND`` if the user has no such item."""
        ...


def create_firestore_client(settings: Settings) -> firestore.Client:
    """Create the Firestore client.

    Credentials come from ``GOOGLE_APPLICATION_CREDENTIALS`` (service account key file).
    If ``FIRESTORE_EMULATOR_HOST`` is set, the client talks to the emulator instead.
    """
    return firestore.Client(
        project=settings.google_cloud_project, database=settings.firestore_database
    )


class FirestoreItemRepository:
    def __init__(self, client: firestore.Client, item_limit: int) -> None:
        self._client = client
        self._item_limit = item_limit

    def _user_ref(self, uid: str) -> firestore.DocumentReference:
        return self._client.collection(USERS).document(uid)

    def _items_ref(self, uid: str) -> firestore.CollectionReference:
        return self._user_ref(uid).collection(ITEMS)

    def list_items(self, uid: str) -> list[Item]:
        query = self._items_ref(uid).order_by("seq").limit(self._item_limit)
        return [_to_item(snapshot.id, snapshot.to_dict() or {}) for snapshot in query.stream()]

    def create_items(self, uid: str, new_items: Sequence[NewItem]) -> list[Item]:
        user_ref = self._user_ref(uid)
        items_ref = self._items_ref(uid)
        item_limit = self._item_limit

        @firestore.transactional
        def create(transaction: firestore.Transaction) -> list[Item]:
            user = user_ref.get(transaction=transaction)
            data = (user.to_dict() or {}) if user.exists else {}
            item_count = int(data.get("itemCount", 0))
            next_seq = int(data.get("nextSeq", 1))

            if item_count + len(new_items) > item_limit:
                raise ApiError(ErrorCode.ITEM_LIMIT_REACHED)

            created: list[Item] = []
            for offset, new_item in enumerate(new_items):
                item_ref = items_ref.document()  # Firestore auto-ID
                transaction.create(
                    item_ref,
                    {
                        "name": new_item.name,
                        "source": new_item.source.value,
                        "seq": next_seq + offset,
                        "createdAt": firestore.SERVER_TIMESTAMP,
                    },
                )
                created.append(Item(id=item_ref.id, name=new_item.name, source=new_item.source))

            user_update = {
                "itemCount": item_count + len(new_items),
                "nextSeq": next_seq + len(new_items),
                "updatedAt": firestore.SERVER_TIMESTAMP,
            }
            if user.exists:
                transaction.update(user_ref, user_update)
            else:
                # The user document is created lazily with the first item.
                transaction.create(
                    user_ref, {**user_update, "createdAt": firestore.SERVER_TIMESTAMP}
                )
            return created

        return create(self._client.transaction())

    def delete_item(self, uid: str, item_id: str) -> None:
        user_ref = self._user_ref(uid)
        item_ref = self._items_ref(uid).document(item_id)

        @firestore.transactional
        def delete(transaction: firestore.Transaction) -> None:
            # Firestore transactions require all reads before the first write.
            item = item_ref.get(transaction=transaction)
            user = user_ref.get(transaction=transaction)
            if not item.exists:
                raise ApiError(ErrorCode.ITEM_NOT_FOUND)

            transaction.delete(item_ref)
            if user.exists:
                item_count = int((user.to_dict() or {}).get("itemCount", 0))
                transaction.update(
                    user_ref,
                    {
                        "itemCount": max(0, item_count - 1),
                        "updatedAt": firestore.SERVER_TIMESTAMP,
                    },
                )

        delete(self._client.transaction())


def _to_item(item_id: str, data: dict[str, Any]) -> Item:
    return Item(
        id=item_id,
        name=data["name"],
        source=ItemSource(data.get("source", ItemSource.MANUAL.value)),
    )
