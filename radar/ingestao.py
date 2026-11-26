"""Receives the prices captured by the Chrome extension (pages opened by you) and saves them
with the same rules as the automatic collection: GPU family classification, minimum
price, suspicious flag and alerts."""
import statistics
from urllib.parse import urlsplit

from . import db, alertas
from .familias import classificar

# accepted domains per store: the link of every offer must point to the store itself
DOMINIOS = {
    "pichau": ("pichau.com.br",),
    "terabyte": ("terabyteshop.com.br",),
    "mercadolivre": ("mercadolivre.com.br", "mercadolibre.com"),
    "shopee": ("shopee.com.br",),
}
MAX_ITENS = 200


def _url_da_loja(url, loja):
    try:
        p = urlsplit(url)
    except ValueError:
        return False
    host = (p.hostname or "").lower()
    return p.scheme == "https" and any(host == d or host.endswith("." + d) for d in DOMINIOS[loja])


def _limpar(item, loja):
    """Validates one item sent by the extension; returns None if it's invalid."""
    try:
        preco = float(item.get("preco_vista"))
        cheio = float(item.get("preco_cheio") or preco)
    except (TypeError, ValueError):
        return None
    titulo = str(item.get("titulo") or "").strip()[:300]
    url = str(item.get("url") or "").strip()[:600]
    sku = str(item.get("sku") or url).strip()[:120]
    if not titulo or not sku or not (0 < preco < 100000) or not _url_da_loja(url, loja):
        return None
    return {
        "loja": loja, "sku": sku, "titulo": titulo, "url": url,
        "preco_vista": round(preco, 2), "preco_cheio": round(max(cheio, preco), 2),
        "disponivel": bool(item.get("disponivel", True)),
        "vendedor": str(item.get("vendedor") or "").strip()[:120],
    }


def _medianas_varejo(con, familias):
    """Median price of the national retail stores right now, per family (suspect reference)."""
    saida = {}
    for f in familias:
        precos = [o["preco_vista"] for o in db.ofertas_atuais(con, f["id"])
                  if o["loja"] not in ("aliexpress", "shopee") and not o["suspeito"]]
        if precos:
            saida[f["id"]] = statistics.median(precos)
    return saida


def processar(cfg, loja, itens):
    if loja not in DOMINIOS:
        raise ValueError(f"loja desconhecida: {loja}")
    familias = cfg["familias"]
    piso = cfg.get("preco_minimo_reais", 700)
    fator = cfg.get("suspeito_abaixo_da_mediana", 0.6)

    limpos = [x for x in (_limpar(i, loja) for i in itens[:MAX_ITENS]) if x]
    con = db.conectar()
    try:
        ts = db.agora()
        minimos_antes = {f["id"]: db.minimos_por_janela(con, f["id"]) for f in familias}
        medianas = _medianas_varejo(con, familias)

        classificadas = []
        for o in limpos:
            if o["preco_vista"] < piso:
                continue
            for fid in classificar(familias, o["titulo"]):
                ref = medianas.get(fid)
                classificadas.append({**o, "familia": fid,
                                      "suspeito": bool(ref and o["preco_vista"] < ref * fator)})
        if classificadas:
            db.salvar_ofertas(con, ts, classificadas)
        db.registrar_coleta(con, ts, loja, len(classificadas), None)

        alvos = db.alvos(con, familias)
        afetadas = {o["familia"] for o in classificadas}
        for f in familias:
            if f["id"] not in afetadas:
                continue
            validas = [o for o in db.ofertas_atuais(con, f["id"]) if not o["suspeito"]]
            if validas and validas[0]["ts"] == ts:  # the new lowest price came from this capture
                alertas.avaliar(cfg, con, f, alvos[f["id"]], validas[0], minimos_antes[f["id"]])

        por_familia = {}
        for o in classificadas:
            por_familia[o["familia"]] = por_familia.get(o["familia"], 0) + 1
        return {"recebidos": len(itens), "validos": len(limpos), "classificados": len(classificadas),
                "suspeitos": sum(o["suspeito"] for o in classificadas), "por_familia": por_familia}
    finally:
        con.close()
