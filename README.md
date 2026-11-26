# Radar de Preços — GPUs

Monitora preços de famílias de placas de vídeo (sem prender a um modelo específico),
guarda o histórico e mostra um painel com o menor preço, mínimos por período e comparativo.

## Como usar

1. Dê dois cliques em `iniciar.bat` (ou rode `.venv\Scripts\python run.py`).
2. O painel abre em http://localhost:8765. A coleta roda a cada 15 min enquanto a janela estiver aberta.
3. Deixe o PC ligado e sem suspensão durante a Black Friday.

## Configuração (`config.json`)

- `familias[].preco_alvo`: preço que dispara alerta. Edite direto no painel (campo 🎯 Preço-alvo de cada
  card; Enter salva, Esc limpa). Vazio = só alertar novos mínimos. Se o preço atual já estiver
  abaixo do alvo ao salvar, o alerta sai na hora.
- `intervalo_minutos`: frequência da coleta.
- `telegram.token` e `telegram.chat_id`: preencha para receber alertas no Telegram
  1. No Telegram, fale com **@BotFather** → `/newbot` → copie o token.
  2. Mande qualquer mensagem para o seu bot novo.
  3. Abra `https://api.telegram.org/bot<TOKEN>/getUpdates` e copie o número em `"chat":{"id": ...}`.
- Regras de título: `incluir` / `excluir` (regex) e `memoria` (8, 16…) por família.

Alterações no `config.json` valem a partir da próxima coleta (não precisa reiniciar).

## Alertas

Disparados quando o menor preço da família:
- atinge o `preco_alvo`, ou
- fica abaixo do menor preço já registrado (ou do mínimo de 90d / 30d).

Não repete o alerta para o mesmo preço; só alerta de novo se cair mais `queda_minima_reais`.

## Histórico

Só a partir do momento em que o radar começou a coletar (sem histórico de longo prazo).
O painel mostra os mínimos de 24h, 7 dias, 30 dias e desde o início.

## Ofertas suspeitas

Ofertas abaixo de `preco_minimo_reais` (R$ 700) são ignoradas (acessórios, ventoinhas).
Ofertas abaixo de 60% da mediana da família (`suspeito_abaixo_da_mediana`; referência: KaBuM)
são marcadas como ⚠ suspeitas e ficam fora do menor preço e dos alertas.

## Comparativo

Especificações e índice de desempenho ficam em `dados/specs.json` (desempenho é aproximado,
RTX 4060 = 100). O painel calcula R$ por ponto de desempenho e R$ por GB de VRAM.

## Lojas

Ativas: KaBuM (a cada 15 min) e AliExpress (a cada 30 min, com pausa entre buscas para não
cair na verificação anti-robô). Se uma loja falhar, o painel mantém as ofertas anteriores dela por até 3h.
AliExpress: o preço da busca pode não incluir impostos de importação e frete; confira no checkout.

Para adicionar outra loja, crie um módulo com `buscar(termo)` retornando ofertas no mesmo
formato e registre em `radar/lojas/__init__.py`. Terabyte, Pichau e Shopee bloqueiam acesso automatizado.
