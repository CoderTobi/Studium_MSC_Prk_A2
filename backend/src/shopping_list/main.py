"""Application factory.

Run with::

    uv run --env-file .env uvicorn shopping_list.main:create_app --factory
"""

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI

from shopping_list.auth import build_authenticator
from shopping_list.config import Settings
from shopping_list.errors import RouteMethodIndex, register_exception_handlers
from shopping_list.logging_setup import configure_logging, get_logger
from shopping_list.middleware import (
    BodySizeLimitMiddleware,
    ErrorGuardMiddleware,
    JSONCORSMiddleware,
    RequestContextMiddleware,
)
from shopping_list.ollama import OllamaClient
from shopping_list.rate_limit import Bucket, RateLimiter
from shopping_list.recommendations import AIClient, RecommendationService
from shopping_list.repository import (
    FirestoreItemRepository,
    ItemRepository,
    create_firestore_client,
)
from shopping_list.routers import health, items, recommendations

API_PREFIX = "/api/v1"

logger = get_logger("app")


def create_app(
    settings: Settings | None = None,
    *,
    repository: ItemRepository | None = None,
    ai_client: AIClient | None = None,
) -> FastAPI:
    """Build the app. ``repository`` and ``ai_client`` can be replaced in tests."""
    settings = settings or Settings.from_env()
    configure_logging(settings.log_level)
    authenticator = build_authenticator(settings)  # refuses to start if not possible

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        if settings.auth_disabled:
            logger.warning(
                "AUTHENTICATION VERIFICATION IS DISABLED (AUTH_DISABLED=true). Tokens are "
                "not verified and any caller can act as any user. Never use this in "
                "production."
            )
        if app.state.repository is None:
            client = create_firestore_client(settings)
            app.state.repository = FirestoreItemRepository(client, settings.item_limit)
            logger.info(
                "Using Firestore project %r, database %r",
                client.project,
                settings.firestore_database,
            )
        if isinstance(app.state.recommendation_service.ai_client, OllamaClient):
            logger.info(
                "Using Ollama at %s with model %r (timeout %ss)",
                settings.ollama_url,
                settings.ollama_model,
                settings.ollama_timeout_seconds,
            )
        yield

    app = FastAPI(
        title="AI Supported Shopping List API",
        version="1.0.0",
        lifespan=lifespan,
        # The contract is api/openapi.yaml; don't serve a second, generated one.
        openapi_url=None,
        docs_url=None,
        redoc_url=None,
        # A redirect would not be a JSON response.
        redirect_slashes=False,
    )

    app.state.settings = settings
    app.state.authenticator = authenticator
    app.state.repository = repository
    app.state.rate_limiter = RateLimiter(
        {
            Bucket.GENERAL: settings.rate_limit_general_per_minute,
            Bucket.AI: settings.rate_limit_ai_per_minute,
        }
    )
    if ai_client is None:
        ai_client = OllamaClient(
            settings.ollama_url, settings.ollama_model, settings.ollama_timeout_seconds
        )
    app.state.recommendation_service = RecommendationService(ai_client, settings.prompt_max_length)

    register_exception_handlers(app)

    # add_middleware puts each new middleware *outside* the previous ones, so this is
    # the order from innermost to outermost (see middleware.py).
    app.add_middleware(BodySizeLimitMiddleware, max_bytes=settings.max_body_bytes)
    app.add_middleware(ErrorGuardMiddleware)
    app.add_middleware(
        JSONCORSMiddleware,
        allow_origins=list(settings.cors_allowed_origins),
        allow_methods=["GET", "POST", "DELETE"],
        allow_headers=["Authorization", "Content-Type"],
        expose_headers=[
            "X-Request-ID",
            "RateLimit-Limit",
            "RateLimit-Remaining",
            "RateLimit-Reset",
            "Retry-After",
            "Location",
        ],
        max_age=600,
    )
    app.add_middleware(RequestContextMiddleware)

    routers = [health.router, items.router, recommendations.router]
    for router in routers:
        app.include_router(router, prefix=API_PREFIX)
    app.state.route_methods = RouteMethodIndex(API_PREFIX, routers)
    return app
