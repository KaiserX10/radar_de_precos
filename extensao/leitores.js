// Reads the products ALREADY VISIBLE on the page you opened. It doesn't make extra requests
// to the store: it just reads the screen, the same way you do.
(() => {
  const limpo = s => (s || '').replace(/\s+/g, ' ').trim();

  /** "R$ 3.159,99" | "3,159.99" | "5299 reales con 90 centavos" -> 3159.99 */
  function preco(txt) {
    if (txt == null) return null;
    const s = String(txt);
    const aria = s.match(/(\d+)\s*reais?|(\d+)\s*reales?/i);
    if (aria) {
      const inteiro = Number(aria[1] || aria[2]);
      const cent = s.match(/(\d{1,2})\s*centavos?/i);
      return inteiro + (cent ? Number(cent[1]) / 100 : 0);
    }
    const m = s.replace(/\s/g, '').match(/\d[\d.,]*/);
    if (!m) return null;
    let n = m[0].replace(/[.,]$/, '');
    const ultPonto = n.lastIndexOf('.'), ultVirg = n.lastIndexOf(',');
    if (ultPonto >= 0 && ultVirg >= 0) {           // both: the last one is the decimal separator
      const dec = ultPonto > ultVirg ? '.' : ',';
      n = n.split(dec === '.' ? ',' : '.').join('').replace(dec, '.');
    } else if (ultVirg >= 0) {                      // comma only: decimal if followed by 1-2 digits
      n = /,\d{1,2}$/.test(n) ? n.replace(/\./g, '').replace(',', '.') : n.replace(/,/g, '');
    } else if (ultPonto >= 0) {                     // dot only: thousands if followed by 3 digits
      n = /\.\d{3}$/.test(n) || (n.match(/\./g) || []).length > 1 ? n.replace(/\./g, '') : n;
    }
    const v = parseFloat(n);
    return Number.isFinite(v) && v > 0 ? v : null;
  }
  const precoApos = (txt) => { const m = String(txt).match(/R\$\s*([\d.,]+)/); return m ? preco(m[1]) : null; };
  const absoluta = href => { try { return new URL(href, location.origin).href.split('#')[0]; } catch { return null; } };
  const linhas = el => el.innerText.split('\n').map(limpo).filter(Boolean);
  const pareceGpu = t => /\b(rtx|gtx|rx\s?\d{3,4}|radeon|geforce|placa de v[ií]deo)\b/i.test(t);

  // --- product page: schema.org (JSON-LD), used by several stores ---
  function jsonLd(lojaVendedor) {
    const itens = [];
    for (const s of document.querySelectorAll('script[type="application/ld+json"]')) {
      let dados; try { dados = JSON.parse(s.textContent); } catch { continue; }
      const nos = [].concat(dados['@graph'] || dados);
      for (const p of nos) {
        if (!p || !/Product/i.test([].concat(p['@type']).join())) continue;
        const of = [].concat(p.offers || [])[0] || {};
        const v = preco(of.price ?? of.lowPrice);
        if (!v || !p.name) continue;
        itens.push({ sku: String(p.sku || p.productID || location.pathname), titulo: limpo(p.name), url: absoluta(location.href),
          preco_vista: v, preco_cheio: v, disponivel: !/OutOfStock|SoldOut/i.test(of.availability || ''), vendedor: lojaVendedor || limpo(of.seller?.name) });
      }
    }
    return itens;
  }

  const LEITORES = {
    // Pichau: <a data-cy="list-product"> with <h2> title; "de R$ X por" / "R$ Y" + "À vista"
    pichau() {
      const itens = [];
      for (const c of document.querySelectorAll('a[data-cy="list-product"]')) {
        const titulo = limpo(c.querySelector('h2')?.textContent);
        const url = absoluta(c.getAttribute('href'));
        if (!titulo || !url) continue;
        const ls = linhas(c);
        const iVista = ls.findIndex(l => /^à vista$/i.test(l));
        let vista = iVista > 0 ? precoApos(ls[iVista - 1]) : null;
        const lDe = ls.find(l => /^de R\$.*por$/i.test(l));
        if (!vista) { const iPor = ls.findIndex(l => /por$/i.test(l)); vista = iPor >= 0 ? precoApos(ls[iPor + 1]) : precoApos(ls.find(l => /R\$/.test(l))); }
        if (!vista) continue;
        itens.push({ sku: new URL(url).pathname.replace(/^\//, ''), titulo, url, preco_vista: vista,
          preco_cheio: lDe ? precoApos(lDe) || vista : vista, disponivel: !/esgotad|indispon/i.test(c.innerText), vendedor: 'Pichau' });
      }
      return itens.length ? itens : jsonLd('Pichau');
    },

    // Terabyte: .product-item with __name (title attr), __new-price, __old-price; link /produto/<id>/...
    terabyte() {
      const itens = [], vistos = new Set();
      for (const c of document.querySelectorAll('.product-item')) {
        const a = c.querySelector('a.product-item__name') || c.querySelector('a[href*="/produto/"]');
        if (!a) continue;
        const url = absoluta(a.getAttribute('href'));
        const id = (url || '').match(/\/produto\/(\d+)/)?.[1];
        if (!id || vistos.has(id)) continue;
        vistos.add(id);
        const vista = precoApos(c.querySelector('.product-item__new-price')?.textContent);
        const indisponivel = /esgotad|indispon/i.test(c.innerText);
        if (!vista && !indisponivel) continue;
        itens.push({ sku: id, titulo: limpo(a.getAttribute('title') || a.textContent), url, preco_vista: vista || 0,
          preco_cheio: precoApos(c.querySelector('.product-item__old-price')?.textContent) || vista || 0,
          disponivel: !indisponivel && !!vista, vendedor: 'Terabyte' });
      }
      return itens.filter(i => i.preco_vista > 0).length ? itens.filter(i => i.preco_vista > 0) : jsonLd('Terabyte');
    },

    // Mercado Livre: li.ui-search-layout__item; prices with aria-label ("5299 reales con 90 centavos")
    mercadolivre() {
      const itens = [];
      for (const c of document.querySelectorAll('li.ui-search-layout__item')) {
        const a = c.querySelector('a.poly-component__title') || c.querySelector('.poly-component__title a, h2 a, a.ui-search-link');
        if (!a) continue;
        const url = absoluta(a.getAttribute('href'));
        const sku = (url || '').match(/MLB-?\d+/i)?.[0]?.replace('-', '').toUpperCase();
        if (!url || !sku) continue;
        if (/compra internacional|\binternacional\b/i.test(c.innerText)) continue;  // only stock in Brazil
        const atual = c.querySelector('.poly-price__current .andes-money-amount') ||
                      c.querySelector('.andes-money-amount:not(.andes-money-amount--previous)');
        const vista = preco(atual?.getAttribute('aria-label')) || preco(atual?.textContent);
        if (!vista) continue;
        const antes = c.querySelector('.andes-money-amount--previous');
        itens.push({ sku, titulo: limpo(a.textContent), url, preco_vista: vista,
          preco_cheio: preco(antes?.getAttribute('aria-label')) || vista, disponivel: true,
          vendedor: limpo(c.querySelector('.poly-component__seller')?.textContent).replace(/^por\s+/i, '') });
      }
      return itens.length ? itens : jsonLd('');
    },

    // Shopee (needs login to search): product links contain "-i.<shop>.<item>"
    shopee() {
      const itens = [], vistos = new Set();
      for (const a of document.querySelectorAll('a[href*="-i."]')) {
        const url = absoluta(a.getAttribute('href'));
        const m = (url || '').match(/-i\.(\d+)\.(\d+)/);
        if (!m || vistos.has(m[2])) continue;
        const c = a.closest('li') || a;
        const texto = c.innerText || '';
        if (/\b(exterior|china continental|internacional)\b/i.test(texto)) continue;  // only stock in Brazil
        const titulo = limpo(c.querySelector('img[alt]')?.getAttribute('alt')) ||
                       linhas(c).find(l => l.length > 20 && !/R\$/.test(l));
        const vista = precoApos(texto.replace(/R\$\s*\n\s*/g, 'R$ '));
        if (!titulo || !vista) continue;
        vistos.add(m[2]);
        const riscado = c.querySelector('s, del, [style*="line-through"]');
        itens.push({ sku: `${m[1]}.${m[2]}`, titulo, url, preco_vista: vista,
          preco_cheio: precoApos(riscado?.textContent) || vista, disponivel: true, vendedor: '' });
      }
      return itens.length ? itens : jsonLd('');
    },
  };

  function lojaDaPagina(host = location.hostname) {
    if (host.endsWith('pichau.com.br')) return 'pichau';
    if (host.endsWith('terabyteshop.com.br')) return 'terabyte';
    if (host.endsWith('mercadolivre.com.br')) return 'mercadolivre';
    if (host.endsWith('shopee.com.br')) return 'shopee';
    return null;
  }

  function ler(loja) {
    const itens = (LEITORES[loja]?.() || []).filter(i => i.titulo && i.url && pareceGpu(i.titulo));
    return itens.slice(0, 200);
  }

  globalThis.RadarLeitores = { lojaDaPagina, ler, preco };
})();
