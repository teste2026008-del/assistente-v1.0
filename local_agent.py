#!/usr/bin/env python3
"""Agente local da Sexta-Feira. Escuta somente em localhost."""
from http.server import ThreadingHTTPServer, SimpleHTTPRequestHandler
from pathlib import Path
from urllib.parse import urlparse, quote_plus, unquote
import json, platform, subprocess, webbrowser, urllib.request, urllib.error, datetime, os, unicodedata, asyncio, sys, io, ipaddress, socket, re, tempfile, hashlib, mimetypes
from email.message import Message
from threading import Lock

ROOT=Path(__file__).resolve().parent
PUBLIC=ROOT/"public"
WORKER="https://assistente-v1-0.teste2026008.workers.dev"
NOTES=ROOT/"notas"
MEMORY_DIR=Path.home()/"AppData"/"Local"/"Sexta-Feira"
MEMORY_FILE=MEMORY_DIR/"memoria.json"
REMINDERS_FILE=MEMORY_DIR/"lembretes.json"
_MUSIC_INDEX={}
_MUSIC_EXTENSIONS={".mp3",".wav",".m4a",".aac",".ogg",".flac",".opus"}
MEMORY_DIR.mkdir(parents=True,exist_ok=True)
HOST,PORT="127.0.0.1",8765
# Controle de navegador isolado, iniciado somente quando o usuário pedir.
_BROWSER_PLAYWRIGHT=None
_BROWSER_CONTEXT=None
_BROWSER_PAGE=None
_BROWSER_LOCK=Lock()
TTS_DIR=MEMORY_DIR/"models"/"kokoro"
TTS_MODEL=TTS_DIR/"kokoro-v1.0.onnx"
TTS_VOICES=TTS_DIR/"voices-v1.0.bin"
KOKORO_MODEL_URL="https://github.com/thewh1teagle/kokoro-onnx/releases/download/model-files-v1.1/kokoro-v1.0.onnx"
KOKORO_VOICES_URL="https://github.com/thewh1teagle/kokoro-onnx/releases/download/model-files-v1.1/voices-v1.0.bin"
_KOKORO=None
_KOKORO_G2P=None
_TTS_LOCK=Lock()

def _download_model(url,path,min_bytes):
 path.parent.mkdir(parents=True,exist_ok=True)
 if path.exists() and path.stat().st_size>=min_bytes: return
 temp=path.with_suffix(path.suffix+".download")
 try:
  request=urllib.request.Request(url,headers={"User-Agent":"Sexta-Feira-Local/1.0"})
  with urllib.request.urlopen(request,timeout=90) as response, temp.open("wb") as target:
   while True:
    chunk=response.read(1024*1024)
    if not chunk: break
    target.write(chunk)
  if temp.stat().st_size<min_bytes: raise RuntimeError("O arquivo do modelo baixado está incompleto.")
  temp.replace(path)
 finally:
  try:
   if temp.exists(): temp.unlink()
  except OSError: pass

def _ensure_kokoro():
 global _KOKORO,_KOKORO_G2P
 if _KOKORO is not None and _KOKORO_G2P is not None: return _KOKORO,_KOKORO_G2P
 try:
  from kokoro_onnx import Kokoro
  from misaki.espeak import EspeakG2P
 except ImportError:
  installed=subprocess.run([sys.executable,"-m","pip","install","--user","kokoro-onnx","soundfile","misaki-fork[en]"],capture_output=True,text=True,timeout=600)
  if installed.returncode!=0: raise RuntimeError("Não consegui instalar o Kokoro local: "+(installed.stderr or installed.stdout or "erro no pip")[-240:])
  from kokoro_onnx import Kokoro
  from misaki.espeak import EspeakG2P
 _download_model(KOKORO_MODEL_URL,TTS_MODEL,50_000_000)
 _download_model(KOKORO_VOICES_URL,TTS_VOICES,5_000_000)
 _KOKORO=Kokoro(str(TTS_MODEL),str(TTS_VOICES))
 _KOKORO_G2P=EspeakG2P(language="pt-br")
 return _KOKORO,_KOKORO_G2P

def _kokoro_wav(text):
 import soundfile as sf
 with _TTS_LOCK:
  engine,g2p=_ensure_kokoro()
  phonemes,_=g2p(text)
  samples,rate=engine.create(phonemes,"pf_dora",is_phonemes=True)
  output=io.BytesIO()
  sf.write(output,samples,rate,format="WAV",subtype="PCM_16")
  return output.getvalue()

FOLDERS={"downloads":Path.home()/"Downloads","pasta de downloads":Path.home()/"Downloads","documentos":Path.home()/"Documents","meus documentos":Path.home()/"Documents","área de trabalho":Path.home()/"Desktop","area de trabalho":Path.home()/"Desktop","desktop":Path.home()/"Desktop","imagens":Path.home()/"Pictures","fotos":Path.home()/"Pictures","musicas":Path.home()/"Music","musica":Path.home()/"Music","músicas":Path.home()/"Music","música":Path.home()/"Music","videos":Path.home()/"Videos","video":Path.home()/"Videos","vídeos":Path.home()/"Videos","vídeo":Path.home()/"Videos"}
# Lista fixa de aplicativos permitidos: não aceita comandos arbitrários vindos do chat.
APPS={
 "bloco de notas":["notepad.exe"],"calculadora":["calc.exe"],"paint":["mspaint.exe"],
 "explorador de arquivos":["explorer.exe"],"gerenciador de tarefas":["taskmgr.exe"],
 "chrome":["cmd.exe","/c","start","","chrome"],"edge":["cmd.exe","/c","start","","msedge"],
 "firefox":["cmd.exe","/c","start","","firefox"],"opera":["cmd.exe","/c","start","","opera"],
 "opera gx":["cmd.exe","/c","start","","opera://"],
 "whatsapp":["cmd.exe","/c","start","","whatsapp:"],"spotify":["cmd.exe","/c","start","","spotify:"],
 "discord":["cmd.exe","/c","start","","discord:"],"steam":["cmd.exe","/c","start","","steam:"],
 "vscode":["cmd.exe","/c","start","","code"],"word":["cmd.exe","/c","start","","winword"],
 "excel":["cmd.exe","/c","start","","excel"],"powerpoint":["cmd.exe","/c","start","","powerpnt"],
 "configuracoes":["cmd.exe","/c","start","","ms-settings:"],
 "terminal":["cmd.exe","/c","start","","wt.exe"],"prompt de comando":["cmd.exe","/c","start","","cmd.exe"],
 "cmd":["cmd.exe","/c","start","","cmd.exe"],"powershell":["cmd.exe","/c","start","","powershell.exe"]
}
def normalize_key(value):
 return unicodedata.normalize("NFD",str(value or "").lower()).encode("ascii","ignore").decode("ascii").strip()

MAX_DOWNLOAD_BYTES=100*1024*1024

