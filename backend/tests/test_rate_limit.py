import pytest

from shopping_list.rate_limit import Bucket, RateLimiter

G, A = Bucket.GENERAL, Bucket.AI


class FakeClock:
    def __init__(self) -> None:
        self.now = 1000.0

    def __call__(self) -> float:
        return self.now


@pytest.fixture
def clock():
    return FakeClock()


def make_limiter(clock, general=3, ai=2, window=60):
    return RateLimiter({G: general, A: ai}, window_seconds=window, clock=clock)


class TestRateLimiter:
    def test_counts_down_then_denies(self, clock):
        limiter = make_limiter(clock)
        remaining = [limiter.hit("u", [G]).remaining for _ in range(3)]
        assert remaining == [2, 1, 0]
        denied = limiter.hit("u", [G])
        assert not denied.allowed
        assert (denied.limit, denied.remaining) == (3, 0)

    def test_reset_seconds(self, clock):
        limiter = make_limiter(clock)
        assert limiter.hit("u", [G]).reset_seconds == 60
        clock.now += 10.5
        assert limiter.hit("u", [G]).reset_seconds == 50  # ceil(49.5)

    def test_window_resets(self, clock):
        limiter = make_limiter(clock)
        for _ in range(3):
            limiter.hit("u", [G])
        assert not limiter.hit("u", [G]).allowed
        clock.now += 59.9
        assert not limiter.hit("u", [G]).allowed
        clock.now += 0.1
        decision = limiter.hit("u", [G])
        assert decision.allowed
        assert decision.remaining == 2

    def test_denied_decision_reports_time_until_reset(self, clock):
        limiter = make_limiter(clock)
        for _ in range(3):
            limiter.hit("u", [G])
        clock.now += 20
        assert limiter.hit("u", [G]).reset_seconds == 40

    def test_users_are_separate(self, clock):
        limiter = make_limiter(clock, general=1)
        assert limiter.hit("a", [G]).allowed
        assert not limiter.hit("a", [G]).allowed
        assert limiter.hit("b", [G]).allowed

    def test_buckets_are_separate(self, clock):
        limiter = make_limiter(clock)
        limiter.hit("u", [A])
        limiter.hit("u", [A])
        assert not limiter.hit("u", [A]).allowed
        assert limiter.hit("u", [G]).allowed

    def test_denied_request_is_not_counted(self, clock):
        limiter = make_limiter(clock, general=5, ai=2)
        assert limiter.hit("u", [G, A]).allowed
        assert limiter.hit("u", [G, A]).allowed
        assert not limiter.hit("u", [G, A]).allowed  # ai exhausted
        assert not limiter.hit("u", [G, A]).allowed
        # Only the two accepted requests were counted against general.
        decision = limiter.hit("u", [G])
        assert decision.remaining == 2

    def test_most_restrictive_bucket_is_reported(self, clock):
        limiter = make_limiter(clock, general=5, ai=2)
        first = limiter.hit("u", [G, A])
        assert (first.limit, first.remaining) == (2, 1)  # ai: 1 left, general: 4 left
        second = limiter.hit("u", [G, A])
        assert (second.limit, second.remaining) == (2, 0)

    def test_denial_reports_the_exhausted_bucket(self, clock):
        limiter = make_limiter(clock, general=5, ai=1)
        limiter.hit("u", [G, A])
        denied = limiter.hit("u", [G, A])
        assert (denied.allowed, denied.limit, denied.remaining) == (False, 1, 0)

    def test_general_can_be_more_restrictive_than_ai(self, clock):
        limiter = make_limiter(clock, general=2, ai=10)
        decision = limiter.hit("u", [G, A])
        assert (decision.limit, decision.remaining) == (2, 1)

    def test_expired_windows_are_cleaned_up(self, clock):
        limiter = make_limiter(clock)
        for uid in ("a", "b", "c"):
            limiter.hit(uid, [G, A])
        assert len(limiter._windows) == 6
        clock.now += 61
        limiter.hit("d", [G])
        assert set(limiter._windows) == {(G, "d")}

    def test_windows_are_kept_before_expiry(self, clock):
        limiter = make_limiter(clock)
        limiter.hit("a", [G])
        clock.now += 30
        limiter.hit("b", [G])
        assert len(limiter._windows) == 2


