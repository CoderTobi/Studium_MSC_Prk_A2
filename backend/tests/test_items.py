import pytest

URL = "/api/v1/items"
BATCH = "/api/v1/items/batch"


def names(client):
    return [item["name"] for item in client.get(URL).json()["items"]]


def error_of(response):
    return response.json()["error"]


class TestList:
    def test_empty(self, client):
        response = client.get(URL)
        assert response.status_code == 200
        assert response.json() == {"items": []}

    def test_oldest_first(self, client):
        for name in ["Milk", "Eggs", "Bread"]:
            client.post(URL, json={"name": name})
        assert names(client) == ["Milk", "Eggs", "Bread"]


class TestCreate:
    def test_created(self, client):
        response = client.post(URL, json={"name": "Milk"})
        assert response.status_code == 201
        body = response.json()
        assert set(body) == {"id", "name", "source"}
        assert body["name"] == "Milk"
        assert body["source"] == "manual"
        assert response.headers["Location"] == f"/api/v1/items/{body['id']}"

    def test_name_is_trimmed(self, client):
        response = client.post(URL, json={"name": "  Milk \t"})
        assert response.json()["name"] == "Milk"
        assert names(client) == ["Milk"]

    def test_source_ai_recommendation(self, client):
        response = client.post(URL, json={"name": "Pasta", "source": "ai_recommendation"})
        assert response.status_code == 201
        assert response.json()["source"] == "ai_recommendation"
        assert client.get(URL).json()["items"][0]["source"] == "ai_recommendation"

    def test_duplicate_names_are_allowed(self, client):
        ids = {client.post(URL, json={"name": "Milk"}).json()["id"] for _ in range(2)}
        assert len(ids) == 2
        assert names(client) == ["Milk", "Milk"]

    def test_name_of_100_characters_is_ok(self, client):
        assert client.post(URL, json={"name": "a" * 100}).status_code == 201


class TestBatch:
    def test_created_in_request_order(self, client):
        client.post(URL, json={"name": "Existing"})
        response = client.post(
            BATCH,
            json={
                "items": [
                    {"name": "B", "source": "ai_recommendation"},
                    {"name": " A "},
                    {"name": "C"},
                ]
            },
        )
        assert response.status_code == 201
        items = response.json()["items"]
        assert [i["name"] for i in items] == ["B", "A", "C"]
        assert [i["source"] for i in items] == ["ai_recommendation", "manual", "manual"]
        assert names(client) == ["Existing", "B", "A", "C"]

    def test_invalid_entry_creates_nothing(self, client):
        response = client.post(BATCH, json={"items": [{"name": "ok"}, {"name": "  "}]})
        assert response.status_code == 400
        error = error_of(response)
        assert error["code"] == "VALIDATION_ERROR"
        assert [d["field"] for d in error["details"]] == ["items[1].name"]
        assert names(client) == []

    def test_details_list_every_invalid_entry(self, client):
        response = client.post(
            BATCH, json={"items": [{"name": ""}, {"name": "ok"}, {"name": "x" * 101}]}
        )
        fields = [d["field"] for d in error_of(response)["details"]]
        assert fields == ["items[0].name", "items[2].name"]

    def test_empty_batch_is_rejected(self, client):
        response = client.post(BATCH, json={"items": []})
        assert response.status_code == 400
        assert error_of(response)["details"][0]["field"] == "items"

    def test_one_entry_is_ok(self, client):
        assert client.post(BATCH, json={"items": [{"name": "a"}]}).status_code == 201

    def test_20_entries_are_ok(self, client):
        response = client.post(BATCH, json={"items": [{"name": f"i{n}"} for n in range(20)]})
        assert response.status_code == 201
        assert len(response.json()["items"]) == 20

    def test_21_entries_are_rejected(self, client):
        response = client.post(BATCH, json={"items": [{"name": f"i{n}"} for n in range(21)]})
        assert response.status_code == 400
        assert error_of(response)["code"] == "VALIDATION_ERROR"
        assert names(client) == []

    def test_limit_reached_leaves_list_unchanged(self, make_client):
        client = make_client(item_limit=3)
        client.post(URL, json={"name": "one"})
        client.post(URL, json={"name": "two"})
        response = client.post(BATCH, json={"items": [{"name": "a"}, {"name": "b"}]})
        assert response.status_code == 409
        assert error_of(response)["code"] == "ITEM_LIMIT_REACHED"
        assert names(client) == ["one", "two"]

    def test_batch_may_fill_the_list_exactly(self, make_client):
        client = make_client(item_limit=3)
        response = client.post(BATCH, json={"items": [{"name": n} for n in "abc"]})
        assert response.status_code == 201

    def test_single_create_over_limit(self, make_client):
        client = make_client(item_limit=1)
        assert client.post(URL, json={"name": "a"}).status_code == 201
        response = client.post(URL, json={"name": "b"})
        assert response.status_code == 409
        assert error_of(response)["code"] == "ITEM_LIMIT_REACHED"


