# Extensão "Radar de Preços — Captura"

Adiciona **Pichau, Terabyte, Mercado Livre e Shopee** ao Radar sem robô na nuvem:
quando **você** abre uma página de busca ou de produto dessas lojas no Chrome, a extensão lê os
preços que já estão na tela e envia ao painel. Não faz requisições escondidas nem tenta driblar
proteção dos sites — é a sua visita normal.

## Instalar (uma vez)

1. Abra `chrome://extensions` no Chrome.
2. Ligue o **Modo do desenvolvedor** (canto superior direito).
3. Clique em **Carregar sem compactação** e escolha esta pasta (`extensao`).
4. Fixe o ícone (quebra-cabeça → alfinete ao lado de "Radar de Preços").
5. Clique no ícone → em **Conexão com o Radar**, digite a **senha do painel** → **Testar** → **Salvar**.

## Usar

- **Navegando normalmente:** abra uma busca (ex.: "rtx 5060") ou um produto em qualquer uma das
  4 lojas. Um aviso no canto da página mostra quantos preços de GPU foram enviados.
- **Abrir minhas buscas:** no ícone, escolha as lojas e clique em **Abrir buscas**. A extensão abre
  as buscas das suas GPUs (uma aba a cada 4 s), captura os preços e fecha as abas.
- **Shopee:** exige estar logado na Shopee para buscar. Faça login normalmente no site antes.

## Como os preços aparecem no painel

- Entram com as mesmas regras das outras lojas (família da GPU, piso de R$ 700, "suspeito",
  usados/PCs descartados, alertas).
- Valem como "oferta atual" por **12 horas** depois da captura; o painel mostra "capturado às HH:MM".
- Mercado Livre e Shopee: anúncios internacionais são ignorados.

## Privacidade

A senha fica salva só neste Chrome (`chrome.storage.local`). A extensão só lê páginas das 4 lojas
e só envia dados para o endereço do painel configurado.
