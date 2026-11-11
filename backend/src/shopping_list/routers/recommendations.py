from typing import Annotated

from fastapi import APIRouter, Depends

from shopping_list.dependencies import Recommender, json_body
from shopping_list.models import RecommendationRequest, RecommendationResponse
from shopping_list.rate_limit import Bucket, rate_limited

router = APIRouter(
    tags=["Recommendations"],
    # Counts against both the ai and the general bucket.
    dependencies=[Depends(rate_limited(Bucket.GENERAL, Bucket.AI))],
)


@router.post("/recommendations", response_model=RecommendationResponse)
def create_recommendations(
    service: Recommender,
    body: Annotated[RecommendationRequest, Depends(json_body(RecommendationRequest))],
) -> RecommendationResponse:
    return service.recommend(body.prompt)
