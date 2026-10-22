# Assistente V1.0

Assistente de programação em português brasileiro, com interface de conversa, entrada por microfone e respostas faladas pelo navegador.

## Estado atual

- Interface responsiva em `public/index.html`.
- Captura de voz pelo reconhecimento de fala do navegador (quando suportado).
- Leitura das respostas com a síntese de voz do navegador.
- Endpoint `/api/chat` em `src/index.js`, preparado para Cloudflare Workers AI.
- A integração com GitHub e Cloudflare para executar alterações em projetos ainda não está implementada.

## Publicar no Cloudflare Workers

1. Instale Node.js LTS e Wrangler em um ambiente local.
2. Na raiz do projeto, execute `npm install -D wrangler`.
3. Faça login com `npx wrangler login`.
4. Confira a disponibilidade e os limites do Workers AI na sua conta.
5. Execute `npx wrangler deploy`.

O arquivo `wrangler.jsonc` define o binding `AI`. Verifique o modelo disponível para sua conta antes de usar em produção. A voz usa recursos do navegador e pode variar entre Chrome, Edge e outros navegadores.

## Segurança

- Nunca coloque tokens do GitHub, chaves da Cloudflare ou segredos de API no HTML ou em arquivos públicos.
- A integração futura com GitHub/Cloudflare deve usar OAuth ou tokens restritos armazenados como secrets no servidor, com permissões mínimas e confirmação antes de ações destrutivas.
- Não exponha publicamente um endpoint de IA sem limites de uso, proteção contra abuso e controles de custo.

## Custos e limites

Hospedar a interface não significa que o processamento de IA seja ilimitado. Workers AI, reconhecimento de voz e síntese de voz têm requisitos, compatibilidade e limites próprios. Confirme as condições vigentes no painel/documentação da Cloudflare antes de disponibilizar o serviço publicamente.