def _download_folder(label):
 key=normalize_key(label or "downloads")
 folder=FOLDERS.get(key)
 if folder is None:
  raise ValueError("Escolha uma pasta permitida: Downloads, Documentos, Área de Trabalho, Imagens, Músicas ou Vídeos.")
 folder.mkdir(parents=True,exist_ok=True)
 return folder

def _validate_public_http_url(raw):
 url=str(raw or "").strip()
 if len(url)>2048: raise ValueError("O link é longo demais.")
 parsed=urlparse(url)
 if parsed.scheme not in ("http","https") or not parsed.hostname or parsed.username or parsed.password:
  raise ValueError("Use um link HTTP ou HTTPS público, sem usuário ou senha no endereço.")
 try: port=parsed.port
 except ValueError: raise ValueError("A porta do endereço é inválida.")
 expected=443 if parsed.scheme=="https" else 80
 if port not in (None,expected): raise ValueError("Por segurança, só aceito as portas padrão de HTTP e HTTPS.")
 try:
  addresses=socket.getaddrinfo(parsed.hostname,port or expected,type=socket.SOCK_STREAM)
  ips={ipaddress.ip_address(item[4][0].split("%")[0]) for item in addresses}
 except (OSError,ValueError):
  raise ValueError("Não consegui validar o endereço público. Confira o link e tente novamente.")
 if not ips or any(not address.is_global for address in ips):
  raise ValueError("Por segurança, não baixo arquivos de endereços locais ou privados.")
 return parsed

class _SafeDownloadRedirect(urllib.request.HTTPRedirectHandler):
 def redirect_request(self,req,fp,code,msg,headers,newurl):
  before=urlparse(req.full_url)
  after=_validate_public_http_url(newurl)
  if before.scheme=="https" and after.scheme!="https":
   raise ValueError("O link tentou sair de HTTPS para uma conexão sem criptografia.")
  return super().redirect_request(req,fp,code,msg,headers,newurl)

def _safe_download_name(name):
 value=str(name or "").replace("\\","/").rsplit("/",1)[-1]
 value=re.sub(r'[<>:"/\\|?*\x00-\x1f]','_',value).strip(" .")
 if not value or value in (".",".."): value="arquivo"
 if len(value)>160:
  suffix=Path(value).suffix[:20]
  value=value[:160-len(suffix)].rstrip(" .")+suffix
 if Path(value).stem.upper() in {"CON","PRN","AUX","NUL","COM1","COM2","COM3","COM4","COM5","COM6","COM7","COM8","COM9","LPT1","LPT2","LPT3","LPT4","LPT5","LPT6","LPT7","LPT8","LPT9"}:
  value="_"+value
 return value

def _reserve_download_path(folder,filename):
 base=_safe_download_name(filename)
 stem=Path(base).stem or "arquivo";suffix=Path(base).suffix
 for index in range(1,1000):
  candidate=folder/(base if index==1 else f"{stem} ({index}){suffix}")
  try:
   fd=os.open(str(candidate),os.O_CREAT|os.O_EXCL|os.O_WRONLY,0o600)
   os.close(fd)
   return candidate
  except FileExistsError: continue
 raise OSError("Não encontrei um nome de arquivo livre na pasta.")

def _finish_download(temp_path,folder,filename):
 temp_path=Path(temp_path)
 size=temp_path.stat().st_size
 if size<=0: raise ValueError("O arquivo recebido está vazio.")
 if size>MAX_DOWNLOAD_BYTES: raise ValueError("O arquivo excede o limite de 100 MB.")
 target=_reserve_download_path(folder,filename)
 try: os.replace(str(temp_path),str(target))
 except Exception:
  try: target.unlink()
  except OSError: pass
  raise
 return target,size

def _download_http_file(url,folder):
 parsed=_validate_public_http_url(url)
 request=urllib.request.Request(parsed.geturl(),headers={"User-Agent":"Sexta-Feira-Local/1.0","Accept":"*/*"})
 opener=urllib.request.build_opener(_SafeDownloadRedirect())
 temp_path=None
 try:
  with opener.open(request,timeout=30) as response:
   final_url=_validate_public_http_url(response.geturl())
   if parsed.scheme=="https" and final_url.scheme!="https":
    raise ValueError("O link terminou em uma conexão sem criptografia.")
   length=response.headers.get("Content-Length")
   if length:
    try: expected_size=int(length)
    except ValueError: expected_size=0
    if expected_size>MAX_DOWNLOAD_BYTES: raise ValueError("O arquivo excede o limite de 100 MB.")
   disposition=response.headers.get("Content-Disposition","")
   message=Message();message["content-disposition"]=disposition
   filename=message.get_filename() or Path(unquote(final_url.path)).name or "arquivo"
   filename=_safe_download_name(filename)
   content_type=response.headers.get("Content-Type","").split(";",1)[0].strip().lower()
   if content_type=="text/html" and "attachment" not in disposition.lower() and Path(filename).suffix.lower() not in (".html",".htm"):
    raise ValueError("Esse link abre uma página, não um arquivo direto. Use o navegador controlável e peça para baixar o link da página.")
   with tempfile.NamedTemporaryFile(prefix=".sexta-download-",suffix=".part",dir=str(folder),delete=False) as target:
    temp_path=Path(target.name);total=0
    while True:
     chunk=response.read(256*1024)
     if not chunk: break
     total+=len(chunk)
     if total>MAX_DOWNLOAD_BYTES: raise ValueError("O arquivo excede o limite de 100 MB.")
     target.write(chunk)
  final_path,size=_finish_download(temp_path,folder,filename)
  temp_path=None
  return final_path,size
 finally:
  if temp_path is not None:
   try: temp_path.unlink()
   except OSError: pass


