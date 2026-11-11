import asyncio

import pytest
from fastapi.testclient import TestClient

from shopping_list.config import Settings
from shopping_list.errors import ApiError, field_errors
from shopping_list.main import create_app
from shopping_list.middleware import BodySizeLimitMiddleware
from tests.fakes import InMemoryItemRepository

ORIGIN = "http://localhost:5173"


def assert_error(response, status, code):
    assert response.status_code == status
    assert response.headers["content-type"].startswith("application/json")
    error = response.json()["error"]
    assert error["code"] == code
    assert error["message"]
    assert error["requestId"] == response.headers["X-Request-ID"]
    return error


class TestFrameworkErrors:
    def test_unknown_route(self, client):
        assert_error(client.get("/nope"), 404, "NOT_FOUND")

    def test_unknown_route_under_prefix(self, client):
        assert_error(client.get("/api/v1/nope"), 404, "NOT_FOUND")

    def test_wrong_method(self, client):
        response = client.put("/api/v1/items")
        assert_error(response, 405, "METHOD_NOT_ALLOWED")
        assert "GET" in response.headers["Allow"]

    def test_allow_header_lists_all_methods(self, client):
        allowed = {m.strip() for m in client.put("/api/v1/items").headers["Allow"].split(",")}
        assert {"GET", "POST"} <= allowed

    def test_wrong_method_on_health(self, client):
        response = client.post("/api/v1/health")
        assert_error(response, 405, "METHOD_NOT_ALLOWED")
        assert "GET" in response.headers["Allow"]

    @pytest.mark.parametrize("path", ["/api/v1/items/", "/api/v1/health/", "/api/v1/items/batch/"])
    def test_trailing_slash_is_not_redirected(self, client, path):
        response = client.get(path, follow_redirects=False)
        assert_error(response, 404, "NOT_FOUND")

    def test_no_openapi_or_docs_served(self, client):
        for path in ("/openapi.json", "/docs", "/redoc"):
            assert_error(client.get(path), 404, "NOT_FOUND")


class TestMediaType:
    URL = "/api/v1/items"

    def test_text_plain(self, client):
        response = client.post(
            self.URL, content=b'{"name":"x"}', headers={"Content-Type": "text/plain"}
        )
        assert_error(response, 415, "UNSUPPORTED_MEDIA_TYPE")

    def test_form_data(self, client):
        assert_error(client.post(self.URL, data={"name": "x"}), 415, "UNSUPPORTED_MEDIA_TYPE")

    def test_missing_content_type(self, client):
        response = client.post(self.URL, content=b'{"name":"x"}')
        assert_error(response, 415, "UNSUPPORTED_MEDIA_TYPE")

    def test_batch_and_recommendations(self, client):
        for url in ("/api/v1/items/batch", "/api/v1/recommendations"):
            response = client.post(url, content=b"{}", headers={"Content-Type": "text/plain"})
            assert_error(response, 415, "UNSUPPORTED_MEDIA_TYPE")


