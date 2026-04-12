from __future__ import annotations

import os
from pathlib import Path


def load_dotenv(path: str = ".env") -> bool:
    env_path = Path(path)
    if not env_path.exists():
        return False

    loaded_any = False
    for raw_line in env_path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        value = _strip_quotes(value.strip())
        if not key or key in os.environ:
            continue
        os.environ[key] = value
        loaded_any = True
    return loaded_any


def load_default_dotenvs() -> bool:
    loaded_any = False
    for candidate in (".env", ".venv/.env"):
        loaded_any = load_dotenv(candidate) or loaded_any
    return loaded_any


def _strip_quotes(value: str) -> str:
    if len(value) >= 2 and value[0] == value[-1] and value[0] in {'"', "'"}:
        return value[1:-1]
    return value
