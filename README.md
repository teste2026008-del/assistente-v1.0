# Assistente V1.0

Assistente de programação em português brasileiro, com interface de conversa, entrada por microfone e respostas faladas pelo navegador.

## Estado atual

- Interface responsiva em `public/index.html`.
- Captura de voz pelo reconhecimento de fala do navegador (quando suportado).
- Leitura das respostas com a síntese de voz do navegador.
- Endpoint `/api/chat` em `src/index.js`, preparado para Cloudflare Workers AI.
- O agente local pode abrir uma janela própria de navegador com Playwright, navegar, ler conteúdo, clicar em links, preencher campos e baixar arquivos oferecidos por uma página.
- Downloads por link HTTP/HTTPS direto vão para pastas conhecidas do usuário, sem sobrescrever arquivos existentes.

## Executar localmente no Windows

1. Baixe o ZIP pelo botão **Code → Download ZIP**.
2. Instale Python 3.11+ e marque **Add Python to PATH**.
3. Extraia o ZIP e execute `ABRIR-SEXTA-FEIRA.vbs` para abrir a janela nativa sem deixar o terminal visível. Na primeira execução, o inicializador pode instalar o pacote pywebview.
4. A janela nativa carrega a interface local em `http://127.0.0.1:8765`; não é necessário abrir uma aba externa.
5. Para atualizar arquivos sem baixar outro ZIP, execute `ATUALIZAR-SEXTA-FEIRA.ps1` no PowerShell depois que o repositório estiver público. O script cria um backup antes de substituir os arquivos.
6. O Whisper usa o cache do navegador/WebView quando disponível. Na primeira utilização, o modelo pode precisar ser baixado.

Comandos locais: abrir sites, pesquisar na web, abrir aplicativos e pastas conhecidas, listar pastas, consultar informações do computador, controlar uma janela de navegador isolada, baixar arquivos por link direto ou por link visível na página, consultar Git e criar notas. Não executa comandos arbitrários nem abre ou executa automaticamente arquivos baixados. O navegador controlável usa um perfil separado; ele não assume a sessão já aberta do Chrome/Edge. Para links que exigem login, captcha ou confirmação, o usuário pode precisar concluir a etapa no navegador.

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
