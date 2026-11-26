import json
import urllib.parse
import urllib.request

from . import RAIZ


def windows(titulo, mensagem, url=None):
    try:
        from winotify import Notification, audio
        n = Notification(app_id="Radar de Preços", title=titulo, msg=mensagem,
                         icon=str(RAIZ / "web" / "icone.png") if (RAIZ / "web" / "icone.png").exists() else "")
        n.set_audio(audio.Default, loop=False)
        if url:
            n.add_actions(label="Abrir oferta", launch=url)
        n.show()
    except Exception as e:  # notificação nunca deve derrubar a coleta
        print("[alerta windows] falhou:", e)


def telegram(cfg, mensagem):
    tg = cfg.get("telegram") or {}
    if not tg.get("token") or not tg.get("chat_id"):
        return
    try:
        dados = urllib.parse.urlencode({
            "chat_id": tg["chat_id"], "text": mensagem, "disable_web_page_preview": "true"}).encode()
        urllib.request.urlopen(f"https://api.telegram.org/bot{tg['token']}/sendMessage", dados, timeout=20)
    except Exception as e:
        print("[alerta telegram] falhou:", e)


def fmt(v):
    return f"R$ {v:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")


def avaliar(cfg, con, familia, melhor, minimos_antes):
    """Dispara alerta se o menor preço atual é novo mínimo ou atingiu o preço-alvo."""
    conf = cfg.get("alertas", {})
    preco = melhor["preco_vista"]
    row = con.execute("SELECT menor_alertado FROM alertas_enviados WHERE familia=?",
                      (familia["id"],)).fetchone()
    ja_alertado = row[0] if row else None
    queda = conf.get("queda_minima_reais", 20)

    motivos = []
    alvo = familia.get("preco_alvo")
    if alvo and preco <= alvo:
        motivos.append(f"🎯 atingiu o preço-alvo ({fmt(alvo)})")
    inicio = minimos_antes.get("inicio")
    if conf.get("novo_menor_preco", True) and inicio and preco < inicio - 0.009:
        motivos.append(f"📉 menor preço desde o início do monitoramento (antes {fmt(inicio)})")
    if not motivos:
        return
    # não repetir alerta para o mesmo preço; só se cair mais que `queda`
    if ja_alertado is not None and preco > ja_alertado - queda:
        return

    titulo = f"{familia['nome']}: {fmt(preco)} na {melhor['loja'].upper()}"
    texto = "\n".join(motivos) + f"\n{melhor['titulo'][:120]}"
    if conf.get("windows", True):
        windows(titulo, texto, melhor["url"])
    if conf.get("telegram", True):
        telegram(cfg, f"{titulo}\n{texto}\n{melhor['url']}")
    con.execute("INSERT OR REPLACE INTO alertas_enviados (familia, menor_alertado) VALUES (?,?)",
                (familia["id"], preco))
    con.commit()
    print("[alerta]", titulo, "|", " / ".join(motivos))
