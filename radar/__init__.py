import json
import os
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent

# Variáveis locais opcionais (ex.: DATABASE_URL) num arquivo .env que não vai para o git
_env = RAIZ / ".env"
if _env.exists():
    for _linha in _env.read_text(encoding="utf-8").splitlines():
        if "=" in _linha and not _linha.lstrip().startswith("#"):
            _k, _v = _linha.split("=", 1)
            os.environ.setdefault(_k.strip(), _v.strip().strip('"').strip("'"))


def carregar_config():
    return json.loads((RAIZ / "config.json").read_text(encoding="utf-8"))
