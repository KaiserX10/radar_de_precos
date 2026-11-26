import json
import threading

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from . import RAIZ, carregar_config, salvar_config, db, coletor, alertas

app = FastAPI(title="Radar de Preços")
app.mount("/static", StaticFiles(directory=RAIZ / "web"), name="static")


def specs():
    return json.loads((RAIZ / "dados" / "specs.json").read_text(encoding="utf-8"))["gpus"]


@app.get("/")
def index():
    return FileResponse(RAIZ / "web" / "index.html")


@app.get("/api/resumo")
def resumo():
    cfg = carregar_config()
    sp = specs()
    con = db.conectar()
    saida = []
    for f in cfg["familias"]:
        atuais = db.ofertas_atuais(con, f["id"])
        validas = [o for o in atuais if not o["suspeito"]]
        melhor = validas[0] if validas else None
        s = sp.get(f["id"], {})
        preco = melhor["preco_vista"] if melhor else None
        por_loja = {}
        for o in validas:
            por_loja.setdefault(o["loja"], o["preco_vista"])
        saida.append({
            "id": f["id"], "nome": f["nome"], "preco_alvo": f.get("preco_alvo"),
            "melhor": melhor, "qtd_ofertas": len(validas), "qtd_suspeitas": len(atuais) - len(validas),
            "menor_por_loja": por_loja,
            "minimos": db.minimos_por_janela(con, f["id"]),
            "specs": s,
            "reais_por_ponto": round(preco / s["desempenho"], 2) if preco and s.get("desempenho") else None,
            "reais_por_gb": round(preco / s["vram_gb"], 2) if preco and s.get("vram_gb") else None,
        })
    con.close()
    return saida


@app.get("/api/serie/{familia}")
def serie(familia: str, horas: int | None = None):
    con = db.conectar()
    try:
        return [{"x": t, "y": p} for t, p in db.serie(con, familia, horas)]
    finally:
        con.close()


@app.get("/api/ofertas/{familia}")
def ofertas(familia: str):
    con = db.conectar()
    try:
        return db.ofertas_atuais(con, familia)
    finally:
        con.close()


@app.get("/api/status")
def status():
    con = db.conectar()
    try:
        ultima = con.execute("SELECT MAX(ts) FROM coletas").fetchone()[0]
        rows = con.execute("SELECT * FROM coletas WHERE ts=?", (ultima,)).fetchall() if ultima else []
        return {"ultima": ultima, "coletas": [dict(r) for r in rows],
                "intervalo_minutos": carregar_config().get("intervalo_minutos", 15),
                "coletando": _coleta_manual.locked()}
    finally:
        con.close()


class Alvo(BaseModel):
    preco: float | None = None


_trava_config = threading.Lock()


@app.put("/api/alvo/{familia}")
def definir_alvo(familia: str, alvo: Alvo):
    if alvo.preco is not None and alvo.preco <= 0:
        raise HTTPException(400, "Preço-alvo inválido")
    with _trava_config:
        cfg = carregar_config()
        f = next((x for x in cfg["familias"] if x["id"] == familia), None)
        if not f:
            raise HTTPException(404, "Família não encontrada")
        f["preco_alvo"] = round(alvo.preco, 2) if alvo.preco else None
        salvar_config(cfg)
    # permite um novo alerta para o alvo recém-definido
    con = db.conectar()
    con.execute("DELETE FROM alertas_enviados WHERE familia=?", (familia,))
    con.commit()
    validas = [o for o in db.ofertas_atuais(con, familia) if not o["suspeito"]]
    atingido = bool(f["preco_alvo"] and validas and validas[0]["preco_vista"] <= f["preco_alvo"])
    if atingido:  # já está abaixo do alvo: avisa agora, sem esperar a próxima coleta
        alertas.avaliar(cfg, con, f, validas[0], {})
    con.close()
    return {"ok": True, "preco_alvo": f["preco_alvo"], "atingido": atingido}


_coleta_manual = threading.Lock()


@app.post("/api/coletar")
def coletar_agora():
    if _coleta_manual.locked():
        return {"ok": False, "msg": "Coleta já em andamento"}

    def rodar():
        with _coleta_manual:
            coletor.coletar_uma_vez()
    threading.Thread(target=rodar, daemon=True).start()
    return {"ok": True}
