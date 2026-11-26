"""Coletor AliExpress: only products shipped from Brazil ("Do Brasil"), with prices in BRL.

Reads the product list embedded in the search page."""
import json
import re
import time
import urllib.parse
import urllib.request

from .kabum import UA

MAX_PAGINAS = 1
PAUSA_ENTRE_BUSCAS = 10  # seconds; avoids triggering the anti-bot check
ORIGEM = re.compile(r'"shipFrom"\s*:\s*"([A-Z]{2})"')


def _baixar(url):
    req = urllib.request.Request(url, headers={
        "User-Agent": UA, "Accept-Language": "pt-BR,pt;q=0.9",
        # site preference (Brazil / BRL / Portuguese): without it, foreign servers
        # such as GitHub Actions receive prices in dollars
        "Cookie": "aep_usuc_f=site=bra&c_tp=BRL&region=BR&b_locale=pt_BR",
    })
    html = urllib.request.urlopen(req, timeout=40).read().decode("utf-8", "replace")
    i = html.find('"itemList":')
    if i < 0:
        raise RuntimeError("AliExpress: lista de produtos não encontrada (página de verificação?)")
    lista, _ = json.JSONDecoder().raw_decode(html, i + len('"itemList":'))
    return lista.get("content", [])


def _origem(item):
    """Country the item ships from (e.g. 'BR', 'CN'), read from the search tracking data."""
    m = ORIGEM.search(urllib.parse.unquote(json.dumps(item, ensure_ascii=False)))
    return m.group(1) if m else None


def buscar(termo):
    termo = termo.replace("placa de video", "").strip()
    slug = urllib.parse.quote(termo.replace(" ", "-"))
    vistos, saida, moedas = set(), [], set()
    for pagina in range(1, MAX_PAGINAS + 1):
        # shipFromCountry=BR = the "Do Brasil" filter (national stock, no import)
        itens = _baixar(f"https://pt.aliexpress.com/w/wholesale-{slug}.html"
                        f"?page={pagina}&shipCountry=br&shipFromCountry=BR")
        for p in itens:
            pid = p.get("productId")
            preco = ((p.get("prices") or {}).get("salePrice") or {})
            moedas.add(preco.get("currencyCode"))
            if not pid or pid in vistos or preco.get("currencyCode") != "BRL" or not preco.get("minPrice"):
                continue
            if _origem(p) != "BR":  # second check: drops anything that doesn't ship from Brazil
                continue
            vistos.add(pid)
            original = ((p.get("prices") or {}).get("originalPrice") or {}).get("minPrice")
            saida.append({
                "loja": "aliexpress",
                "sku": str(pid),
                "titulo": (p.get("title") or {}).get("displayTitle", ""),
                "url": f"https://pt.aliexpress.com/item/{pid}.html",
                "preco_vista": float(preco["minPrice"]),
                "preco_cheio": float(original or preco["minPrice"]),
                "disponivel": True,
                "vendedor": "AliExpress · envio do Brasil",
            })
        if not itens:
            break
    if not vistos and moedas - {"BRL", None}:
        raise RuntimeError(f"AliExpress: preços vieram em {', '.join(sorted(m for m in moedas if m))}, não em R$")
    time.sleep(PAUSA_ENTRE_BUSCAS)
    return saida
