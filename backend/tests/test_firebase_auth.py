"""Firebase ID token verification (``FirebaseTokenAuthenticator``, ``PublicKeyCache``).

Tokens are signed with locally generated RSA keys, so the real signature check runs.
Google's key endpoint is replaced by a fake fetcher, so no network is needed.
"""

import base64
import datetime
import io
import json
import logging
import time
from typing import Any

import google.auth
import pytest
from cryptography import x509
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.x509.oid import NameOID
from fastapi.testclient import TestClient
from google.auth import crypt
from google.auth import jwt as google_jwt
from google.auth.exceptions import DefaultCredentialsError

from shopping_list import auth as auth_module
from shopping_list.auth import (
    CLOCK_SKEW_SECONDS,
    FirebaseTokenAuthenticator,
    PublicKeyCache,
    UnverifiedTokenAuthenticator,
    build_authenticator,
    fetch_firebase_certs,
)
from shopping_list.config import ConfigError, Settings
from shopping_list.errors import ApiError, ErrorCode
from shopping_list.main import create_app

PROJECT_ID = "demo-shopping-list"
ISSUER = f"https://securetoken.google.com/{PROJECT_ID}"


class KeyPair:
    """An RSA key with a self-signed certificate, like the ones Google publishes."""

    def __init__(self, key_id: str) -> None:
        self.key_id = key_id
        key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
        self.private_pem = key.private_bytes(
            serialization.Encoding.PEM,
            serialization.PrivateFormat.PKCS8,
            serialization.NoEncryption(),
        ).decode()
        name = x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, "securetoken.test")])
        now = datetime.datetime.now(datetime.UTC)
        cert = (
            x509.CertificateBuilder()
            .subject_name(name)
            .issuer_name(name)
            .public_key(key.public_key())
            .serial_number(x509.random_serial_number())
            .not_valid_before(now - datetime.timedelta(days=1))
            .not_valid_after(now + datetime.timedelta(days=1))
            .sign(key, hashes.SHA256())
        )
        self.cert_pem = cert.public_bytes(serialization.Encoding.PEM).decode()

    def sign(self, claims: dict[str, Any], key_id: str | None = None) -> str:
        signer = crypt.RSASigner.from_string(self.private_pem, key_id or self.key_id)
        return google_jwt.encode(signer, claims).decode()


# Key generation is slow, so the keys are shared by all tests.
KEY = KeyPair("key-1")
OTHER_KEY = KeyPair("key-2")


# Marker for valid_claims(): leave this claim out.
_DROP = object()


def valid_claims(**overrides: Any) -> dict[str, Any]:
    now = int(time.time())
    claims: dict[str, Any] = {
        "iss": ISSUER,
        "aud": PROJECT_ID,
        "auth_time": now - 60,
        "user_id": "alice-uid",
        "sub": "alice-uid",
        "iat": now - 10,
        "exp": now + 3600,
        "firebase": {"identities": {}, "sign_in_provider": "password"},
    }
    claims.update(overrides)
    return {k: v for k, v in claims.items() if v is not _DROP}


