import { pipeline, env } from 'https://esm.sh/@huggingface/transformers@3.7.2?bundle';
env.allowLocalModels = false;
env.useBrowserCache = true;
// O cache do navegador fica persistente no perfil WebView2 definido em desktop_app.py.

const $ = id => document.getElementById(id);
let asr = null, stream = null, audioContext = null, source = null, processor = null;
let active = false, loading = false, transcribing = false, pending = [], sampleCount = 0, lastRate = 0;
let speechFrames = 0, silenceFrames = 0, peakRms = 0, commandCooldownUntil = 0;
let preRoll = [], capturingSpeech = false;
let session = 0;
let modelPromise = null;
let asrDevice = null;
let inferenceQueue = Promise.resolve();
let permissionStatus = 'unknown';

const normalize = value => String(value || '')
  .toLocaleLowerCase('pt-BR')
  .normalize('NFD').replace(/[\u0300-\u036f]/g, '')
  .replace(/[^a-z0-9\s]/g, ' ').replace(/\s+/g, ' ').trim();

function state(value) {
  if (typeof window.setState === 'function') window.setState(value);
  else if ($('status')) $('status').textContent = value;
}

function stopLocal() {
  active = false;
  session++;
  try { processor?.disconnect(); } catch {}
  try { source?.disconnect(); } catch {}
  try { stream?.getTracks().forEach(track => track.stop()); } catch {}
  try { if (audioContext && audioContext.state !== 'closed') audioContext.close(); } catch {}
  processor = source = stream = audioContext = null;
  pending = [];
  sampleCount = 0;
  lastRate = 0;
  speechFrames = 0;
  silenceFrames = 0;
  peakRms = 0;
  preRoll = [];
  capturingSpeech = false;
  commandCooldownUntil = 0;
  transcribing = false;
  window.localWakeAwaiting = false;
  window.localWhisperRunning = false;
  $('mic')?.classList.remove('active');
  if ($('mic')) $('mic').innerHTML = '🎙 <span class="mic-label">ATIVAR VOZ</span>';
}

function resample(input, fromRate, toRate) {
  if (fromRate === toRate) return input;
  const length = Math.floor(input.length * toRate / fromRate);
  const output = new Float32Array(length);
  const ratio = fromRate / toRate;
  for (let i = 0; i < length; i++) {
    const position = i * ratio;
    const left = Math.floor(position);
    const fraction = position - left;
    const a = input[left] || 0;
    const b = input[Math.min(left + 1, input.length - 1)] || 0;
    output[i] = a * (1 - fraction) + b * fraction;
  }
  return output;
}

async function deliver(text) {
  const message = String(text || '').trim();
  if (!message) return;
  if (typeof window.send === 'function') return window.send(message);
  const input = $('prompt');
  const form = $('form');
  if (input && form) {
    input.value = message;
    if (typeof form.requestSubmit === 'function') form.requestSubmit();
    else form.dispatchEvent(new Event('submit', { bubbles: true, cancelable: true }));
  }
}

