import pytest

from shopping_list.errors import ApiError, ErrorCode
from shopping_list.models import Recommendation
from shopping_list.recommendations import DISCLAIMER
from tests.fakes import FakeAIClient

URL = "/api/v1/recommendations"


def ask(client, prompt, **kwargs):
    return client.post(URL, json={"prompt": prompt}, **kwargs)


@pytest.fixture
def ai():
    return FakeAIClient([Recommendation(name="Spaghetti"), Recommendation(name="Tomatoes")])


class TestSuccess:
    def test_returns_recommendations_and_disclaimer(self, make_client, ai):
        response = ask(make_client(ai_client=ai), "spaghetti bolognese")
        assert response.status_code == 200
        assert response.json() == {
            "recommendations": [{"name": "Spaghetti"}, {"name": "Tomatoes"}],
            "disclaimer": DISCLAIMER,
        }

    def test_empty_result_is_valid(self, make_client):
        response = ask(make_client(ai_client=FakeAIClient([])), "hello")
        assert response.status_code == 200
        assert response.json()["recommendations"] == []
        assert response.json()["disclaimer"]

    def test_client_receives_trimmed_prompt(self, make_client, ai):
        ask(make_client(ai_client=ai), "  pasta \n")
        assert ai.prompts == ["pasta"]

    def test_nothing_is_stored(self, make_client, ai):
        client = make_client(ai_client=ai)
        ask(client, "pasta")
        assert client.get("/api/v1/items").json() == {"items": []}


class TestPromptValidation:
    @pytest.mark.parametrize("prompt", ["", " ", " \t\n  "])
    def test_empty(self, make_client, ai, prompt):
        response = ask(make_client(ai_client=ai), prompt)
        assert response.status_code == 400
        assert response.json()["error"]["code"] == "PROMPT_EMPTY"
        assert ai.prompts == []

    def test_too_long(self, make_client, ai):
        response = ask(make_client(ai_client=ai), "a" * 501)
        assert response.status_code == 400
        error = response.json()["error"]
        assert error["code"] == "PROMPT_TOO_LONG"
        assert error["message"] == "The prompt must not be longer than 500 characters."
        assert ai.prompts == []

    def test_500_characters_with_surrounding_whitespace_is_ok(self, make_client, ai):
        response = ask(make_client(ai_client=ai), f"  \n{'a' * 500}\t ")
        assert response.status_code == 200
        assert ai.prompts == ["a" * 500]

    def test_length_is_counted_in_unicode_characters(self, make_client, ai):
        client = make_client(ai_client=ai, max_body_bytes=64 * 1024)
        assert ask(client, "🍝" * 500).status_code == 200
        assert ask(client, "🍝" * 501).json()["error"]["code"] == "PROMPT_TOO_LONG"

    def test_limit_is_configurable(self, make_client, ai):
        client = make_client(ai_client=ai, prompt_max_length=5)
        assert ask(client, "12345").status_code == 200
        assert ask(client, "123456").status_code == 400

    @pytest.mark.parametrize("prompt", [1, None, True, ["a"], {"a": 1}])
    def test_non_string_prompt(self, make_client, ai, prompt):
        response = ask(make_client(ai_client=ai), prompt)
        assert response.status_code == 400
        error = response.json()["error"]
        assert error["code"] == "VALIDATION_ERROR"
        assert error["details"][0]["field"] == "prompt"

    def test_missing_prompt(self, client):
        response = client.post(URL, json={})
        assert response.json()["error"]["code"] == "VALIDATION_ERROR"

    def test_unknown_field(self, client):
        response = client.post(URL, json={"prompt": "pasta", "model": "x"})
        assert response.status_code == 400
        assert response.json()["error"]["details"][0]["field"] == "model"

    def test_content_type_must_be_json(self, client):
        response = client.post(
            URL, content=b'{"prompt":"a"}', headers={"Content-Type": "text/plain"}
        )
        assert response.status_code == 415


class TestAiErrors:
    def test_default_client_is_unavailable(self, client):
        response = ask(client, "pasta")
        assert response.status_code == 503
        assert response.json()["error"]["code"] == "AI_UNAVAILABLE"

    @pytest.mark.parametrize(
        ("code", "status"),
        [
            (ErrorCode.AI_TIMEOUT, 504),
            (ErrorCode.AI_UNAVAILABLE, 503),
            (ErrorCode.AI_INVALID_RESPONSE, 502),
            (ErrorCode.PROMPT_REJECTED, 422),
        ],
    )
    def test_error_from_client_is_passed_through(self, make_client, code, status):
        client = make_client(ai_client=FakeAIClient(error=ApiError(code)))
        response = ask(client, "pasta")
        assert response.status_code == status
        error = response.json()["error"]
        assert error["code"] == code.value
        assert error["requestId"] == response.headers["X-Request-ID"]

    def test_unexpected_client_failure_is_500_without_details(self, make_client):
        class Broken:
            def recommend(self, prompt):
                raise RuntimeError("model output: secret-text")

        response = ask(make_client(ai_client=Broken()), "pasta")
        assert response.status_code == 500
        assert response.json()["error"]["code"] == "INTERNAL_ERROR"
        assert "secret-text" not in response.text


def test_prompt_is_not_echoed_in_errors(make_client):
    response = ask(make_client(), "x" * 600)
    assert "x" * 600 not in response.text
