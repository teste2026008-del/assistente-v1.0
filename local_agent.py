#!/usr/bin/env python3
"""Agente local da Sexta-Feira. Escuta apenas em localhost."""
from http.server import ThreadingHTTPServer, SimpleHTTPRequestHandler
from pathlib import Path
from urllib.parse import urlparse
import json, platform, subprocess, webbrowser, urllib.request, urllib.error, datetime

ROOT=Path(__file__).resolve().parent
PUBLIC=ROOT/"public"
WORKER="https://assistente-v1-0.teste2026008.workers.dev"
NOTES=ROOT/"notas"
HOST,PORT="127.0.0.1",8765

class Handler(SimpleHTTPRequestHandler):
 def __init__(self,*a,**kw): super().__init__(*a,directory=str(PUBLIC),**kw)
 def log_message(self,fmt,*args): print("[Sexta-Feira] "+(fmt%args))
 def send_json(self,status,obj):
  b=json.dumps(obj,ensure_ascii=False).encode()
  self.send_response(status);self.send_header("Content-Type","application/json; charset=utf-8");self.send_header("Content-Length",str(len(b)));self.send_header("Cache-Control","no-store");self.end_headers();self.wfile.write(b)
 def do_GET(self):
  p=urlparse(self.path).path
  if p=="/api/health": return self.send_json(200,{"ok":True,"service":"Sexta-Feira Local"})
  if p.startswith("/api/"): return self.proxy(p,b"","GET")
  return super().do_GET()
 def do_POST(self):
  p=urlparse(self.path).path
  n=min(int(self.headers.get("Content-Length","0")),100000);body=self.rfile.read(n)
  if p=="/api/action":
   try: data=json.loads(body or b"{}")
   except Exception: return self.send_json(400,{"error":"JSON inválido."})
   return self.action(data)
  if p.startswith("/api/"): return self.proxy(p,body,"POST")
  return self.send_json(404,{"error":"Rota não encontrada."})
 def proxy(self,path,body,method):
  try:
   req=urllib.request.Request(WORKER+path,data=body if method=="POST" else None,method=method,headers={"Content-Type":"application/json","User-Agent":"Sexta-Feira-Local/1.0"})
   with urllib.request.urlopen(req,timeout=45) as res:
    data=res.read();self.send_response(res.status);self.send_header("Content-Type",res.headers.get("Content-Type","application/json"));self.send_header("Content-Length",str(len(data)));self.end_headers();self.wfile.write(data)
  except urllib.error.HTTPError as e:
   data=e.read();self.send_response(e.code);self.send_header("Content-Type",e.headers.get("Content-Type","application/json"));self.send_header("Content-Length",str(len(data)));self.end_headers();self.wfile.write(data)
  except Exception as e: self.send_json(502,{"error":"Falha ao conectar à IA/voz online.","detail":str(e)[:200]})
 def action(self,d):
  k=d.get("type")
  if k=="open_browser":
   webbrowser.open("https://www.google.com");return self.send_json(200,{"message":"Abri o navegador na página inicial do Google."})
  if k=="open_url":
   url=str(d.get("url","")).strip();u=urlparse(url)
   if u.scheme not in ("http","https") or not u.netloc:return self.send_json(400,{"error":"Informe um link HTTP ou HTTPS válido."})
   webbrowser.open(url);return self.send_json(200,{"message":"Solicitei ao Windows que abra: "+url})
  if k=="system_info":return self.send_json(200,{"message":f"Computador: {platform.node()} • Sistema: {platform.platform()} • Python: {platform.python_version()}"})
  if k=="git_status":
   try:
    p=subprocess.run(["git","-C",str(ROOT),"status","--short","--branch"],capture_output=True,text=True,timeout=10)
    if p.returncode:return self.send_json(400,{"error":(p.stderr or "Git não disponível nesta pasta.")[:250]})
    return self.send_json(200,{"message":"Status do Git:\n"+(p.stdout.strip() or "Sem alterações locais.")})
   except FileNotFoundError:return self.send_json(400,{"error":"Git não está instalado."})
  if k=="create_note":
   note=str(d.get("text","")).strip()
   if not note:return self.send_json(400,{"error":"A nota está vazia."})
   if len(note)>4000:return self.send_json(413,{"error":"A nota ultrapassa 4.000 caracteres."})
   NOTES.mkdir(exist_ok=True);p=NOTES/("nota-"+datetime.datetime.now().strftime("%Y%m%d-%H%M%S")+".txt");p.write_text(note+"\n",encoding="utf-8")
   return self.send_json(200,{"message":"Nota salva em "+str(p)})
  return self.send_json(400,{"error":"Comando não implementado. Disponíveis: abrir navegador, abrir link, informações do sistema, status do Git e criar nota."})

if __name__=="__main__":
 print(f"Sexta-Feira Local: http://{HOST}:{PORT}");print("Feche esta janela para encerrar.")
 try:
  server=ThreadingHTTPServer((HOST,PORT),Handler);webbrowser.open(f"http://{HOST}:{PORT}");server.serve_forever()
 except KeyboardInterrupt: print("Encerrando.")
