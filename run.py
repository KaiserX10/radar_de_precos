"""Modo local: coletor em segundo plano + painel em http://localhost:<porta>.
`--so-coletar` faz uma coleta e sai (usado pelo GitHub Actions)."""
import sys

from radar import carregar_config, coletor

if __name__ == "__main__":
    if "--so-coletar" in sys.argv:
        coletor.coletar_uma_vez()
        sys.exit(0)

    import threading
    import webbrowser

    import uvicorn

    from radar.servidor import app

    porta = carregar_config().get("porta", 8765)
    threading.Thread(target=coletor.loop, daemon=True).start()
    if "--sem-navegador" not in sys.argv:
        threading.Timer(2, lambda: webbrowser.open(f"http://localhost:{porta}")).start()
    uvicorn.run(app, host="127.0.0.1", port=porta, log_level="warning")
