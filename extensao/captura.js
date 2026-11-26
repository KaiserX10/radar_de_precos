// Runs on store pages: reads the visible prices and hands them to the extension to send to the Radar.
(() => {
  const loja = RadarLeitores.lojaDaPagina();
  if (!loja) return;

  const enviados = new Map();   // sku -> price already sent on this page (avoids resending)
  let espera = null;

  function capturar() {
    const itens = RadarLeitores.ler(loja).filter(i => enviados.get(i.sku) !== i.preco_vista);
    if (!itens.length) return;
    chrome.runtime.sendMessage({ tipo: 'captura', loja, pagina: location.href, itens }, resp => {
      if (chrome.runtime.lastError || !resp) return;
      if (resp.ok) itens.forEach(i => enviados.set(i.sku, i.preco_vista));
      if (resp.aviso) aviso(resp);
    });
  }

  // the stores load products dynamically (infinite scroll, filters): re-read after things settle
  const agendar = () => { clearTimeout(espera); espera = setTimeout(capturar, 2500); };
  new MutationObserver(agendar).observe(document.body, { childList: true, subtree: true });
  agendar();

  // --- discreet notice in the corner of the page (inside a shadow DOM so it doesn't clash with the site's CSS) ---
  let caixa;
  function aviso(r) {
    if (!caixa) {
      const host = document.createElement('div');
      host.style.cssText = 'position:fixed;left:16px;bottom:16px;z-index:2147483647';
      document.documentElement.appendChild(host);
      const raiz = host.attachShadow({ mode: 'closed' });
      raiz.innerHTML = `<style>
        .t{font:500 13px/1.35 Inter,system-ui,sans-serif;background:#111;color:#fff;padding:10px 14px;border-radius:999px;
           box-shadow:0 10px 30px -10px rgba(0,0,0,.5);opacity:0;transform:translateY(8px);transition:.25s;max-width:320px}
        .t.on{opacity:1;transform:none}.t b{font-weight:700}.t.erro{background:#c93b3b}</style><div class="t"></div>`;
      caixa = raiz.querySelector('.t');
    }
    caixa.className = 't on' + (r.ok ? '' : ' erro');
    caixa.innerHTML = r.ok
      ? `Radar: <b>${r.classificados}</b> preço${r.classificados == 1 ? '' : 's'} de GPU enviado${r.classificados == 1 ? '' : 's'}`
      : `Radar: ${r.erro || 'não foi possível enviar'}`;
    clearTimeout(caixa._h);
    caixa._h = setTimeout(() => caixa.classList.remove('on'), 4000);
  }
})();
