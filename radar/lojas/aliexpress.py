"""Coletor AliExpress: lê a lista de produtos embutida na página de busca (preços em BRL)."""
import json
import time
import urllib.parse
import urllib.request

from .kabum import UA

MAX_PAGINAS = 1
PAUSA_ENTRE_BUSCAS = 10  # segundos; evita disparar a verificação anti-robô


def _baixar(url):
    req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept-Language": "pt-BR,pt;q=0.9"})
    html = urllib.request.urlopen(req, timeout=40).read().decode("utf-8", "replace")
    i = html.find('"itemList":')
    if i < 0:
        raise RuntimeError("AliExpress: lista de produtos não encontrada (página de verificação?)")
    lista, _ = json.JSONDecoder().raw_decode(html, i + len('"itemList":'))
    return lista.get("content", [])


def buscar(termo):
    termo = termo.replace("placa de video", "").strip()
    slug = urllib.parse.quote(termo.replace(" ", "-"))
    vistos, saida = set(), []
    for pagina in range(1, MAX_PAGINAS + 1):
        itens = _baixar(f"https://pt.aliexpress.com/w/wholesale-{slug}.html?page={pagina}&shipCountry=br")
        for p in itens:
            pid = p.get("productId")
            preco = ((p.get("prices") or {}).get("salePrice") or {})
            if not pid or pid in vistos or preco.get("currencyCode") != "BRL" or not preco.get("minPrice"):
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
                "vendedor": "AliExpress",
            })
        if not itens:
            break
    time.sleep(PAUSA_ENTRE_BUSCAS)
    return saida
