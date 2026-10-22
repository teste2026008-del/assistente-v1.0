import { pipeline, env } from 'https://cdn.jsdelivr.net/npm/@huggingface/transformers@3.7.2';
env.allowLocalModels = false;
let asr, stream, ctx, source, processor, active = false, busy = false, pending = [], count = 0;
const $ = id => document.getElementById(id);
const norm = s => s.toLocaleLowerCase('pt-BR').normalize('NFD').replace(/[\u0300-\u036f]/g,'').replace(/[^a-z0-9\s]/g,' ').replace(/\s+/g,' ').trim();
function stop() {
 active = false;
 try { processor?.disconnect(); source?.disconnect(); stream?.getTracks().forEach(t=>t.stop()); ctx?.close(); } catch {}
 processor = source = stream = ctx = null;
 window.localWhisperRunning = false;
}
function resample(a, from, to) {
 if(from===to)return a;
 const n=Math.floor(a.length*to/from), out=new Float32Array(n), ratio=from/to;
 for(let i=0;i<n;i++){const p=i*ratio,l=Math.floor(p),f=p-l;out[i]=(a[l]||0)*(1-f)+(a[Math.min(l+1,a.length-1)]||0)*f}
 return out;
}
async function transcribe(samples, rate) {
 if(busy||!active||!samples.length)return;
 busy=true;
 try {
  const audio=resample(samples,rate,16000);
  const result=await asr(audio,{sampling_rate:16000,language:'portuguese',task:'transcribe'});
  const heard=String(result?.text||'').trim(), clean=norm(heard);
  if(!heard||!active)return;
  const wake=clean.match(/\b(bom dia|boa tarde|boa noite|ola|oi)\s+sexta feira\b/);
  if(wake){const rest=clean.slice(wake.index+wake[0].length).trim();window.localWakeAwaiting=!rest;if(typeof window.localWakeSend==='function')window.localWakeSend(rest||wake[0]);}
  else if(window.localWakeAwaiting){window.localWakeAwaiting=false;if(typeof window.localWakeSend==='function')window.localWakeSend(heard);}
 } catch(e) { $('hint').textContent='Erro no reconhecimento local: '+(e.message||'tente novamente'); }
 finally {busy=false}
}
async function start() {
 if(window.localWhisperRunning)return;
 window.localWhisperRunning=true;active=true;window.localWakeAwaiting=false;
 $('hint').textContent='Preparando reconhecimento de voz gratuito. Primeira utilização: baixando modelo (~75–120 MB)…';
 try {
  if(!asr) asr=await pipeline('automatic-speech-recognition','onnx-community/whisper-tiny',{device:navigator.gpu?'webgpu':'wasm',progress_callback:p=>{if(p?.status==='progress'&&p.progress!=null)$('hint').textContent='Baixando modelo de voz local: '+Math.round(p.progress)+'%'}});
  if(!active)return;
  stream=await navigator.mediaDevices.getUserMedia({audio:{channelCount:1,echoCancellation:true,noiseSuppression:true,autoGainControl:true}});
  ctx=new AudioContext();await ctx.resume();source=ctx.createMediaStreamSource(stream);processor=ctx.createScriptProcessor(16384,1,1);
  pending=[];count=0;
  processor.onaudioprocess=e=>{
   const a=e.inputBuffer.getChannelData(0);pending.push(new Float32Array(a));count+=a.length;
   if(count>=ctx.sampleRate*6&&!busy){const all=new Float32Array(count);let pos=0;for(const part of pending){all.set(part,pos);pos+=part.length}pending=[];count=0;transcribe(all,ctx.sampleRate)}
   e.outputBuffer.getChannelData(0).fill(0);
  };
  source.connect(processor);processor.connect(ctx.destination);
  $('mic').classList.add('active');$('mic').innerHTML='● <span class="mic-label">VOZ LOCAL</span>';
  $('hint').textContent='RECONHECIMENTO LOCAL GRATUITO ATIVO • DIGA “BOM DIA, SEXTA-FEIRA”';
  if(typeof window.setState==='function')window.setState('AGUARDANDO SEXTA-FEIRA');
 } catch(e){stop();$('hint').textContent='Não consegui iniciar a voz local: '+(e.message||e.name||'erro');if(typeof window.setState==='function')window.setState('ERRO NO RECONHECIMENTO')}
}
window.startLocalWhisper=start;
window.stopLocalWhisper=startStop;
window.localWakeSend = text => { if (typeof window.send === 'function') window.send(text); };
window.setState = window.setState || (s => { const el=$('status'); if(el)el.textContent=s; });
function startStop(){stop();$('mic').classList.remove('active');$('mic').innerHTML='🎙 <span class="mic-label">ATIVAR VOZ</span>'}
$('mic').addEventListener('click', e=>{e.preventDefault();e.stopImmediatePropagation();if(active){startStop();$('hint').textContent='ESCUTA DESATIVADA';return;}start();}, true);
$('stop').addEventListener('click', e=>{if(active){e.preventDefault();e.stopImmediatePropagation();startStop();$('hint').textContent='ESCUTA PARADA';}}, true);
