"""Inicia o coletor (em segundo plano) e o painel em http://localhost:<porta>."""
import sys
import threading
import webbrowser

import uvicorn

from radar import carregar_config, coletor
from radar.servidor import app

if __name__ == "__main__":
    porta = carregar_config().get("porta", 8765)
    if "--so-coletar" in sys.argv:
        coletor.coletar_uma_vez()
        sys.exit(0)
    threading.Thread(target=coletor.loop, daemon=True).start()
    if "--sem-navegador" not in sys.argv:
        threading.Timer(2, lambda: webbrowser.open(f"http://localhost:{porta}")).start()
    uvicorn.run(app, host="127.0.0.1", port=porta, log_level="warning")
