export default {
 async fetch(request, env) {
  const url = new URL(request.url);
  const headers = { "Content-Type":"application/json; charset=utf-8", "Cache-Control":"no-store", "Access-Control-Allow-Origin":url.origin, "Access-Control-Allow-Methods":"GET, POST, OPTIONS", "Access-Control-Allow-Headers":"Content-Type" };
  if (url.pathname.startsWith("/api/")) {
   if (request.method === "OPTIONS") return new Response(null,{headers});
   if (url.pathname === "/api/health") return Response.json({ok:true,service:"Sexta-Feira",aiAvailable:!!env.AI,elevenLabsAvailable:!!env.ELEVENLABS_API_KEY,voiceId:"GM2UA3fbsIaLHcswCDX9"},{headers});
   if (request.method !== "POST") return Response.json({error:"Use POST para este endpoint."},{status:405,headers});
   if (url.pathname === "/api/tts") {
    if (!env.ELEVENLABS_API_KEY) return Response.json({error:"A chave ELEVENLABS_API_KEY não está configurada como Secret no Worker."},{status:503,headers});
    try {
     const body = await request.json();
     const text = typeof body.text === "string" ? body.text.trim() : "";
     if (!text) return Response.json({error:"Texto vazio para gerar a voz."},{status:400,headers});
     if (text.length > 4500) return Response.json({error:"O texto para voz excede o limite de 4.500 caracteres."},{status:413,headers});
     const response = await fetch("https://api.elevenlabs.io/v1/text-to-speech/GM2UA3fbsIaLHcswCDX9?output_format=mp3_44100_128", {
      method:"POST",
      headers:{"xi-api-key":env.ELEVENLABS_API_KEY,"Content-Type":"application/json","Accept":"audio/mpeg"},
      body:JSON.stringify({text,model_id:"eleven_multilingual_v2",voice_settings:{stability:0.48,similarity_boost:0.82,style:0.25,use_speaker_boost:true}})
     });
     if (!response.ok) {
      const detail = (await response.text()).slice(0,500);
      return Response.json({error:"ElevenLabs recusou a geração de voz.",detail},{status:response.status===401||response.status===403?502:response.status,headers});
     }
     return new Response(response.body,{status:200,headers:{"Content-Type":"audio/mpeg","Cache-Control":"no-store","Access-Control-Allow-Origin":url.origin}});
    } catch (err) {
     return Response.json({error:"Falha ao gerar áudio com ElevenLabs.",detail:String(err?.message||err).slice(0,250)},{status:502,headers});
    }
   }
   if (url.pathname === "/api/chat") {
    if (!env.AI) return Response.json({error:"A inteligência artificial não está conectada ao Worker. O binding AI precisa estar habilitado."},{status:503,headers});
    try {
     const body = await request.json();
     const message = typeof body.message === "string" ? body.message.trim() : "";
     if (!message) return Response.json({error:"Digite ou fale uma mensagem."},{status:400,headers});
     if (message.length > 8000) return Response.json({error:"A mensagem passou do limite de 8.000 caracteres."},{status:413,headers});
     const result = await env.AI.run("@cf/meta/llama-3.1-8b-fast-v2",{messages:[
      {role:"system",content:"Seu nome é Sexta-Feira, assistente pessoal inspirado em uma IA de ficção científica. Converse em português brasileiro natural, com tom amigável, humano, direto e informal. Responda ao que a pessoa perguntou, faça perguntas só quando necessário e não repita saudações sem motivo. Ajude com programação e projetos. Seja transparente: não afirme que acessou GitHub, Cloudflare ou arquivos sem integração real disponível. Nunca peça senhas, tokens ou chaves secretas."},
      {role:"user",content:message}
     ],max_tokens:700});
     const reply = result?.response ?? result?.result?.response ?? result?.output_text ?? result?.choices?.[0]?.message?.content;
     if (typeof reply !== "string" || !reply.trim()) return Response.json({error:"A IA foi chamada, mas não retornou texto. Confira o modelo e a cota de Workers AI."},{status:502,headers});
     return Response.json({reply:reply.trim()},{headers});
    } catch (err) {
     return Response.json({error:"Falha ao gerar resposta na IA. Verifique o acesso ao Workers AI, o modelo configurado e a cota disponível.",detail:String(err?.message||err).slice(0,300)},{status:502,headers});
    }
   }
   return Response.json({error:"Endpoint não encontrado."},{status:404,headers});
  }
  return env.ASSETS.fetch(request);
 }
};
