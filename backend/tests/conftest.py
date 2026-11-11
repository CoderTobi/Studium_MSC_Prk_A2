import base64
import json
from collections.abc import Callable
from typing import Any

import pytest
from fastapi.testclient import TestClient

from shopping_list.config import Settings
from shopping_list.main import create_app
from shopping_list.recommendations import AIClient
from tests.fakes import InMemoryItemRepository

ClientFactory = Callable[..., TestClient]


def _b64(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode()


def build_token(claims: Any) -> str:
    """Unsigned JWT-like token ``header.payload.sig``; the signature is never checked."""
    header = _b64(json.dumps({"alg": "none", "typ": "JWT"}).encode())
    return f"{header}.{_b64(json.dumps(claims).encode())}.sig"


@pytest.fixture
def make_token() -> Callable[[Any], str]:
    return build_token


@pytest.fixture
def auth() -> Callable[[str], dict[str, str]]:
    """``auth("alice")`` -> headers that make a request act as user ``alice``."""

    def headers(uid: str) -> dict[str, str]:
        return {"Authorization": f"Bearer {build_token({'sub': uid})}"}

    return headers


@pytest.fixture
def make_client() -> ClientFactory:
    """Factory: ``make_client(item_limit=3, ai_client=...)`` builds an app and its TestClient.

    Keyword arguments other than ``ai_client`` and ``raise_server_exceptions`` are
    ``Settings`` fields. The repository is available as ``client.app.state.repository``.
    """

    def factory(
        *,
        ai_client: AIClient | None = None,
        raise_server_exceptions: bool = False,
        **settings: Any,
    ) -> TestClient:
        cfg = Settings(auth_disabled=True, **settings)
        app = create_app(
            cfg, repository=InMemoryItemRepository(cfg.item_limit), ai_client=ai_client
        )
        return TestClient(app, raise_server_exceptions=raise_server_exceptions)

    return factory


@pytest.fixture
def client(make_client: ClientFactory) -> TestClient:
    return make_client()
