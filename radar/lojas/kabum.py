"""Coletor KaBuM: lê os dados estruturados (__NEXT_DATA__) da página de busca."""
import json
import re
import time
import urllib.parse
import urllib.request

UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/131.0 Safari/537.36")
MAX_PAGINAS = 3


def _baixar(url):
    req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept-Language": "pt-BR"})
    resp = urllib.request.urlopen(req, timeout=40)
    html = resp.read().decode("utf-8", "replace")
    m = re.search(r'<script id="__NEXT_DATA__"[^>]*>(.*?)</script>', html, re.S)
    if not m:
        raise RuntimeError("KaBuM: dados da página não encontrados")
    data = json.loads(m.group(1))["props"]["pageProps"]["data"]
    if isinstance(data, str):  # páginas de categoria trazem o JSON como texto
        data = json.loads(data)
    return data["catalogServer"], resp.geturl()


def _url_pagina(base, pagina):
    partes = urllib.parse.urlsplit(base)
    q = dict(urllib.parse.parse_qsl(partes.query))
    q.update({"page_number": str(pagina), "page_size": "100", "sort": "price"})
    return urllib.parse.urlunsplit(partes._replace(query=urllib.parse.urlencode(q)))


def _preco(p):
    """Menor preço à vista válido agora (inclui 'Oferta Ninja' quando ativa)."""
    candidatos = [p.get("priceWithDiscount") or p.get("price")]
    of = p.get("offer")
    agora = time.time()
    if of and of.get("priceWithDiscount") and (of.get("quantityAvailable") or 0) > 0:
        if (of.get("startsAt") or 0) <= agora <= (of.get("endsAt") or 0):
            candidatos.append(of["priceWithDiscount"])
    candidatos = [c for c in candidatos if c]
    return min(candidatos) if candidatos else None


def buscar(termo):
    slug = urllib.parse.quote(termo.strip().replace(" ", "-"))
    vistos, saida = set(), []
    base = f"https://www.kabum.com.br/busca/{slug}"
    for pagina in range(1, MAX_PAGINAS + 1):
        cat, final = _baixar(_url_pagina(base, pagina))
        if pagina == 1:
            base = final  # a busca pode redirecionar para uma categoria filtrada
        for p in cat.get("data", []):
            if p["code"] in vistos:
                continue
            vistos.add(p["code"])
            preco = _preco(p)
            if not preco:
                continue
            saida.append({
                "loja": "kabum",
                "sku": str(p["code"]),
                "titulo": p["name"],
                "url": f"https://www.kabum.com.br/produto/{p['code']}/{p.get('friendlyName', '')}",
                "preco_vista": float(preco),
                "preco_cheio": float(p.get("price") or preco),
                "disponivel": bool(p.get("available")),
                "vendedor": p.get("sellerName") or "",
            })
        if pagina >= (cat["meta"].get("totalPagesCount") or 1):
            break
        time.sleep(2)
    return saida