class TestBodySize:
    URL = "/api/v1/items"

    def test_content_length_too_large(self, make_client):
        client = make_client(max_body_bytes=100)
        response = client.post(self.URL, json={"name": "a" * 99, "source": "manual"})
        assert_error(response, 413, "PAYLOAD_TOO_LARGE")

    def test_small_body_is_fine(self, make_client):
        client = make_client(max_body_bytes=100)
        assert client.post(self.URL, json={"name": "a"}).status_code == 201

    def test_default_limit_is_16_kib(self, client):
        assert_error(
            client.post(
                self.URL,
                content=b" " * (16 * 1024 + 1),
                headers={"Content-Type": "application/json"},
            ),
            413,
            "PAYLOAD_TOO_LARGE",
        )

    def test_streamed_body_without_content_length(self, make_client):
        client = make_client(max_body_bytes=100)

        def chunks():
            for _ in range(10):
                yield b" " * 50

        response = client.post(
            self.URL, content=chunks(), headers={"Content-Type": "application/json"}
        )
        assert_error(response, 413, "PAYLOAD_TOO_LARGE")

    def test_streamed_body_with_middleware_directly(self):
        sent: list[dict] = []
        read: list[bytes] = []

        async def app(scope, receive, send):
            try:
                while True:
                    message = await receive()
                    read.append(message.get("body", b""))
                    if not message.get("more_body"):
                        break
            except ApiError:
                await send({"type": "http.response.start", "status": 413, "headers": []})
                await send({"type": "http.response.body", "body": b""})
                return
            await send({"type": "http.response.start", "status": 200, "headers": []})
            await send({"type": "http.response.body", "body": b"ok"})

        middleware = BodySizeLimitMiddleware(app, max_bytes=10)
        messages = iter(
            [
                {"type": "http.request", "body": b"123456", "more_body": True},
                {"type": "http.request", "body": b"789012", "more_body": False},
            ]
        )

        async def receive():
            return next(messages)

        async def send(message):
            sent.append(message)

        scope = {"type": "http", "method": "POST", "path": "/", "headers": []}
        asyncio.run(middleware(scope, receive, send))
        assert sent[0]["status"] == 413

    def test_invalid_content_length_does_not_crash_middleware(self, make_client):
        client = make_client(max_body_bytes=100)
        response = client.post(self.URL, json={"name": "a"}, headers={"Content-Length": "abc"})
        assert response.status_code != 500


class TestInternalError:
    @pytest.fixture
    def boom_client(self):
        settings = Settings(auth_disabled=True)
        app = create_app(settings, repository=InMemoryItemRepository())

        @app.get("/boom")
        def boom():
            raise RuntimeError("secret internal detail /etc/passwd")

        return TestClient(app, raise_server_exceptions=False)

    def test_500_is_generic_json(self, boom_client):
        response = boom_client.get("/boom")
        error = assert_error(response, 500, "INTERNAL_ERROR")
        assert "secret" not in response.text
        assert "RuntimeError" not in response.text
        assert "Traceback" not in response.text
        assert error["message"] == "Something went wrong. Please try again later."

    def test_500_has_cors_headers(self, boom_client):
        response = boom_client.get("/boom", headers={"Origin": ORIGIN})
        assert response.headers["access-control-allow-origin"] == ORIGIN

    def test_repository_failure_is_500(self, make_client):
        client = make_client()

        def fail(uid):
            raise ConnectionError("firestore down: secret-host")

        client.app.state.repository.list_items = fail
        response = client.get("/api/v1/items")
        assert_error(response, 500, "INTERNAL_ERROR")
        assert "secret-host" not in response.text

    def test_app_keeps_working_after_a_500(self, boom_client):
        boom_client.get("/boom")
        assert boom_client.get("/api/v1/health").status_code == 200


class TestRequestId:
    def test_every_response_has_a_unique_id(self, client):
        ids = {client.get("/api/v1/health").headers["X-Request-ID"] for _ in range(3)}
        assert len(ids) == 3

    def test_client_supplied_id_is_ignored(self, client):
        response = client.get("/nope", headers={"X-Request-ID": "attacker-chosen"})
        assert response.headers["X-Request-ID"] != "attacker-chosen"
        assert "attacker-chosen" not in response.text

    @pytest.mark.parametrize(
        ("method", "path", "kwargs", "status"),
        [
            ("GET", "/api/v1/nope", {}, 404),
            ("PUT", "/api/v1/items", {}, 405),
            ("GET", "/api/v1/items", {"headers": {"Authorization": "Bearer x"}}, 401),
            ("POST", "/api/v1/items", {"json": {"name": ""}}, 400),
            ("DELETE", "/api/v1/items/missing", {}, 404),
            ("POST", "/api/v1/recommendations", {"json": {"prompt": "a"}}, 503),
        ],
    )
    def test_error_body_matches_header(self, client, method, path, kwargs, status):
        response = client.request(method, path, **kwargs)
        error = assert_error(response, status, response.json()["error"]["code"])
        assert set(error) <= {"code", "message", "requestId", "details", "retryAfterSeconds"}
        assert len(error["requestId"]) <= 64


