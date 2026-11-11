from typing import Annotated

from fastapi import APIRouter, Depends, Path, Request, Response, status

from shopping_list.auth import CurrentUid
from shopping_list.dependencies import Repository, json_body
from shopping_list.models import ITEM_ID_PATTERN, Item, ItemList, NewItem, NewItemBatch
from shopping_list.rate_limit import Bucket, rate_limited

router = APIRouter(
    prefix="/items",
    tags=["Items"],
    # Runs before everything else of the route: authentication, then rate limiting.
    dependencies=[Depends(rate_limited(Bucket.GENERAL))],
)

ItemId = Annotated[str, Path(alias="itemId", pattern=ITEM_ID_PATTERN)]


@router.get("", response_model=ItemList)
def list_items(uid: CurrentUid, repository: Repository) -> ItemList:
    return ItemList(items=repository.list_items(uid))


@router.post("", status_code=status.HTTP_201_CREATED, response_model=Item)
def create_item(
    request: Request,
    response: Response,
    uid: CurrentUid,
    repository: Repository,
    new_item: Annotated[NewItem, Depends(json_body(NewItem))],
) -> Item:
    [item] = repository.create_items(uid, [new_item])
    response.headers["Location"] = request.app.url_path_for("delete_item", itemId=item.id)
    return item


@router.post("/batch", status_code=status.HTTP_201_CREATED, response_model=ItemList)
def create_items_batch(
    uid: CurrentUid,
    repository: Repository,
    batch: Annotated[NewItemBatch, Depends(json_body(NewItemBatch))],
) -> ItemList:
    return ItemList(items=repository.create_items(uid, batch.items))


@router.delete("/{itemId}", status_code=status.HTTP_204_NO_CONTENT, response_class=Response)
def delete_item(item_id: ItemId, uid: CurrentUid, repository: Repository) -> None:
    repository.delete_item(uid, item_id)
