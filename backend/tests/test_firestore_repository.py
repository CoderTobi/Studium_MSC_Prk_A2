"""Integration tests against the Firestore emulator.

Run with ``FIRESTORE_EMULATOR_HOST=localhost:8080`` set (for example through
``firebase emulators:start --only firestore``). Skipped otherwise.
"""

import os
import uuid
from concurrent.futures import ThreadPoolExecutor

import pytest

from shopping_list.errors import ApiError, ErrorCode
from shopping_list.models import ItemSource, NewItem
from shopping_list.repository import FirestoreItemRepository

pytestmark = pytest.mark.skipif(
    not os.environ.get("FIRESTORE_EMULATOR_HOST"),
    reason="FIRESTORE_EMULATOR_HOST is not set (no Firestore emulator)",
)

LIMIT = 5


@pytest.fixture(scope="module")
def firestore_client():
    from google.cloud import firestore

    return firestore.Client(project="demo-shopping-list")


@pytest.fixture
def repo(firestore_client):
    return FirestoreItemRepository(firestore_client, LIMIT)


@pytest.fixture
def uid():
    return f"test-{uuid.uuid4().hex}"


def new(*names, source=ItemSource.MANUAL):
    return [NewItem(name=name, source=source) for name in names]


def user_doc(firestore_client, uid):
    snapshot = firestore_client.collection("users").document(uid).get()
    return snapshot.to_dict() if snapshot.exists else None


def item_docs(firestore_client, uid):
    items = firestore_client.collection("users").document(uid).collection("items")
    return {doc.id: doc.to_dict() for doc in items.stream()}


def test_empty_list(repo, uid):
    assert repo.list_items(uid) == []


def test_create_and_list_in_order(repo, uid):
    created = repo.create_items(uid, new("a", "b"))
    created += repo.create_items(uid, new("c", source=ItemSource.AI_RECOMMENDATION))
    assert [i.name for i in created] == ["a", "b", "c"]
    listed = repo.list_items(uid)
    assert listed == created
    assert listed[2].source is ItemSource.AI_RECOMMENDATION


def test_seq_and_counters(repo, firestore_client, uid):
    created = repo.create_items(uid, new("a", "b", "c"))
    user = user_doc(firestore_client, uid)
    assert user["itemCount"] == 3
    assert user["nextSeq"] == 4
    assert "createdAt" in user
    assert "updatedAt" in user
    docs = item_docs(firestore_client, uid)
    assert [docs[i.id]["seq"] for i in created] == [1, 2, 3]
    assert docs[created[0].id]["name"] == "a"
    assert docs[created[0].id]["source"] == "manual"
    assert "createdAt" in docs[created[0].id]


def test_seq_continues_after_delete(repo, firestore_client, uid):
    first, second = repo.create_items(uid, new("a", "b"))
    repo.delete_item(uid, first.id)
    third = repo.create_items(uid, new("c"))[0]
    assert item_docs(firestore_client, uid)[third.id]["seq"] == 3
    assert [i.id for i in repo.list_items(uid)] == [second.id, third.id]


def test_item_limit(repo, firestore_client, uid):
    repo.create_items(uid, new(*"abcde"))
    with pytest.raises(ApiError) as exc:
        repo.create_items(uid, new("f"))
    assert exc.value.code is ErrorCode.ITEM_LIMIT_REACHED
    assert len(repo.list_items(uid)) == LIMIT
    assert user_doc(firestore_client, uid)["itemCount"] == LIMIT


def test_batch_over_limit_creates_nothing(repo, firestore_client, uid):
    repo.create_items(uid, new("a", "b", "c"))
    with pytest.raises(ApiError) as exc:
        repo.create_items(uid, new("d", "e", "f"))
    assert exc.value.code is ErrorCode.ITEM_LIMIT_REACHED
    assert [i.name for i in repo.list_items(uid)] == ["a", "b", "c"]
    assert user_doc(firestore_client, uid)["itemCount"] == 3
    assert len(item_docs(firestore_client, uid)) == 3


def test_delete_decrements_counter(repo, firestore_client, uid):
    a, b = repo.create_items(uid, new("a", "b"))
    repo.delete_item(uid, a.id)
    assert [i.id for i in repo.list_items(uid)] == [b.id]
    user = user_doc(firestore_client, uid)
    assert user["itemCount"] == 1
    assert user["nextSeq"] == 3


def test_delete_frees_capacity(repo, uid):
    items = repo.create_items(uid, new(*"abcde"))
    repo.delete_item(uid, items[0].id)
    assert len(repo.create_items(uid, new("f"))) == 1


def test_delete_missing_item(repo, uid):
    repo.create_items(uid, new("a"))
    with pytest.raises(ApiError) as exc:
        repo.delete_item(uid, "doesNotExist")
    assert exc.value.code is ErrorCode.ITEM_NOT_FOUND


def test_delete_for_unknown_user(repo, uid):
    with pytest.raises(ApiError) as exc:
        repo.delete_item(uid, "doesNotExist")
    assert exc.value.code is ErrorCode.ITEM_NOT_FOUND


def test_users_are_isolated(repo, firestore_client, uid):
    other = f"{uid}-other"
    mine = repo.create_items(uid, new("mine"))[0]
    repo.create_items(other, new("theirs"))
    assert [i.name for i in repo.list_items(uid)] == ["mine"]
    assert [i.name for i in repo.list_items(other)] == ["theirs"]

    with pytest.raises(ApiError) as exc:
        repo.delete_item(other, mine.id)
    assert exc.value.code is ErrorCode.ITEM_NOT_FOUND
    assert [i.name for i in repo.list_items(uid)] == ["mine"]
    assert user_doc(firestore_client, uid)["itemCount"] == 1


def test_limit_is_per_user(repo, uid):
    repo.create_items(uid, new(*"abcde"))
    assert len(repo.create_items(f"{uid}-other", new("a"))) == 1


def test_concurrent_creates_respect_limit(repo, firestore_client, uid):
    """Parallel requests must never slip past the limit or corrupt the counters.

    Under heavy contention on the user document Firestore may give up on some
    transactions (they end up as 500 INTERNAL_ERROR); what matters is that every
    transaction is all-or-nothing and the invariants hold afterwards.
    """

    def create_one(index: int) -> str:
        try:
            repo.create_items(uid, new(f"item {index}"))
        except ApiError as exc:
            assert exc.code is ErrorCode.ITEM_LIMIT_REACHED
            return "limit"
        except Exception:  # contention abort, allowed here
            return "aborted"
        return "created"

    with ThreadPoolExecutor(max_workers=8) as pool:
        results = list(pool.map(create_one, range(8)))

    docs = item_docs(firestore_client, uid)
    assert results.count("created") == len(docs) <= LIMIT
    assert user_doc(firestore_client, uid)["itemCount"] == len(docs)
    seqs = sorted(doc["seq"] for doc in docs.values())
    assert len(set(seqs)) == len(seqs)
    if "aborted" not in results:
        assert len(docs) == LIMIT
