"""Acesso ao banco: SQLite local (dados/radar.db) ou Postgres quando DATABASE_URL está definido
(nuvem: GitHub Actions grava, Vercel lê)."""
import os
import sqlite3
from datetime import datetime, timedelta, timezone

from . import RAIZ

ARQUIVO = RAIZ / "dados" / "radar.db"
FUSO = timezone(timedelta(hours=-3))  # horário de Brasília (sem horário de verão)
def _limpar_url(valor):
    """Accepts the value pasted as an entire .env line: DATABASE_URL="postgresql://..."."""
    if not valor:
        return None
    valor = valor.strip()
    antes = valor.split("://", 1)[0]
    if "=" in antes:  # removes the 'NAME=' prefix (the '=' in ?sslmode=... comes after '://')
        valor = valor.split("=", 1)[1].strip()
    return valor.strip('"').strip("'").strip() or None


URL = _limpar_url(os.environ.get("DATABASE_URL") or os.environ.get("POSTGRES_URL"))
PG = bool(URL)

ESQUEMA = """
CREATE TABLE IF NOT EXISTS precos (
    id {ID},
    ts TEXT NOT NULL,
    loja TEXT NOT NULL,
    familia TEXT NOT NULL,
    sku TEXT NOT NULL,
    titulo TEXT NOT NULL,
    url TEXT NOT NULL,
    vendedor TEXT,
    preco_vista {REAL} NOT NULL,
    preco_cheio {REAL},
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
    menor_alertado {REAL}
);
CREATE TABLE IF NOT EXISTS alvos (
    familia TEXT PRIMARY KEY,
    preco {REAL}
);
"""

# Janelas medidas a partir do início da coleta (sem histórico de longo prazo)
JANELAS = {"24h": 24, "7d": 24 * 7, "30d": 24 * 30, "inicio": None}
VALIDA = "disponivel=1 AND suspeito=0"


class Conexao:
    """Mesma interface para SQLite e Postgres: SQL com '?' e linhas como dict."""

    def __init__(self):
        if PG:
            import psycopg
            from psycopg.rows import dict_row
            self.con = psycopg.connect(URL, row_factory=dict_row, connect_timeout=20)
        else:
            ARQUIVO.parent.mkdir(exist_ok=True)
            self.con = sqlite3.connect(ARQUIVO, timeout=30)
            self.con.row_factory = lambda c, r: {d[0]: v for d, v in zip(c.description, r)}

    def execute(self, sql, args=()):
        if PG:
            sql = sql.replace("?", "%s")
        cur = self.con.cursor()
        cur.execute(sql, args)
        return cur

    def executemany(self, sql, linhas):
        if PG:
            sql = sql.replace("?", "%s")
        self.con.cursor().executemany(sql, linhas)

    def um(self, sql, args=()):
        """Primeira coluna da primeira linha (ou None)."""
        row = self.execute(sql, args).fetchone()
        return next(iter(row.values())) if row else None

    def todos(self, sql, args=()):
        return self.execute(sql, args).fetchall()

    def commit(self):
        self.con.commit()

    def close(self):
        self.con.close()


_esquema_ok = False


def conectar():
    global _esquema_ok
    con = Conexao()
    if not _esquema_ok:
        ddl = ESQUEMA.format(ID="BIGSERIAL PRIMARY KEY" if PG else "INTEGER PRIMARY KEY",
                            REAL="DOUBLE PRECISION" if PG else "REAL")
        for comando in filter(str.strip, ddl.split(";")):
            con.execute(comando)
        if not PG:
            _migrar_sqlite(con)
        con.commit()
        _esquema_ok = True
    return con


def _migrar_sqlite(con):
    cols = {r["name"] for r in con.todos("PRAGMA table_info(precos)")}
    if "suspeito" not in cols:
        con.execute("ALTER TABLE precos ADD COLUMN suspeito INTEGER NOT NULL DEFAULT 0")
    pk = [r["name"] for r in con.todos("PRAGMA table_info(coletas)") if r["pk"]]
    if pk == ["ts"]:  # versão antiga: uma linha por coleta, não por loja
        con.execute("DROP TABLE coletas")
        con.execute("CREATE TABLE coletas (ts TEXT NOT NULL, loja TEXT NOT NULL, ofertas INTEGER,"
                    " erro TEXT, PRIMARY KEY (ts, loja))")
    con.execute("DROP TABLE IF EXISTS historico_manual")


def agora_dt():
    return datetime.now(FUSO).replace(tzinfo=None, microsecond=0)


def agora():
    return agora_dt().isoformat()


def _corte(horas):
    return (agora_dt() - timedelta(hours=horas)).isoformat()


# ---------- escrita ----------

