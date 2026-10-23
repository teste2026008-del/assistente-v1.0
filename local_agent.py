#!/usr/bin/env python3
"""Agente local da Sexta-Feira. Escuta somente em localhost."""
from http.server import ThreadingHTTPServer, SimpleHTTPRequestHandler
from pathlib import Path
from urllib.parse import urlparse, quote_plus
import json, platform, subprocess, webbrowser, urllib.request, urllib.error, datetime, os

ROOT=Path(__file__).resolve().parent
PUBLIC=ROOT/"public"
WORKER="https://assistente-v1-0.teste2026008.workers.dev"
NOTES=ROOT/"notas"
HOST,PORT="127.0.0.1",8765
FOLDERS={"downloads":Path.home()/"Downloads","documentos":Path.home()/"Documents","área de trabalho":Path.home()/"Desktop","desktop":Path.home()/"Desktop","imagens":Path.home()/"Pictures","músicas":Path.home()/"Music","música":Path.home()/"Music","vídeos":Path.home()/"Videos","vídeo":Path.home()/"Videos"}
APPS={"bloco de notas":["notepad.exe"],"calculadora":["calc.exe"],"paint":["mspaint.exe"],"explorador de arquivos":["explorer.exe"],"gerenciador de tarefas":["taskmgr.exe"]}

class Handler(SimpleHTTPRequestHandler):
 def __init__(self,*a,**kw): super().__init__(*a,directory=str(PUBLIC),**kw)
 def log_message(self,fmt,*args): print("[Sexta-Feira] "+(fmt%args))
 def send_json(self,status,obj):
  b=json.dumps(obj,ensure_ascii=False).encode("utf-8")
  self.send_response(status);self.send_header("Content-Type","application/json; charset=utf-8");self.send_header("Content-Length",str(len(b)));self.send_header("Cache-Control","no-store");self.end_headers();self.wfile.write(b)
 def do_GET(self):
  p=urlparse(self.path).path
  if p=="/api/health": return self.send_json(200,{"ok":True,"service":"Sexta-Feira Local","host":HOST,"port":PORT})
  if p.startswith("/api/"): return self.proxy(p,b"","GET")
  return super().do_GET()
 def do_POST(self):
  p=urlparse(self.path).path;n=min(int(self.headers.get("Content-Length","0")),100000);body=self.rfile.read(n)
  if p=="/api/action":
   try:data=json.loads(body or b"{}")
   except Exception:return self.send_json(400,{"error":"JSON inválido."})
   return self.action(data)
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
   p=FOLDERS.get(str(d.get("name","")).lower())
   if not p:return self.send_json(400,{"error":"Pasta não permitida."})
   p.mkdir(parents=True,exist_ok=True)
   try:os.startfile(str(p))
   except Exception as e:return self.send_json(500,{"error":"Não consegui abrir a pasta: "+str(e)[:150]})
   return self.send_json(200,{"message":"Abri a pasta "+str(p)})
  if k=="open_app":
   name=str(d.get("name","")).lower();cmd=APPS.get(name)
   if not cmd:return self.send_json(400,{"error":"Aplicativo não permitido."})
   try:subprocess.Popen(cmd)
   except Exception as e:return self.send_json(500,{"error":"Não consegui abrir o aplicativo: "+str(e)[:150]})
   return self.send_json(200,{"message":"Abri "+name+"."})
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
