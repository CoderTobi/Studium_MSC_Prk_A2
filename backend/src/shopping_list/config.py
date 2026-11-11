"""Backend configuration, read from environment variables.

All options are documented in ``.env.example``. Invalid values make the backend
refuse to start instead of silently falling back to a default.
"""

import os
from collections.abc import Mapping
from dataclasses import dataclass


class ConfigError(Exception):
    """Raised when the configuration is invalid or incomplete."""


_TRUE = {"1", "true", "yes", "on"}
_FALSE = {"0", "false", "no", "off"}


def _get_bool(env: Mapping[str, str], name: str, default: bool) -> bool:
    raw = env.get(name)
    if raw is None or raw.strip() == "":
        return default
    value = raw.strip().lower()
    if value in _TRUE:
        return True
    if value in _FALSE:
        return False
    raise ConfigError(f"{name} must be a boolean (true/false), got {raw!r}")


def _get_positive_int(env: Mapping[str, str], name: str, default: int) -> int:
    raw = env.get(name)
    if raw is None or raw.strip() == "":
        return default
    try:
        value = int(raw.strip())
    except ValueError:
        raise ConfigError(f"{name} must be an integer, got {raw!r}") from None
    if value <= 0:
        raise ConfigError(f"{name} must be greater than 0, got {value}")
    return value


def _get_str(env: Mapping[str, str], name: str, default: str | None) -> str | None:
    raw = env.get(name)
    if raw is None or raw.strip() == "":
        return default
    return raw.strip()


def _get_list(env: Mapping[str, str], name: str, default: tuple[str, ...]) -> tuple[str, ...]:
    raw = env.get(name)
    if raw is None:
        return default
    return tuple(part.strip() for part in raw.split(",") if part.strip())


@dataclass(frozen=True, slots=True)
class Settings:
    # Authentication
    auth_disabled: bool = False

    # Firestore. Credentials are taken from GOOGLE_APPLICATION_CREDENTIALS by the
    # Google client library itself, so they are not part of this object.
    google_cloud_project: str | None = None
    firestore_database: str = "(default)"

    # HTTP
    cors_allowed_origins: tuple[str, ...] = ("http://localhost:5173",)
    max_body_bytes: int = 16 * 1024

    # Limits
    item_limit: int = 200
    prompt_max_length: int = 500
    rate_limit_general_per_minute: int = 60
    rate_limit_ai_per_minute: int = 10

    # Logging
    log_level: str = "INFO"

    @classmethod
    def from_env(cls, env: Mapping[str, str] | None = None) -> "Settings":
        env = os.environ if env is None else env
        defaults = cls()
        log_level = (_get_str(env, "LOG_LEVEL", defaults.log_level) or "INFO").upper()
        if log_level not in {"DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"}:
            raise ConfigError(f"LOG_LEVEL is not a valid log level: {log_level!r}")

        return cls(
            auth_disabled=_get_bool(env, "AUTH_DISABLED", defaults.auth_disabled),
            google_cloud_project=_get_str(env, "GOOGLE_CLOUD_PROJECT", None),
            firestore_database=_get_str(env, "FIRESTORE_DATABASE", defaults.firestore_database)
            or defaults.firestore_database,
            cors_allowed_origins=_get_list(
                env, "CORS_ALLOWED_ORIGINS", defaults.cors_allowed_origins
            ),
            max_body_bytes=_get_positive_int(env, "MAX_BODY_BYTES", defaults.max_body_bytes),
            item_limit=_get_positive_int(env, "ITEM_LIMIT", defaults.item_limit),
            prompt_max_length=_get_positive_int(
                env, "PROMPT_MAX_LENGTH", defaults.prompt_max_length
            ),
            rate_limit_general_per_minute=_get_positive_int(
                env, "RATE_LIMIT_GENERAL_PER_MINUTE", defaults.rate_limit_general_per_minute
            ),
            rate_limit_ai_per_minute=_get_positive_int(
                env, "RATE_LIMIT_AI_PER_MINUTE", defaults.rate_limit_ai_per_minute
            ),
            log_level=log_level,
        )
