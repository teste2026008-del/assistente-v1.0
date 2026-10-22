export default {
  async fetch(request, env) {
    const url = new URL(request.url);
    const cors = {
      "Access-Control-Allow-Origin": url.origin,
      "Access-Control-Allow-Methods": "POST, OPTIONS",
      "Access-Control-Allow-Headers": "Content-Type",
      "Content-Type": "application/json; charset=utf-8",
      "Cache-Control": "no-store"
    };
    if (url.pathname.startsWith("/api/")) {
      if (request.method === "OPTIONS") return new Response(null, { headers: cors });
      if (url.pathname === "/api/health") return Response.json({ ok: true, service: "Assistente V1.0" }, { headers: cors });
      if (url.pathname !== "/api/chat") return Response.json({ error: "Endpoint não encontrado." }, { status: 404, headers: cors });
      if (request.method !== "POST") return Response.json({ error: "Método não permitido." }, { status: 405, headers: cors });
      if (!env.AI) return Response.json({ error: "A IA ainda não está habilitada. Confira o binding AI nas configurações do Worker." }, { status: 503, headers: cors });
      try {
        const body = await request.json();
        const message = typeof body.message === "string" ? body.message.trim() : "";
        if (!message) return Response.json({ error: "Diga ou escreva uma mensagem." }, { status: 400, headers: cors });
        if (message.length > 8000) return Response.json({ error: "A mensagem é muito longa. Envie até 8.000 caracteres." }, { status: 413, headers: cors });
        const result = await env.AI.run("@cf/meta/llama-3.1-8b-instruct", {
          messages: [
            { role: "system", content: "Você é Jarvis, o assistente pessoal do usuário. Converse em português brasileiro natural, de forma humana, amigável, dialogal e concisa, com tom masculino informal sem exagerar nas gírias. Faça perguntas de acompanhamento quando necessário e mantenha o assunto da conversa. Ajude com programação e projetos. Seja transparente: não diga que acessou GitHub, Cloudflare ou arquivos sem uma integração real disponível. Nunca peça senhas, tokens ou chaves secretas." },
            { role: "user", content: message }
          ],
          max_tokens: 700
        });
        const reply = result?.response || result?.result?.response;
        if (!reply) return Response.json({ error: "O modelo não retornou uma resposta válida." }, { status: 502, headers: cors });
        return Response.json({ reply }, { headers: cors });
      } catch (err) {
        return Response.json({ error: "Não consegui gerar a resposta. Confira se Workers AI está habilitado e se há cota disponível." }, { status: 502, headers: cors });
      }
    }
    if (env.ASSETS) return env.ASSETS.fetch(request);
    return new Response("Assistente V1.0: o binding ASSETS não está configurado.", { status: 503, headers: { "Content-Type": "text/plain; charset=utf-8" } });
  }
};