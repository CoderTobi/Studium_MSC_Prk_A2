"""Authentication: turns the ``Authorization`` header into the user's ``uid``.

The ``uid`` is the only user identity in the backend. It is never taken from a path,
query or body parameter.

Right now only the debug mode from the API description exists
(``UnverifiedTokenAuthenticator``). Firebase token verification will be added as a
second ``Authenticator`` implementation; until then the backend refuses to start
unless ``AUTH_DISABLED=true`` (see ``build_authenticator``).
"""

import base64
import binascii
import json
import re
from typing import Annotated, Protocol

from fastapi import Depends, Request

from shopping_list.config import ConfigError, Settings
from shopping_list.errors import ApiError, ErrorCode

DEBUG_UID = "debug-user"

_UID_MAX_LENGTH = 128
_RESERVED_ID = re.compile(r"^__.*__$", re.DOTALL)


def is_valid_uid(uid: object) -> bool:
    """Check that a uid is safe to use as a Firestore document ID.

    In debug mode the uid comes from an unverified token, so it must not be able to
    change the document path (for example ``victim/items/x``).
    """
    return (
        isinstance(uid, str)
        and 1 <= len(uid) <= _UID_MAX_LENGTH
        and "/" not in uid
        and uid not in {".", ".."}
        and not _RESERVED_ID.match(uid)
        and uid.isprintable()
    )


def _unauthenticated() -> ApiError:
    return ApiError(ErrorCode.UNAUTHENTICATED)


def _bearer_token(authorization: str) -> str:
    scheme, _, token = authorization.strip().partition(" ")
    token = token.strip()
    if scheme.lower() != "bearer" or not token:
        raise _unauthenticated()
    return token


class Authenticator(Protocol):
    def authenticate(self, authorization: str | None) -> str:
        """Return the uid for the given ``Authorization`` header or raise UNAUTHENTICATED."""
        ...


class UnverifiedTokenAuthenticator:
    """Debug mode: token signatures are NOT checked. Never use in production.

    * Bearer token present: its ``sub`` (Firebase: the uid) or ``user_id`` claim is
      decoded without verification, which allows testing with several users.
    * No ``Authorization`` header: the request belongs to ``DEBUG_UID``.
    """

    def authenticate(self, authorization: str | None) -> str:
        if authorization is None:
            return DEBUG_UID
        token = _bearer_token(authorization)
        parts = token.split(".")
        if len(parts) != 3:
            raise _unauthenticated()
        try:
            payload_b64 = parts[1] + "=" * (-len(parts[1]) % 4)
            claims = json.loads(base64.urlsafe_b64decode(payload_b64))
        except (binascii.Error, ValueError):
            raise _unauthenticated() from None
        if not isinstance(claims, dict):
            raise _unauthenticated()
        uid = claims.get("sub") or claims.get("user_id")
        if not is_valid_uid(uid):
            raise _unauthenticated()
        return uid


def build_authenticator(settings: Settings) -> Authenticator:
    if settings.auth_disabled:
        return UnverifiedTokenAuthenticator()
    raise ConfigError(
        "Firebase token verification is not implemented yet. "
        "Set AUTH_DISABLED=true to run the backend in debug mode."
    )


def get_current_uid(request: Request) -> str:
    """FastAPI dependency for every protected endpoint."""
    authenticator: Authenticator = request.app.state.authenticator
    return authenticator.authenticate(request.headers.get("authorization"))


CurrentUid = Annotated[str, Depends(get_current_uid)]