def b64(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode()


class FakeFetcher:
    """Stands in for ``fetch_firebase_certs``. Counts calls, can fail on demand."""

    def __init__(self, certs: dict[str, str] | None = None, max_age: int = 3600) -> None:
        self.certs = {KEY.key_id: KEY.cert_pem} if certs is None else certs
        self.max_age = max_age
        self.calls = 0
        self.error: Exception | None = None

    def __call__(self) -> tuple[dict[str, str], int]:
        self.calls += 1
        if self.error is not None:
            raise self.error
        return dict(self.certs), self.max_age


class FakeClock:
    def __init__(self) -> None:
        self.now = 1000.0

    def __call__(self) -> float:
        return self.now


@pytest.fixture
def fetcher() -> FakeFetcher:
    return FakeFetcher()


@pytest.fixture
def clock() -> FakeClock:
    return FakeClock()


@pytest.fixture
def authenticator(fetcher: FakeFetcher, clock: FakeClock) -> FirebaseTokenAuthenticator:
    return FirebaseTokenAuthenticator(PROJECT_ID, PublicKeyCache(fetcher, clock=clock))


def bearer(token: str) -> str:
    return f"Bearer {token}"


def assert_rejected(authenticator: FirebaseTokenAuthenticator, header: str | None) -> None:
    with pytest.raises(ApiError) as exc:
        authenticator.authenticate(header)
    assert exc.value.code is ErrorCode.UNAUTHENTICATED


class TestValidTokens:
    def test_valid_token_gives_sub_as_uid(self, authenticator):
        assert authenticator.authenticate(bearer(KEY.sign(valid_claims()))) == "alice-uid"

    def test_scheme_is_case_insensitive(self, authenticator):
        assert authenticator.authenticate(f"bearer {KEY.sign(valid_claims())}") == "alice-uid"

    def test_small_clock_skew_is_tolerated(self, authenticator):
        now = int(time.time())
        claims = valid_claims(iat=now + CLOCK_SKEW_SECONDS - 3, auth_time=now)
        assert authenticator.authenticate(bearer(KEY.sign(claims))) == "alice-uid"

    def test_keys_are_cached(self, authenticator, fetcher):
        for _ in range(3):
            authenticator.authenticate(bearer(KEY.sign(valid_claims())))
        assert fetcher.calls == 1


class TestRejectedTokens:
    def test_missing_header_is_rejected(self, authenticator):
        # Unlike debug mode, there is no fallback user.
        assert_rejected(authenticator, None)

    @pytest.mark.parametrize(
        "header", ["", "Bearer", "Bearer   ", "Basic dXNlcjpwYXNz", "Token x.y.z", "x.y.z"]
    )
    def test_malformed_header(self, authenticator, header):
        assert_rejected(authenticator, header)

    @pytest.mark.parametrize(
        "token",
        ["notatoken", "a.b", "a.b.c.d", "a.!!!.c", f"{b64(b'[]')}.{b64(b'{}')}.c", "ü.ü.ü"],
    )
    def test_malformed_token(self, authenticator, token):
        assert_rejected(authenticator, bearer(token))

    def test_too_long_token(self, authenticator):
        assert_rejected(authenticator, bearer(KEY.sign(valid_claims(pad="x" * 9000))))

    def test_expired(self, authenticator):
        now = int(time.time())
        claims = valid_claims(iat=now - 7200, exp=now - 3600, auth_time=now - 7200)
        assert_rejected(authenticator, bearer(KEY.sign(claims)))

    def test_issued_in_the_future(self, authenticator):
        now = int(time.time())
        claims = valid_claims(iat=now + 600, exp=now + 4200)
        assert_rejected(authenticator, bearer(KEY.sign(claims)))

    @pytest.mark.parametrize("claim", ["iat", "exp", "auth_time", "aud", "iss", "sub"])
    def test_missing_claim(self, authenticator, claim):
        assert_rejected(authenticator, bearer(KEY.sign(valid_claims(**{claim: _DROP}))))

    @pytest.mark.parametrize("aud", ["other-project", "", [PROJECT_ID], f"{PROJECT_ID}x", None])
    def test_wrong_audience(self, authenticator, aud):
        assert_rejected(authenticator, bearer(KEY.sign(valid_claims(aud=aud))))

    @pytest.mark.parametrize(
        "iss",
        [
            "https://securetoken.google.com/other-project",
            f"http://securetoken.google.com/{PROJECT_ID}",
            "https://accounts.google.com",
            PROJECT_ID,
        ],
    )
    def test_wrong_issuer(self, authenticator, iss):
        assert_rejected(authenticator, bearer(KEY.sign(valid_claims(iss=iss))))

    @pytest.mark.parametrize("auth_time", [int(time.time()) + 600, "yesterday", True, None])
    def test_invalid_auth_time(self, authenticator, auth_time):
        assert_rejected(authenticator, bearer(KEY.sign(valid_claims(auth_time=auth_time))))

    @pytest.mark.parametrize("sub", ["", "a/b", "..", "__x__", "a" * 129, 42, None])
    def test_invalid_sub(self, authenticator, sub):
        assert_rejected(authenticator, bearer(KEY.sign(valid_claims(sub=sub))))

    def test_user_id_claim_is_not_used_as_fallback(self, authenticator):
        claims = valid_claims(sub=_DROP, user_id="alice-uid")
        assert_rejected(authenticator, bearer(KEY.sign(claims)))

    def test_signed_by_unknown_key_with_known_key_id(self, authenticator):
        assert_rejected(authenticator, bearer(OTHER_KEY.sign(valid_claims(), key_id=KEY.key_id)))

    def test_tampered_payload(self, authenticator):
        header, _, signature = KEY.sign(valid_claims()).split(".")
        forged = b64(json.dumps(valid_claims(sub="mallory")).encode())
        assert_rejected(authenticator, bearer(f"{header}.{forged}.{signature}"))

    def test_signature_stripped(self, authenticator):
        header, payload, _ = KEY.sign(valid_claims()).split(".")
        assert_rejected(authenticator, bearer(f"{header}.{payload}."))

    @pytest.mark.parametrize(
        "header",
        [
            {"alg": "none", "kid": KEY.key_id},
            {"alg": "HS256", "kid": KEY.key_id},
            {"alg": "ES256", "kid": KEY.key_id},
            {"alg": "RS256"},
            {"alg": "RS256", "kid": 1},
            {"alg": "RS256", "kid": ""},
        ],
    )
    def test_wrong_header(self, authenticator, header):
        _, payload, signature = KEY.sign(valid_claims()).split(".")
        token = f"{b64(json.dumps(header).encode())}.{payload}.{signature}"
        assert_rejected(authenticator, bearer(token))

    def test_debug_token_is_rejected(self, authenticator, make_token):
        # The unsigned tokens that work in debug mode must not work here.
        assert_rejected(authenticator, bearer(make_token({"sub": "alice"})))

    def test_rejection_is_logged_without_the_token(self, authenticator, app_logs):
        token = KEY.sign(valid_claims(aud="other-project"))
        assert_rejected(authenticator, bearer(token))
        assert "Rejected ID token" in app_logs.text
        for part in token.split("."):
            assert part not in app_logs.text


class TestPublicKeyCache:
    def test_refetch_after_max_age(self, fetcher, clock):
        fetcher.max_age = 600
        keys = PublicKeyCache(fetcher, clock=clock)
        assert keys.get(KEY.key_id) == KEY.cert_pem
        clock.now += 599
        keys.get(KEY.key_id)
        assert fetcher.calls == 1
        clock.now += 1
        keys.get(KEY.key_id)
        assert fetcher.calls == 2

    @pytest.mark.parametrize(("max_age", "expected"), [(0, 60), (10**9, 24 * 3600)])
    def test_max_age_is_clamped(self, fetcher, clock, max_age, expected):
        fetcher.max_age = max_age
        keys = PublicKeyCache(fetcher, clock=clock)
        keys.get(KEY.key_id)
        clock.now += expected - 1
        keys.get(KEY.key_id)
        assert fetcher.calls == 1
        clock.now += 1
        keys.get(KEY.key_id)
        assert fetcher.calls == 2

    def test_key_rotation(self, fetcher, clock):
        keys = PublicKeyCache(fetcher, clock=clock)
        authenticator = FirebaseTokenAuthenticator(PROJECT_ID, keys)
        authenticator.authenticate(bearer(KEY.sign(valid_claims())))

        # Google publishes a new key before the cached keys expire.
        fetcher.certs = {KEY.key_id: KEY.cert_pem, OTHER_KEY.key_id: OTHER_KEY.cert_pem}
        clock.now += 60
        token = OTHER_KEY.sign(valid_claims())
        assert authenticator.authenticate(bearer(token)) == "alice-uid"
        assert fetcher.calls == 2

    def test_unknown_key_ids_refetch_at_most_every_30_seconds(self, fetcher, clock):
        keys = PublicKeyCache(fetcher, clock=clock)
        assert keys.get("unknown") is None
        for _ in range(5):
            clock.now += 5
            assert keys.get("unknown") is None
        assert fetcher.calls == 1
        clock.now += 5
        keys.get("unknown")
        assert fetcher.calls == 2

    def test_no_keys_at_all_is_an_internal_error(self, fetcher, clock):
        fetcher.error = OSError("network down")
        keys = PublicKeyCache(fetcher, clock=clock)
        for _ in range(3):
            with pytest.raises(ApiError) as exc:
                keys.get(KEY.key_id)
            assert exc.value.code is ErrorCode.INTERNAL_ERROR
        assert fetcher.calls == 1  # no new attempt within 30 seconds

        clock.now += 30
        fetcher.error = None
        assert keys.get(KEY.key_id) == KEY.cert_pem

    def test_failed_refresh_keeps_the_cached_keys(self, fetcher, clock, app_logs):
        fetcher.max_age = 60
        keys = PublicKeyCache(fetcher, clock=clock)
        keys.get(KEY.key_id)
        clock.now += 60
        fetcher.error = OSError("network down")
        assert keys.get(KEY.key_id) == KEY.cert_pem
        assert "using the cached keys" in app_logs.text


class FakeResponse(io.BytesIO):
    def __init__(self, body: bytes, cache_control: str | None) -> None:
        super().__init__(body)
        self.headers = {} if cache_control is None else {"Cache-Control": cache_control}


class TestFetchFirebaseCerts:
    @pytest.fixture
    def serve(self, monkeypatch):
        def serve(body: bytes, cache_control: str | None = None) -> list[Any]:
            requests: list[Any] = []

            def urlopen(request, timeout):
                requests.append((request, timeout))
                return FakeResponse(body, cache_control)

            monkeypatch.setattr(auth_module.urllib.request, "urlopen", urlopen)
            return requests

        return serve

    def test_parses_certs_and_max_age(self, serve):
        requests = serve(
            json.dumps({"k": "PEM"}).encode(), "public, max-age=19302, must-revalidate"
        )
        assert fetch_firebase_certs() == ({"k": "PEM"}, 19302)
        [(request, timeout)] = requests
        assert request.full_url == auth_module.FIREBASE_CERTS_URL
        assert timeout > 0

    def test_default_max_age(self, serve):
        serve(json.dumps({"k": "PEM"}).encode())
        assert fetch_firebase_certs() == ({"k": "PEM"}, 3600)

    @pytest.mark.parametrize(
        "body",
        [b"not json", b"[]", b"{}", b'{"k": 1}', json.dumps({"k": "x" * 70_000}).encode()],
    )
    def test_invalid_responses_raise(self, serve, body):
        serve(body)
        with pytest.raises(ValueError):
            fetch_firebase_certs()


class TestOverHttp:
    @pytest.fixture
    def firebase_client(self, make_client, authenticator):
        return make_client(authenticator=authenticator)

    def test_valid_token(self, firebase_client):
        headers = {"Authorization": bearer(KEY.sign(valid_claims()))}
        created = firebase_client.post("/api/v1/items", headers=headers, json={"name": "Milk"})
        assert created.status_code == 201
        response = firebase_client.get("/api/v1/items", headers=headers)
        assert response.status_code == 200
        assert [item["name"] for item in response.json()["items"]] == ["Milk"]
        repository = firebase_client.app.state.repository
        assert [item.name for item in repository.list_items("alice-uid")] == ["Milk"]

    def test_users_are_isolated(self, firebase_client):
        alice = {"Authorization": bearer(KEY.sign(valid_claims()))}
        bob = {"Authorization": bearer(KEY.sign(valid_claims(sub="bob-uid", user_id="bob-uid")))}
        firebase_client.post("/api/v1/items", headers=alice, json={"name": "Milk"})
        assert firebase_client.get("/api/v1/items", headers=bob).json() == {"items": []}

    @pytest.mark.parametrize(
        ("method", "path"),
        [
            ("GET", "/items"),
            ("POST", "/items"),
            ("POST", "/items/batch"),
            ("DELETE", "/items/x"),
            ("POST", "/recommendations"),
        ],
    )
    def test_protected_endpoints_need_a_token(self, firebase_client, method, path):
        response = firebase_client.request(method, f"/api/v1{path}", json={})
        assert response.status_code == 401
        assert response.headers["WWW-Authenticate"] == "Bearer"
        assert response.json()["error"]["code"] == "UNAUTHENTICATED"

    def test_expired_token(self, firebase_client):
        now = int(time.time())
        claims = valid_claims(iat=now - 7200, exp=now - 3600, auth_time=now - 7200)
        response = firebase_client.get(
            "/api/v1/items", headers={"Authorization": bearer(KEY.sign(claims))}
        )
        assert response.status_code == 401

    def test_health_needs_no_token(self, firebase_client):
        assert firebase_client.get("/api/v1/health").status_code == 200

    def test_unavailable_keys_give_500(self, make_client, fetcher):
        fetcher.error = OSError("network down")
        authenticator = FirebaseTokenAuthenticator(PROJECT_ID, PublicKeyCache(fetcher))
        client = make_client(authenticator=authenticator)
        response = client.get(
            "/api/v1/items", headers={"Authorization": bearer(KEY.sign(valid_claims()))}
        )
        assert response.status_code == 500
        assert response.json()["error"]["code"] == "INTERNAL_ERROR"


class TestBuildAuthenticator:
    def test_auth_disabled_gives_debug_mode(self):
        assert isinstance(
            build_authenticator(Settings(auth_disabled=True)), UnverifiedTokenAuthenticator
        )

    def test_project_from_settings(self, monkeypatch):
        def fail():
            raise AssertionError("must not look up the default credentials")

        monkeypatch.setattr(google.auth, "default", fail)
        authenticator = build_authenticator(Settings(google_cloud_project=PROJECT_ID))
        assert isinstance(authenticator, FirebaseTokenAuthenticator)
        assert authenticator.project_id == PROJECT_ID

    def test_project_from_credentials(self, monkeypatch):
        monkeypatch.setattr(google.auth, "default", lambda: (object(), "from-key-file"))
        authenticator = build_authenticator(Settings())
        assert isinstance(authenticator, FirebaseTokenAuthenticator)
        assert authenticator.project_id == "from-key-file"

    def test_no_credentials_refuses_to_start(self, monkeypatch):
        def no_credentials():
            raise DefaultCredentialsError("none")

        monkeypatch.setattr(google.auth, "default", no_credentials)
        with pytest.raises(ConfigError, match="GOOGLE_CLOUD_PROJECT"):
            create_app(Settings())

    def test_credentials_without_project_refuse_to_start(self, monkeypatch):
        monkeypatch.setattr(google.auth, "default", lambda: (object(), None))
        with pytest.raises(ConfigError, match="GOOGLE_CLOUD_PROJECT"):
            create_app(Settings())

    def test_startup_log_names_the_project(self, app_logs):
        app = create_app(
            Settings(google_cloud_project=PROJECT_ID),
            repository=object(),  # type: ignore[arg-type]
            ai_client=object(),  # type: ignore[arg-type]
        )
        with TestClient(app):
            pass
        assert f"Verifying Firebase ID tokens for project {PROJECT_ID!r}" in app_logs.text
        assert "DISABLED" not in app_logs.text
        assert not any(r.levelno >= logging.WARNING for r in app_logs.records)