class Handler(SimpleHTTPRequestHandler):
 def __init__(self,*a,**kw): super().__init__(*a,directory=str(PUBLIC),**kw)
 def log_message(self,fmt,*args): print("[Sexta-Feira] "+(fmt%args))
 def end_headers(self):
  self.send_header("Cache-Control","no-store, no-cache, must-revalidate, max-age=0")
  self.send_header("Pragma","no-cache")
  super().end_headers()
 def send_json(self,status,obj):
  b=json.dumps(obj,ensure_ascii=False).encode("utf-8")
  self.send_response(status);self.send_header("Content-Type","application/json; charset=utf-8");self.send_header("Content-Length",str(len(b)));self.send_header("Cache-Control","no-store");self.end_headers();self.wfile.write(b)
 def do_GET(self):
  p=urlparse(self.path).path
  if p=="/api/health": return self.send_json(200,{"ok":True,"service":"Sexta-Feira Local","host":HOST,"port":PORT})
  if p=="/api/update/status":
   try:
    state=json.loads((MEMORY_DIR/"web-update-state.json").read_text(encoding="utf-8"))
   except Exception: state={"commit":"","restart_required":False}
   return self.send_json(200,state)
  if p=="/api/music/file":
   params=urllib.parse.parse_qs(urlparse(self.path).query)
   file_id=(params.get("id") or [""])[0]
   target=_MUSIC_INDEX.get(file_id)
   if not target:return self.send_json(404,{"error":"Faixa não encontrada. Peça para a Sexta-Feira procurar novamente."})
   try:
    path=Path(target).resolve(strict=True)
    roots=[(Path.home()/"Music").resolve(),(Path.home()/"Downloads").resolve()]
    if not any(path==root or root in path.parents for root in roots) or path.suffix.lower() not in _MUSIC_EXTENSIONS or not path.is_file():return self.send_json(403,{"error":"A faixa está fora das pastas de música permitidas."})
    size=path.stat().st_size
    start,end=0,size-1;status=200
    byte_range=self.headers.get("Range","")
    if byte_range.startswith("bytes="):
     spec=byte_range[6:].split(",",1)[0].strip()
     left,right=(spec.split("-",1)+[""])[:2]
     if left:
      start=int(left);end=min(int(right),size-1) if right else size-1
     elif right:
      suffix=int(right);start=max(0,size-suffix)
     if start>=size or end<start:
      self.send_response(416);self.send_header("Content-Range",f"bytes */{size}");self.end_headers();return
     status=206
    length=end-start+1;self.send_response(status);self.send_header("Content-Type",mimetypes.guess_type(path.name)[0] or "application/octet-stream");self.send_header("Accept-Ranges","bytes");self.send_header("Content-Length",str(length));self.send_header("Content-Disposition","inline; filename*=UTF-8''"+quote_plus(path.name));self.send_header("Cache-Control","no-store")
    if status==206:self.send_header("Content-Range",f"bytes {start}-{end}/{size}")
    self.end_headers()
    with path.open("rb") as media:
     media.seek(start);remaining=length
     while remaining:
      chunk=media.read(min(65536,remaining))
      if not chunk:break
      self.wfile.write(chunk);remaining-=len(chunk)
   except (OSError,ValueError,OverflowError):return self.send_json(404,{"error":"Não consegui abrir essa faixa."})
   return
  if p=="/api/memory": return self.memory_get()
  if p=="/api/reminders/check": return self.reminders_check()
  if p=="/api/reminders": return self.reminders_get()
  if p.startswith("/api/"): return self.proxy(p,b"","GET")
  return super().do_GET()
 def do_POST(self):
  p=urlparse(self.path).path;n=min(int(self.headers.get("Content-Length","0")),100000);body=self.rfile.read(n)
  if p=="/api/action":
   try:data=json.loads(body or b"{}")
   except Exception:return self.send_json(400,{"error":"JSON inválido."})
   return self.action(data)
  if p=="/api/tts": return self.local_tts(body)
  if p=="/api/reminders":
   try:data=json.loads(body or b"{}")
   except Exception:return self.send_json(400,{"error":"JSON inválido."})
   return self.reminders_save(data)
  if p=="/api/memory":
   try:data=json.loads(body or b"{}")
   except Exception:return self.send_json(400,{"error":"JSON inválido."})
   return self.memory_save(data)
  if p.startswith("/api/"):return self.proxy(p,body,"POST")
  return self.send_json(404,{"error":"Rota não encontrada."})
 def local_tts(self,body):
  try:
   data=json.loads(body or b"{}")
  except Exception:
   return self.send_json(400,{"error":"Pedido de voz inválido."})
  text=str(data.get("text","")).strip()[:1800]
  if not text:
   return self.send_json(400,{"error":"Não recebi texto para falar."})
  # Prioridade real: vozes neurais online da Microsoft; Kokoro fica somente como reserva.
  try:
   import edge_tts
  except ImportError:
   try:
    install=subprocess.run([sys.executable,"-m","pip","install","--user","edge-tts"],capture_output=True,text=True,timeout=180)
    if install.returncode!=0:
     raise RuntimeError((install.stderr or install.stdout or "pip falhou")[-240:])
    import edge_tts
   except Exception as e:
    print("[Sexta-Feira] Não consegui preparar Edge TTS: "+str(e)[:220])
    edge_tts=None
  audio=None
  voice_used=None
  if edge_tts is not None:
   async def generate(voice):
    communicate=edge_tts.Communicate(text,voice=voice,rate="-5%",pitch="+0Hz",volume="+0%")
    chunks=[]
    async for chunk in communicate.stream():
     if chunk.get("type")=="audio":
      chunks.append(chunk.get("data",b""))
    result=b"".join(chunks)
    if not result:
     raise RuntimeError("A voz neural não retornou áudio.")
    return result
   for voice in ("pt-BR-FranciscaNeural","pt-BR-ThalitaMultilingualNeural"):
    try:
     audio=asyncio.run(generate(voice))
     voice_used=voice
     break
    except Exception as e:
     print("[Sexta-Feira] Falha na voz "+voice+": "+str(e)[:180])
  if not audio:
   try:
    audio=_kokoro_wav(text)
    voice_used="Kokoro Dora (reserva local)"
    content_type="audio/wav"
   except Exception as e:
    return self.send_json(502,{"error":"As vozes neurais não puderam gerar áudio. Verifique a conexão com a internet e tente novamente.","detail":str(e)[:240]})
  else:
   content_type="audio/mpeg"
  self.send_response(200)
  self.send_header("Content-Type",content_type)
  self.send_header("X-Voice-Name",voice_used or "Voz neural")
  self.send_header("Content-Length",str(len(audio)))
  self.send_header("Cache-Control","no-store")
  self.end_headers()
  self.wfile.write(audio)
 def proxy(self,path,body,method):
  try:
   req=urllib.request.Request(WORKER+path,data=body if method=="POST" else None,method=method,headers={"Content-Type":"application/json","User-Agent":"Sexta-Feira-Local/1.0"})
   with urllib.request.urlopen(req,timeout=60) as res:
    content_type=res.headers.get("Content-Type","application/json")
    if path=="/api/chat" and "text/event-stream" in content_type:
     self.send_response(res.status);self.send_header("Content-Type",content_type);self.send_header("Cache-Control","no-cache, no-transform");self.send_header("Connection","close");self.end_headers();self.close_connection=True
     while True:
      chunk=res.readline()
      if not chunk:break
      self.wfile.write(chunk);self.wfile.flush()
     return
    data=res.read();self.send_response(res.status);self.send_header("Content-Type",content_type);self.send_header("Content-Length",str(len(data)));self.end_headers();self.wfile.write(data)
  except urllib.error.HTTPError as e:
   data=e.read();self.send_response(e.code);self.send_header("Content-Type",e.headers.get("Content-Type","application/json"));self.send_header("Content-Length",str(len(data)));self.end_headers();self.wfile.write(data)
  except (BrokenPipeError,ConnectionResetError):return
  except Exception as e:self.send_json(502,{"error":"Falha ao conectar à IA/voz online.","detail":str(e)[:220]})
 def reminders_read(self):
  try:
   data=json.loads(REMINDERS_FILE.read_text(encoding="utf-8"))
   return data if isinstance(data,list) else []
  except (OSError,ValueError,TypeError): return []
 def reminders_check(self):
  items=self.reminders_read();now=datetime.datetime.now().astimezone();due=[];changed=False
  for item in items:
   if item.get("done"): continue
   try: when=datetime.datetime.fromisoformat(str(item.get("due","")))
   except ValueError: continue
   if when.tzinfo is None: when=when.astimezone()
   if when<=now:
    item["done"]=True;due.append({"id":item.get("id",""),"text":item.get("text","")});changed=True
  if changed:
   try: REMINDERS_FILE.write_text(json.dumps(items,ensure_ascii=False,indent=2),encoding="utf-8")
   except OSError: pass
  return self.send_json(200,{"due":due})
 def reminders_get(self):
  return self.send_json(200,{"reminders":self.reminders_read()})
 def reminders_save(self,d):
  items=d.get("reminders",[])
  if not isinstance(items,list): return self.send_json(400,{"error":"Lista de lembretes inválida."})
  clean=[]
  for x in items[-100:]:
   if isinstance(x,dict) and str(x.get("text","")).strip() and str(x.get("due","")).strip():
    clean.append({"id":str(x.get("id",""))[:80],"text":str(x.get("text","")).strip()[:300],"due":str(x.get("due",""))[:40],"done":bool(x.get("done",False))})
  try: REMINDERS_FILE.write_text(json.dumps(clean,ensure_ascii=False,indent=2),encoding="utf-8")
  except OSError as e:return self.send_json(500,{"error":"Não consegui salvar os lembretes: "+str(e)[:120]})
  return self.send_json(200,{"ok":True,"count":len(clean)})
 def memory_read(self):
  try:
   data=json.loads(MEMORY_FILE.read_text(encoding="utf-8"))
   if not isinstance(data,dict): raise ValueError("Formato inválido")
  except (OSError,ValueError,TypeError):
   data={"facts":[],"history":[]}
  data.setdefault("facts",[]);data.setdefault("history",[])
  return data
 def memory_get(self):
  data=self.memory_read()
  return self.send_json(200,{"facts":data["facts"],"history":data["history"][-12:]})
 def memory_save(self,d):
  facts=d.get("facts",[]);history=d.get("history",[])
  if not isinstance(facts,list) or not isinstance(history,list):
   return self.send_json(400,{"error":"Memória inválida."})
  facts=[str(x).strip()[:500] for x in facts if str(x).strip()][:100]
  history=[{"role":str(x.get("role",""))[:20],"text":str(x.get("text","")).strip()[:3000]} for x in history[-12:] if isinstance(x,dict) and str(x.get("text","")).strip()]
  try:
   MEMORY_FILE.write_text(json.dumps({"facts":facts,"history":history},ensure_ascii=False,indent=2),encoding="utf-8")
  except OSError as e:
   return self.send_json(500,{"error":"Não consegui salvar a memória local: "+str(e)[:160]})
  return self.send_json(200,{"ok":True,"facts":len(facts),"history":len(history)})
 def browser_action(self,d):
  global _BROWSER_PLAYWRIGHT,_BROWSER_CONTEXT,_BROWSER_PAGE
  kind=str(d.get("type",""))
  with _BROWSER_LOCK:
   try:
    if kind=="browser_start":
     if _BROWSER_PAGE is not None:
      return self.send_json(200,{"message":"O navegador controlável já está aberto. Diga o endereço ou a próxima ação."})
     try:
      from playwright.sync_api import sync_playwright
     except ImportError:
      install=subprocess.run([sys.executable,"-m","pip","install","--user","playwright"],capture_output=True,text=True,timeout=240)
      if install.returncode!=0:return self.send_json(503,{"error":"Não consegui instalar o controlador do navegador. "+(install.stderr or install.stdout or "Confira a conexão.")[-240:]})
      try: from playwright.sync_api import sync_playwright
      except ImportError:return self.send_json(503,{"error":"O controlador Playwright não ficou disponível após a instalação."})
     _BROWSER_PLAYWRIGHT=sync_playwright().start()
     launch_errors=[]
     for channel in ("msedge","chrome",None):
      try:
       options={"headless":False}
       if channel: options["channel"]=channel
       _BROWSER_CONTEXT=_BROWSER_PLAYWRIGHT.chromium.launch_persistent_context(str(MEMORY_DIR/"browser-profile"),**options)
       break
      except Exception as e:launch_errors.append(str(e)[:180])
     if _BROWSER_CONTEXT is None:
      try:_BROWSER_PLAYWRIGHT.stop()
      except Exception:pass
      _BROWSER_PLAYWRIGHT=None
      return self.send_json(503,{"error":"Não encontrei Chrome/Edge compatível nem o Chromium do Playwright. Instale Google Chrome ou Microsoft Edge e tente novamente. Detalhe: "+" | ".join(launch_errors)[-320:]})
     _BROWSER_PAGE=_BROWSER_CONTEXT.pages[0] if _BROWSER_CONTEXT.pages else _BROWSER_CONTEXT.new_page()
     _BROWSER_PAGE.goto("https://www.google.com",wait_until="domcontentloaded",timeout=30000)
     return self.send_json(200,{"message":"Abri uma janela de navegador controlável. Agora posso navegar, ler a página e interagir com campos e botões."})
    if kind=="browser_stop":
     if _BROWSER_CONTEXT is not None:_BROWSER_CONTEXT.close()
     if _BROWSER_PLAYWRIGHT is not None:_BROWSER_PLAYWRIGHT.stop()
     _BROWSER_CONTEXT=None;_BROWSER_PAGE=None;_BROWSER_PLAYWRIGHT=None
     return self.send_json(200,{"message":"Fechei a sessão de navegador controlável."})
    if _BROWSER_PAGE is None:return self.send_json(409,{"error":"O navegador controlável ainda não foi iniciado. Peça para iniciar o navegador primeiro."})
    if kind=="browser_navigate":
     url=str(d.get("url","")).strip()
     u=urlparse(url if "://" in url else "https://"+url)
     if u.scheme not in ("http","https") or not u.netloc:return self.send_json(400,{"error":"Informe um endereço HTTP ou HTTPS válido."})
     _BROWSER_PAGE.goto(u.geturl(),wait_until="domcontentloaded",timeout=30000)
     return self.send_json(200,{"message":"Naveguei para "+_BROWSER_PAGE.url,"url":_BROWSER_PAGE.url})
    if kind=="browser_snapshot":
     title=_BROWSER_PAGE.title()
     page_text=_BROWSER_PAGE.locator("body").inner_text(timeout=8000)[:10000]
     return self.send_json(200,{"message":"Página: "+title+"\nEndereço: "+_BROWSER_PAGE.url+"\nConteúdo visível:\n"+page_text,"url":_BROWSER_PAGE.url,"title":title})
    if kind=="browser_click":
     target=str(d.get("target","")).strip()[:250]
     if not target:return self.send_json(400,{"error":"Diga o texto do botão ou link em que devo clicar."})
     loc=_BROWSER_PAGE.get_by_role("button",name=target,exact=False)
     if loc.count()==0:loc=_BROWSER_PAGE.get_by_role("link",name=target,exact=False)
     if loc.count()==0:loc=_BROWSER_PAGE.get_by_text(target,exact=False)
     if loc.count()==0:return self.send_json(404,{"error":"Não encontrei botão ou link com esse texto: "+target})
     loc.first.click(timeout=10000)
     return self.send_json(200,{"message":"Cliquei em: "+target})
    if kind=="browser_download":
     target=str(d.get("target","")).strip()[:250]
     folder=_download_folder(d.get("folder","downloads"))
     if not target:return self.send_json(400,{"error":"Diga o nome do link ou arquivo que devo baixar da página."})
     link=_BROWSER_PAGE.get_by_role("link",name=target,exact=False)
     if link.count()==0:return self.send_json(404,{"error":"Não encontrei um link com esse nome na página: "+target})
     with _BROWSER_PAGE.expect_download(timeout=30000) as download_info:
      link.first.click(timeout=10000)
     download=download_info.value
     if download.failure():return self.send_json(502,{"error":"O site não concluiu o download: "+str(download.failure())[:180]})
     with tempfile.TemporaryDirectory(prefix=".sexta-download-",dir=str(folder)) as temporary:
      temp_path=Path(temporary)/_safe_download_name(download.suggested_filename)
      download.save_as(str(temp_path))
      final_path,size=_finish_download(temp_path,folder,download.suggested_filename)
     return self.send_json(200,{"message":f"Baixei {final_path.name} para {folder} ({size/1024/1024:.1f} MB).","path":str(final_path)})
    if kind=="browser_fill":
     target=str(d.get("target","")).strip()[:250];value=str(d.get("value",""))[:4000]
     if not target:return self.send_json(400,{"error":"Diga o nome ou rótulo do campo que devo preencher."})
     loc=_BROWSER_PAGE.get_by_label(target,exact=False)
     if loc.count()==0:loc=_BROWSER_PAGE.get_by_placeholder(target,exact=False)
     if loc.count()==0:loc=_BROWSER_PAGE.get_by_role("textbox",name=target,exact=False)
     if loc.count()==0:return self.send_json(404,{"error":"Não encontrei campo identificado como: "+target})
     loc.first.fill(value,timeout=10000)
     return self.send_json(200,{"message":"Preenchi o campo "+target+". Confira os dados antes de enviar."})
    if kind=="browser_type":
     value=str(d.get("text",""))[:4000]
     if not value:return self.send_json(400,{"error":"Diga o texto que devo digitar."})
     _BROWSER_PAGE.locator(":focus").press_sequentially(value,timeout=8000)
     return self.send_json(200,{"message":"Digitei o texto no campo que está selecionado."})
    if kind=="browser_press":
     key=str(d.get("key","")).strip().lower()
     allowed={"enter":"Enter","tab":"Tab","escape":"Escape","esc":"Escape","space":"Space","seta para baixo":"ArrowDown","baixo":"ArrowDown","seta para cima":"ArrowUp"}
     if key not in allowed:return self.send_json(400,{"error":"Tecla não permitida. Use Enter, Tab, Escape ou setas."})
     _BROWSER_PAGE.keyboard.press(allowed[key])
     return self.send_json(200,{"message":"Pressionei "+allowed[key]+"."})
   except Exception as e:
    return self.send_json(500,{"error":"Falha no controle do navegador: "+str(e)[:260]})
 def action(self,d):
  k=d.get("type")
  if k in ("browser_start","browser_navigate","browser_snapshot","browser_click","browser_fill","browser_type","browser_press","browser_download","browser_stop"):
   return self.browser_action(d)
  if k=="create_reminder":
   text=str(d.get("text","")).strip()[:300]
   try: minutes=int(d.get("minutes",0))
   except (TypeError,ValueError): minutes=0
   if not text or minutes<1 or minutes>525600:return self.send_json(400,{"error":"Diga o lembrete e um prazo entre 1 minuto e 365 dias."})
   items=self.reminders_read(); due=(datetime.datetime.now()+datetime.timedelta(minutes=minutes)).astimezone().isoformat(timespec="seconds")
   item={"id":str(int(datetime.datetime.now().timestamp()*1000)),"text":text,"due":due,"done":False};items.append(item)
   try: REMINDERS_FILE.write_text(json.dumps(items[-100:],ensure_ascii=False,indent=2),encoding="utf-8")
   except OSError as e:return self.send_json(500,{"error":"Não consegui salvar o lembrete: "+str(e)[:120]})
   return self.send_json(200,{"message":f"Anotado. Vou lembrar você de {text} em {minutes} minutos, às {due[11:16]}."})
  if k=="list_reminders":
   items=[x for x in self.reminders_read() if not x.get("done")]
   if not items:return self.send_json(200,{"message":"Você não tem lembretes pendentes."})
   lines=[]
   for x in items[:20]: lines.append(str(x.get("due",""))[:16].replace("T"," às ")+" — "+str(x.get("text","")))
   return self.send_json(200,{"message":"Seus lembretes pendentes:\n"+"\n".join(lines)})
  if k=="download_file":
   url=str(d.get("url","")).strip()
   try:
    folder=_download_folder(d.get("folder","downloads"))
    final_path,size=_download_http_file(url,folder)
    return self.send_json(200,{"message":f"Baixei {final_path.name} para {folder} ({size/1024/1024:.1f} MB).","path":str(final_path)})
   except ValueError as e:return self.send_json(400,{"error":str(e)})
   except urllib.error.HTTPError as e:return self.send_json(502,{"error":f"O site respondeu com erro HTTP {e.code}."})
   except Exception as e:return self.send_json(502,{"error":"Não consegui baixar o arquivo: "+str(e)[:180]})
  if k=="music_play":
   query=str(d.get("query","")).strip()[:160]
   wanted=normalize_key(query)
   # O apelido do tema é resolvido antes da busca de arquivos locais.
   iron_man_alias=("homem de ferro" in wanted or "iron man" in wanted or re.search(r"\btum+\s+turum+(?:\s+turum+)?\b",wanted))
   if iron_man_alias:
    return self.send_json(200,{"message":"Encontrei Iron Man, do Black Sabbath, e abri no player da Sexta-Feira.","title":"Iron Man — Black Sabbath (ao vivo oficial)","video_url":"https://www.youtube-nocookie.com/embed/7-thChxjcVw?autoplay=1&playsinline=1"})
   roots=[Path.home()/"Music",Path.home()/"Downloads"]
   matches=[]
   for root in roots:
    if not root.exists():continue
    try:
     for path in root.rglob("*"):
      if len(matches)>=3000:break
      try:
       if path.is_file() and path.suffix.lower() in _MUSIC_EXTENSIONS and not path.is_symlink():
        resolved=path.resolve()
        if resolved==root.resolve() or root.resolve() in resolved.parents:matches.append(path)
      except OSError:continue
    except OSError:continue
   matches.sort(key=lambda p:p.stat().st_mtime,reverse=True)
   if wanted and wanted not in ("musicas populares brasileiras","musica popular brasileira"):
    matching=[p for p in matches if wanted in normalize_key(p.stem)]
    if not matching:
     terms=[part for part in wanted.split() if len(part)>2]
     matching=[p for p in matches if terms and sum(1 for term in terms if term in normalize_key(p.stem))>=max(1,len(terms)//2)]
    matches=matching
   if not matches:
    return self.send_json(200,{"message":"Não encontrei uma faixa compatível nas pastas Música e Downloads. Coloque um arquivo de áudio nessas pastas ou diga o nome de uma música que já esteja salva no computador."})
   chosen=matches[0];stat=chosen.stat();file_id=hashlib.sha256((str(chosen.resolve())+str(stat.st_size)+str(stat.st_mtime_ns)).encode("utf-8")).hexdigest()
   _MUSIC_INDEX[file_id]=str(chosen.resolve())
   title=chosen.stem
   return self.send_json(200,{"message":"Encontrei "+title+" e abri no player da Sexta-Feira.","title":title,"audio_url":"/api/music/file?id="+file_id})
  if k=="create_site":
   request_text=str(d.get("request","")).strip()[:2500]
   if not request_text:return self.send_json(400,{"error":"Diga sobre o que deve ser o site."})
   try:
    payload=json.dumps({"request":request_text},ensure_ascii=False).encode("utf-8")
    req=urllib.request.Request(WORKER+"/api/create-site",data=payload,headers={"Content-Type":"application/json"},method="POST")
    with urllib.request.urlopen(req,timeout=100) as response:generated=json.loads(response.read(150000).decode("utf-8"))
    html=generated.get("html","")
    if not isinstance(html,str) or len(html)>120000 or "<html" not in html.lower() or "</html>" not in html.lower():return self.send_json(502,{"error":"A IA não gerou uma página HTML completa e segura para salvar."})
    folder=Path.home()/"Documents"/"Sexta-Feira Sites";folder.mkdir(parents=True,exist_ok=True)
    stamp=datetime.datetime.now().strftime("%Y%m%d-%H%M%S")
    path=folder/("site-"+stamp+".html")
    suffix=2
    while path.exists():
     path=folder/("site-"+stamp+"-"+str(suffix)+".html");suffix+=1
    path.write_text(html,encoding="utf-8")
    return self.send_json(200,{"message":"Criei o site e salvei em "+str(path)+". A prévia está aberta dentro da Sexta-Feira.","path":str(path),"preview_html":html})
   except urllib.error.HTTPError as e:
    try:detail=json.loads(e.read(3000).decode("utf-8")).get("error","")
    except Exception:detail=""
    return self.send_json(502,{"error":"A criação do site não respondeu corretamente."+(" "+detail if detail else "")})
   except Exception as e:return self.send_json(502,{"error":"Não consegui criar o site: "+str(e)[:180]})
  if k=="youtube_search":
   return self.action({"type":"music_play","query":d.get("query","")})
  if k=="screenshot":
   if os.name!="nt":return self.send_json(400,{"error":"Captura de tela disponível nesta versão para Windows."})
   try:
    subprocess.Popen(["explorer.exe","ms-screenclip:"])
    return self.send_json(200,{"message":"Abri a ferramenta de captura. Selecione a área da tela que deseja capturar."})
   except Exception as e:return self.send_json(500,{"error":"Não consegui abrir a captura: "+str(e)[:120]})
  if k=="open_browser":
   try:
    opened=webbrowser.open("https://www.google.com",new=2)
    if not opened:return self.send_json(502,{"error":"O Windows não confirmou a abertura do navegador padrão."})
    return self.send_json(200,{"message":"Abri o navegador na página inicial do Google."})
   except Exception as e:return self.send_json(500,{"error":"Não consegui abrir o navegador: "+str(e)[:150]})
  if k=="open_url":
   url=str(d.get("url","")).strip()
   if url and not urlparse(url).scheme:url="https://"+url.lstrip("/")
   u=urlparse(url)
   if u.scheme not in ("http","https") or not u.netloc:return self.send_json(400,{"error":"Informe um endereço de site válido, como youtube.com."})
   try:
    opened=webbrowser.open(url,new=2)
    if not opened:return self.send_json(502,{"error":"O Windows não confirmou a abertura do navegador para: "+url})
    return self.send_json(200,{"message":"Abri o navegador em "+url})
   except Exception as e:return self.send_json(500,{"error":"Não consegui abrir o site: "+str(e)[:150]})
  if k=="web_search":
   q=str(d.get("query","")).strip()[:300]
   if not q:return self.send_json(400,{"error":"Diga o que devo pesquisar."})
   try:
    url="https://www.google.com/search?q="+quote_plus(q);opened=webbrowser.open(url,new=2)
    if not opened:return self.send_json(502,{"error":"O Windows não confirmou a abertura da pesquisa."})
    return self.send_json(200,{"message":"Abri uma pesquisa no navegador por: "+q})
   except Exception as e:return self.send_json(500,{"error":"Não consegui abrir a pesquisa: "+str(e)[:150]})
  if k=="open_folder":
   p=FOLDERS.get(normalize_key(d.get("name", "")))
   if not p:return self.send_json(400,{"error":"Pasta não permitida."})
   p.mkdir(parents=True,exist_ok=True)
   try:os.startfile(str(p))
   except Exception as e:return self.send_json(500,{"error":"Não consegui abrir a pasta: "+str(e)[:150]})
   return self.send_json(200,{"message":"Abri a pasta "+str(p)})
  if k=="close_app":
   name=normalize_key(d.get("name",""))
   process_map={
    "calculadora":["CalculatorApp","calc"],"bloco de notas":["notepad"],"paint":["mspaint"],
    "explorador de arquivos":["explorer"],"gerenciador de tarefas":["Taskmgr"],
    "chrome":["chrome"],"edge":["msedge"],"firefox":["firefox"],"opera":["opera"],"opera gx":["opera"],
    "whatsapp":["WhatsApp"],"spotify":["Spotify"],"discord":["Discord"],"steam":["steam"],
    "vscode":["Code"],"word":["WINWORD"],"excel":["EXCEL"],"powerpoint":["POWERPNT"],
    "terminal":["WindowsTerminal"],"prompt de comando":["cmd"],"powershell":["powershell"]
   }
   targets=process_map.get(name)
   if not targets:return self.send_json(400,{"error":"Não posso encerrar esse aplicativo automaticamente."})
   if os.name!="nt":return self.send_json(400,{"error":"Fechar aplicativos por nome está disponível nesta versão para Windows."})
   closed=[]
   for proc in targets:
    try:
     result=subprocess.run(["taskkill.exe","/F","/IM",proc+".exe"],capture_output=True,text=True,timeout=8,creationflags=getattr(subprocess,"CREATE_NO_WINDOW",0))
     if result.returncode==0:closed.append(proc)
    except Exception:pass
   if not closed:return self.send_json(404,{"error":"Não encontrei "+name+" aberto, ou o Windows não permitiu fechá-lo."})
   return self.send_json(200,{"message":"Fechei "+name+"."})
  if k=="open_app":
   name=normalize_key(d.get("name", ""));cmd=APPS.get(name)
   if not cmd:return self.send_json(400,{"error":"Aplicativo não permitido. Posso abrir apenas programas da lista segura."})
   try:
    if name=="calculadora":
     # O alias do Windows inicia a Calculadora do sistema; o URI fica como reserva.
     try:
      subprocess.Popen(["calc.exe"],shell=False)
     except Exception:
      try:os.startfile("calculator:")
      except Exception:subprocess.Popen(["cmd.exe","/c","start","","calculator:"],shell=False)
    elif name in ("opera","opera gx"):
     # O comando start permite que o Windows resolva a instalação/registro do navegador.
     subprocess.Popen(cmd,creationflags=getattr(subprocess,"CREATE_NO_WINDOW",0))
    else:subprocess.Popen(cmd,creationflags=getattr(subprocess,"CREATE_NO_WINDOW",0))
   except Exception as e:return self.send_json(500,{"error":"Não consegui abrir o aplicativo: "+str(e)[:150]})
   return self.send_json(200,{"message":"Abri a "+name+"." if name=="calculadora" else "Abri "+name+"."})
  if k=="weather":
   city=str(d.get("city","")).strip()[:120]
   if not city:return self.send_json(400,{"error":"Diga a cidade. Por exemplo: 'como está o tempo em Goiânia?'."})
   try:
    geo_url="https://geocoding-api.open-meteo.com/v1/search?name="+quote_plus(city)+"&count=1&language=pt&format=json"
    with urllib.request.urlopen(urllib.request.Request(geo_url,headers={"User-Agent":"Sexta-Feira-Local/1.0"}),timeout=12) as response: geo=json.loads(response.read().decode("utf-8"))
    results=geo.get("results") or []
    if not results:return self.send_json(404,{"error":"Não encontrei essa cidade. Diga o nome da cidade e do estado."})
    place=results[0];lat=place["latitude"];lon=place["longitude"]
    forecast_url=f"https://api.open-meteo.com/v1/forecast?latitude={lat}&longitude={lon}&current=temperature_2m,relative_humidity_2m,apparent_temperature,is_day,precipitation,weather_code,wind_speed_10m&timezone=auto"
    with urllib.request.urlopen(urllib.request.Request(forecast_url,headers={"User-Agent":"Sexta-Feira-Local/1.0"}),timeout=12) as response: forecast=json.loads(response.read().decode("utf-8"))
    current=forecast.get("current",{})
    codes={0:"céu limpo",1:"predominantemente limpo",2:"parcialmente nublado",3:"nublado",45:"neblina",48:"neblina com geada",51:"garoa leve",53:"garoa moderada",55:"garoa intensa",61:"chuva fraca",63:"chuva moderada",65:"chuva forte",71:"neve fraca",73:"neve moderada",75:"neve forte",80:"pancadas de chuva fracas",81:"pancadas de chuva moderadas",82:"pancadas de chuva fortes",95:"trovoadas",96:"trovoadas com granizo leve",99:"trovoadas com granizo forte"}
    label=place.get("name",city)
    admin=place.get("admin1","")
    if admin:label+=", "+admin
    temp=current.get("temperature_2m");feels=current.get("apparent_temperature");humidity=current.get("relative_humidity_2m");wind=current.get("wind_speed_10m");rain=current.get("precipitation")
    message=f"Tempo agora em {label}: {codes.get(current.get('weather_code'),'condição não identificada')}. "
    if temp is not None:message+=f"Temperatura de {temp:g} °C"
    if feels is not None:message+=f", sensação de {feels:g} °C"
    if humidity is not None:message+=f", umidade de {humidity}%"
    if wind is not None:message+=f" e vento de {wind:g} km/h"
    if rain is not None:message+=f". Precipitação atual: {rain:g} mm"
    return self.send_json(200,{"message":message+"."})
   except Exception as e:return self.send_json(502,{"error":"Não consegui consultar o tempo agora. Verifique a conexão e tente novamente.","detail":str(e)[:180]})
  if k=="media_control":
   command=normalize_key(d.get("command",""))
   keys={"volume_up":0xAF,"volume_down":0xAE,"volume_mute":0xAD,"play_pause":0xB3,"next_track":0xB0,"previous_track":0xB1}
   messages={"volume_up":"Aumentei o volume.","volume_down":"Diminuí o volume.","volume_mute":"Alternei o mudo do volume.","play_pause":"Enviei o comando de reproduzir ou pausar.","next_track":"Pulei para a próxima faixa.","previous_track":"Voltei para a faixa anterior."}
   if command not in keys:return self.send_json(400,{"error":"Controle de mídia não reconhecido."})
   if os.name!="nt":return self.send_json(400,{"error":"O controle de mídia está disponível nesta versão para Windows."})
   try:
    import ctypes
    KEYEVENTF_KEYUP=0x0002
    class KEYBDINPUT(ctypes.Structure):
     _fields_=[("wVk",ctypes.c_ushort),("wScan",ctypes.c_ushort),("dwFlags",ctypes.c_ulong),("time",ctypes.c_ulong),("dwExtraInfo",ctypes.POINTER(ctypes.c_ulong))]
    class INPUTUNION(ctypes.Union):
     _fields_=[("ki",KEYBDINPUT)]
    class INPUT(ctypes.Structure):
     _fields_=[("type",ctypes.c_ulong),("union",INPUTUNION)]
    extra=ctypes.c_ulong(0)
    key=keys[command]
    events=(INPUT*2)()
    events[0].type=1;events[0].union.ki=KEYBDINPUT(key,0,0,0,ctypes.pointer(extra))
    events[1].type=1;events[1].union.ki=KEYBDINPUT(key,0,KEYEVENTF_KEYUP,0,ctypes.pointer(extra))
    sent=ctypes.windll.user32.SendInput(2,ctypes.byref(events),ctypes.sizeof(INPUT))
    if sent!=2:raise OSError("O Windows não aceitou o comando de mídia.")
    return self.send_json(200,{"message":messages[command]})
   except Exception as e:return self.send_json(500,{"error":"Não consegui controlar o volume ou a mídia: "+str(e)[:150]})
  if k=="battery_info":
   try:
    if os.name=="nt":
     import ctypes
     class BatteryStatus(ctypes.Structure):
      _fields_=[("ACLineStatus",ctypes.c_byte),("BatteryFlag",ctypes.c_byte),("BatteryLifePercent",ctypes.c_byte),("SystemStatusFlag",ctypes.c_byte),("BatteryLifeTime",ctypes.c_uint32),("BatteryFullLifeTime",ctypes.c_uint32)]
     status=BatteryStatus()
     if not ctypes.windll.kernel32.GetSystemPowerStatus(ctypes.byref(status)): raise OSError("Não foi possível consultar a bateria.")
     if status.BatteryLifePercent<=100: message="Bateria em "+str(status.BatteryLifePercent)+" por cento."
     else: message="O Windows não informou a porcentagem da bateria."
     message += " Conectado à tomada." if status.ACLineStatus==1 else (" Funcionando na bateria." if status.ACLineStatus==0 else "")
     return self.send_json(200,{"message":message})
    return self.send_json(200,{"message":"A consulta detalhada da bateria está disponível no Windows."})
   except Exception as e:return self.send_json(500,{"error":"Não consegui consultar a bateria: "+str(e)[:150]})
  if k=="lock_screen":
   if os.name!="nt":return self.send_json(400,{"error":"Esse comando está disponível no Windows."})
   try:
    subprocess.Popen(["rundll32.exe","user32.dll,LockWorkStation"],creationflags=getattr(subprocess,"CREATE_NO_WINDOW",0))
    return self.send_json(200,{"message":"Vou bloquear a tela do computador agora."})
   except Exception as e:return self.send_json(500,{"error":"Não consegui bloquear a tela: "+str(e)[:150]})
  if k=="current_time":return self.send_json(200,{"message":"Agora são "+datetime.datetime.now().strftime("%H:%M")+" de "+datetime.datetime.now().strftime("%d/%m/%Y")+" (horário local do computador)."})
  if k=="system_info":
   try:
    import shutil
    lines=[f"Computador: {platform.node()}",f"Sistema: {platform.platform()}",f"Processadores lógicos: {os.cpu_count() or 'não informado'}",f"Python: {platform.python_version()}"]
    try:
     if os.name=="nt":
      import ctypes
      class MemoryStatus(ctypes.Structure):
       _fields_=[("dwLength",ctypes.c_ulong),("dwMemoryLoad",ctypes.c_ulong),("ullTotalPhys",ctypes.c_ulonglong),("ullAvailPhys",ctypes.c_ulonglong),("ullTotalPageFile",ctypes.c_ulonglong),("ullAvailPageFile",ctypes.c_ulonglong),("ullTotalVirtual",ctypes.c_ulonglong),("ullAvailVirtual",ctypes.c_ulonglong),("ullAvailExtendedVirtual",ctypes.c_ulonglong)]
      mem=MemoryStatus();mem.dwLength=ctypes.sizeof(mem)
      if ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(mem)):
       total=mem.ullTotalPhys/1024**3;avail=mem.ullAvailPhys/1024**3
       lines.append(f"Memória RAM: {total:.1f} GB total, {avail:.1f} GB disponível ({mem.dwMemoryLoad}% em uso)")
     else:
      lines.append("Memória RAM: consulta detalhada disponível no Windows.")
    except Exception:pass
    try:
     usage=shutil.disk_usage(str(Path.home()))
     lines.append(f"Disco da unidade do usuário: {usage.free/1024**3:.1f} GB livres de {usage.total/1024**3:.1f} GB")
    except Exception:pass
    return self.send_json(200,{"message":"\n".join(lines)})
   except Exception as e:return self.send_json(500,{"error":"Não consegui consultar o sistema: "+str(e)[:150]})
  if k in ("git_status","git_log"):
   try:
    args=["git","-C",str(ROOT),"status","--short","--branch"] if k=="git_status" else ["git","-C",str(ROOT),"log","-5","--oneline"]
    p=subprocess.run(args,capture_output=True,text=True,timeout=10)
    if p.returncode:return self.send_json(400,{"error":(p.stderr or "Git não disponível nesta pasta.")[:300]})
    return self.send_json(200,{"message":("Status do Git:\n" if k=="git_status" else "Últimos commits:\n")+(p.stdout.strip() or "Nenhuma informação encontrada.")})
   except FileNotFoundError:return self.send_json(400,{"error":"Git não está instalado."})
  if k=="list_folder":
   p=FOLDERS.get(str(d.get("name","")).lower())
   if not p:return self.send_json(400,{"error":"Pasta não permitida."})
   if not p.exists():return self.send_json(200,{"message":"A pasta ainda não existe: "+str(p)})
   entries=sorted(p.iterdir(),key=lambda x:(not x.is_dir(),x.name.lower()))[:60]
   return self.send_json(200,{"message":"Conteúdo de "+str(p)+":\n"+("\n".join(("📁 " if x.is_dir() else "📄 ")+x.name for x in entries) if entries else "Pasta vazia.")})
  if k=="organize_preview":
   name=normalize_key(d.get("name","downloads"));p=FOLDERS.get(name)
   if not p:return self.send_json(400,{"error":"Escolha uma pasta permitida, como Downloads, Documentos ou Área de Trabalho."})
   if not p.exists():return self.send_json(200,{"message":"A pasta ainda não existe: "+str(p)})
   files=[x for x in p.iterdir() if x.is_file()];groups={"Imagens":{".jpg",".jpeg",".png",".gif",".webp",".bmp",".heic"},"Vídeos":{".mp4",".mov",".mkv",".avi",".webm"},"Áudio":{".mp3",".wav",".m4a",".flac",".ogg"},"Documentos":{".pdf",".doc",".docx",".txt",".rtf",".xls",".xlsx",".ppt",".pptx"},"Compactados":{".zip",".rar",".7z",".tar",".gz"}}
   counts={label:sum(1 for f in files if f.suffix.lower() in exts) for label,exts in groups.items()};counts["Outros"]=sum(1 for f in files if not any(f.suffix.lower() in exts for exts in groups.values()))
   summary="Prévia de organização de "+str(p)+": "+str(len(files))+" arquivos. "+"; ".join(k+": "+str(v) for k,v in counts.items())+". Não movi nem alterei nenhum arquivo."
   return self.send_json(200,{"message":summary})
  if k=="create_note":
   note=str(d.get("text","")).strip()
   if not note:return self.send_json(400,{"error":"A nota está vazia."})
   if len(note)>4000:return self.send_json(413,{"error":"A nota ultrapassa 4.000 caracteres."})
   NOTES.mkdir(exist_ok=True);p=NOTES/("nota-"+datetime.datetime.now().strftime("%Y%m%d-%H%M%S")+".txt");p.write_text(note+"\n",encoding="utf-8")
   return self.send_json(200,{"message":"Nota salva em "+str(p)})
  return self.send_json(400,{"error":"Comando ainda não implementado. Disponíveis: navegador, links, pesquisa web, aplicativos e pastas, informações do sistema, Git e anotações. Comandos arbitrários e destrutivos ficam bloqueados."})

def run_local_server():
 """Inicia o servidor local sem abrir navegador automaticamente."""
 server=ThreadingHTTPServer((HOST,PORT),Handler)
 server.serve_forever()

if __name__=="__main__":
 print(f"Sexta-Feira Local: http://{HOST}:{PORT}")
 print("Execute INICIAR-SEXTA-FEIRA.bat para abrir a interface.")
 try:
  run_local_server()
 except KeyboardInterrupt:
  print("Encerrando.")