async function transcribe(samples, rate, thisSession) {
  if (transcribing || !active || !asr || !samples.length) return;
  // O microfone continua aberto, mas não transcrevemos silêncio/ruído nem o áudio
  // que a própria Sexta-Feira está reproduzindo.
  if (Date.now() < commandCooldownUntil || window.localAssistantSpeaking || window.localAssistantBusy) return;
  transcribing = true;
  try {
    let audio = resample(samples, rate, 16000);
    // Ajuste leve de volume para microfones baixos, sem amplificar ruído indefinidamente.
    let sumSquares = 0, peak = 0;
    for (let i = 0; i < audio.length; i++) {
      const value = audio[i];
      sumSquares += value * value;
      peak = Math.max(peak, Math.abs(value));
    }
    const rms = Math.sqrt(sumSquares / Math.max(1, audio.length));
    if (rms > 0.002 && rms < 0.12) {
      const gain = Math.min(4, 0.12 / rms, peak > 0 ? 0.96 / peak : 4);
      if (gain > 1.05) {
        const boosted = new Float32Array(audio.length);
        for (let i = 0; i < audio.length; i++) boosted[i] = Math.max(-0.98, Math.min(0.98, audio[i] * gain));
        audio = boosted;
      }
    }
    const runOptions = {
      sampling_rate: 16000,
      language: 'portuguese',
      task: 'transcribe',
      chunk_length_s: 20,
      stride_length_s: 4
    };
    const doInference = async () => {
      try {
        return await asr(audio, runOptions);
      } catch (inferenceError) {
        const message = String(inferenceError?.message || inferenceError || '');
        if (!/session already started|already started/i.test(message) || asrDevice !== 'webgpu') throw inferenceError;
        console.warn('Whisper WebGPU session conflict; switching to stable CPU/WASM.', inferenceError);
        if ($('hint')) $('hint').textContent = 'Ajustando o reconhecimento de voz para evitar conflito de sessão…';
        asr = null;
        modelPromise = null;
        asrDevice = null;
        const cpuModel = await ensureCpuModel($('hint'));
        return await cpuModel(audio, runOptions);
      }
    };
    const inferenceJob = inferenceQueue.then(doInference, doInference);
    inferenceQueue = inferenceJob.then(() => undefined, () => undefined);
    const result = await inferenceJob;
    if (!active || thisSession !== session) return;
    // O estado pode ter mudado enquanto o modelo estava transcrevendo.
    if (Date.now() < commandCooldownUntil || window.localAssistantSpeaking || window.localAssistantBusy) return;
    const heard = String(result?.text || '').trim();
    const clean = normalize(heard);
    const hint = $('hint');

    if (!clean) return;

    // O Whisper às vezes inventa frases a partir de silêncio, ruído ou áudio de fundo.
    // Exigimos conteúdo mínimo e descartamos frases típicas de alucinação/legendas.
    const words = clean.split(' ').filter(Boolean);
    const hallucinations = [
      'obrigado por assistir', 'obrigada por assistir', 'legendas pela comunidade',
      'inscreva se no canal', 'se inscreva no canal', 'muito obrigado por assistir',
      'thanks for watching', 'subscribe to the channel', 'amara org',
      'som de fundo', 'musica de fundo', 'estou ouvindo um som', 'estou ouvindo uma musica',
      'nao consigo identificar', 'pode ser um som de agua', 'pode ser musica classica',
      'som de agua vento', 'musica tocando ao fundo', 'musica instrumental',
      'musica alegre', 'que abertura mais animada', 'estou ouvindo', 'parece ser um som',
      'o som de', 'uma musica tocando', 'barulho de fundo', 'audio de fundo'
    ];
    const likelyWake = /\b(?:sexta\s*(?:feira|feir|fera|ver)|sexto\s*ver)\b/.test(clean);
    const likelyCommand = /\b(?:abra|abre|abrir|inicie|inicia|iniciar|execute|executa|executar|rode|rodar|pesquise|pesquisar|procure|buscar|busque|crie|criar|anote|lembre|guarde|memorize|pare|parar|cancele|cancelar)\b/.test(clean);
    // O Whisper pode transformar música, abertura e ruído em frases inventadas.
    // Só descartamos os padrões de alucinação conhecidos; uma fala curta como "boa noite"
    // continua permitida para conversa, mas nunca interpretamos som ambiente como comando.
    if (words.length < 2 || clean.length < 5 || hallucinations.some(phrase => clean.includes(phrase))) {
      if (hint) hint.textContent = 'OUVINDO • descartei áudio sem fala clara';
      return;
    }
    // Evita encaminhar descrições inventadas de sons. Mantém frases conversacionais reais.
    if (!likelyWake && !likelyCommand && /\b(?:abertura|trilha|instrumental|som ambiente|som de fundo|musica|vento|agua|barulho)\b/.test(clean)) {
      if (hint) hint.textContent = 'OUVINDO • ignorei possível áudio de fundo';
      return;
    }
    if (hint) hint.textContent = 'RECONHECI: “' + heard + '”';

    const wake = clean.match(/\b(?:(?:bom dia|boa tarde|boa noite|ola|oi)\s+)?(?:sexta\s*(?:feira|feir|fera|ver)|sexto\s*ver)\b/);
    let command = '';
    if (wake) {
      command = clean.slice(wake.index + wake[0].length).trim();
      if (!command) {
        window.localWakeAwaiting = true;
        if (hint) hint.textContent = 'CHAMADA RECONHECIDA • FALE AGORA O COMANDO';
        state('OUVINDO COMANDO');
        return;
      }
      window.localWakeAwaiting = false;
    } else if (window.localWakeAwaiting) {
      command = heard;
      window.localWakeAwaiting = false;
    } else {
      // A fala comum é aceita, mas somente após o detector de atividade de voz
      // confirmar som de fala e fora do período em que a assistente está respondendo.
      command = heard;
    }

    if (!command || window.localAssistantSpeaking || window.localAssistantBusy) return;
    commandCooldownUntil = Date.now() + 4500;
    await deliver(command);
  } catch (error) {
    if (active && thisSession === session) {
      const hint = $('hint');
      if (hint) hint.textContent = 'Erro no Whisper local: ' + (error?.message || String(error));
      state('ERRO NO RECONHECIMENTO LOCAL');
    }
  } finally {
    transcribing = false;
  }
}

