import base64
import json

import pytest

from shopping_list.auth import DEBUG_UID, UnverifiedTokenAuthenticator, is_valid_uid
from shopping_list.config import ConfigError, Settings
from shopping_list.errors import ApiError, ErrorCode
from shopping_list.main import create_app


def b64(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode()


class TestIsValidUid:
    @pytest.mark.parametrize(
        "uid",
        ["debug-user", "x", "4kLzR0pQe9Sd8Vh2WbNnTjYuCaM3", "user@example.com", "ü-ß", "a" * 128],
    )
    def test_valid(self, uid):
        assert is_valid_uid(uid)

    @pytest.mark.parametrize(
        "uid",
        [
            "a/b",
            "/",
            ".",
            "..",
            "__x__",
            "____",
            "a" * 129,
            "",
            None,
            123,
            ["a"],
            "bad\nuid",
            "bad\x00uid",
            "tab\tuid",
        ],
    )
    def test_invalid(self, uid):
        assert not is_valid_uid(uid)

    def test_double_underscore_only_reserved_when_both_sides(self):
        assert is_valid_uid("__x")
        assert is_valid_uid("x__")
        assert is_valid_uid("a__b")


class TestAuthenticator:
    authenticator = UnverifiedTokenAuthenticator()

    def token(self, claims) -> str:
        return f"{b64(b'{}')}.{b64(json.dumps(claims).encode())}.sig"

    def assert_unauthenticated(self, header):
        with pytest.raises(ApiError) as exc:
            self.authenticator.authenticate(header)
        assert exc.value.code is ErrorCode.UNAUTHENTICATED

    def test_no_header_is_debug_user(self):
        assert self.authenticator.authenticate(None) == DEBUG_UID == "debug-user"

    def test_sub_claim(self):
        assert self.authenticator.authenticate(f"Bearer {self.token({'sub': 'alice'})}") == "alice"

    def test_user_id_claim(self):
        assert self.authenticator.authenticate(f"Bearer {self.token({'user_id': 'bob'})}") == "bob"

    def test_sub_wins_over_user_id(self):
        token = self.token({"sub": "alice", "user_id": "bob"})
        assert self.authenticator.authenticate(f"Bearer {token}") == "alice"

    def test_scheme_is_case_insensitive(self):
        assert self.authenticator.authenticate(f"bearer {self.token({'sub': 'a'})}") == "a"

    def test_padded_payload_is_accepted(self):
        payload = base64.urlsafe_b64encode(json.dumps({"sub": "alice"}).encode()).decode()
        assert self.authenticator.authenticate(f"Bearer h.{payload}.s") == "alice"

    @pytest.mark.parametrize(
        "header",
        [
            "",
            "Bearer",
            "Bearer ",
            "Bearer    ",
            "Basic dXNlcjpwYXNz",
            "Token abc.def.ghi",
            "abc.def.ghi",
            "Bearer notatoken",
            "Bearer a.b",
            "Bearer a.b.c.d",
            "Bearer a.!!!.c",
            "Bearer a.ü.c",
        ],
    )
    def test_malformed(self, header):
        self.assert_unauthenticated(header)

    def test_payload_not_json(self):
        self.assert_unauthenticated(f"Bearer h.{b64(b'not json')}.s")

    def test_payload_not_utf8(self):
        self.assert_unauthenticated(f"Bearer h.{b64(b'\xff\xfe')}.s")

    @pytest.mark.parametrize("claims", [["sub"], "sub", 42, None, True])
    def test_payload_json_but_not_object(self, claims):
        self.assert_unauthenticated(f"Bearer {self.token(claims)}")

    @pytest.mark.parametrize(
        "claims",
        [
            {},
            {"sub": ""},
            {"sub": None},
            {"sub": 5},
            {"sub": "a/b"},
            {"sub": ".."},
            {"sub": "__x__"},
        ],
    )
    def test_missing_or_invalid_claim(self, claims):
        self.assert_unauthenticated(f"Bearer {self.token(claims)}")


class TestOverHttp:
    @pytest.mark.parametrize(
        "header",
        [
            "Bearer",
            "Basic abc",
            "Bearer a.b",
            f"Bearer h.{b64(b'[]')}.s",
            f"Bearer h.{b64(b'{}')}.s",
        ],
    )
    def test_401_response(self, client, header):
        response = client.get("/api/v1/items", headers={"Authorization": header})
        assert response.status_code == 401
        assert response.headers["WWW-Authenticate"] == "Bearer"
        error = response.json()["error"]
        assert error["code"] == "UNAUTHENTICATED"
        assert error["requestId"] == response.headers["X-Request-ID"]

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
    def test_every_protected_endpoint_checks_auth(self, client, method, path):
        response = client.request(
            method, f"/api/v1{path}", headers={"Authorization": "Bearer nope"}, json={}
        )
        assert response.status_code == 401

    def test_unauthenticated_requests_are_not_counted_for_rate_limit(self, make_client):
        client = make_client(rate_limit_general_per_minute=1)
        for _ in range(3):
            assert client.get("/api/v1/items", headers={"Authorization": "x"}).status_code == 401
        assert client.get("/api/v1/items").status_code == 200


def test_auth_must_be_disabled_explicitly():
    with pytest.raises(ConfigError):
        create_app(Settings(auth_disabled=False))


def test_default_settings_do_not_start():
    with pytest.raises(ConfigError):
        create_app(Settings())
