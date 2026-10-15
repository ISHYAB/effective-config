
import os
from pathlib import Path

import yaml
from dotenv import dotenv_values
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware

app = FastAPI(title="Effective Configuration Service")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["GET"],
    allow_headers=["*"],
)

DEFAULTS = {
    "port": 8000,
    "workers": 1,
    "debug": False,
    "log_level": "info",
    "api_key": "default-secret-000",
}

BASE_DIR = Path(__file__).resolve().parent


def to_value(key: str, value):
    value = str(value)

    if key in ("port", "workers"):
        return int(value)

    if key == "debug":
        return value.strip().lower() in {
            "true", "1", "yes", "on"
        }

    return value


def normalize_key(key: str) -> str:
    key = key.strip().lower()

    if key == "num_workers":
        return "workers"

    if key.startswith("app_"):
        key = key[4:]

    return key


def apply_layer(config: dict, layer: dict):
    for raw_key, value in layer.items():
        if value is None:
            continue

        key = normalize_key(raw_key)

        if key in config:
            config[key] = to_value(key, value)


def load_config():
    config = DEFAULTS.copy()

    # Layer 2: environment-specific YAML
    environment = os.getenv("APP_ENV", "development")
    yaml_path = BASE_DIR / f"config.{environment}.yaml"

    if yaml_path.exists():
        with yaml_path.open(encoding="utf-8") as file:
            yaml_config = yaml.safe_load(file) or {}
        apply_layer(config, yaml_config)

    # Layer 3: .env file
    env_path = BASE_DIR / ".env"
    if env_path.exists():
        apply_layer(config, dotenv_values(env_path))

    # Layer 4: actual OS environment variables
    os_config = {
        key: value
        for key, value in os.environ.items()
        if key.startswith("APP_")
    }
    apply_layer(config, os_config)

    return config


@app.get("/effective-config")
async def effective_config(request: Request):
    config = load_config()

    # Layer 5: CLI overrides supplied as repeated ?set= parameters
    for item in request.query_params.getlist("set"):
        key, separator, value = item.partition("=")

        if not separator:
            continue

        key = normalize_key(key)

        if key in config:
            try:
                config[key] = to_value(key, value)
            except ValueError:
                continue

    # Never return the real secret.
    config["api_key"] = "****"

    return config


@app.get("/")
async def root():
    return {"message": "Effective Configuration API is running"}