async function ensureCpuModel(hint) {
  if (asr && asrDevice === 'wasm') return asr;
  if (!modelPromise) {
    modelPromise = (async () => {
      if (hint) hint.textContent = 'Preparando reconhecimento estável pela CPU…';
      const model = await pipeline('automatic-speech-recognition', 'onnx-community/whisper-base', {
        device: 'wasm',
        progress_callback: progress => {
          if (!hint) return;
          if (progress?.status === 'progress' && Number.isFinite(progress.progress)) {
            hint.textContent = 'Preparando reconhecimento estável: ' + Math.round(progress.progress) + '%';
          }
        }
      });
      asr = model;
      asrDevice = 'wasm';
      return model;
    })().catch(error => { modelPromise = null; throw error; });
  }
  return modelPromise;
}

async function ensureModel(hint) {
  if (asr) return asr;
  if (!modelPromise) {
    modelPromise = (async () => {
      const options = {
        progress_callback: progress => {
          if (!hint) return;
          if (progress?.status === 'progress' && Number.isFinite(progress.progress)) {
            hint.textContent = 'Preparando modelo de voz: ' + Math.round(progress.progress) + '%';
          } else if (progress?.status === 'download') {
            hint.textContent = 'Baixando o modelo de voz otimizado pela primeira vez; depois será reutilizado do cache…';
          }
        }
      };
      // Usa Whisper Base na GPU para equilibrar velocidade e precisão; se a GPU falhar, recua para Whisper Base na CPU.
      if (navigator.gpu) {
        try {
          const model = await pipeline('automatic-speech-recognition', 'onnx-community/whisper-base', { ...options, device: 'webgpu' });
          asr = model; asrDevice = 'webgpu'; return model;
        } catch (gpuError) {
          console.warn('WebGPU indisponível para Whisper Base; usando WASM.', gpuError);
          if (hint) hint.textContent = 'GPU indisponível; preparando reconhecimento local pela CPU…';
        }
      }
      return await ensureCpuModel(hint);
    })().catch(error => { modelPromise = null; throw error; });
  }
  return modelPromise;
}

async function inspectMicPermission() {
  try {
    if (!navigator.permissions?.query) return 'unknown';
    const status = await navigator.permissions.query({ name: 'microphone' });
    permissionStatus = status.state;
    status.onchange = () => { permissionStatus = status.state; };
    return permissionStatus;
  } catch { return 'unknown'; }
}