class TestDelete:
    def test_delete(self, client):
        keep = client.post(URL, json={"name": "keep"}).json()["id"]
        drop = client.post(URL, json={"name": "drop"}).json()["id"]
        response = client.delete(f"{URL}/{drop}")
        assert response.status_code == 204
        assert response.content == b""
        assert [i["id"] for i in client.get(URL).json()["items"]] == [keep]

    def test_missing_item(self, client):
        response = client.delete(f"{URL}/doesNotExist")
        assert response.status_code == 404
        assert error_of(response)["code"] == "ITEM_NOT_FOUND"

    def test_delete_twice(self, client):
        item_id = client.post(URL, json={"name": "x"}).json()["id"]
        assert client.delete(f"{URL}/{item_id}").status_code == 204
        assert client.delete(f"{URL}/{item_id}").status_code == 404

    @pytest.mark.parametrize("item_id", ["bad!id", "a" * 65, "sp%20ace", "a.b"])
    def test_invalid_id(self, client, item_id):
        response = client.delete(f"{URL}/{item_id}")
        assert response.status_code == 400
        error = error_of(response)
        assert error["code"] == "VALIDATION_ERROR"
        assert error["details"][0]["field"] == "itemId"

    def test_id_of_64_characters_is_valid(self, client):
        assert client.delete(f"{URL}/{'a' * 64}").status_code == 404


class TestValidation:
    @pytest.mark.parametrize(
        "name",
        [
            "",
            "   ",
            "\t\n",
            "a" * 101,
            "bad\x00name",
            "line\nbreak",
            "tab\there",
            1,
            1.5,
            True,
            None,
            [],
        ],
        ids=[
            "empty",
            "spaces",
            "only-whitespace",
            "too-long",
            "nul",
            "newline",
            "tab-inside",
            "int",
            "float",
            "bool",
            "null",
            "list",
        ],
    )
    def test_invalid_name(self, client, name):
        response = client.post(URL, json={"name": name})
        assert response.status_code == 400
        error = error_of(response)
        assert error["code"] == "VALIDATION_ERROR"
        assert error["details"][0]["field"] == "name"
        assert names(client) == []

    def test_name_is_required(self, client):
        response = client.post(URL, json={})
        assert response.status_code == 400
        assert error_of(response)["details"][0]["field"] == "name"

    def test_unknown_field(self, client):
        response = client.post(URL, json={"name": "Milk", "id": "x"})
        assert response.status_code == 400
        assert error_of(response)["details"][0]["field"] == "id"

    def test_unknown_field_in_batch_entry(self, client):
        response = client.post(BATCH, json={"items": [{"name": "Milk", "extra": 1}]})
        assert error_of(response)["details"][0]["field"] == "items[0].extra"

    @pytest.mark.parametrize("source", ["other", "", "MANUAL", None, 1])
    def test_invalid_source(self, client, source):
        response = client.post(URL, json={"name": "Milk", "source": source})
        assert response.status_code == 400
        assert error_of(response)["details"][0]["field"] == "source"

    def test_malformed_json(self, client):
        response = client.post(
            URL, content=b'{"name": ', headers={"Content-Type": "application/json"}
        )
        assert response.status_code == 400
        assert error_of(response)["code"] == "VALIDATION_ERROR"

    def test_json_array_body(self, client):
        response = client.post(URL, json=[{"name": "Milk"}])
        assert response.status_code == 400
        assert error_of(response)["code"] == "VALIDATION_ERROR"

    def test_empty_body(self, client):
        response = client.post(URL, content=b"", headers={"Content-Type": "application/json"})
        assert response.status_code == 400

    def test_rejected_value_is_not_echoed(self, client):
        response = client.post(URL, json={"name": "x" * 101, "source": "secret-value"})
        assert "secret-value" not in response.text
        assert "x" * 101 not in response.text

    def test_content_type_with_charset_is_accepted(self, client):
        response = client.post(
            URL,
            content=b'{"name": "Milk"}',
            headers={"Content-Type": "application/json; charset=utf-8"},
        )
        assert response.status_code == 201
