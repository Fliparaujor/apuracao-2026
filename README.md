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
