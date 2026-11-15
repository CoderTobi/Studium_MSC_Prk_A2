"""Authentication: turns the ``Authorization`` header into the user's ``uid``.

The ``uid`` is the only user identity in the backend. It is never taken from a path,
query or body parameter.

``build_authenticator`` picks one of two ``Authenticator`` implementations at startup:

* ``FirebaseTokenAuthenticator`` (default): verifies Firebase ID tokens. The checks are
  the ones Firebase documents for verifying ID tokens without the Admin SDK
  (https://firebase.google.com/docs/auth/admin/verify-id-tokens): RS256 signature by
  one of Google's published keys, ``exp``/``iat``/``auth_time``, ``aud`` = project ID,
  ``iss`` = ``https://securetoken.google.com/<project ID>``, and ``sub`` as the uid.
  It uses ``google-auth``, which the Firestore client already depends on, so it adds no
  dependency. The Firebase Admin SDK would pull in many more packages.
* ``UnverifiedTokenAuthenticator`` (``AUTH_DISABLED=true``): debug mode, nothing is
  verified.

Token revocation is not checked. Revocation would need an extra call to Firebase on every
request. A revoked ID token stays valid until it expires, which is at most one hour
after it was issued.
"""

import base64
import binascii
import json
import math
import re
import threading
import time
import urllib.request
from collections.abc import Callable
from typing import Annotated, NoReturn, Protocol

import google.auth
from fastapi import Depends, Request
from google.auth import jwt as google_jwt
from google.auth.exceptions import GoogleAuthError

from shopping_list.config import ConfigError, Settings
from shopping_list.errors import ApiError, ErrorCode
from shopping_list.logging_setup import get_logger

logger = get_logger("auth")

DEBUG_UID = "debug-user"

_UID_MAX_LENGTH = 128
_RESERVED_ID = re.compile(r"^__.*__$", re.DOTALL)

# Google's public keys for Firebase ID tokens: {"key id": "PEM X.509 certificate"}.
FIREBASE_CERTS_URL = (
    "https://www.googleapis.com/robot/v1/metadata/x509/securetoken@system.gserviceaccount.com"
)
FIREBASE_ISSUER_PREFIX = "https://securetoken.google.com/"

# Allowed difference between our clock and Google's for exp, iat and auth_time.
CLOCK_SKEW_SECONDS = 10

# Firebase ID tokens are about 1 KB. Custom claims add at most 1000 bytes.
_TOKEN_MAX_LENGTH = 8 * 1024

_CERTS_MAX_BYTES = 64 * 1024
_CERTS_FETCH_TIMEOUT_SECONDS = 5
# Used when the response has no Cache-Control max-age. Google currently sends ~6 h.
_CERTS_DEFAULT_MAX_AGE = 3600
_CERTS_MIN_MAX_AGE = 60
_CERTS_MAX_MAX_AGE = 24 * 3600
# The keys are fetched at most once per this many seconds after a failed fetch or
# for a token with an unknown key ID, so bad tokens can't trigger a fetch every time.
_CERTS_RETRY_SECONDS = 30
_MAX_AGE = re.compile(r"(?:^|,)\s*max-age\s*=\s*(\d+)", re.IGNORECASE)


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


CertsFetcher = Callable[[], tuple[dict[str, str], int]]


def fetch_firebase_certs() -> tuple[dict[str, str], int]:
    """Download Google's public keys. Returns ``(certs by key ID, max-age in seconds)``.

    Uses only the standard library. Raises on network, HTTP or format errors.
    """
    request = urllib.request.Request(FIREBASE_CERTS_URL, headers={"Accept": "application/json"})
    with urllib.request.urlopen(request, timeout=_CERTS_FETCH_TIMEOUT_SECONDS) as response:
        body = response.read(_CERTS_MAX_BYTES + 1)
        cache_control = response.headers.get("Cache-Control", "")
    if len(body) > _CERTS_MAX_BYTES:
        raise ValueError("Firebase public key response is too large")
    certs = json.loads(body)
    if (
        not isinstance(certs, dict)
        or not certs
        or not all(isinstance(k, str) and isinstance(v, str) for k, v in certs.items())
    ):
        raise ValueError("Firebase public key response has an unexpected format")
    match = _MAX_AGE.search(cache_control)
    max_age = int(match.group(1)) if match else _CERTS_DEFAULT_MAX_AGE
    return certs, max_age


