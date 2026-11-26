import json
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent


def carregar_config():
    return json.loads((RAIZ / "config.json").read_text(encoding="utf-8"))


def salvar_config(cfg):
    arq = RAIZ / "config.json"
    tmp = arq.with_suffix(".tmp")
    tmp.write_text(json.dumps(cfg, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    tmp.replace(arq)  # troca atômica: o coletor nunca lê um arquivo pela metade
