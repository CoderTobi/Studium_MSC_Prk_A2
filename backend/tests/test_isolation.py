URL = "/api/v1/items"


def test_users_only_see_their_own_items(client, auth):
    client.post(URL, json={"name": "alice-item"}, headers=auth("alice"))
    client.post(URL, json={"name": "bob-item"}, headers=auth("bob"))
    alice = client.get(URL, headers=auth("alice")).json()["items"]
    bob = client.get(URL, headers=auth("bob")).json()["items"]
    assert [i["name"] for i in alice] == ["alice-item"]
    assert [i["name"] for i in bob] == ["bob-item"]


def test_foreign_item_looks_like_a_missing_item(client, auth):
    item_id = client.post(URL, json={"name": "secret"}, headers=auth("alice")).json()["id"]

    foreign = client.delete(f"{URL}/{item_id}", headers=auth("bob"))
    missing = client.delete(f"{URL}/doesNotExist", headers=auth("bob"))

    assert foreign.status_code == missing.status_code == 404
    assert foreign.json()["error"]["code"] == missing.json()["error"]["code"] == "ITEM_NOT_FOUND"
    assert foreign.json()["error"]["message"] == missing.json()["error"]["message"]
    # Alice's item is untouched.
    assert len(client.get(URL, headers=auth("alice")).json()["items"]) == 1


def test_item_limit_is_per_user(make_client, auth):
    client = make_client(item_limit=1)
    assert client.post(URL, json={"name": "a"}, headers=auth("alice")).status_code == 201
    assert client.post(URL, json={"name": "a"}, headers=auth("alice")).status_code == 409
    assert client.post(URL, json={"name": "a"}, headers=auth("bob")).status_code == 201


def test_rate_limit_is_per_user(make_client, auth):
    client = make_client(rate_limit_general_per_minute=1)
    assert client.get(URL, headers=auth("alice")).status_code == 200
    assert client.get(URL, headers=auth("alice")).status_code == 429
    assert client.get(URL, headers=auth("bob")).status_code == 200


def test_request_without_header_is_the_debug_user(client, auth):
    client.post(URL, json={"name": "anonymous"})
    assert [i["name"] for i in client.get(URL).json()["items"]] == ["anonymous"]
    assert client.get(URL, headers=auth("debug-user")).json()["items"][0]["name"] == "anonymous"
    assert client.get(URL, headers=auth("alice")).json()["items"] == []


def test_uid_cannot_be_chosen_by_query_or_body(client, auth):
    client.post(URL, json={"name": "alice-item"}, headers=auth("alice"))
    assert client.get(URL, params={"uid": "alice"}).json()["items"] == []
    response = client.post(URL, json={"name": "x", "uid": "alice"})
    assert response.status_code == 400
