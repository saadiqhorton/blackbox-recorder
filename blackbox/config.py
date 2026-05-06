import os
from pathlib import Path

import yaml
from pydantic import BaseModel


class LLMConfig(BaseModel):
    provider: str = "ollama"
    model: str = "gemma4:31b-cloud"
    base_url: str = "http://localhost:11434/v1"
    api_key: str | None = None


class StorageConfig(BaseModel):
    runs_dir: str = ".blackbox/runs"


class ThresholdsConfig(BaseModel):
    min_completeness: int = 50
    min_veracity: int = 50


class BlackboxConfig(BaseModel):
    llm: LLMConfig = LLMConfig()
    storage: StorageConfig = StorageConfig()
    thresholds: ThresholdsConfig = ThresholdsConfig()


_ENV_OVERRIDE_MAP: dict[str, list[str]] = {
    "BLACKBOX_LLM_PROVIDER": ["llm", "provider"],
    "BLACKBOX_LLM_MODEL": ["llm", "model"],
    "BLACKBOX_LLM_BASE_URL": ["llm", "base_url"],
    "BLACKBOX_LLM_API_KEY": ["llm", "api_key"],
    "BLACKBOX_STORAGE_RUNS_DIR": ["storage", "runs_dir"],
    "BLACKBOX_MIN_COMPLETENESS": ["thresholds", "min_completeness"],
    "BLACKBOX_MIN_VERACITY": ["thresholds", "min_veracity"],
}

_INT_ENV_KEYS = {"BLACKBOX_MIN_COMPLETENESS", "BLACKBOX_MIN_VERACITY"}


def get_config_path() -> Path:
    env_path = os.environ.get("BLACKBOX_CONFIG")
    if env_path:
        return Path(env_path)
    return Path.cwd() / ".blackbox" / "config.yaml"


def _deep_merge(base: dict, override: dict) -> dict:
    result = base.copy()
    for key, value in override.items():
        if key in result and isinstance(result[key], dict) and isinstance(value, dict):
            result[key] = _deep_merge(result[key], value)
        else:
            result[key] = value
    return result


def _apply_env_overrides(config: dict) -> dict:
    for env_key, config_path in _ENV_OVERRIDE_MAP.items():
        value = os.environ.get(env_key)
        if value is not None:
            if env_key in _INT_ENV_KEYS:
                try:
                    value = int(value)
                except (ValueError, TypeError):
                    import warnings
                    warnings.warn(f"Invalid integer value for {env_key}: {value!r}, skipping")
                    continue
            target = config
            for key in config_path[:-1]:
                target = target.setdefault(key, {})
            target[config_path[-1]] = value
    return config


def load_config() -> BlackboxConfig:
    defaults = BlackboxConfig().model_dump()
    config_path = get_config_path()

    merged = dict(defaults)
    if config_path.is_file():
        try:
            with open(config_path) as f:
                yaml_data = yaml.safe_load(f)
            if isinstance(yaml_data, dict):
                merged = _deep_merge(merged, yaml_data)
        except (PermissionError, OSError) as e:
            import warnings
            warnings.warn(f"Cannot read config at {config_path}: {e}")

    merged = _apply_env_overrides(merged)

    return BlackboxConfig.model_validate(merged)


def save_default_config(path: Path | None = None) -> None:
    target = path or get_config_path()
    target.parent.mkdir(parents=True, exist_ok=True)
    config = {
        "llm": {
            "provider": "ollama",
            "model": "gemma4:31b-cloud",
            "base_url": "http://localhost:11434/v1",
            "api_key": None,
        },
        "storage": {
            "runs_dir": ".blackbox/runs",
        },
        "thresholds": {
            "min_completeness": 50,
            "min_veracity": 50,
        },
    }
    with open(target, "w") as f:
        yaml.dump(config, f, default_flow_style=False)
