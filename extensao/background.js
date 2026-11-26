// Extension service worker: sends captures to the Radar and opens your searches when you ask.
const PADRAO = {
  api: 'https://radar-de-precos-henna.vercel.app',
  senha: '',
  lojas: { pichau: true, terabyte: true, mercadolivre: true, shopee: true },
  aviso: true,          // show the notice on the store page
  fecharAbas: true,     // close the tabs opened by "Abrir minhas buscas" after the capture
};
const BUSCA = {
  pichau: t => `https://www.pichau.com.br/search?q=${encodeURIComponent(t)}`,
  terabyte: t => `https://www.terabyteshop.com.br/busca?str=${encodeURIComponent(t).replace(/%20/g, '+')}`,
  mercadolivre: t => `https://lista.mercadolivre.com.br/${encodeURIComponent(t.replace(/\s+/g, '-'))}`,
  shopee: t => `https://shopee.com.br/search?keyword=${encodeURIComponent(t)}`,
};

async function config() {
  const { config: c } = await chrome.storage.local.get('config');
  return { ...PADRAO, ...(c || {}), lojas: { ...PADRAO.lojas, ...(c?.lojas || {}) } };
}
const base = c => c.api.replace(/\/+$/, '');

async function registrar(loja, dados) {
  const { stats = {} } = await chrome.storage.local.get('stats');
  stats[loja] = { ...(stats[loja] || {}), ...dados, quando: Date.now() };
  await chrome.storage.local.set({ stats });
}

async function enviar({ loja, pagina, itens }, tabId) {
  const c = await config();
  if (!c.lojas[loja]) return { ok: false, ignorado: true };
  try {
    const r = await fetch(`${base(c)}/api/captura`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json', ...(c.senha ? { 'X-Senha': c.senha } : {}) },
      body: JSON.stringify({ loja, pagina, itens }),
    });
    if (r.status === 401) throw new Error('senha do painel incorreta — confira no ícone da extensão');
    if (!r.ok) throw new Error(`o Radar respondeu ${r.status}`);
    const res = await r.json();
    await registrar(loja, { ok: true, enviados: itens.length, classificados: res.classificados, erro: null });
    chrome.action.setBadgeBackgroundColor({ color: '#111' });
    chrome.action.setBadgeText({ text: String(res.classificados || '') });
    setTimeout(() => chrome.action.setBadgeText({ text: '' }), 6000);
    await fecharSeFoiAberta(tabId, c);
    return { ok: true, aviso: c.aviso, classificados: res.classificados };
  } catch (e) {
    const erro = String(e.message || e).replace(/^TypeError: /, '');
    await registrar(loja, { ok: false, erro });
    chrome.action.setBadgeBackgroundColor({ color: '#c93b3b' });
    chrome.action.setBadgeText({ text: '!' });
    return { ok: false, aviso: c.aviso, erro };
  }
}

// ---- "Abrir minhas buscas": opens (at YOUR click) the search pages, one by one, gently ----
async function abasAbertas() { return (await chrome.storage.session.get('abas')).abas || []; }
async function fecharSeFoiAberta(tabId, c) {
  if (!tabId || !c.fecharAbas) return;
  const abas = await abasAbertas();
  if (!abas.includes(tabId)) return;
  await chrome.storage.session.set({ abas: abas.filter(t => t !== tabId) });
  setTimeout(() => chrome.tabs.remove(tabId).catch(() => {}), 1500);
}

async function abrirBuscas(lojas) {
  const c = await config();
  const r = await fetch(`${base(c)}/api/buscas`);
  if (!r.ok) throw new Error(`o Radar respondeu ${r.status}`);
  const { termos } = await r.json();
  const urls = lojas.flatMap(l => termos.map(t => BUSCA[l](t)));
  for (const [i, url] of urls.entries()) {
    const aba = await chrome.tabs.create({ url, active: false });
    await chrome.storage.session.set({ abas: [...await abasAbertas(), aba.id] });
    if (i < urls.length - 1) await new Promise(res => setTimeout(res, 4000));  // gentle pace: 1 page every 4 s
  }
  return urls.length;
}

chrome.runtime.onMessage.addListener((msg, sender, responder) => {
  if (msg.tipo === 'captura') { enviar(msg, sender.tab?.id).then(responder); return true; }
  if (msg.tipo === 'abrirBuscas') {
    abrirBuscas(msg.lojas).then(n => responder({ ok: true, n }), e => responder({ ok: false, erro: e.message }));
    return true;
  }
  if (msg.tipo === 'testar') {
    config().then(c => fetch(`${base(c)}/api/status`)).then(r => r.ok ? r.json() : Promise.reject(new Error('HTTP ' + r.status)))
      .then(s => responder({ ok: true, s }), e => responder({ ok: false, erro: e.message }));
    return true;
  }
});
