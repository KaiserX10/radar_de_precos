import sqlite3
from datetime import datetime, timedelta

from . import RAIZ

ARQUIVO = RAIZ / "dados" / "radar.db"

ESQUEMA = """
CREATE TABLE IF NOT EXISTS precos (
    id INTEGER PRIMARY KEY,
    ts TEXT NOT NULL,            -- data/hora local da coleta (ISO)
    loja TEXT NOT NULL,
    familia TEXT NOT NULL,
    sku TEXT NOT NULL,
    titulo TEXT NOT NULL,
    url TEXT NOT NULL,
    vendedor TEXT,
    preco_vista REAL NOT NULL,
    preco_cheio REAL,
    disponivel INTEGER NOT NULL,
    suspeito INTEGER NOT NULL DEFAULT 0
);
CREATE INDEX IF NOT EXISTS ix_precos_fam_ts ON precos(familia, ts);

CREATE TABLE IF NOT EXISTS coletas (
    ts TEXT NOT NULL,
    loja TEXT NOT NULL,
    ofertas INTEGER,
    erro TEXT,
    PRIMARY KEY (ts, loja)
);

CREATE TABLE IF NOT EXISTS alertas_enviados (
    familia TEXT PRIMARY KEY,
    menor_alertado REAL
);
"""

# Janelas medidas a partir do início da coleta (sem histórico de longo prazo)
JANELAS = {"24h": 24, "7d": 24 * 7, "30d": 24 * 30, "inicio": None}

VALIDA = "disponivel=1 AND suspeito=0"


def _migrar(con):
    cols = {r[1] for r in con.execute("PRAGMA table_info(precos)")}
    if "suspeito" not in cols:
        con.execute("ALTER TABLE precos ADD COLUMN suspeito INTEGER NOT NULL DEFAULT 0")
    pk = [r[1] for r in con.execute("PRAGMA table_info(coletas)") if r[5]]
    if pk == ["ts"]:  # versão antiga: uma linha por coleta, não por loja
        con.executescript("DROP TABLE coletas;")
        con.executescript(ESQUEMA)
    con.execute("DROP TABLE IF EXISTS historico_manual")


def conectar():
    ARQUIVO.parent.mkdir(exist_ok=True)
    con = sqlite3.connect(ARQUIVO, timeout=30)
    con.row_factory = sqlite3.Row
    con.executescript(ESQUEMA)
    _migrar(con)
    return con


def agora():
    return datetime.now().replace(microsecond=0).isoformat()


def salvar_ofertas(con, ts, ofertas):
    con.executemany(
        "INSERT INTO precos (ts, loja, familia, sku, titulo, url, vendedor, preco_vista, preco_cheio, disponivel, suspeito)"
        " VALUES (?,?,?,?,?,?,?,?,?,?,?)",
        [(ts, o["loja"], o["familia"], o["sku"], o["titulo"], o["url"], o.get("vendedor"),
          o["preco_vista"], o.get("preco_cheio"), int(o["disponivel"]), int(o.get("suspeito", 0)))
         for o in ofertas],
    )
    con.commit()


def ultima_coleta(con, familia=None):
    row = con.execute("SELECT MAX(ts) FROM precos" + (" WHERE familia=?" if familia else ""),
                      (familia,) if familia else ()).fetchone()
    return row[0]


def ofertas_atuais(con, familia, max_horas=3):
    """Ofertas da coleta mais recente de cada loja (se uma loja falhar, mantém a anterior
    por até `max_horas`); as suspeitas vêm por último."""
    corte = (datetime.now() - timedelta(hours=max_horas)).isoformat()
    rows = con.execute(
        "SELECT p.* FROM precos p JOIN ("
        "  SELECT loja, MAX(ts) ts FROM precos WHERE familia=? AND ts>=? GROUP BY loja"
        ") u ON p.loja=u.loja AND p.ts=u.ts"
        " WHERE p.familia=? AND p.disponivel=1 ORDER BY p.suspeito, p.preco_vista",
        (familia, corte, familia)).fetchall()
    return [dict(r) for r in rows]


def serie(con, familia, horas=None):
    """Menor preço válido em cada coleta."""
    filtro, args = "", [familia]
    if horas:
        filtro = " AND ts >= ?"
        args.append((datetime.now() - timedelta(hours=horas)).isoformat())
    rows = con.execute(
        f"SELECT ts, MIN(preco_vista) preco FROM precos WHERE familia=? AND {VALIDA}{filtro}"
        " GROUP BY ts ORDER BY ts", args).fetchall()
    return [(r["ts"], r["preco"]) for r in rows]


def minimos_por_janela(con, familia):
    saida = {}
    for nome, horas in JANELAS.items():
        filtro, args = "", [familia]
        if horas:
            filtro = " AND ts >= ?"
            args.append((datetime.now() - timedelta(hours=horas)).isoformat())
        saida[nome] = con.execute(
            f"SELECT MIN(preco_vista) FROM precos WHERE familia=? AND {VALIDA}{filtro}", args).fetchone()[0]
    inicio = con.execute("SELECT MIN(ts) FROM precos WHERE familia=?", (familia,)).fetchone()[0]
    saida["desde"] = inicio
    saida["coletas"] = con.execute("SELECT COUNT(DISTINCT ts) FROM precos WHERE familia=?",
                                   (familia,)).fetchone()[0]
    return saida
