import json
import os
import secrets
import threading
import urllib.request

from fastapi import FastAPI, Header, HTTPException
from fastapi.responses import FileResponse

from pydantic import BaseModel

from . import RAIZ, carregar_config, db, coletor, alertas

app = FastAPI(title="Radar de Preços")

# Na nuvem, alterações (preço-alvo, coletar agora) exigem a senha do painel
SENHA = os.environ.get("PAINEL_SENHA")
# Na Vercel, "Coletar agora" dispara o workflow do GitHub Actions
GITHUB_TOKEN = os.environ.get("GITHUB_TOKEN")
GITHUB_REPO = os.environ.get("GITHUB_REPO")  # ex.: usuario/radarPrecos
NA_VERCEL = bool(os.environ.get("VERCEL"))


def exigir_senha(x_senha):
    if SENHA and not secrets.compare_digest(x_senha or "", SENHA):
        raise HTTPException(401, "Senha do painel incorreta")


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
    try:
        alvos = db.alvos(con, cfg["familias"])
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
                "id": f["id"], "nome": f["nome"], "preco_alvo": alvos[f["id"]],
                "melhor": melhor, "qtd_ofertas": len(validas), "qtd_suspeitas": len(atuais) - len(validas),
                "menor_por_loja": por_loja,
                "minimos": db.minimos_por_janela(con, f["id"]),
                "specs": s,
                "reais_por_ponto": round(preco / s["desempenho"], 2) if preco and s.get("desempenho") else None,
                "reais_por_gb": round(preco / s["vram_gb"], 2) if preco and s.get("vram_gb") else None,
            })
        return saida
    finally:
        con.close()


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
    cfg = carregar_config()
    con = db.conectar()
    try:
        ultima, linhas, por_loja = db.status(con)
        return {"ultima": ultima, "coletas": linhas, "por_loja": por_loja,
                "intervalo_minutos": cfg.get("intervalo_minutos", 15),
                "coletando": _coleta_manual.locked(),
                "nuvem": NA_VERCEL, "pode_coletar": (not NA_VERCEL) or bool(GITHUB_TOKEN and GITHUB_REPO),
                "pede_senha": bool(SENHA)}
    finally:
        con.close()


class Alvo(BaseModel):
    preco: float | None = None


@app.put("/api/alvo/{familia}")
def definir_alvo(familia: str, alvo: Alvo, x_senha: str | None = Header(None)):
    exigir_senha(x_senha)
    if alvo.preco is not None and alvo.preco <= 0:
        raise HTTPException(400, "Preço-alvo inválido")
    cfg = carregar_config()
    f = next((x for x in cfg["familias"] if x["id"] == familia), None)
    if not f:
        raise HTTPException(404, "Família não encontrada")
    preco = round(alvo.preco, 2) if alvo.preco else None
    con = db.conectar()
    try:
        db.definir_alvo(con, familia, preco)
        db.limpar_alertado(con, familia)  # permite um novo alerta para o alvo recém-definido
        validas = [o for o in db.ofertas_atuais(con, familia) if not o["suspeito"]]
        atingido = bool(preco and validas and validas[0]["preco_vista"] <= preco)
        if atingido:  # já está abaixo do alvo: avisa agora, sem esperar a próxima coleta
            alertas.avaliar(cfg, con, f, preco, validas[0], {})
    finally:
        con.close()
    return {"ok": True, "preco_alvo": preco, "atingido": atingido}


_coleta_manual = threading.Lock()


@app.post("/api/coletar")
def coletar_agora(x_senha: str | None = Header(None)):
    exigir_senha(x_senha)
    if NA_VERCEL:
        if not (GITHUB_TOKEN and GITHUB_REPO):
            raise HTTPException(501, "Coleta manual não configurada na nuvem")
        req = urllib.request.Request(
            f"https://api.github.com/repos/{GITHUB_REPO}/actions/workflows/coletar.yml/dispatches",
            data=b'{"ref":"main"}', method="POST",
            headers={"Authorization": f"Bearer {GITHUB_TOKEN}", "Accept": "application/vnd.github+json"})
        urllib.request.urlopen(req, timeout=20)
        return {"ok": True, "msg": "Coleta disparada no GitHub Actions (leva 1–3 min)"}
    if _coleta_manual.locked():
        return {"ok": False, "msg": "Coleta já em andamento"}

    def rodar():
        with _coleta_manual:
            coletor.coletar_uma_vez()
    threading.Thread(target=rodar, daemon=True).start()
    return {"ok": True}
