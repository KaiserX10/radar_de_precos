"""Classifica o título de uma oferta numa família de GPU (ex.: 'RTX 5060')."""
import re
import unicodedata

# Ofertas que não são placas de vídeo avulsas
EXCLUIR_GERAL = [
    r"notebook", r"^pc\b", r"\bpc gamer (completo|ryzen|intel|amd|core|i[3579])", r"^computador",
    r"\bkit\b", r"usad[ao]", r"recondicionad", r"^anuncios", r"compre \d+ e ganhe",
    r"all[\s-]?in[\s-]?one", r"desktop", r"workstation", r"cooler para", r"suporte",
    r"water\s*block", r"backplate", r"compativel", r"\bcabo\b", r"riser", r"\bcapa\b",
    r"^ventilador", r"^ventoinha", r"^novo ventilador", r"dissipador", r"bracket", r"^substitui",
    r"segunda mao", r"refurbish", r"minera", r"\b99\s*new\b", r"seminov", r"\bused\b",
    r"\bopen\s*box\b", r"de vitrine", r"mostruario",
]

MEMORIA = re.compile(r"(?<!\d)(\d{1,2})\s*g(?:b|ddr|\b)")


def normalizar(texto):
    t = unicodedata.normalize("NFKD", texto).encode("ascii", "ignore").decode()
    return re.sub(r"\s+", " ", t.lower())


def eh_placa_de_video(titulo_norm):
    if not re.search(r"placa (de )?(video|grafica)|\bgpu\b", titulo_norm):
        return False
    return not any(re.search(p, titulo_norm) for p in EXCLUIR_GERAL)


def memorias(titulo_norm):
    return {int(m) for m in MEMORIA.findall(titulo_norm) if int(m) in (8, 12, 16, 24)}


def pertence(familia, titulo):
    t = normalizar(titulo)
    if not eh_placa_de_video(t):
        return False
    if not any(re.search(p, t) for p in familia["incluir"]):
        return False
    if any(re.search(p, t) for p in familia["excluir"]):
        return False
    mem = familia.get("memoria")
    if mem:
        encontradas = memorias(t)
        # exige a memória certa e nenhuma outra (ex.: 8GB sem mencionar 16GB)
        if mem not in encontradas or (encontradas - {mem}):
            return False
    return True


def classificar(familias, titulo):
    return [f["id"] for f in familias if pertence(f, titulo)]
