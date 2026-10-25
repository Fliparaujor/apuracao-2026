# Radar 2026 — 2º turno ao vivo

Novo painel mobile-first para acompanhar a totalização presidencial do segundo turno de 25/10/2026. Evolução e análises baseadas exclusivamente nas parciais oficiais do Tribunal Superior Eleitoral.

## Abrir no Samsung S23 (sem computador, sem instalar nada)

**[ABRIR O RADAR AO VIVO](https://raw.githack.com/Fliparaujor/apuracao-2026/main/ao-vivo.html)**

No Chrome Android, use o menu `⋮` → **Adicionar à tela inicial** (ou **Instalar app**, se disponível). Precisa de internet para consultar o TSE. Esse endereço é servido por um serviço estático externo, não é hospedagem oficial do GitHub Pages. Na primeira visita, o rawgit.hack mostra uma tela de confirmação de segurança: revise o endereço e continue se estiver correto.

### Rodar em localhost, diretamente no celular (Termux)

1. Instale o Termux atualizado pelo F-Droid.
2. Abra o Termux e execute:

```bash
pkg update
pkg install -y git python
git clone https://github.com/Fliparaujor/apuracao-2026.git
cd apuracao-2026
python server.py
```

3. Abra **http://127.0.0.1:8080/ao-vivo.html** no Chrome do S23.

O Termux deve permanecer com o servidor ligado para o endereço localhost funcionar. O servidor local faz proxy restrito dos JSON oficiais e evita bloqueio CORS ao abrir pelo localhost.

### Hospedagem recomendada (opcional)

Ative GitHub Pages em **Settings → Pages → Deploy from a branch → main → /(root)**. Depois use o endereço `https://fliparaujor.github.io/apuracao-2026/ao-vivo.html` para instalar como PWA. Antes da ativação, esse endereço pode não existir.

## Recursos

- Presidente no Brasil inteiro, 27 UFs, Fortaleza e Macapá
- Disputas de governador no 2º turno nas seis UFs com eleição (AC, AM, DF, ES, RN, TO)
- Atualização automática a cada 30 segundos, com pausa quando o app está em segundo plano
- Liderança parcial, diferenças em votos e em pontos percentuais, percentual de seções, comparecimento, brancos/nulos
- Séries históricas no navegador do aparelho, armazenadas durante a utilização
- Análises automáticas determinísticas, sem IA e sem API paga
- Modo instalável via manifesto, suporte básico a tela offline (nunca cachear JSON do TSE)

**Fonte:** `https://resultados.tse.jus.br/oficial/ele2026/`
- Presidente, 2º turno: eleição **6258**, cargo **1**
- Governador, 2º turno: eleição **6260**, cargo **3**

Os dados serão publicados após 17h (horário de Brasília). O TSE publica arquivos públicos e pode haver latência de atualização, erros de rede e mudanças nas políticas CORS. O app não apresenta resultados fictícios. **Apurado = percentual de seções totalizadas**, não votação futura ou estimativa de vitória. O histórico local só captura os momentos em que a página está aberta.

## Versão anterior preservada

O arquivo **index.html** é a versão feita anteriormente para 1º turno, com análises estáticas. Acesse: https://raw.githack.com/Fliparaujor/apuracao-2026/main/index.html

## Responsabilidade

Projeto independente, sem vínculo institucional com o Tribunal Superior Eleitoral.

## Analista político com IA real — novo

O painel possui uma aba **✦ Analista**, que pode ler dados oficiais em tempo quase real e elaborar uma análise com Gemini 3.8 Flash. O app continua exibindo os resultados sem chave; a aba de IA requer uma API key criada em [Google AI Studio](https://aistudio.google.com/api-keys). Há uma cota gratuita sujeita a limites e disponibilidade conforme o projeto. **Não usa o limite do Claude Code e não usa a assinatura ChatGPT.**

1. No Termux, pare o servidor atual com **Ctrl+C**.
2. Execute:

```bash
cd ~/apuracao-2026
git pull
read -rsp "Cole a chave Gemini: " GEMINI_API_KEY; echo
export GEMINI_API_KEY
python server.py
```

3. Cole a chave **no próprio Termux** quando solicitado (o texto digitado não aparece). Não compartilhe a chave em chat, screenshots ou GitHub.
4. No Chrome, abra **http://127.0.0.1:8080/ao-vivo.html** → **✦ Analista** → **Analisar agora**.

A chave permanece somente no processo/sessão do Termux; reiniciando o aplicativo, é preciso reexportá-la. Para testar a conexão, abra `http://127.0.0.1:8080/api/ia/status` — o endpoint revela se está configurada, **nunca o segredo**. Se seu modelo não estiver disponível, opcionalmente configure `export GEMINI_MODEL=gemini-3.8-flash` ou outro modelo suportado pela sua conta. Não use modelos pagos sem verificar a cobrança da sua conta.

**Recursos:** entrevista com perguntas livres, modo briefing, investigação de divergências regionais e comparações históricas, cenário matemático condicional e atualização por IA a cada 3 minutos **somente se habilitada**, enquanto a aba estiver visível. São consultados dados oficiais da eleição federal 6258 e, para contexto histórico, da 6257. Os cálculos e o histórico local usam somente Python padrão e SQLite; Gemini é chamado pelo backend com a chave privada. O navegador **nunca** recebe a API key.

**Limitações importantes:** não é observação ininterrupta; a aba precisa estar aberta e o Android precisa manter o Termux executando. O Gemini não navega na imprensa; só interpreta os boletins recuperados, e pode errar. Não produz prognóstico de quem será eleito nem chances numéricas. Em problemas de TSE ou cota do Gemini, a aba explicita a falha. Os arquivos oficiais podem mudar de formato ou ficar indisponíveis temporariamente.

O Google pode usar conteúdo enviado pela API gratuita para melhorar seus serviços; evite inserir dados pessoais nas perguntas. Confirme a política atual ao cadastrar sua chave.


## ◈ O Conselho — debate entre várias IAs (25/10/2026)

O Conselho é uma **segunda aba nova** do Radar 2026: chega a ter **7 modelos de 6 provedores**, conforme as chaves que você configurar no Termux. Nenhuma assinatura de chatbot é usada como se fosse API. Nenhuma API paga é cadastrada automaticamente.

| Cadeira | Provedor | Modelo | Variável de ambiente |
| --- | --- | --- | --- |
| Quantitativo | Groq | GPT-OSS 120B | GROQ_API_KEY |
| Cético | Groq | Qwen 3.8 27B | GROQ_API_KEY |
| Regional | Mistral | Mistral Small | MISTRAL_API_KEY |
| Histórico | OpenRouter | Router de modelos gratuitos (varia) | OPENROUTER_API_KEY |
| Auditoria | Cohere | Command A+ (trial/eval) | COHERE_API_KEY |
| Investigação | Cloudflare Workers AI | Nemotron 3 120B (Free, 10 mil Neurons/dia) | CLOUDFLARE_API_TOKEN + CLOUDFLARE_ACCOUNT_ID |
| Contraponto | Gemini | Gemini Flash (quando elegível para a cota Free) | GEMINI_API_KEY |

**Apenas membros com chave e resposta bem-sucedida participam.** Duas IAs do Groq com uma única chave não significam dois provedores independentes. O OpenRouter usa SOMENTE \`openrouter/free\`, sem fallback pago. Serviços que agora exigem cartão ou pagamento (por exemplo, SambaNova e o crédito promocional da Cerebras, conforme condições recentes) ficaram de fora para respeitar a restrição de **não cadastrar faturamento**.

**Começando só pelo Groq, sem faturamento:**

1. Crie sua chave no [GroqCloud](https://console.groq.com/keys), selecionando o nível gratuito.
2. No Termux, pare o servidor atual com **Ctrl+C**.
3. Execute um comando por vez:

\`\`\`bash
cd ~/apuracao-2026
git pull
read -rsp "Cole a chave do Groq: " GROQ_API_KEY; echo
export GROQ_API_KEY
python server.py
\`\`\`

4. Quando o Termux pedir, cole o segredo **lá no próprio Termux**, nunca nesta conversa. Digitar não exibe caracteres. Abra [localhost](http://127.0.0.1:8080/ao-vivo.html) → aba **◈ Conselho** → **Convocar Conselho**.

Para ativar novos membros, interrompa o servidor (**Ctrl+C**) e, ANTES de iniciar \`python server.py\`, exporte outras chaves gratuitas:

\`\`\`bash
read -rsp "Chave Mistral: " MISTRAL_API_KEY; echo
export MISTRAL_API_KEY
read -rsp "Chave OpenRouter: " OPENROUTER_API_KEY; echo
export OPENROUTER_API_KEY
read -rsp "Chave Cohere: " COHERE_API_KEY; echo
export COHERE_API_KEY
# (Opcional) caso sua conta Google tenha Gemini API Free:
read -rsp "Chave Gemini: " GEMINI_API_KEY; echo
export GEMINI_API_KEY
python server.py
\`\`\`

Opcional para Cloudflare (precisa de **plano Workers Free**, ID da conta e token com permissão Workers AI; mantenha a conta no plano Free para evitar cobranças):

```bash
read -rsp "Token Cloudflare Workers AI: " CLOUDFLARE_API_TOKEN; echo
export CLOUDFLARE_API_TOKEN
read -rp "ID da conta Cloudflare: " CLOUDFLARE_ACCOUNT_ID
export CLOUDFLARE_ACCOUNT_ID
python server.py
```

Acesse https://dash.cloudflare.com para obter o Account ID e gerar o token Workers AI. O código só chama o modelo `@cf/nvidia/nemotron-3-120b-a12b` do Workers Free; **não** ativa modelos terceirizados via Unified Billing. O plano Free impõe o limite de 10 mil Neurons/dia e nega o excesso, conforme a documentação da Cloudflare.

Só faça as linhas dos provedores que tiverem chave; os demais permanecem inativos. Cada provedor tem termos de uso, políticas de tratamento de dados e limites gratuitos próprios. Para o modo Free não há cadastro de cartão feito pelo aplicativo. Nunca compartilhe as chaves por WhatsApp ou screenshot. A consulta ao TSE é pública, mas sua pergunta é enviada aos provedores configurados.

### Como uma reunião funciona

1. **Análises independentes:** cada modelo recebe somente os mesmos boletins públicos do TSE, a pergunta e uma função específica.
2. **Críticas cruzadas:** cada modelo analisa os argumentos de outros modelos, aponta falhas, concordâncias fundamentadas e dados faltantes.
3. **Relatoria:** um modelo sintetiza pontos de convergência e as discordâncias não resolvidas. Não declara consenso quando só uma IA respondeu.

Os pareceres e réplicas aparecem separadamente. O relatório não é previsão eleitoral, não estima probabilidades, não recomenda votos e não substitui a totalização do TSE. Uma sessão pode consumir **2 chamadas por modelo + 1 para o relator**. O app permite reunião manual e atualização opcional a cada dez minutos quando houver boletim novo e a aba estiver aberta, com intervalo mínimo no servidor de nove minutos. Se um modelo não responder, aparece como indisponível, sem forjar participação.

**Observação:** recursos gratuitos podem ser retirados, sofrer erros HTTP 429, ou exigir políticas adicionais de conta sem aviso. As chaves não ficam em \`index.html\` nem \`conselho.js\`; os endpoints localizados em \`/api/conselho/status\` e \`/api/conselho/debater\` recebem somente a pergunta/UF. O número que aparece como "ativado" indica chave presente, não comprovação prévia de disponibilidade do serviço. O console no Termux precisa ficar executando.

O código é validado com \`python -m unittest discover -s tests -v\`, \`python -m py_compile\` e \`node --check\` no GitHub Actions. A validação é sintática/unitária com respostas simuladas; é preciso configurar chaves e testar a conexão real no próprio S23.

### Diagnóstico seguro do Groq (erro HTTP 401/403)

O botão **Testar autenticação Groq** na aba Analista consulta a API de modelos do Groq pelo servidor Termux e mostra o HTTP sem expor a chave. Também pode abrir `http://127.0.0.1:8080/api/ia/diagnostico` no Chrome; a resposta nunca inclui a chave. `401` significa que a credencial enviada foi rejeitada; `403` indica acesso negado; `429` é limite de consultas e `200` confirma apenas autenticação (não disponibilidade de modelo). Uma variável presente pode conter uma chave inválida: status "configurada" significa apenas que existe um valor na variável. Se uma chave foi publicada em print/chat, revogue-a e gere outra. Após trocar a variável, reinicie `python server.py`.

O Radar também avisa quando o horário do último boletim do TSE está mais de 10 minutos atrasado em relação ao horário do dispositivo (considerando data/hora de Brasília). Uma resposta HTTP 200 do TSE comprova conexão, não necessariamente que há novos votos.


## Reparação do S23 — diagnóstico único, mesmo sem API de IA

O app inclui agora duas ferramentas para quando **O Conselho** não consegue autenticar:

- **Diagnóstico do S23**: http://127.0.0.1:8080/diagnostico.html testa se o servidor local está vivo, se consegue ler um boletim TSE, o HTTP devolvido pelo Groq (sem mostrar a chave) e quantas cadeiras do Conselho foram configuradas. Pode copiar o resumo seguro.
- **Leitura sem IA**: na aba Analista, toque em **Ler dados sem IA**. Um módulo Python calcula diferenças, percentuais de seções e comparação com o último boletim local somente com o TSE, sem Groq, Gemini, chave ou cartão. O resultado é explicitamente marcado como cálculo descritivo, **não IA**.

No Termux, se a pasta já estiver instalada, basta:

\`\`\`bash
# Pare o servidor anterior com Ctrl+C e execute:
cd ~/apuracao-2026
git pull
python server.py
\`\`\`

Com o Termux aberto, abra pelo Chrome:
http://127.0.0.1:8080/diagnostico.html

**Interpretando o resultado:** Servidor OK + TSE OK = o app consegue funcionar para apuração sem IA. Groq HTTP 401 = chave rejeitada pelo Groq, que o programa não consegue corrigir. Groq 200 significa autenticação aceita, não prova de que cada modelo esteja disponível. Cadeira com "chave" significa só que a variável existe. Se você já expôs uma chave em conversa ou print, revogue-a, não a reutilize e não envie outras chaves por mensagem.

A página de diagnóstico e os endpoints não retornam os segredos. A leitura sem IA depende da disponibilidade dos arquivos oficiais do TSE. Nenhum dado eleitoral é inventado em caso de erro.
