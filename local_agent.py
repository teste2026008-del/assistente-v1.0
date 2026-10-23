#!/usr/bin/env python3
"""Agente local da Sexta-Feira. Escuta somente em localhost."""
from http.server import ThreadingHTTPServer, SimpleHTTPRequestHandler
from pathlib import Path
from urllib.parse import urlparse, quote_plus
import json, platform, subprocess, webbrowser, urllib.request, urllib.error, datetime, os, unicodedata

ROOT=Path(__file__).resolve().parent
PUBLIC=ROOT/"public"
WORKER="https://assistente-v1-0.teste2026008.workers.dev"
NOTES=ROOT/"notas"
MEMORY_DIR=Path.home()/"AppData"/"Local"/"Sexta-Feira"
MEMORY_FILE=MEMORY_DIR/"memoria.json"
MEMORY_DIR.mkdir(parents=True,exist_ok=True)
HOST,PORT="127.0.0.1",8765
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
  if p=="/api/memory":
   try:data=json.loads(body or b"{}")
   except Exception:return self.send_json(400,{"error":"JSON inválido."})
   return self.memory_save(data)
  if p.startswith("/api/"):return self.proxy(p,body,"POST")
  return self.send_json(404,{"error":"Rota não encontrada."})
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
  if k=="current_time":return self.send_json(200,{"message":"Agora são "+datetime.datetime.now().strftime("%H:%M")+" de "+datetime.datetime.now().strftime("%d/%m/%Y")+" (horário local do computador)."})
  if k=="system_info":return self.send_json(200,{"message":f"Computador: {platform.node()}\nSistema: {platform.platform()}\nPython: {platform.python_version()}\nPasta do agente: {ROOT}"})
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