async function startLocal() {
  if (active || loading) return;
  loading = true;
  active = true;
  window.localWhisperRunning = true;
  window.localWakeAwaiting = false;
  const thisSession = ++session;
  const hint = $('hint');

  try {
    if (!navigator.mediaDevices?.getUserMedia) {
      throw new Error('Este navegador não disponibilizou getUserMedia. Abra o site por HTTPS e confira o acesso ao microfone.');
    }

    if (hint) hint.textContent = 'Abrindo microfone…';
    stream = await navigator.mediaDevices.getUserMedia({
      audio: { channelCount: 1, echoCancellation: true, noiseSuppression: true, autoGainControl: true }
    });
    if (!active || thisSession !== session) return;

    const AudioContextClass = window.AudioContext || window.webkitAudioContext;
    if (!AudioContextClass) throw new Error('Este navegador não oferece suporte ao processamento de áudio.');
    audioContext = new AudioContextClass();
    await audioContext.resume();
    source = audioContext.createMediaStreamSource(stream);
    // Blocos menores reduzem a latência e deixam o detector de pausa mais preciso.
    processor = audioContext.createScriptProcessor(4096, 1, 1);
    pending = [];
    preRoll = [];
    sampleCount = 0;
    speechFrames = 0;
    silenceFrames = 0;
    peakRms = 0;
    capturingSpeech = false;

    processor.onaudioprocess = event => {
      if (!active || thisSession !== session) return;
      const channel = event.inputBuffer.getChannelData(0);
      let sumSquares = 0, framePeak = 0;
      for (let i = 0; i < channel.length; i++) {
        const value = channel[i];
        sumSquares += value * value;
        framePeak = Math.max(framePeak, Math.abs(value));
      }
      const rms = Math.sqrt(sumSquares / Math.max(1, channel.length));
      const voiceNow = rms >= 0.0065 && framePeak >= 0.018;

      if (Date.now() < commandCooldownUntil || window.localAssistantSpeaking || window.localAssistantBusy) {
        pending = [];
        preRoll = [];
        sampleCount = 0;
        speechFrames = 0;
        silenceFrames = 0;
        peakRms = 0;
        capturingSpeech = false;
      } else if (!transcribing) {
        lastRate = audioContext.sampleRate;

        if (voiceNow) {
          if (!capturingSpeech) {
            // Guarda só ~0,35 s antes da fala; nunca envia vários segundos de silêncio ao Whisper.
            pending = preRoll.slice();
            sampleCount = pending.reduce((total, part) => total + part.length, 0);
            capturingSpeech = true;
            speechFrames = 0;
            silenceFrames = 0;
            peakRms = 0;
          }
          const copy = new Float32Array(channel);
          pending.push(copy);
          sampleCount += copy.length;
          speechFrames++;
          silenceFrames = 0;
          peakRms = Math.max(peakRms, framePeak);
        } else if (capturingSpeech) {
          const copy = new Float32Array(channel);
          pending.push(copy);
          sampleCount += copy.length;
          silenceFrames++;
        } else {
          // Buffer circular curto para preservar o começo da palavra sem acumular silêncio.
          preRoll.push(new Float32Array(channel));
          if (preRoll.length > 5) preRoll.shift();
        }

        // ~0,7 s de silêncio encerra a frase. O tamanho mínimo evita transcrever cliques.
        const endedBySilence = capturingSpeech && speechFrames >= 4 && silenceFrames >= 12;
        const reachedLimit = capturingSpeech && sampleCount >= audioContext.sampleRate * 12;
        if ((endedBySilence || reachedLimit) && !transcribing) {
          const combined = new Float32Array(sampleCount);
          let offset = 0;
          for (const part of pending) {
            combined.set(part, offset);
            offset += part.length;
          }
          const hasVoice = speechFrames >= 3 && peakRms >= 0.018 && sampleCount >= audioContext.sampleRate * 0.38;
          pending = [];
          preRoll = [];
          sampleCount = 0;
          speechFrames = 0;
          silenceFrames = 0;
          peakRms = 0;
          capturingSpeech = false;
          if (hasVoice) transcribe(combined, lastRate || audioContext.sampleRate, thisSession);
        }
      }
      event.outputBuffer.getChannelData(0).fill(0);
    };
    source.connect(processor);
    processor.connect(audioContext.destination);

    if (hint) hint.textContent = asr ? 'Modelo de voz já está na memória.' : 'Preparando o modelo de voz; os arquivos baixados serão reutilizados do cache persistente…';
    state(asr ? 'MODELO DE VOZ PRONTO' : 'PREPARANDO MODELO DE VOZ');
    await ensureModel(hint);
    if (!active || thisSession !== session) return;
    $('mic')?.classList.add('active');
    if ($('mic')) $('mic').innerHTML = '● <span class="mic-label">VOZ LOCAL ATIVA</span>';
    if (hint) hint.textContent = 'VOZ LOCAL ATIVA • FALE NORMALMENTE; NÃO PRECISA DIZER “SEXTA-FEIRA”';
    state('OUVINDO COMANDOS');
  } catch (error) {
    stopLocal();
    const hint = $('hint');
    if (hint) hint.textContent = 'Não consegui iniciar a voz local: ' + (error?.message || error?.name || String(error));
    state('ERRO NO RECONHECIMENTO');
  } finally {
    loading = false;
  }
}

function stopByUser() {
  stopLocal();
  if ($('hint')) $('hint').textContent = 'ESCUTA DESATIVADA';
  state('SISTEMA PRONTO');
}

window.startLocalWhisper = startLocal;
window.stopLocalWhisper = stopByUser;
window.localWakeSend = deliver;

$('mic')?.addEventListener('click', event => {
  event.preventDefault();
  event.stopImmediatePropagation();
  if (active) stopByUser();
  else startLocal();
}, true);

$('stop')?.addEventListener('click', event => {
  if (active) {
    event.preventDefault();
    event.stopImmediatePropagation();
    stopByUser();
    if ($('hint')) $('hint').textContent = 'ESCUTA PARADA';
  }
}, true);


// Prepara o modelo em segundo plano ao abrir o app, sem pedir acesso ao microfone.
window.addEventListener('DOMContentLoaded', () => {
  const hint = $('hint');
  inspectMicPermission().then(permission => {
    if (permission === 'denied' && hint) hint.textContent = 'MICROFONE BLOQUEADO • confira as permissões do aplicativo.';
  });
  ensureModel(null).then(() => {
    if (!active && hint) hint.textContent = permissionStatus === 'denied'
      ? 'MODELO DE VOZ PRONTO • MICROFONE BLOQUEADO NAS PERMISSÕES'
      : 'MODELO DE VOZ PRONTO • CACHE PREPARADO';
  }).catch(error => {
    if (hint) hint.textContent = 'A voz será preparada ao ativar o microfone: ' + (error?.message || String(error));
  });
});
