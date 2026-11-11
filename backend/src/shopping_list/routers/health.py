from fastapi import APIRouter

from shopping_list.models import HealthResponse

router = APIRouter(tags=["System"])


@router.get("/health", response_model=HealthResponse)
def get_health() -> HealthResponse:
    """Liveness only: deliberately says nothing about Firestore, Ollama or the config."""
    return HealthResponse()
