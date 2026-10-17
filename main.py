from pathlib import Path
from typing import List
import os

import yaml
from dotenv import dotenv_values
from fastapi import FastAPI, Query
from fastapi.middleware.cors import CORSMiddleware

BASE_DIR = Path(__file__).parent

app = FastAPI()

# CORS: lets the grader's web page call your API from the browser
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# Layer 1: defaults
DEFAULTS = {
    "port": 8000,
    "workers": 1,
    "debug": False,
    "log_level": "info",
    "api_key": "default-secret-000",
}

ALIASES = {"num_workers": "workers"}   # NUM_WORKERS -> workers
TRUE_VALUES = {"true", "1", "yes", "on"}


def normalize_key(raw: str) -> str:
    """'APP_PORT' -> 'port', 'NUM_WORKERS' -> 'workers'"""
    key = raw.strip().lower()
    if key.startswith("app_"):
        key = key[4:]
    return ALIASES.get(key, key)


def coerce(key: str, value):
    """Turn raw values into the right type."""
    if key in ("port", "workers"):
        return int(value)
    if key == "debug":
        return str(value).strip().lower() in TRUE_VALUES
    return str(value)


def load_yaml_layer() -> dict:
    env_name = os.environ.get("APP_ENV", "development")
    path = BASE_DIR / f"config.{env_name}.yaml"
    if not path.exists():
        return {}
    data = yaml.safe_load(path.read_text()) or {}
    return {normalize_key(k): v for k, v in data.items()}


def load_dotenv_layer() -> dict:
    values = dotenv_values(BASE_DIR / ".env")
    return {normalize_key(k): v for k, v in values.items() if v is not None}


def load_os_env_layer() -> dict:
    layer = {}
    for k, v in os.environ.items():
        if k.startswith("APP_") and k != "APP_ENV":
            layer[normalize_key(k)] = v
    return layer


@app.get("/effective-config")
def effective_config(overrides: List[str] = Query(default=[], alias="set")):
    merged = dict(DEFAULTS)                 # bottom sheet
    merged.update(load_yaml_layer())        # + YAML
    merged.update(load_dotenv_layer())      # + .env
    merged.update(load_os_env_layer())      # + OS env

    # Top sheet: ?set=key=value (split only on the FIRST "=")
    for item in overrides:
        if "=" not in item:
            continue
        k, v = item.split("=", 1)
        merged[normalize_key(k)] = v

    result = {k: coerce(k, v) for k, v in merged.items()}
    result["api_key"] = "****"              # never reveal the real secret
    return result