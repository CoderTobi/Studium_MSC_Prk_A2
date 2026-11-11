def test_health_is_ok_without_auth(client):
    response = client.get("/api/v1/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}
    assert response.headers["content-type"].startswith("application/json")


def test_health_has_request_id_and_no_rate_limit_headers(client):
    response = client.get("/api/v1/health")
    assert response.headers["X-Request-ID"]
    assert not any(name.lower().startswith("ratelimit") for name in response.headers)


def test_health_is_not_rate_limited(make_client):
    client = make_client(rate_limit_general_per_minute=1)
    assert all(client.get("/api/v1/health").status_code == 200 for _ in range(5))
