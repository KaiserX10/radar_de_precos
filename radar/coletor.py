import statistics
import time
import traceback
from datetime import datetime

from . import carregar_config, db, alertas
from .familias import classificar
from .lojas import LOJAS


def coletar_uma_vez():
    cfg = carregar_config()
    familias = cfg["familias"]
    con = db.conectar()
    ts = db.agora()
    minimos_antes = {f["id"]: db.minimos_por_janela(con, f["id"]) for f in familias}
    todas = []  # (loja, erro, ofertas classificadas)

    for nome_loja in cfg.get("lojas_ativas", []):
        loja = LOJAS.get(nome_loja)
        if not loja:
            continue
        intervalo = (cfg.get("intervalo_minutos_por_loja") or {}).get(nome_loja)
        if intervalo:
            ultima = con.execute("SELECT MAX(ts) FROM coletas WHERE loja=?", (nome_loja,)).fetchone()[0]
            if ultima and (datetime.fromisoformat(ts) - datetime.fromisoformat(ultima)).total_seconds() < intervalo * 60 - 30:
                continue
        brutas, erro = {}, None
        try:
            # junta o resultado de todas as buscas e só depois classifica
            for termo in dict.fromkeys(f["busca"] for f in familias):
                for o in loja.buscar(termo):
                    brutas[o["sku"]] = o
                time.sleep(2)
        except Exception as e:
            erro = f"{type(e).__name__}: {e}"
            traceback.print_exc()

        classificadas = []
        piso = cfg.get("preco_minimo_reais", 700)  # abaixo disso não é uma GPU (acessório, peça)
        for o in brutas.values():
            if o["preco_vista"] < piso:
                continue
            for fid in classificar(familias, o["titulo"]):
                classificadas.append({**o, "familia": fid})
        todas.append((nome_loja, erro, classificadas))

    # Preço muito abaixo da mediana da família = provável falso/golpe.
    # A referência é a mediana das lojas de varejo nacionais; sem elas, a de todas as lojas.
    fator = cfg.get("suspeito_abaixo_da_mediana", 0.6)
    varejo, geral = {}, {}
    for nome_loja, _, lst in todas:
        for o in lst:
            if o["disponivel"]:
                geral.setdefault(o["familia"], []).append(o["preco_vista"])
                if nome_loja != "aliexpress":
                    varejo.setdefault(o["familia"], []).append(o["preco_vista"])
    medianas = {fid: statistics.median(varejo.get(fid) or v) for fid, v in geral.items()}

    for nome_loja, erro, lst in todas:
        suspeitas = 0
        for o in lst:
            o["suspeito"] = o["preco_vista"] < medianas.get(o["familia"], 0) * fator
            suspeitas += o["suspeito"]
        if lst:
            db.salvar_ofertas(con, ts, lst)
        con.execute("INSERT OR REPLACE INTO coletas (ts, loja, ofertas, erro) VALUES (?,?,?,?)",
                    (ts, nome_loja, len(lst), erro))
        con.commit()
        print(f"[{ts}] {nome_loja}: {len(lst)} ofertas ({suspeitas} suspeitas)" + (f" | ERRO {erro}" if erro else ""))

    for f in familias:
        validas = [o for o in db.ofertas_atuais(con, f["id"]) if not o["suspeito"] and o["ts"] == ts]
        if validas:
            alertas.avaliar(cfg, con, f, validas[0], minimos_antes[f["id"]])
    con.close()


def loop(parar=None):
    while not (parar and parar.is_set()):
        try:
            coletar_uma_vez()
        except Exception:
            traceback.print_exc()
        minutos = carregar_config().get("intervalo_minutos", 15)
        for _ in range(int(minutos * 60)):
            if parar and parar.is_set():
                return
            time.sleep(1)
