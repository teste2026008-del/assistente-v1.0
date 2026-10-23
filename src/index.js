export default {
 async fetch(request, env) {
  const url = new URL(request.url);
  const headers = { "Content-Type":"application/json; charset=utf-8", "Cache-Control":"no-store", "Access-Control-Allow-Origin":url.origin, "Access-Control-Allow-Methods":"GET, POST, OPTIONS", "Access-Control-Allow-Headers":"Content-Type" };
  if (url.pathname.startsWith("/api/")) {
   if (request.method === "OPTIONS") return new Response(null,{headers});
   if (url.pathname === "/api/health") return Response.json({ok:true,service:"Sexta-Feira",aiAvailable:!!env.AI,elevenLabsAvailable:!!env.ELEVENLABS_API_KEY,voiceId:"pNInz6obpgDQGcFmaJgB"},{headers});
   if (request.method !== "POST") return Response.json({error:"Use POST para este endpoint."},{status:405,headers});
   if (url.pathname === "/api/tts") {
    return Response.json({error:"A geração de voz online foi desativada. Use a voz local da Sexta-Feira."},{status:410,headers});
   }
       if (url.pathname === "/api/chat") {
    if (!env.AI) return Response.json({error:"A inteligência artificial não está conectada ao Worker. O binding AI precisa estar habilitado."},{status:503,headers});
    try {
     const body = await request.json();
     const message = typeof body.message === "string" ? body.message.trim() : "";
     if (!message) return Response.json({error:"Digite ou fale uma mensagem."},{status:400,headers});
     if (message.length > 8000) return Response.json({error:"A mensagem passou do limite de 8.000 caracteres."},{status:413,headers});
     const result = await env.AI.run("@cf/meta/llama-3.1-8b-fast-v2",{messages:[
      {role:"system",content:"Você é Sexta-Feira, assistente pessoal que fala português brasileiro. Seja muito direta e econômica: responda exatamente ao que a pessoa pediu, de preferência em poucas frases. Não acrescente explicações, sugestões, ofertas de ajuda, resumos ou perguntas que não foram solicitadas. Faça uma pergunta só se for indispensável para entender ou concluir a tarefa. Pode brincar de vez em quando, com humor leve e natural, mas sem exagerar nem desviar do assunto. Quando ouvir apenas 'bom dia/boa tarde/boa noite, Sexta-Feira', responda com uma saudação curta e natural. Não invente ações ou acessos a sistemas. Nunca peça senhas, tokens ou chaves secretas."},
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
