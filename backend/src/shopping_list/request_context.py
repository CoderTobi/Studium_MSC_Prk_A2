"""Per-request context that has to be reachable from anywhere (logging, error bodies)."""

from contextvars import ContextVar

# Set by RequestContextMiddleware for every HTTP request. Context variables are copied
# into the threadpool that runs sync endpoints, so the value is visible there as well.
request_id_var: ContextVar[str] = ContextVar("request_id", default="-")


def current_request_id() -> str:
    return request_id_var.get()