def salvar_ofertas(con, ts, ofertas):
    con.executemany(
        "INSERT INTO precos (ts, loja, familia, sku, titulo, url, vendedor, preco_vista, preco_cheio, disponivel, suspeito)"
        " VALUES (?,?,?,?,?,?,?,?,?,?,?)",
        [(ts, o["loja"], o["familia"], o["sku"], o["titulo"], o["url"], o.get("vendedor"),
          o["preco_vista"], o.get("preco_cheio"), int(o["disponivel"]), int(o.get("suspeito", 0)))
         for o in ofertas],
    )
    con.commit()


def registrar_coleta(con, ts, loja, ofertas, erro):
    con.execute(
        "INSERT INTO coletas (ts, loja, ofertas, erro) VALUES (?,?,?,?)"
        " ON CONFLICT (ts, loja) DO UPDATE SET ofertas=excluded.ofertas, erro=excluded.erro",
        (ts, loja, ofertas, erro))
    con.commit()


def ultima_tentativa(con, loja):
    return con.um("SELECT MAX(ts) FROM coletas WHERE loja=?", (loja,))


def menor_alertado(con, familia):
    return con.um("SELECT menor_alertado FROM alertas_enviados WHERE familia=?", (familia,))


def marcar_alertado(con, familia, preco):
    con.execute(
        "INSERT INTO alertas_enviados (familia, menor_alertado) VALUES (?,?)"
        " ON CONFLICT (familia) DO UPDATE SET menor_alertado=excluded.menor_alertado",
        (familia, preco))
    con.commit()


def limpar_alertado(con, familia):
    con.execute("DELETE FROM alertas_enviados WHERE familia=?", (familia,))
    con.commit()


def alvos(con, familias):
    """Preço-alvo por família: o definido no painel tem prioridade sobre o config.json."""
    salvos = {r["familia"]: r["preco"] for r in con.todos("SELECT familia, preco FROM alvos")}
    return {f["id"]: salvos[f["id"]] if f["id"] in salvos else f.get("preco_alvo") for f in familias}


def definir_alvo(con, familia, preco):
    con.execute("INSERT INTO alvos (familia, preco) VALUES (?,?)"
                " ON CONFLICT (familia) DO UPDATE SET preco=excluded.preco", (familia, preco))
    con.commit()


# ---------- leitura ----------

def ultima_coleta(con, familia=None):
    if familia:
        return con.um("SELECT MAX(ts) FROM precos WHERE familia=?", (familia,))
    return con.um("SELECT MAX(ts) FROM precos")


def status(con):
    ultima = con.um("SELECT MAX(ts) FROM coletas")
    linhas = con.todos("SELECT * FROM coletas WHERE ts=?", (ultima,)) if ultima else []
    # última tentativa de cada loja (uma loja pode rodar com intervalo maior)
    por_loja = con.todos(
        "SELECT c.* FROM coletas c JOIN (SELECT loja, MAX(ts) ts FROM coletas GROUP BY loja) u"
        " ON c.loja=u.loja AND c.ts=u.ts ORDER BY c.loja")
    return ultima, linhas, por_loja


def ofertas_atuais(con, familia, max_horas=3):
    """Ofertas da coleta mais recente de cada loja (se uma loja falhar, mantém a anterior
    por até `max_horas`); as suspeitas vêm por último."""
    return con.todos(
        "SELECT p.* FROM precos p JOIN ("
        "  SELECT loja, MAX(ts) ts FROM precos WHERE familia=? AND ts>=? GROUP BY loja"
        ") u ON p.loja=u.loja AND p.ts=u.ts"
        " WHERE p.familia=? AND p.disponivel=1 ORDER BY p.suspeito, p.preco_vista",
        (familia, _corte(max_horas), familia))


def serie(con, familia, horas=None):
    """Menor preço válido em cada coleta."""
    filtro, args = "", [familia]
    if horas:
        filtro = " AND ts >= ?"
        args.append(_corte(horas))
    rows = con.todos(
        f"SELECT ts, MIN(preco_vista) AS preco FROM precos WHERE familia=? AND {VALIDA}{filtro}"
        " GROUP BY ts ORDER BY ts", args)
    return [(r["ts"], r["preco"]) for r in rows]


def minimos_por_janela(con, familia):
    saida = {}
    for nome, horas in JANELAS.items():
        filtro, args = "", [familia]
        if horas:
            filtro = " AND ts >= ?"
            args.append(_corte(horas))
        saida[nome] = con.um(f"SELECT MIN(preco_vista) FROM precos WHERE familia=? AND {VALIDA}{filtro}", args)
    saida["desde"] = con.um("SELECT MIN(ts) FROM precos WHERE familia=?", (familia,))
    saida["coletas"] = con.um("SELECT COUNT(DISTINCT ts) FROM precos WHERE familia=?", (familia,))
    return saida
