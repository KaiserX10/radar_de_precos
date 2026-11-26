const PADRAO = {
  api: 'https://radar-de-precos-henna.vercel.app', senha: '',
  lojas: { pichau: true, terabyte: true, mercadolivre: true, shopee: true }, aviso: true, fecharAbas: true,
};
const LOJAS = [
  ['pichau', 'Pichau', 'P', ''], ['terabyte', 'Terabyte', 'T', ''],
  ['mercadolivre', 'Mercado Livre', 'M', 'cinza'], ['shopee', 'Shopee', 'S', 'claro'],
];
const $ = id => document.getElementById(id);
const esc = s => String(s ?? '').replace(/[&<>"']/g, c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));

async function carregar() {
  const { config: c = {}, stats = {} } = await chrome.storage.local.get(['config', 'stats']);
  const cfg = { ...PADRAO, ...c, lojas: { ...PADRAO.lojas, ...(c.lojas || {}) } };
  $('api').value = cfg.api; $('senha').value = cfg.senha; $('aviso').checked = cfg.aviso; $('fecharAbas').checked = cfg.fecharAbas;

  $('lojas').innerHTML = LOJAS.map(([id, nome, letra, estilo]) => {
    const s = stats[id];
    const quando = s ? new Date(s.quando).toLocaleString('pt-BR', { day: '2-digit', month: '2-digit', hour: '2-digit', minute: '2-digit' }) : '';
    const linha = !s ? '<span>nenhuma captura ainda</span>'
      : s.ok ? `<span class="ok">${s.classificados} preço${s.classificados == 1 ? '' : 's'} de GPU · ${quando}</span>`
             : `<span class="erro">${esc(s.erro)} · ${quando}</span>`;
    return `<div class="loja"><span class="av ${estilo}" aria-hidden="true">${letra}</span>
      <div class="info"><b>${nome}</b>${linha}</div>
      <label class="chave" title="Capturar preços da ${nome}"><input type="checkbox" data-loja="${id}" ${cfg.lojas[id] ? 'checked' : ''}><i></i><span hidden>${nome}</span></label></div>`;
  }).join('');
  $('marcas').innerHTML = LOJAS.map(([id, nome]) =>
    `<label><input type="checkbox" data-busca="${id}" ${cfg.lojas[id] && id !== 'shopee' ? 'checked' : ''}>${nome}</label>`).join('');

  document.querySelectorAll('[data-loja]').forEach(i => i.onchange = salvar);
  $('aviso').onchange = salvar; $('fecharAbas').onchange = salvar;
}

async function salvar() {
  const lojas = {};
  document.querySelectorAll('[data-loja]').forEach(i => lojas[i.dataset.loja] = i.checked);
  const api = $('api').value.trim().replace(/\/+$/, '') || PADRAO.api;
  await chrome.storage.local.set({ config: { api, senha: $('senha').value, lojas, aviso: $('aviso').checked, fecharAbas: $('fecharAbas').checked } });
  return api;
}

function msg(id, texto, tipo) { const m = $(id); m.textContent = texto; m.className = 'msg ' + (tipo || ''); }

$('salvar').onclick = async () => { await salvar(); msg('msgCon', 'Salvo.', 'ok'); };
$('testar').onclick = async () => {
  await salvar(); msg('msgCon', 'Testando…');
  const r = await chrome.runtime.sendMessage({ tipo: 'testar' });
  msg('msgCon', r.ok ? `Conectado. Última coleta automática: ${r.s.ultima ? new Date(r.s.ultima).toLocaleTimeString('pt-BR', { hour: '2-digit', minute: '2-digit' }) : '—'}` : 'Sem conexão: ' + r.erro, r.ok ? 'ok' : 'erro');
};
$('abrir').onclick = async () => {
  const lojas = [...document.querySelectorAll('[data-busca]:checked')].map(i => i.dataset.busca);
  if (!lojas.length) return msg('msgBuscas', 'Escolha pelo menos uma loja.', 'erro');
  await salvar();
  $('abrir').disabled = true; msg('msgBuscas', 'Abrindo as buscas…');
  const r = await chrome.runtime.sendMessage({ tipo: 'abrirBuscas', lojas });
  $('abrir').disabled = false;
  msg('msgBuscas', r.ok ? `${r.n} buscas abertas.` : 'Não foi possível: ' + r.erro, r.ok ? 'ok' : 'erro');
};
$('painel').onclick = async e => { e.preventDefault(); chrome.tabs.create({ url: (await salvar()) }); };

carregar();
chrome.storage.onChanged.addListener(ch => { if (ch.stats) carregar(); });