class TestCors:
    URL = "/api/v1/items"

    def preflight(self, client, origin, method="POST"):
        return client.options(
            self.URL,
            headers={
                "Origin": origin,
                "Access-Control-Request-Method": method,
                "Access-Control-Request-Headers": "authorization,content-type",
            },
        )

    def test_allowed_origin(self, client):
        response = self.preflight(client, ORIGIN)
        assert response.status_code == 204
        assert response.content == b""
        assert response.headers["access-control-allow-origin"] == ORIGIN
        assert "POST" in response.headers["access-control-allow-methods"]
        allow_headers = response.headers["access-control-allow-headers"].lower()
        assert "authorization" in allow_headers
        assert "content-type" in allow_headers

    def test_delete_is_allowed(self, client):
        assert self.preflight(client, ORIGIN, "DELETE").status_code == 204

    def test_disallowed_method(self, client):
        response = self.preflight(client, ORIGIN, "PUT")
        assert_error(response, 400, "VALIDATION_ERROR")

    def test_disallowed_origin(self, client):
        response = self.preflight(client, "https://evil.example")
        assert_error(response, 400, "VALIDATION_ERROR")
        assert "access-control-allow-origin" not in response.headers

    def test_configured_origins(self, make_client):
        client = make_client(cors_allowed_origins=("https://app.example",))
        assert self.preflight(client, "https://app.example").status_code == 204
        assert self.preflight(client, ORIGIN).status_code == 400

    def test_simple_request_exposes_headers(self, client):
        response = client.get(self.URL, headers={"Origin": ORIGIN})
        assert response.headers["access-control-allow-origin"] == ORIGIN
        exposed = {
            h.strip().lower() for h in response.headers["access-control-expose-headers"].split(",")
        }
        assert {
            "x-request-id",
            "ratelimit-limit",
            "ratelimit-remaining",
            "ratelimit-reset",
            "retry-after",
            "location",
        } <= exposed

    def test_error_responses_have_cors_headers(self, client):
        response = client.get("/nope", headers={"Origin": ORIGIN})
        assert response.status_code == 404
        assert response.headers["access-control-allow-origin"] == ORIGIN

    def test_disallowed_origin_gets_no_cors_headers(self, client):
        response = client.get(self.URL, headers={"Origin": "https://evil.example"})
        assert "access-control-allow-origin" not in response.headers

    def test_preflight_has_request_id(self, client):
        assert self.preflight(client, ORIGIN).headers["X-Request-ID"]


class TestFieldErrors:
    def test_location_formatting(self):
        errors = [{"loc": ("items", 2, "name"), "msg": "bad"}]
        assert field_errors(errors) == [{"field": "items[2].name", "issue": "bad"}]

    @pytest.mark.parametrize("prefix", ["body", "path", "query", "header", "cookie"])
    def test_prefix_stripping(self, prefix):
        assert field_errors([{"loc": (prefix, "name"), "msg": "m"}])[0]["field"] == "name"

    def test_prefix_only_stripped_at_start(self):
        assert field_errors([{"loc": ("items", "body"), "msg": "m"}])[0]["field"] == "items.body"

    def test_nested_lists(self):
        assert field_errors([{"loc": ("a", 0, 1, "b"), "msg": "m"}])[0]["field"] == "a[0][1].b"

    @pytest.mark.parametrize("loc", [(), ("body",)])
    def test_empty_location_is_body(self, loc):
        assert field_errors([{"loc": loc, "msg": "m"}])[0]["field"] == "body"

    def test_value_error_prefix_removed(self):
        errors = [{"loc": ("name",), "msg": "Value error, must not be empty"}]
        assert field_errors(errors)[0]["issue"] == "must not be empty"

    def test_input_value_is_not_echoed(self):
        errors = [{"loc": ("name",), "msg": "bad", "input": "secret", "ctx": {"error": "secret"}}]
        assert "secret" not in str(field_errors(errors))

    def test_limits(self):
        errors = [{"loc": ("f" * 300,), "msg": "m" * 500} for _ in range(80)]
        result = field_errors(errors)
        assert len(result) == 50
        assert len(result[0]["field"]) == 100
        assert len(result[0]["issue"]) == 200

    def test_details_in_response_are_capped(self, client):
        items = [{"name": ""}] * 20
        response = client.post("/api/v1/items/batch", json={"items": items})
        assert len(response.json()["error"]["details"]) == 20
