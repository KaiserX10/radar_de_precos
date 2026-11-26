"""Copia o histórico local (dados/radar.db) para o Postgres da nuvem.

Uso:  defina DATABASE_URL (no .env ou no ambiente) e rode
      .venv\\Scripts\\python -m radar.migrar
"""
import sqlite3

from . import db

if __name__ == "__main__":
    if not db.PG:
        raise SystemExit("Defina DATABASE_URL (Postgres) no .env antes de migrar.")
    local = sqlite3.connect(db.ARQUIVO)
    local.row_factory = sqlite3.Row
    nuvem = db.conectar()
    ja_tem = nuvem.um("SELECT COUNT(*) FROM precos")
    if ja_tem:
        raise SystemExit(f"O Postgres já tem {ja_tem} preços; migração cancelada para não duplicar.")

    precos = [dict(r) for r in local.execute("SELECT * FROM precos")]
    nuvem.executemany(
        "INSERT INTO precos (ts, loja, familia, sku, titulo, url, vendedor, preco_vista, preco_cheio, disponivel, suspeito)"
        " VALUES (?,?,?,?,?,?,?,?,?,?,?)",
        [(p["ts"], p["loja"], p["familia"], p["sku"], p["titulo"], p["url"], p["vendedor"],
          p["preco_vista"], p["preco_cheio"], p["disponivel"], p["suspeito"]) for p in precos])
    for c in local.execute("SELECT * FROM coletas"):
        db.registrar_coleta(nuvem, c["ts"], c["loja"], c["ofertas"], c["erro"])
    nuvem.commit()
    print(f"Migrados {len(precos)} preços.")
