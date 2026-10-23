import { pipeline, env } from 'https://esm.sh/@huggingface/transformers@3.7.2?bundle';
env.allowLocalModels = false;
env.useBrowserCache = true;

const $ = id => document.getElementById(id);
let asr = null, stream = null, audioContext = null, source = null, processor = null;
let active = false, loading = false, transcribing = false, pending = [], sampleCount = 0, lastRate = 0;
let session = 0;

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
  transcribing = true;
  try {
    const audio = resample(samples, rate, 16000);
    const result = await asr(audio, {
      sampling_rate: 16000,
      language: 'portuguese',
      task: 'transcribe',
      chunk_length_s: 20,
      stride_length_s: 4
    });
    if (!active || thisSession !== session) return;
    const heard = String(result?.text || '').trim();
    const clean = normalize(heard);
    const hint = $('hint');
    if (heard && hint) hint.textContent = 'RECONHECI: “' + heard + '”';

    if (!clean) return;

    // O microfone é ativado manualmente pelo usuário: aceite comandos falados
    // diretamente, sem exigir palavra de ativação. A palavra "Sexta-Feira"
    // continua funcionando para chamar a assistente antes de dar o comando.
    const wake = clean.match(/\b(?:(?:bom dia|boa tarde|boa noite|ola|oi)\s+)?sexta\s*(?:feira|feir|fera)\b/);
    if (wake) {
      const rest = clean.slice(wake.index + wake[0].length).trim();
      if (rest) {
        window.localWakeAwaiting = false;
        await deliver(rest);
      } else {
        window.localWakeAwaiting = true;
        if (hint) hint.textContent = 'CHAMADA RECONHECIDA • FALE AGORA O COMANDO';
        state('OUVINDO COMANDO');
      }
    } else if (window.localWakeAwaiting) {
      window.localWakeAwaiting = false;
      await deliver(heard);
    } else {
      // Como o usuário já clicou para ativar o microfone, envie a fala
      // reconhecida mesmo quando o Whisper não capturar a palavra de ativação.
      await deliver(heard);
    }
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
    processor = audioContext.createScriptProcessor(16384, 1, 1);
    pending = [];
    sampleCount = 0;

    processor.onaudioprocess = event => {
      if (!active || thisSession !== session) return;
      const channel = event.inputBuffer.getChannelData(0);
      if (!transcribing) {
        pending.push(new Float32Array(channel));
        sampleCount += channel.length;
        lastRate = audioContext.sampleRate;
      }
      if (sampleCount >= audioContext.sampleRate * 5 && !transcribing) {
        const combined = new Float32Array(sampleCount);
        let offset = 0;
        for (const part of pending) { combined.set(part, offset); offset += part.length; }
        pending = [];
        sampleCount = 0;
        transcribe(combined, lastRate || audioContext.sampleRate, thisSession);
      }
      event.outputBuffer.getChannelData(0).fill(0);
    };
    source.connect(processor);
    processor.connect(audioContext.destination);

    if (hint) hint.textContent = 'Microfone ativo. Carregando reconhecimento local gratuito; na primeira vez pode demorar…';
    state('CARREGANDO WHISPER LOCAL');

    if (!asr) {
      asr = await pipeline(
        'automatic-speech-recognition',
        'onnx-community/whisper-tiny',
        {
          device: 'wasm',
          progress_callback: progress => {
            if (!active || thisSession !== session || !hint) return;
            if (progress?.status === 'progress' && Number.isFinite(progress.progress)) {
              hint.textContent = 'Preparando modelo de voz (cache local): ' + Math.round(progress.progress) + '%';
            } else if (progress?.status === 'download') {
              hint.textContent = 'Primeira utilização: baixando modelo de voz. Nas próximas vezes, o cache do navegador será reutilizado quando disponível…';
            }
          }
        }
      );
    }
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
