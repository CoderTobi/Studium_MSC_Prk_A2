import pytest

from shopping_list.config import ConfigError, Settings


def test_defaults_without_env():
    settings = Settings.from_env({})
    assert settings == Settings()
    assert settings.auth_disabled is False
    assert settings.google_cloud_project is None
    assert settings.firestore_database == "(default)"
    assert settings.cors_allowed_origins == ("http://localhost:5173",)
    assert settings.max_body_bytes == 16 * 1024
    assert settings.item_limit == 200
    assert settings.prompt_max_length == 500
    assert settings.rate_limit_general_per_minute == 60
    assert settings.rate_limit_ai_per_minute == 10
    assert settings.log_level == "INFO"


def test_reads_os_environ_by_default(monkeypatch):
    monkeypatch.setenv("ITEM_LIMIT", "7")
    assert Settings.from_env().item_limit == 7


def test_all_values_parsed():
    settings = Settings.from_env(
        {
            "AUTH_DISABLED": "true",
            "GOOGLE_CLOUD_PROJECT": " my-project ",
            "FIRESTORE_DATABASE": "shopping",
            "CORS_ALLOWED_ORIGINS": "https://a.example, https://b.example",
            "MAX_BODY_BYTES": "1024",
            "ITEM_LIMIT": "5",
            "PROMPT_MAX_LENGTH": "100",
            "RATE_LIMIT_GENERAL_PER_MINUTE": "30",
            "RATE_LIMIT_AI_PER_MINUTE": "3",
            "LOG_LEVEL": "debug",
        }
    )
    assert settings == Settings(
        auth_disabled=True,
        google_cloud_project="my-project",
        firestore_database="shopping",
        cors_allowed_origins=("https://a.example", "https://b.example"),
        max_body_bytes=1024,
        item_limit=5,
        prompt_max_length=100,
        rate_limit_general_per_minute=30,
        rate_limit_ai_per_minute=3,
        log_level="DEBUG",
    )


@pytest.mark.parametrize("raw", ["1", "true", "TRUE", "yes", "on", " True "])
def test_true_values(raw):
    assert Settings.from_env({"AUTH_DISABLED": raw}).auth_disabled is True


@pytest.mark.parametrize("raw", ["0", "false", "False", "no", "off"])
def test_false_values(raw):
    assert Settings.from_env({"AUTH_DISABLED": raw}).auth_disabled is False


@pytest.mark.parametrize("raw", ["", "  "])
def test_blank_values_use_default(raw):
    settings = Settings.from_env({"AUTH_DISABLED": raw, "ITEM_LIMIT": raw, "LOG_LEVEL": raw})
    assert settings == Settings()


def test_cors_list_ignores_empty_parts():
    settings = Settings.from_env({"CORS_ALLOWED_ORIGINS": " https://a.example ,, "})
    assert settings.cors_allowed_origins == ("https://a.example",)


def test_cors_list_may_be_empty():
    assert Settings.from_env({"CORS_ALLOWED_ORIGINS": ""}).cors_allowed_origins == ()


@pytest.mark.parametrize("raw", ["maybe", "2", "tru", "y"])
def test_invalid_bool(raw):
    with pytest.raises(ConfigError, match="AUTH_DISABLED"):
        Settings.from_env({"AUTH_DISABLED": raw})


@pytest.mark.parametrize(
    "name",
    [
        "MAX_BODY_BYTES",
        "ITEM_LIMIT",
        "PROMPT_MAX_LENGTH",
        "RATE_LIMIT_GENERAL_PER_MINUTE",
        "RATE_LIMIT_AI_PER_MINUTE",
    ],
)
@pytest.mark.parametrize("raw", ["abc", "1.5", "0", "-1"])
def test_invalid_int(name, raw):
    with pytest.raises(ConfigError, match=name):
        Settings.from_env({name: raw})


@pytest.mark.parametrize("raw", ["verbose", "TRACE", "42"])
def test_invalid_log_level(raw):
    with pytest.raises(ConfigError, match="LOG_LEVEL"):
        Settings.from_env({"LOG_LEVEL": raw})


def test_settings_are_immutable():
    with pytest.raises(AttributeError):
        Settings().item_limit = 1  # type: ignore[misc]
