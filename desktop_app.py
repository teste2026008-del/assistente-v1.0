"""Janela nativa da Sexta-Feira para Windows."""
from http.server import ThreadingHTTPServer
from pathlib import Path
from threading import Thread
import logging
import socket
import time

from local_agent import HOST, PORT, Handler

LOG_DIR = Path.home() / "AppData" / "Local" / "Sexta-Feira"
LOG_DIR.mkdir(parents=True, exist_ok=True)
WEBVIEW_DATA_DIR = LOG_DIR / "webview-data"
WEBVIEW_DATA_DIR.mkdir(parents=True, exist_ok=True)
logging.basicConfig(filename=str(LOG_DIR / "app.log"), level=logging.INFO,
                    format="%(asctime)s %(levelname)s %(message)s", encoding="utf-8")

def port_open():
    with socket.socket() as sock:
        sock.settimeout(0.25)
        return sock.connect_ex((HOST, PORT)) == 0

def main():
    import webview
    server = None
    if not port_open():
        server = ThreadingHTTPServer((HOST, PORT), Handler)
        Thread(target=server.serve_forever, daemon=True).start()
        for _ in range(40):
            if port_open():
                break
            time.sleep(0.1)
    try:
        webview.create_window("Sexta-Feira", f"http://{HOST}:{PORT}",
                              width=1180, height=820, min_size=(360, 560),
                              text_select=True)
        webview.start(debug=False, private_mode=False, storage_path=str(WEBVIEW_DATA_DIR))
    except Exception:
        logging.exception("Erro ao abrir a janela da Sexta-Feira")
        raise
    finally:
        if server:
            server.shutdown()
            server.server_close()

if __name__ == "__main__":
    main()
