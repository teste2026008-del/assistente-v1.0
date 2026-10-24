#!/usr/bin/env python3
"""Agente local da Sexta-Feira. Escuta somente em localhost."""
from http.server import ThreadingHTTPServer, SimpleHTTPRequestHandler
from pathlib import Path
from urllib.parse import urlparse, quote_plus
import json, platform, subprocess, webbrowser, urllib.request, urllib.error, datetime, os, unicodedata, asyncio, sys, io
from threading import Lock

ROOT=Path(__file__).resolve().parent
PUBLIC=ROOT/"public"
WORKER="https://assistente-v1-0.teste2026008.workers.dev"
NOTES=ROOT/"notas"
MEMORY_DIR=Path.home()/"AppData"/"Local"/"Sexta-Feira"
MEMORY_FILE=MEMORY_DIR/"memoria.json"
MEMORY_DIR.mkdir(parents=True,exist_ok=True)
HOST,PORT="127.0.0.1",8765
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
  if p=="/api/memory": return self.memory_get()
  if p.startswith("/api/"): return self.proxy(p,b"","GET")
  return super().do_GET()
 def do_POST(self):
  p=urlparse(self.path).path;n=min(int(self.headers.get("Content-Length","0")),100000);body=self.rfile.read(n)
  if p=="/api/action":
   try:data=json.loads(body or b"{}")
   except Exception:return self.send_json(400,{"error":"JSON inválido."})
   return self.action(data)
  if p=="/api/tts": return self.local_tts(body)
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
   with urllib.request.urlopen(req,timeout=45) as res:
    data=res.read();self.send_response(res.status);self.send_header("Content-Type",res.headers.get("Content-Type","application/json"));self.send_header("Content-Length",str(len(data)));self.end_headers();self.wfile.write(data)
  except urllib.error.HTTPError as e:
   data=e.read();self.send_response(e.code);self.send_header("Content-Type",e.headers.get("Content-Type","application/json"));self.send_header("Content-Length",str(len(data)));self.end_headers();self.wfile.write(data)
  except Exception as e:self.send_json(502,{"error":"Falha ao conectar à IA/voz online.","detail":str(e)[:220]})
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
 def action(self,d):
  k=d.get("type")
  if k=="open_browser":webbrowser.open("https://www.google.com");return self.send_json(200,{"message":"Abri o navegador na página inicial do Google."})
  if k=="open_url":
   url=str(d.get("url","")).strip();u=urlparse(url)
   if u.scheme not in ("http","https") or not u.netloc:return self.send_json(400,{"error":"Informe um link HTTP/HTTPS válido."})
   webbrowser.open(url);return self.send_json(200,{"message":"Solicitei ao Windows que abra: "+url})
  if k=="web_search":
   q=str(d.get("query","")).strip()[:300]
   if not q:return self.send_json(400,{"error":"Diga o que devo pesquisar."})
   webbrowser.open("https://www.google.com/search?q="+quote_plus(q));return self.send_json(200,{"message":"Abri uma pesquisa no navegador por: "+q})
  if k=="open_folder":
   p=FOLDERS.get(normalize_key(d.get("name", "")))
   if not p:return self.send_json(400,{"error":"Pasta não permitida."})
   p.mkdir(parents=True,exist_ok=True)
   try:os.startfile(str(p))
   except Exception as e:return self.send_json(500,{"error":"Não consegui abrir a pasta: "+str(e)[:150]})
   return self.send_json(200,{"message":"Abri a pasta "+str(p)})
  if k=="open_app":
   name=normalize_key(d.get("name", ""));cmd=APPS.get(name)
   if not cmd:return self.send_json(400,{"error":"Aplicativo não permitido. Posso abrir apenas programas da lista segura."})
   try:
    if name=="calculadora":
     # Tenta primeiro o URI oficial e depois os caminhos de inicialização do Windows.
     try:
      os.startfile("calculator:")
     except Exception:
      try:subprocess.Popen(["calc.exe"],shell=False)
      except Exception:subprocess.Popen(["cmd.exe","/c","start","","calculator:"],shell=False)
    elif name in ("opera","opera gx"):
     # O comando start permite que o Windows resolva a instalação/registro do navegador.
     subprocess.Popen(cmd,creationflags=getattr(subprocess,"CREATE_NO_WINDOW",0))
    else:subprocess.Popen(cmd,creationflags=getattr(subprocess,"CREATE_NO_WINDOW",0))
   except Exception as e:return self.send_json(500,{"error":"Não consegui abrir o aplicativo: "+str(e)[:150]})
   return self.send_json(200,{"message":"Solicitei ao Windows que abra "+name+"."})
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
    return self.send_json(200,{"message":"\\n".join(lines)})
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