class PublicKeyCache:
    """Google's public keys for Firebase ID tokens, cached as long as Cache-Control allows.

    Google rotates the keys regularly. A token with a key ID that isn't cached triggers
    a refresh, at most once per ``_CERTS_RETRY_SECONDS``. If a refresh fails, the keys
    that are already cached are still used. Without any keys, tokens can't be
    verified, so the request fails with ``INTERNAL_ERROR`` instead of a misleading 401.
    """

    def __init__(
        self,
        fetch: CertsFetcher = fetch_firebase_certs,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        self._fetch = fetch
        self._clock = clock
        self._certs: dict[str, str] = {}
        self._expires_at = -math.inf
        self._last_fetch_at = -math.inf
        self._lock = threading.Lock()

    def get(self, key_id: str) -> str | None:
        """The certificate for ``key_id``, or ``None`` if Google doesn't publish it."""
        with self._lock:
            now = self._clock()
            expired = now >= self._expires_at
            unknown = (
                key_id not in self._certs and now - self._last_fetch_at >= _CERTS_RETRY_SECONDS
            )
            if expired or unknown:
                self._refresh(now)
            if not self._certs:
                raise ApiError(ErrorCode.INTERNAL_ERROR)
            return self._certs.get(key_id)

    def _refresh(self, now: float) -> None:
        self._last_fetch_at = now
        try:
            certs, max_age = self._fetch()
        except Exception as exc:  # network, HTTP or format error
            logger.warning(
                "Could not fetch the Firebase public keys (%s)%s",
                type(exc).__name__,
                ", using the cached keys" if self._certs else "",
            )
            self._expires_at = now + _CERTS_RETRY_SECONDS
            return
        self._certs = dict(certs)
        self._expires_at = now + min(max(max_age, _CERTS_MIN_MAX_AGE), _CERTS_MAX_MAX_AGE)
        logger.debug("Fetched %d Firebase public keys", len(self._certs))


def _is_number(value: object) -> bool:
    return isinstance(value, int | float) and not isinstance(value, bool)


class FirebaseTokenAuthenticator:
    """Verifies Firebase ID tokens. A missing token is rejected."""

    def __init__(
        self,
        project_id: str,
        keys: PublicKeyCache | None = None,
        clock: Callable[[], float] = time.time,
    ) -> None:
        self.project_id = project_id
        self._issuer = FIREBASE_ISSUER_PREFIX + project_id
        self._keys = keys or PublicKeyCache()
        self._clock = clock

    def authenticate(self, authorization: str | None) -> str:
        if authorization is None:
            self._reject("no Authorization header")
        token = _bearer_token(authorization)
        if len(token) > _TOKEN_MAX_LENGTH:
            self._reject("token too long")

        try:
            header = google_jwt.decode_header(token)
        except (GoogleAuthError, ValueError, TypeError):
            self._reject("malformed token")
        if header.get("alg") != "RS256":
            self._reject("wrong algorithm")
        key_id = header.get("kid")
        if not isinstance(key_id, str) or not key_id:
            self._reject("no key ID")
        cert = self._keys.get(key_id)
        if cert is None:
            self._reject("unknown key ID")

        try:
            # Checks the signature, exp, iat and aud.
            claims = google_jwt.decode(
                token,
                certs={key_id: cert},
                audience=self.project_id,
                clock_skew_in_seconds=CLOCK_SKEW_SECONDS,
            )
        except (GoogleAuthError, ValueError, TypeError) as exc:
            # Never log the exception message: some of them contain the token.
            self._reject(f"signature, expiry or audience check failed ({type(exc).__name__})")

        if claims.get("iss") != self._issuer:
            self._reject("wrong issuer")
        auth_time = claims.get("auth_time")
        if not _is_number(auth_time) or auth_time > self._clock() + CLOCK_SKEW_SECONDS:
            self._reject("missing or future auth_time")
        uid = claims.get("sub")
        if not is_valid_uid(uid):
            self._reject("missing or invalid sub")
        return uid

    @staticmethod
    def _reject(reason: str) -> NoReturn:
        logger.info("Rejected ID token: %s", reason)
        raise _unauthenticated()


def resolve_project_id(settings: Settings) -> str:
    """The Firebase project ID: ``GOOGLE_CLOUD_PROJECT``, else the one of the credentials.

    With ``GOOGLE_APPLICATION_CREDENTIALS`` pointing to the service account key, the
    project comes from the key file. Firebase and Google Cloud share the project ID.
    """
    if settings.google_cloud_project:
        return settings.google_cloud_project
    try:
        _, project_id = google.auth.default()
    except GoogleAuthError as exc:
        raise ConfigError(
            "Could not determine the Firebase project ID for token verification. Set "
            "GOOGLE_CLOUD_PROJECT or GOOGLE_APPLICATION_CREDENTIALS."
        ) from exc
    if not project_id:
        raise ConfigError(
            "The credentials don't name a Firebase project. Set GOOGLE_CLOUD_PROJECT."
        )
    return project_id


def build_authenticator(settings: Settings) -> Authenticator:
    if settings.auth_disabled:
        return UnverifiedTokenAuthenticator()
    return FirebaseTokenAuthenticator(resolve_project_id(settings))


def get_current_uid(request: Request) -> str:
    """FastAPI dependency for every protected endpoint."""
    authenticator: Authenticator = request.app.state.authenticator
    return authenticator.authenticate(request.headers.get("authorization"))


CurrentUid = Annotated[str, Depends(get_current_uid)]
