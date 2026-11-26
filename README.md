# Radar de Preços — GPUs

Monitora preços de famílias de placas de vídeo (sem prender a um modelo específico),
guarda o histórico e mostra um painel com o menor preço, mínimos por período e comparativo.

Roda de dois jeitos:

| | Local (Windows) | Nuvem |
|---|---|---|
| Coleta a cada 15 min | processo local (`iniciar.bat`) | GitHub Actions (`.github/workflows/coletar.yml`) |
| Banco | SQLite (`dados/radar.db`) | Postgres (Neon, via Vercel) |
| Painel | http://localhost:8765 | Vercel |
| Alertas | Windows + Telegram | Telegram |

Use **um ou outro** para coletar: os dois juntos geram alertas em dobro.

## Nuvem: configuração

1. **Vercel** → *Add New Project* → importe este repositório → *Deploy*.
2. No projeto da Vercel → *Storage* → *Create Database* → **Neon (Postgres)** → conecte ao projeto.
   Isso cria a variável `DATABASE_URL` no projeto.
3. Vercel → *Settings* → *Environment Variables*:
   - `PAINEL_SENHA`: senha para alterar preços-alvo pelo painel (sem ela, qualquer um com o link altera).
   - Opcional, para o botão "Coletar agora": `GITHUB_REPO` (`KaiserX10/radar_de_precos`) e `GITHUB_TOKEN`
     (token *fine-grained* com permissão **Actions: Read and write** só neste repositório).
   Depois, *Redeploy*.
4. **GitHub** → repositório → *Settings* → *Secrets and variables* → *Actions* → *New repository secret*:
   - `DATABASE_URL`: o mesmo valor da Vercel (Storage → banco → `.env.local` / *Show secret*).
   - `TELEGRAM_TOKEN` e `TELEGRAM_CHAT_ID` (veja abaixo).
5. GitHub → *Actions* → **Coletar preços** → *Run workflow* para a primeira coleta.
   Depois ela roda sozinha a cada ~15 min.

Para levar o histórico local para a nuvem: crie um arquivo `.env` com `DATABASE_URL=...`
e rode `.venv\Scripts\python -m radar.migrar` (só funciona com o Postgres vazio).

## Local: como usar

1. Dê dois cliques em `iniciar.bat`.
2. O painel abre em http://localhost:8765. A coleta roda a cada 15 min enquanto a janela estiver aberta.

## Configuração (`config.json`)

- Preço-alvo: edite direto no painel (campo 🎯 de cada card; Enter salva, Esc limpa). Fica salvo
  no banco. Se o preço atual já estiver abaixo do alvo ao salvar, o alerta sai na hora.
- `intervalo_minutos` / `intervalo_minutos_por_loja`: frequência da coleta (local).
- Telegram (`telegram.token` / `telegram.chat_id` no local; segredos `TELEGRAM_TOKEN` /
  `TELEGRAM_CHAT_ID` na nuvem):
  1. No Telegram, fale com **@BotFather** → `/newbot` → copie o token.
  2. Mande qualquer mensagem para o seu bot novo.
  3. Abra `https://api.telegram.org/bot<TOKEN>/getUpdates` e copie o número em `"chat":{"id": ...}`.
- Regras de título: `incluir` / `excluir` (regex) e `memoria` (8, 16…) por família.

## Alertas

Disparados quando o menor preço da família atinge o preço-alvo ou fica abaixo do menor preço
já registrado. Não repete o alerta para o mesmo preço; só alerta de novo se cair mais
`queda_minima_reais`.

## Histórico

Só a partir do momento em que o radar começou a coletar. O painel mostra os mínimos de
24h, 7 dias, 30 dias e desde o início.

## Ofertas suspeitas

Ofertas abaixo de `preco_minimo_reais` (R$ 700) são ignoradas (acessórios, ventoinhas).
Ofertas abaixo de 60% da mediana da família (`suspeito_abaixo_da_mediana`; referência: KaBuM)
são marcadas como ⚠ suspeitas e ficam fora do menor preço e dos alertas.

## Comparativo

Especificações e índice de desempenho ficam em `dados/specs.json` (desempenho é aproximado,
RTX 4060 = 100). O painel calcula R$ por ponto de desempenho e R$ por GB de VRAM.

## Lojas

KaBuM (a cada 15 min) e AliExpress (a cada 30 min, com pausa entre buscas para não cair na
verificação anti-robô). Se uma loja falhar, o painel mantém as ofertas anteriores dela por até 3h.
AliExpress: só entram produtos com envio do Brasil (filtro "Do Brasil" na busca e conferência do país de
origem de cada item); usados, "99New", seminovos e open box são descartados em todas as lojas.

Para adicionar outra loja, crie um módulo com `buscar(termo)` retornando ofertas no mesmo
formato e registre em `radar/lojas/__init__.py`. Terabyte, Pichau e Shopee bloqueiam acesso automatizado.

**Pichau, Terabyte, Mercado Livre e Shopee** entram pela extensão do Chrome em `extensao/`
(veja `extensao/LEIAME.md`): ela captura os preços das páginas que você abre e envia para
`POST /api/captura` (protegido pela senha do painel). Esses preços valem por 12 h como oferta atual.