class TestApi:
    def test_headers_on_success(self, make_client):
        client = make_client(rate_limit_general_per_minute=5)
        first = client.get("/api/v1/items")
        assert first.headers["RateLimit-Limit"] == "5"
        assert first.headers["RateLimit-Remaining"] == "4"
        assert 1 <= int(first.headers["RateLimit-Reset"]) <= 60
        assert client.get("/api/v1/items").headers["RateLimit-Remaining"] == "3"

    def test_429(self, make_client):
        client = make_client(rate_limit_general_per_minute=2)
        client.get("/api/v1/items")
        client.get("/api/v1/items")
        response = client.get("/api/v1/items")
        assert response.status_code == 429
        error = response.json()["error"]
        assert error["code"] == "RATE_LIMIT_EXCEEDED"
        assert error["requestId"] == response.headers["X-Request-ID"]
        assert response.headers["Retry-After"] == str(error["retryAfterSeconds"])
        assert 1 <= error["retryAfterSeconds"] <= 60
        assert response.headers["RateLimit-Remaining"] == "0"
        assert response.headers["RateLimit-Limit"] == "2"

    @pytest.mark.parametrize(
        ("method", "path", "body"),
        [
            ("POST", "/items", {"name": "x"}),
            ("POST", "/items/batch", {"items": [{"name": "x"}]}),
            ("DELETE", "/items/abc", None),
            ("POST", "/recommendations", {"prompt": "pasta"}),
        ],
    )
    def test_all_authenticated_endpoints_are_limited(self, make_client, method, path, body):
        client = make_client(rate_limit_general_per_minute=1)
        client.get("/api/v1/items")
        response = client.request(method, f"/api/v1/{path.lstrip('/')}", json=body)
        assert response.status_code == 429

    def test_recommendations_count_against_both_buckets(self, make_client):
        client = make_client(rate_limit_general_per_minute=5, rate_limit_ai_per_minute=2)
        response = client.post("/api/v1/recommendations", json={"prompt": "pasta"})
        # ai bucket (2) is more restrictive than general (5)
        assert response.headers["RateLimit-Limit"] == "2"
        assert response.headers["RateLimit-Remaining"] == "1"
        # ...and the general bucket was counted as well
        assert client.get("/api/v1/items").headers["RateLimit-Remaining"] == "3"

    def test_ai_bucket_does_not_limit_items(self, make_client):
        client = make_client(rate_limit_general_per_minute=10, rate_limit_ai_per_minute=1)
        client.post("/api/v1/recommendations", json={"prompt": "pasta"})
        assert client.post("/api/v1/recommendations", json={"prompt": "pasta"}).status_code == 429
        assert client.get("/api/v1/items").status_code == 200

    def test_denied_recommendation_is_not_counted_against_general(self, make_client):
        client = make_client(rate_limit_general_per_minute=4, rate_limit_ai_per_minute=1)
        client.post("/api/v1/recommendations", json={"prompt": "pasta"})  # general 1
        client.post("/api/v1/recommendations", json={"prompt": "pasta"})  # denied
        client.post("/api/v1/recommendations", json={"prompt": "pasta"})  # denied
        assert client.get("/api/v1/items").headers["RateLimit-Remaining"] == "2"

    def test_general_exhaustion_blocks_recommendations(self, make_client):
        client = make_client(rate_limit_general_per_minute=1, rate_limit_ai_per_minute=10)
        client.get("/api/v1/items")
        assert client.post("/api/v1/recommendations", json={"prompt": "x"}).status_code == 429
