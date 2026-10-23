"""Janela nativa da Sexta-Feira para Windows, com atualização automática segura."""
from http.server import ThreadingHTTPServer
from pathlib import Path
from threading import Thread
import hashlib
import json
import logging
import os
import shutil
import socket
import tempfile
import time
from urllib.request import Request, urlopen

ROOT = Path(__file__).resolve().parent
OWNER = "teste2026008-del"
REPO = "assistente-v1.0"
BRANCH = "main"
GITHUB_API = f"https://api.github.com/repos/{OWNER}/{REPO}/commits/{BRANCH}"
RAW_BASE = f"https://raw.githubusercontent.com/{OWNER}/{REPO}/{BRANCH}"
APP_HOST = "127.0.0.1"
APP_PORT = 8765

LOG_DIR = Path.home() / "AppData" / "Local" / "Sexta-Feira"
LOG_DIR.mkdir(parents=True, exist_ok=True)
UPDATE_STATE = LOG_DIR / "update-state.json"
BACKUP_ROOT = LOG_DIR / "backups"
WEBVIEW_DATA_DIR = LOG_DIR / "webview-data"
WEBVIEW_DATA_DIR.mkdir(parents=True, exist_ok=True)
BACKUP_ROOT.mkdir(parents=True, exist_ok=True)
logging.basicConfig(filename=str(LOG_DIR / "app.log"), level=logging.INFO,
                    format="%(asctime)s %(levelname)s %(message)s", encoding="utf-8")

# Lista fixa de arquivos permitidos. Nunca baixa nem executa arquivos arbitrários do repositório.
UPDATE_FILES = (
    "desktop_app.py",
    "local_agent.py",
    "public/index.html",
    "public/local-whisper.js",
    "INICIAR-SEXTA-FEIRA.bat",
    "INICIAR-SEXTA-FEIRA-SOLO.bat",
    "ABRIR-SEXTA-FEIRA.vbs",
)

def _download(url, timeout=12):
    request = Request(url, headers={
        "User-Agent": "Sexta-Feira-AutoUpdater/1.0",
        "Cache-Control": "no-cache",
    })
    with urlopen(request, timeout=timeout) as response:
        if response.status != 200:
            raise RuntimeError(f"HTTP {response.status} ao baixar atualização")
        return response.read()

def _file_is_valid(relative, data):
    if not data or len(data) < 20:
        return False
    if relative.endswith(".py"):
        return b"\x00" not in data and (b"def " in data or b"import " in data or b"class " in data)
    if relative.endswith(".js"):
        return b"\x00" not in data and (b"function" in data or b"const " in data or b"import " in data)
    if relative.endswith(".html"):
        return b"<html" in data.lower() or b"<!doctype html" in data.lower()
    return True

def check_and_apply_updates():
    """Busca a versão main no GitHub e aplica os arquivos em lote com backup/rollback."""
    try:
        commit_info = json.loads(_download(GITHUB_API))
        latest_sha = str(commit_info.get("sha", "")).strip()
        if len(latest_sha) != 40:
            raise RuntimeError("O GitHub não retornou um SHA de commit válido")
        try:
            state = json.loads(UPDATE_STATE.read_text(encoding="utf-8"))
        except Exception:
            state = {}
        installed_sha = str(state.get("commit", ""))
        if installed_sha == latest_sha:
            return

        logging.info("Nova versão detectada no GitHub: %s (instalada: %s)",
                     latest_sha, installed_sha or "desconhecida")
        staged = {}
        with tempfile.TemporaryDirectory(prefix="sexta-feira-update-") as temp_dir:
            temp_root = Path(temp_dir)
            for relative in UPDATE_FILES:
                url = f"{RAW_BASE}/{relative}?v={latest_sha}"
                data = _download(url)
                if not _file_is_valid(relative, data):
                    raise RuntimeError(f"Arquivo de atualização inválido: {relative}")
                target = ROOT / relative
                if target.exists() and target.read_bytes() == data:
                    continue
                stage = temp_root / relative
                stage.parent.mkdir(parents=True, exist_ok=True)
                stage.write_bytes(data)
                staged[relative] = stage

            if not staged:
                UPDATE_STATE.write_text(json.dumps({
                    "commit": latest_sha,
                    "updated_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
                }, indent=2), encoding="utf-8")
                logging.info("Commit novo verificado; arquivos instalados já estavam atualizados.")
                return

            backup_dir = BACKUP_ROOT / time.strftime("%Y%m%d-%H%M%S")
            backups = {}
            replaced = []
            try:
                for relative in staged:
                    target = ROOT / relative
                    target.parent.mkdir(parents=True, exist_ok=True)
                    if target.exists():
                        backup = backup_dir / relative
                        backup.parent.mkdir(parents=True, exist_ok=True)
                        shutil.copy2(target, backup)
                        backups[relative] = backup
                for relative, stage in staged.items():
                    target = ROOT / relative
                    target.parent.mkdir(parents=True, exist_ok=True)
                    replace_temp = target.with_name(target.name + ".update-tmp")
                    shutil.copy2(stage, replace_temp)
                    os.replace(replace_temp, target)
                    replaced.append(relative)
                UPDATE_STATE.write_text(json.dumps({
                    "commit": latest_sha,
                    "updated_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
                    "files": replaced,
                }, indent=2), encoding="utf-8")
                logging.info("Atualização automática concluída: %s", ", ".join(replaced))
            except Exception:
                logging.exception("Falha ao aplicar atualização; restaurando backup")
                for relative in reversed(replaced):
                    target = ROOT / relative
                    backup = backups.get(relative)
                    try:
                        if backup and backup.exists():
                            shutil.copy2(backup, target)
                        elif target.exists():
                            target.unlink()
                    except Exception:
                        logging.exception("Falha ao restaurar %s", relative)
                raise
    except Exception as exc:
        # Atualização não pode impedir a abertura do aplicativo sem internet/GitHub.
        logging.warning("Atualização automática indisponível; abrindo versão local: %s", exc)

def port_open():
    with socket.socket() as sock:
        sock.settimeout(0.25)
        return sock.connect_ex((APP_HOST, APP_PORT)) == 0

def main():
    # Executa antes de importar local_agent e antes de abrir a interface para carregar
    # os arquivos novos nesta sessão. Falhas de internet não bloqueiam a assistente.
    check_and_apply_updates()

    # Importar só depois do updater permite atualizar local_agent.py com segurança.
    from local_agent import HOST, PORT, Handler

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
        webview.create_window("Sexta-Feira",
                              f"http://{HOST}:{PORT}/?v={int(time.time())}",
                              width=1180, height=820, min_size=(360, 560),
                              text_select=True)
        webview.start(debug=False, private_mode=False,
                      storage_path=str(WEBVIEW_DATA_DIR))
    except Exception:
        logging.exception("Erro ao abrir a janela da Sexta-Feira")
        raise
    finally:
        if server:
            server.shutdown()
            server.server_close()

if __name__ == "__main__":
    main()
