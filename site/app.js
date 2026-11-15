/* F&O Research Dashboard — single-page app reading ./data/*.json */
(() => {
  const DATA = 'data/';
  const S = { market: null, latest: [], bySym: {}, sectors: [], charts: [] };

  // ---------------------------------------------------------------- helpers
  const $ = (sel, el = document) => el.querySelector(sel);
  const esc = s => String(s ?? '').replace(/[&<>"']/g, c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));
  const css = v => getComputedStyle(document.documentElement).getPropertyValue(v).trim();
  const nf = (v, d = 2) => v == null || isNaN(v) ? '–' : Number(v).toLocaleString('en-IN', { minimumFractionDigits: d, maximumFractionDigits: d });
  const ni = v => v == null || isNaN(v) ? '–' : Math.round(v).toLocaleString('en-IN');
  const pct = (v, d = 2) => v == null || isNaN(v) ? '<span class="muted">–</span>'
    : `<span class="${v > 0 ? 'up' : v < 0 ? 'down' : ''}">${v > 0 ? '▲' : v < 0 ? '▼' : ''}${nf(Math.abs(v), d)}%</span>`;
  const mult = v => v == null ? '–' : nf(v, 1) + '×';
  const getJSON = async p => { const r = await fetch(DATA + p, { cache: 'no-cache' }); if (!r.ok) throw new Error(p + ' ' + r.status); return r.json(); };
  const fileSym = s => s.replace(/[^A-Za-z0-9_-]/g, '_');

  const TRENDS = ['Long Buildup', 'Short Buildup', 'Short Covering', 'Long Unwinding', 'Neutral'];
  const TREND_VAR = { 'Long Buildup': '--s1', 'Short Buildup': '--s2', 'Short Covering': '--s3', 'Long Unwinding': '--s4', 'Neutral': '--neutral' };
  const TREND_SYMBOL = { 'Long Buildup': 'circle', 'Short Buildup': 'triangle', 'Short Covering': 'diamond', 'Long Unwinding': 'rect', 'Neutral': 'emptyCircle' };
  const baseTrend = t => (t || '').replace('Agg. ', '');
  const trendColor = t => css(TREND_VAR[baseTrend(t)] || '--neutral');
  const trendBadge = t => t ? `<span class="badge"><span class="dot" style="background:${trendColor(t)}"></span>${esc(t)}</span>` : '<span class="muted">–</span>';

  // ---- watchlist (localStorage) ----
  const WL_KEY = 'fno_watchlist';
  const wlGet = () => { try { return JSON.parse(localStorage.getItem(WL_KEY) || '[]'); } catch (e) { return []; } };
  const wlSet = arr => { try { localStorage.setItem(WL_KEY, JSON.stringify(arr)); } catch (e) { } };
  const wlToggle = sym => { const a = wlGet(); const i = a.indexOf(sym); if (i >= 0) a.splice(i, 1); else a.push(sym); wlSet(a); };
  const wlHas = sym => wlGet().includes(sym);
  const starBtn = sym => `<button class="star${wlHas(sym) ? ' on' : ''}" data-wl="${esc(sym)}" title="${wlHas(sym) ? 'Remove from watchlist' : 'Add to watchlist'}">${wlHas(sym) ? '★' : '☆'}</button>`;

  // ---- ban list helper ----
  const isBanned = sym => (S.market.banned || []).includes(sym);
  const banBadge = sym => isBanned(sym) ? '<span class="ban-badge" title="F&amp;O ban: stock is in F&amp;O ban list (OI &gt; 95% of MWPL). No new positions allowed.">⛔ BAN</span>' : '';

  // ---- OI streak badge ----
  const streakBadge = r => {
    if (!r.oi_streak || r.oi_streak < 2) return '';
    const t = baseTrend(r.oi_trend);
    const abbr = { 'Long Buildup': 'LB', 'Short Buildup': 'SB', 'Short Covering': 'SC', 'Long Unwinding': 'LU', 'Neutral': 'N' }[t] || t.slice(0, 2);
    return `<span class="streak-badge" style="background:${trendColor(r.oi_trend)}22;color:${trendColor(r.oi_trend)};border:1px solid ${trendColor(r.oi_trend)}44" title="${t} for ${r.oi_streak} consecutive days">${abbr}×${r.oi_streak}</span>`;
  };

  // ---- tile tooltips ----
  const TILE_TIPS = {
    'Futures OI': 'Total open contracts in futures. Rising OI = new positions being created.',
    'OI value': 'Futures OI × CMP, in crore rupees. Proxy for institutional interest.',
    'PCR (OI)': 'Put/Call ratio by OI. >1.2 = more put OI = market hedged/bearish; <0.7 = complacency zone.',
    'Rollover': 'Share of OI beyond the near-month expiry. High = traders carried positions forward.',
    'Basis': 'Near-month future price minus spot, as %. Positive = contango (normal); negative = backwardation.',
    'Max pain': 'Strike where option sellers (writers) lose the least. Often acts as a magnet near expiry.',
    'Highest call OI': 'Strike with the highest call OI. Often acts as near-term resistance.',
    'Highest put OI': 'Strike with the highest put OI. Often acts as near-term support.',
    'Expiry': 'Days left to the near-month contract expiry.',
    'Volume': 'Today\'s volume vs its 20-day average. ≥2× = unusually active day.',
    'Delivery': 'Delivery % = shares delivered vs traded. High delivery + big move = conviction.',
    '1 week': 'Price return over the last 5 trading days.',
    '1 month': 'Price return over the last 21 trading days.',
    '3 months': 'Price return over the last 63 trading days.',
    '6 months': 'Price return over the last 126 trading days.',
    '1 year': 'Price return over the last 252 trading days.',
    'RSI (14)': 'Relative Strength Index over 14 days. >70 = overbought; <30 = oversold; 50 = neutral.',
    'Volatility (20D, ann.)': 'Realised (historical) volatility over 20 days, annualised. High = wider options premiums.',
    'Beta vs Nifty (120D)': 'Sensitivity to Nifty movement over 120 days. Beta 1.5 = moves ~1.5× Nifty.',
    'From 52W high': '% distance from the 52-week high. Negative means below the high.',
    'From 52W low': '% gain from the 52-week low.',
    '50 / 200-DMA': 'Whether price is above or below the 50-day and 200-day moving averages.',
  };

  function divColor(v, lim = 4) { // diverging: down(red) – gray – up(blue)
    const t = Math.max(-1, Math.min(1, (v || 0) / lim));
    const a = hex(css('--mid')), b = hex(t >= 0 ? css('--up') : css('--down'));
    const k = Math.abs(t);
    return `rgb(${a.map((x, i) => Math.round(x + (b[i] - x) * k)).join(',')})`;
  }
  function hex(h) { h = h.replace('#', ''); return [0, 2, 4].map(i => parseInt(h.substr(i, 2), 16)); }

  function chart(el, opt) {
    const c = echarts.init(el, null, { renderer: 'canvas' });
    const ink = css('--text-secondary'), grid = css('--border');
    c.setOption(Object.assign({
      textStyle: { color: ink, fontFamily: 'system-ui, sans-serif' },
      animation: false,
      grid: { left: 56, right: 16, top: 24, bottom: 40 },
    }, opt));
    S.charts.push(c);
    return c;
  }
  const axisStyle = () => ({ axisLine: { lineStyle: { color: css('--border') } }, axisLabel: { color: css('--text-secondary') }, splitLine: { lineStyle: { color: css('--border'), opacity: 0.6 } } });
  const tooltipStyle = () => ({ backgroundColor: css('--surface-1'), borderColor: css('--border'), textStyle: { color: css('--text-primary') } });
  window.addEventListener('resize', () => S.charts.forEach(c => c.resize()));

  // ---------------------------------------------------------------- boot
  async function boot() {
    const t = localStorage.getItem('theme'); if (t) document.documentElement.dataset.theme = t;
    else if (matchMedia('(prefers-color-scheme: dark)').matches) document.documentElement.dataset.theme = 'dark';
    $('#theme').onclick = () => { const d = document.documentElement; d.dataset.theme = d.dataset.theme === 'dark' ? 'light' : 'dark'; try { localStorage.setItem('theme', d.dataset.theme); } catch (e) { } route(); };
    try {
      [S.market, S.latest, S.sectors] = await Promise.all([getJSON('market.json'), getJSON('latest.json'), getJSON('sectors.json')]);
    } catch (e) {
      $('#app').innerHTML = `<div class="card">Could not load data (${esc(e.message)}). Run the pipeline first.</div>`; return;
    }
    S.latest.forEach(r => S.bySym[r.sym] = r);
    if (S.market.demo) $('#banner').innerHTML = '<div class="demo">DEMO DATA — prices, OI and history below are simulated for testing the layout. Not real market data.</div>';
    $('#symlist').innerHTML = S.latest.map(r => `<option value="${esc(r.sym)}">${esc(r.name)}</option>`).join('');
    $('#q').addEventListener('change', e => { const v = e.target.value.trim().toUpperCase(); const hit = S.bySym[v] || S.latest.find(r => r.name.toUpperCase().includes(v)); if (hit) { location.hash = '#/stock/' + encodeURIComponent(hit.sym); e.target.value = ''; } });
    window.addEventListener('hashchange', route);
    route();
  }

  function route() {
    S.charts.forEach(c => c.dispose()); S.charts = [];
    const [, page, arg] = (location.hash || '#/').split('/');
    document.querySelectorAll('nav a').forEach(a => a.classList.toggle('active', a.dataset.nav === (page || 'market')));
    const app = $('#app'); window.scrollTo(0, 0);
    if (page === 'stock' && arg) return stockPage(app, decodeURIComponent(arg));
    if (page === 'screener') return screenerPage(app);
    if (page === 'sectors') return sectorsPage(app);
    if (page === 'sector' && arg) return sectorPage(app, decodeURIComponent(arg));
    if (page === 'watchlist') return watchlistPage(app);
    if (page === 'expiry') return expiryPage(app);
    return marketPage(app);
  }

  // ---------------------------------------------------------------- market
  function marketPage(app) {
    const m = S.market, tc = m.trend_counts || {};
    const expiryNote = m.dte != null && m.dte <= 5
      ? `<div class="note" style="margin-top:6px">⚠ Expiry week: OI changes are distorted by rollover and expiry. Read OI trends with care.</div>` : '';
    app.innerHTML = `
      <div class="row spread"><div><h1>Market pulse</h1><div class="muted">${esc(m.date)} · ${m.n} F&amp;O stocks · ${m.n_days} days of history · source: ${m.source === 'nse' ? 'NSE files' : 'StockEdge CSV only'}</div></div></div>
      <div class="tiles" style="margin:14px 0">
        <div class="tile"><div class="k">Advances / declines</div><div class="v"><span class="up">${m.adv}</span> / <span class="down">${m.dec}</span></div></div>
        ${TRENDS.slice(0, 4).map(t => `<div class="tile"><div class="k"><span class="dot" style="background:${trendColor(t)}"></span> ${t}</div><div class="v">${tc[t] || 0}</div><div class="s">stocks</div></div>`).join('')}
        <div class="tile"><div class="k">Median PCR</div><div class="v">${nf(m.pcr_median)}</div></div>
        <div class="tile"><div class="k">Nearest expiry</div><div class="v">${m.expiry ? esc(m.expiry.slice(5)) : '–'}</div><div class="s">${m.dte != null ? m.dte + ' days left' : ''}</div></div>
      </div>${expiryNote}
      <div class="grid g2" style="margin-top:14px">
        <div class="card"><h2>Heatmap by sector</h2><div class="note">Box size = futures OI value · colour = today's price change</div><div id="tm" class="chart tall"></div>
          <div class="legend"><span><span class="dot" style="background:var(--down)"></span> ▼ falling</span><span><span class="dot" style="background:var(--mid);border:1px solid var(--border)"></span> flat</span><span><span class="dot" style="background:var(--up)"></span> ▲ rising</span></div></div>
        <div class="card"><h2>OI buildup map</h2><div class="note">Price change vs futures OI change. Click a dot to open the stock.</div><div id="sc" class="chart tall"></div>
          <div class="legend">${TRENDS.map(t => `<span><span class="dot" style="background:${trendColor(t)}"></span> ${t}</span>`).join('')}</div></div>
      </div>
      <div class="grid g4" style="margin-top:16px">${TRENDS.slice(0, 4).map(t => `<div class="card"><h2><span class="dot" style="background:${trendColor(t)}"></span> ${t}</h2><div id="top-${t.replace(/ /g, '')}"></div></div>`).join('')}</div>
      <div class="card" style="margin-top:16px"><h2>Sectors today</h2><div id="sectbl"></div></div>`;

    // treemap
    const sec = {};
    S.latest.forEach(r => { (sec[r.sector] = sec[r.sector] || []).push(r); });
    chart($('#tm'), {
      tooltip: { ...tooltipStyle(), formatter: p => p.data.sym ? `<b>${esc(p.data.sym)}</b> ${esc(p.data.full)}<br>Price ${pct(p.data.chg)} · OI ${pct(p.data.oi_chg)}<br>${esc(p.data.trend || '')}` : `<b>${esc(p.name)}</b>` },
      series: [{
        type: 'treemap', roam: false, nodeClick: false, breadcrumb: { show: false }, width: '100%', height: '100%', top: 0, left: 0,
        upperLabel: { show: true, height: 18, color: css('--text-primary'), fontSize: 11, formatter: '{b}' },
        levels: [{ itemStyle: { borderColor: css('--surface-1'), borderWidth: 2, gapWidth: 2 } }, { itemStyle: { borderColor: css('--surface-1'), borderWidth: 1, gapWidth: 1 } }],
        label: { color: css('--text-primary'), fontSize: 11, formatter: p => p.data.sym ? `${p.data.sym}\n${p.data.chg > 0 ? '+' : ''}${nf(p.data.chg, 1)}%` : p.name },
        data: Object.entries(sec).map(([s, rs]) => ({
          name: s, children: rs.map(r => ({ name: r.sym, sym: r.sym, full: r.name, chg: r.chg, oi_chg: r.oi_chg, trend: r.oi_trend, value: Math.max(r.oi_val_cr || 1, 1), itemStyle: { color: divColor(r.chg) } }))
        }))
      }]
    }).on('click', p => p.data?.sym && (location.hash = '#/stock/' + encodeURIComponent(p.data.sym)));

    // scatter
    const clip = (v, l) => Math.max(-l, Math.min(l, v ?? 0));
    chart($('#sc'), {
      grid: { left: 50, right: 20, top: 34, bottom: 44 },
      tooltip: { ...tooltipStyle(), formatter: p => `<b>${esc(p.data.sym)}</b><br>Price ${pct(p.data.chg)} · OI ${pct(p.data.oi)}<br>${esc(p.data.trend || '')}` },
      xAxis: { name: 'Price change %', nameLocation: 'middle', nameGap: 26, ...axisStyle(), max: 8, min: -8 },
      yAxis: { name: 'OI change %', nameGap: 14, ...axisStyle(), max: 30, min: -30 },
      series: TRENDS.map(t => ({
        type: 'scatter', name: t, symbol: TREND_SYMBOL[t], symbolSize: 9,
        itemStyle: { color: trendColor(t), borderColor: css('--surface-1'), borderWidth: 1 },
        data: S.latest.filter(r => baseTrend(r.oi_trend) === t).map(r => ({ value: [clip(r.chg, 8), clip(r.oi_chg, 30)], sym: r.sym, chg: r.chg, oi: r.oi_chg, trend: r.oi_trend })),
        markLine: t === 'Long Buildup' ? { silent: true, symbol: 'none', lineStyle: { color: css('--text-muted'), type: 'dashed' }, label: { show: false }, data: [{ xAxis: 0 }, { yAxis: 0 }] } : undefined
      }))
    }).on('click', p => p.data?.sym && (location.hash = '#/stock/' + encodeURIComponent(p.data.sym)));

    TRENDS.slice(0, 4).forEach(t => {
      const rows = S.latest.filter(r => baseTrend(r.oi_trend) === t).sort((a, b) => Math.abs(b.oi_chg) - Math.abs(a.oi_chg)).slice(0, 8);
      $('#top-' + t.replace(/ /g, '')).innerHTML = rows.length ? `<table><thead><tr><th>Stock</th><th>Price</th><th>OI</th><th>Vol</th></tr></thead><tbody>${rows.map(r => `<tr><td><a href="#/stock/${encodeURIComponent(r.sym)}">${esc(r.sym)}</a></td><td>${pct(r.chg)}</td><td>${pct(r.oi_chg)}</td><td>${mult(r.vol_mult)}</td></tr>`).join('')}</tbody></table>` : '<div class="muted">None today</div>';
    });
    sectorTable($('#sectbl'));
  }

  function sectorTable(el) {
    const rows = S.sectors;
    const lg = `<div class="legend" style="margin-bottom:6px">OI trend counts: ${TRENDS.slice(0, 4).map(t => `<span><span class="dot" style="background:${trendColor(t)}"></span> ${t}</span>`).join('')}</div>`;
    el.innerHTML = lg + `<div class="tablewrap"><table><thead><tr><th>Sector</th><th>Stocks</th><th>Avg price chg</th><th>Up / down</th><th>Avg OI chg</th><th>1 week</th><th>1 month</th><th>% above 50-DMA</th><th>Median PCR</th><th class="l">OI trends</th></tr></thead><tbody>
      ${rows.map(s => `<tr><td><a href="#/sector/${encodeURIComponent(s.sector)}">${esc(s.sector)}</a></td><td>${s.n}</td><td>${pct(s.chg)}</td><td><span class="up">${s.adv}</span> / <span class="down">${s.dec}</span></td><td>${pct(s.oi_chg)}</td><td>${pct(s.r_1w)}</td><td>${pct(s.r_1m)}</td><td>${s.above_sma50 == null ? '–' : nf(s.above_sma50, 0) + '%'}</td><td>${nf(s.pcr)}</td>
      <td class="l">${TRENDS.slice(0, 4).filter(t => s.trends[t]).map(t => `<span class="chip" title="${t}"><span class="dot" style="background:${trendColor(t)}"></span> ${s.trends[t]}</span>`).join('')}</td></tr>`).join('')}</tbody></table></div>`;
  }

  // ---------------------------------------------------------------- screener
  const COLS = [
    ['sym', 'Stock', r => `<a href="#/stock/${encodeURIComponent(r.sym)}">${esc(r.sym)}</a>${banBadge(r.sym)}`, 'l'],
    ['_wl', '★', r => starBtn(r.sym), 'l'],
    ['sector', 'Sector', r => esc(r.sector), 'l'],
    ['close', 'Close', r => nf(r.close)], ['chg', 'Chg', r => pct(r.chg)],
    ['oi_chg', 'OI chg', r => pct(r.oi_chg)],
    ['oi_trend', 'OI trend', r => `${trendBadge(r.oi_trend)}${streakBadge(r)}`, 'l'],
    ['se_oi_trend', 'StockEdge trend', r => esc(r.se_oi_trend || '–'), 'l'],
    ['pcr', 'PCR', r => nf(r.pcr)], ['vol_mult', 'Vol ×', r => mult(r.vol_mult)],
    ['deliv_pct', 'Deliv %', r => r.deliv_pct == null ? '–' : nf(r.deliv_pct, 1)], ['deliv_mult', 'Deliv ×', r => mult(r.deliv_mult)],
    ['roll', 'Rollover %', r => r.roll == null ? '–' : nf(r.roll, 1)], ['basis_pct', 'Basis %', r => nf(r.basis_pct)],
    ['r_1w', '1W', r => pct(r.r_1w, 1)], ['r_1m', '1M', r => pct(r.r_1m, 1)], ['r_3m', '3M', r => pct(r.r_3m, 1)], ['r_1y', '1Y', r => pct(r.r_1y, 1)],
    ['rsi', 'RSI', r => nf(r.rsi, 0)], ['rv20', 'Vol 20D %', r => nf(r.rv20, 0)], ['beta', 'Beta', r => nf(r.beta)],
    ['dist_hi52', 'From 52W high', r => pct(r.dist_hi52, 1)],
  ];

  function screenerPage(app, preset = {}) {
    const secs = [...new Set(S.latest.map(r => r.sector))].sort();
    app.innerHTML = `<h1>Screener</h1><div class="muted" style="margin-bottom:10px">All F&amp;O stocks on ${esc(S.market.date)}. Click a column to sort.</div>
      <div class="filters">
        <input id="f-q" placeholder="Filter by name…">
        <select id="f-sec"><option value="">All sectors</option>${secs.map(s => `<option ${preset.sector === s ? 'selected' : ''}>${esc(s)}</option>`).join('')}</select>
        <select id="f-tr"><option value="">All OI trends</option>${TRENDS.map(t => `<option>${t}</option>`).join('')}</select>
        <button data-f="sma50">Above 50-DMA</button><button data-f="vol">Volume ≥ 2×</button><button data-f="deliv">Delivery ≥ 1.5×</button><button data-f="agg">Aggressive only</button><button data-f="ban">⛔ Ban list</button><button data-f="wl">★ Watchlist</button>
        <span class="muted" id="f-n"></span><button id="f-csv">Download CSV</button>
      </div><div class="card"><div class="tablewrap" id="tbl"></div></div>`;
    const st = { sort: 'oi_chg', dir: -1, on: {} };
    const draw = () => {
      const q = $('#f-q').value.toLowerCase(), sec = $('#f-sec').value, tr = $('#f-tr').value;
      let rows = S.latest.filter(r => (!q || (r.sym + ' ' + r.name).toLowerCase().includes(q)) && (!sec || r.sector === sec) && (!tr || baseTrend(r.oi_trend) === tr)
        && (!st.on.sma50 || r.above_sma50) && (!st.on.vol || r.vol_mult >= 2) && (!st.on.deliv || r.deliv_mult >= 1.5) && (!st.on.agg || (r.oi_trend || '').startsWith('Agg'))
        && (!st.on.ban || isBanned(r.sym)) && (!st.on.wl || wlHas(r.sym)));
      rows.sort((a, b) => { const x = a[st.sort], y = b[st.sort]; if (x == null) return 1; if (y == null) return -1; return (x > y ? 1 : x < y ? -1 : 0) * st.dir; });
      S.view = rows;
      $('#f-n').textContent = rows.length + ' stocks';
      $('#tbl').innerHTML = `<table><thead><tr>${COLS.map(c => `<th class="${c[3] || ''}" data-k="${c[0]}">${c[1]}${st.sort === c[0] ? (st.dir > 0 ? ' ↑' : ' ↓') : ''}</th>`).join('')}</tr></thead><tbody>${rows.map(r => `<tr>${COLS.map(c => `<td class="${c[3] || ''}">${c[2](r)}</td>`).join('')}</tr>`).join('')}</tbody></table>`;
      $('#tbl').querySelectorAll('th[data-k]:not([data-k="_wl"])').forEach(th => th.onclick = () => { const k = th.dataset.k; st.dir = st.sort === k ? -st.dir : -1; st.sort = k; draw(); });
      // wire up star buttons in table
      $('#tbl').querySelectorAll('[data-wl]').forEach(btn => btn.onclick = (e) => {
        e.preventDefault(); wlToggle(btn.dataset.wl); draw(); // redraw to update star state
      });
    };
    ['f-q', 'f-sec', 'f-tr'].forEach(id => $('#' + id).addEventListener('input', draw));
    app.querySelectorAll('[data-f]').forEach(b => b.onclick = () => { st.on[b.dataset.f] = !st.on[b.dataset.f]; b.classList.toggle('on'); draw(); });
    $('#f-csv').onclick = () => {
      const keys = COLS.map(c => c[0]).concat(['name', 'industry', 'fut_oi', 'max_pain', 'top_ce', 'top_pe', 'dte']);
      const csv = [keys.join(',')].concat(S.view.map(r => keys.map(k => JSON.stringify(r[k] ?? '')).join(','))).join('\n');
      const a = document.createElement('a'); a.href = URL.createObjectURL(new Blob([csv], { type: 'text/csv' })); a.download = `fno_screener_${S.market.date}.csv`; a.click();
    };
    draw();
  }

  // ---------------------------------------------------------------- sectors
  function sectorsPage(app) {
    app.innerHTML = `<h1>Sectors</h1><div class="grid g2" style="margin-top:12px"><div class="card"><h2>Average price change today</h2><div id="sb" class="chart tall"></div></div>
      <div class="card"><h2>1-month vs 1-week return</h2><div class="note">Top-right = strong and still rising; bottom-left = weak and still falling</div><div id="rr" class="chart tall"></div></div></div>
      <div class="card" style="margin-top:16px"><div id="sectbl"></div></div>`;
    const rows = [...S.sectors].sort((a, b) => (a.chg ?? 0) - (b.chg ?? 0));
    chart($('#sb'), {
      grid: { left: 170, right: 30, top: 10, bottom: 30 }, tooltip: { ...tooltipStyle(), trigger: 'axis', axisPointer: { type: 'shadow' } },
      xAxis: { type: 'value', ...axisStyle(), axisLabel: { formatter: '{value}%', color: css('--text-secondary') } },
      yAxis: { type: 'category', data: rows.map(r => r.sector), ...axisStyle(), axisLabel: { color: css('--text-secondary'), fontSize: 11, interval: 0 } },
      series: [{ type: 'bar', barWidth: '60%', data: rows.map(r => ({ value: r.chg, itemStyle: { color: (r.chg ?? 0) >= 0 ? css('--up') : css('--down'), borderRadius: (r.chg ?? 0) >= 0 ? [0, 4, 4, 0] : [4, 0, 0, 4] } })) }]
    }).on('click', p => location.hash = '#/sector/' + encodeURIComponent(p.name));
    chart($('#rr'), {
      grid: { left: 50, right: 20, top: 34, bottom: 44 },
      tooltip: { ...tooltipStyle(), formatter: p => `<b>${esc(p.data.name)}</b><br>1M ${pct(p.data.value[0])} · 1W ${pct(p.data.value[1])}` },
      xAxis: { name: '1-month return %', nameLocation: 'middle', nameGap: 26, ...axisStyle() }, yAxis: { name: '1-week return %', nameGap: 14, ...axisStyle() },
      series: [{ type: 'scatter', symbolSize: 8, labelLayout: { hideOverlap: true }, itemStyle: { color: css('--s1'), borderColor: css('--surface-1'), borderWidth: 1 },
        label: { show: true, position: 'right', fontSize: 10, color: css('--text-secondary'), formatter: p => p.data.name.split(' ')[0] },
        data: S.sectors.filter(s => s.r_1m != null).map(s => ({ name: s.sector, value: [s.r_1m, s.r_1w] })),
        markLine: { silent: true, symbol: 'none', lineStyle: { color: css('--text-muted'), type: 'dashed' }, label: { show: false }, data: [{ xAxis: 0 }, { yAxis: 0 }] } }]
    }).on('click', p => location.hash = '#/sector/' + encodeURIComponent(p.data.name));
    sectorTable($('#sectbl'));
  }

  function sectorPage(app, name) {
    const s = S.sectors.find(x => x.sector === name);
    if (!s) { app.innerHTML = '<div class="card">Sector not found.</div>'; return; }
    screenerPage(app, { sector: name });
    $('h1').textContent = name;
    $('#f-sec').value = name; $('#f-sec').dispatchEvent(new Event('input'));
  }

  // ---------------------------------------------------------------- stock
  async function stockPage(app, sym) {
    const r = S.bySym[sym];
    if (!r) { app.innerHTML = `<div class="card">${esc(sym)} is not in the F&amp;O list for ${esc(S.market.date)}.</div>`; return; }
    app.innerHTML = `<p class="muted pad">Loading ${esc(sym)}…</p>`;
    let h = null, vc = null, prof = null, news = null;
    try { h = await getJSON('history/' + fileSym(sym) + '.json'); } catch (e) { }
    if ((S.market.valuechain || []).includes(sym)) { try { vc = await getJSON('valuechain/' + fileSym(sym) + '.json'); } catch (e) { } }
    try { prof = await getJSON('profiles/' + fileSym(sym) + '.json'); } catch (e) { }
    try { news = await getJSON('news/' + fileSym(sym) + '.json'); } catch (e) { }
    const se = r.se_oi_trend ? `<span class="muted">StockEdge:</span> ${esc(r.se_oi_trend)}` : '';
    const banned = isBanned(sym);
    const links = [
      ['NSE', `https://www.nseindia.com/get-quotes/derivatives?symbol=${encodeURIComponent(sym)}`],
      ['Screener.in', `https://www.screener.in/company/${encodeURIComponent(sym)}/consolidated/`],
      ['StockEdge', `https://web.stockedge.com/app/markets`],
      ['TradingView', `https://www.tradingview.com/chart/?symbol=NSE:${encodeURIComponent(sym)}`],
    ];
    const tile = (k, v, s = '') => { const tip = TILE_TIPS[k]; return `<div class="tile"${tip ? ` title="${esc(tip)}"` : ''}><div class="k">${k}${tip ? ' <span class="tip-icon">?</span>' : ''}</div><div class="v">${v}</div>${s ? `<div class="s">${s}</div>` : ''}</div>`; };
    app.innerHTML = `
      <div class="row spread"><div>
        <div class="muted"><a href="#/sector/${encodeURIComponent(r.sector)}">${esc(r.sector)}</a> · ${esc(r.industry || '')} · ${esc(r.mcap_cat || '')} · lot ${ni(r.lot)}</div>
        <h1>${esc(r.name)} <span class="muted" style="font-weight:400">${esc(sym)}</span> ${starBtn(sym)}</h1>
        ${banned ? `<div class="ban-warn">⛔ <b>F&amp;O Ban:</b> This stock is on the NSE F&amp;O ban list (OI exceeded 95% of MWPL). No new positions may be opened. Existing positions can be squared off only.</div>` : ''}
        <div class="row">${streakBadge(r)}<span style="font-size:24px;font-weight:600">₹${nf(r.close)}</span> ${pct(r.chg)} ${trendBadge(r.oi_trend)} ${se}</div>
      </div><div class="row">${links.map(([t, u]) => `<a class="chip" href="${u}" target="_blank" rel="noopener">${t} ↗</a>`).join('')}</div></div>

      <h2 style="margin-top:18px">Derivatives</h2>
      <div class="tiles">
        ${tile('Futures OI', ni(r.fut_oi), `OI chg ${pct(r.oi_chg)}`)}
        ${tile('OI value', r.oi_val_cr == null ? '–' : '₹' + nf(r.oi_val_cr, 0) + ' Cr')}
        ${tile('PCR (OI)', nf(r.pcr), r.pcr_chg == null ? '' : `1-day ${r.pcr_chg > 0 ? '+' : ''}${nf(r.pcr_chg)}`)}
        ${tile('Rollover', r.roll == null ? '–' : nf(r.roll, 1) + '%', 'share of OI beyond near month')}
        ${tile('Basis', r.basis_pct == null ? '–' : nf(r.basis_pct) + '%', 'near future vs spot')}
        ${tile('Max pain', r.max_pain == null ? '–' : nf(r.max_pain, 0), 'near expiry')}
        ${tile('Highest call OI', r.top_ce == null ? '–' : nf(r.top_ce, 0), 'possible resistance')}
        ${tile('Highest put OI', r.top_pe == null ? '–' : nf(r.top_pe, 0), 'possible support')}
        ${tile('Expiry', r.expiry ? esc(r.expiry) : '–', r.dte == null ? '' : r.dte + ' days left')}
        ${tile('Volume', mult(r.vol_mult), 'vs 20-day average')}
        ${tile('Delivery', r.deliv_pct == null ? '–' : nf(r.deliv_pct, 1) + '%', `${mult(r.deliv_mult)} vs 20-day avg`)}
      </div>

      <h2 style="margin-top:18px">Price and statistics</h2>
      <div class="tiles">
        ${tile('1 week', pct(r.r_1w, 1))}${tile('1 month', pct(r.r_1m, 1), r.rs_1m == null ? '' : `vs Nifty ${r.rs_1m > 0 ? '+' : ''}${nf(r.rs_1m, 1)} pts`)}${tile('3 months', pct(r.r_3m, 1))}${tile('6 months', pct(r.r_6m, 1))}${tile('1 year', pct(r.r_1y, 1))}
        ${tile('RSI (14)', nf(r.rsi, 0), r.rsi == null ? '' : r.rsi >= 70 ? 'overbought zone' : r.rsi <= 30 ? 'oversold zone' : 'neutral zone')}
        ${tile('Volatility (20D, ann.)', r.rv20 == null ? '–' : nf(r.rv20, 0) + '%')}
        ${tile('Beta vs Nifty (120D)', nf(r.beta))}
        ${tile('From 52W high', pct(r.dist_hi52, 1))}${tile('From 52W low', pct(r.dist_lo52, 1))}
        ${tile('50 / 200-DMA', `${r.above_sma50 == null ? '–' : r.above_sma50 ? 'Above' : 'Below'} / ${r.above_sma200 == null ? '–' : r.above_sma200 ? 'Above' : 'Below'}`)}
      </div>
      ${r.hi52 != null && r.lo52 != null ? `<div class="card" style="margin-top:12px;padding:12px 16px">
        <div style="display:flex;justify-content:space-between;font-size:12px;color:var(--text-secondary);margin-bottom:4px">
          <span>52W Low ₹${nf(r.lo52)}</span><span style="font-weight:600;color:var(--text-primary)">₹${nf(r.close)}</span><span>52W High ₹${nf(r.hi52)}</span>
        </div>
        <div class="range-bar"><div class="range-fill" style="left:0;width:${((r.close - r.lo52) / (r.hi52 - r.lo52) * 100).toFixed(1)}%"></div><div class="range-thumb" style="left:${((r.close - r.lo52) / (r.hi52 - r.lo52) * 100).toFixed(1)}%"></div></div>
        <div style="font-size:11px;color:var(--text-muted);margin-top:5px">Current price sits at ${((r.close - r.lo52) / (r.hi52 - r.lo52) * 100).toFixed(0)}% of the 52-week range</div>
      </div>` : ''}

      ${h ? `<div class="card" style="margin-top:16px"><div class="row spread"><h2>Price</h2><div class="row" id="rng">${['3M', '6M', '1Y', 'All'].map((x, i) => `<button data-r="${x}" class="${i === 1 ? 'on' : ''}">${x}</button>`).join('')}</div></div><div id="c-price" class="chart"></div></div>
      <div class="grid g2" style="margin-top:16px">
        <div class="card"><h2>Futures open interest</h2><div class="note">Bar colour = that day's OI trend</div><div id="c-oi" class="chart short"></div></div>
        <div class="card"><h2>Put-call ratio (OI)</h2><div id="c-pcr" class="chart short"></div></div>
        <div class="card"><h2>Delivery %</h2><div id="c-del" class="chart short"></div></div>
        <div class="card"><h2>Rollover %</h2><div class="note">Share of futures OI in next and far months</div><div id="c-roll" class="chart short"></div></div>
      </div>` : '<div class="placeholder" style="margin-top:16px">No price history yet. It builds up as the daily pipeline runs.</div>'}

      <h2 style="margin-top:22px">Goods and services</h2>
      <div id="vc"></div>

      <div id="sec-profile"></div>
      <div id="sec-news"></div>
      <div id="sec-macro"></div>
      <div class="placeholder" style="margin-top:16px"><b>Financials</b> — 10 years + quarters: margins, ROCE/ROE, cash flow, debt, valuation band. Coming soon.</div>`;
    if (h) stockCharts(h);
    renderVC($('#vc'), vc, sym);
    renderProfile($('#sec-profile'), prof, r);
    renderNews($('#sec-news'), news, sym);
    renderMacro($('#sec-macro'), prof);
    // watchlist star interaction
    app.querySelectorAll('[data-wl]').forEach(btn => btn.onclick = (e) => {
      e.preventDefault(); wlToggle(btn.dataset.wl);
      btn.textContent = wlHas(btn.dataset.wl) ? '★' : '☆';
      btn.classList.toggle('on', wlHas(btn.dataset.wl));
      btn.title = wlHas(btn.dataset.wl) ? 'Remove from watchlist' : 'Add to watchlist';
    });
  }

  function stockCharts(h) {
    const n = h.dates.length;
    const ts = (i0) => h.dates.slice(i0);
    const line = (name, arr, i0, color, w = 2, dash) => ({ type: 'line', name, data: arr ? arr.slice(i0) : [], showSymbol: false, lineStyle: { width: w, color, type: dash || 'solid' }, itemStyle: { color }, connectNulls: true });
    const base = (i0) => ({
      tooltip: { ...tooltipStyle(), trigger: 'axis', axisPointer: { type: 'cross', label: { backgroundColor: css('--text-secondary') } } },
      xAxis: { type: 'category', data: ts(i0), ...axisStyle(), axisLabel: { color: css('--text-secondary'), hideOverlap: true } },
      yAxis: { type: 'value', scale: true, ...axisStyle() },
    });
    let price;
    const drawPrice = (r) => {
      const i0 = r === 'All' ? 0 : Math.max(0, n - { '3M': 63, '6M': 126, '1Y': 252 }[r]);
      const opt = { ...base(i0), legend: { top: 0, textStyle: { color: css('--text-secondary') } }, grid: { left: 64, right: 16, top: 30, bottom: 30 },
        series: [line('Close', h.close, i0, css('--s1')), line('50-DMA', h.sma50, i0, css('--s2'), 1.5), line('200-DMA', h.sma200, i0, css('--s3'), 1.5)] };
      if (price) price.setOption(opt, true); else price = chart($('#c-price'), opt);
    };
    drawPrice('6M');
    $('#rng').querySelectorAll('button').forEach(b => b.onclick = () => { $('#rng').querySelectorAll('button').forEach(x => x.classList.remove('on')); b.classList.add('on'); drawPrice(b.dataset.r); });
    const i0 = Math.max(0, n - 126);
    chart($('#c-oi'), { ...base(i0), grid: { left: 70, right: 10, top: 10, bottom: 30 },
      series: [{ type: 'bar', name: 'Futures OI', data: (h.fut_oi || []).slice(i0).map((v, k) => ({ value: v, itemStyle: { color: trendColor((h.oi_trend || [])[i0 + k]), borderRadius: [3, 3, 0, 0] } })) }],
      yAxis: { type: 'value', scale: true, ...axisStyle(), axisLabel: { color: css('--text-secondary'), formatter: v => v >= 1e7 ? (v / 1e7).toFixed(1) + 'Cr' : v >= 1e5 ? (v / 1e5).toFixed(1) + 'L' : v } } });
    chart($('#c-pcr'), { ...base(i0), grid: { left: 44, right: 10, top: 10, bottom: 30 }, series: [line('PCR', h.pcr, i0, css('--s1'))] });
    chart($('#c-del'), { ...base(i0), grid: { left: 44, right: 10, top: 10, bottom: 30 }, yAxis: { type: 'value', ...axisStyle(), max: 100 },
      series: [{ type: 'bar', name: 'Delivery %', data: (h.deliv_pct || []).slice(i0), itemStyle: { color: css('--s1'), borderRadius: [3, 3, 0, 0] } }] });
    chart($('#c-roll'), { ...base(i0), grid: { left: 44, right: 10, top: 10, bottom: 30 }, yAxis: { type: 'value', ...axisStyle(), max: 100 }, series: [line('Rollover %', h.roll, i0, css('--s1'))] });
  }

  // ---------------------------------------------------------------- value chain
  function renderVC(el, vc, sym) {
    if (!vc) {
      el.innerHTML = `<div class="placeholder">No breakdown yet for ${esc(sym)}. Each stock gets an inputs (raw materials and services used) and outputs (products and services sold) tree, with the price driver to watch and links to the F&amp;O stocks that supply or buy from it.</div>`;
      return;
    }
    const node = (x) => {
      const id = 'n' + Math.random().toString(36).slice(2);
      const meta = [x.weight ? `Weight: ${esc(x.weight)}` : '', x.driver ? `Price driver: ${esc(x.driver)}` : ''].filter(Boolean).join(' · ');
      const chips = (x.fno || []).map(s => S.bySym[s] ? `<a class="chip" href="#/stock/${encodeURIComponent(s)}">${esc(s)} ${S.bySym[s].chg != null ? (S.bySym[s].chg > 0 ? '▲' : '▼') + nf(Math.abs(S.bySym[s].chg), 1) + '%' : ''}</a>` : `<span class="chip">${esc(s)}</span>`).join('')
        + (x.other || []).map(s => `<span class="chip" title="Not in the F&amp;O list">${esc(s)}</span>`).join('');
      const kids = x.children ? `<ul id="${id}" hidden>${x.children.map(node).join('')}</ul>` : '';
      return `<li><span class="node" ${x.children ? `data-t="${id}"` : ''}>${x.children ? '▸ ' : ''}${esc(x.name)}</span>${meta ? `<div class="meta">${meta}</div>` : ''}${chips ? `<div class="meta">${chips}</div>` : ''}${kids}</li>`;
    };
    el.innerHTML = `<div class="card">${vc.status === 'draft' ? `<div class="note" style="margin-bottom:8px">Draft: ${esc(vc.note || '')}</div>` : ''}
      <div class="vc"><div><h2>Inputs: raw materials and services used</h2><ul>${vc.inputs.map(node).join('')}</ul></div>
      <div><h2>Outputs: products and services sold</h2><ul>${vc.outputs.map(node).join('')}</ul></div></div>
      <div class="note">Chips are linked companies; F&amp;O stocks show today's move. Click an item with ▸ to open it.</div></div>`;
    el.querySelectorAll('[data-t]').forEach(n => n.onclick = () => { const u = document.getElementById(n.dataset.t); u.hidden = !u.hidden; n.textContent = (u.hidden ? '▸ ' : '▾ ') + n.textContent.slice(2); });
  }

  // ---------------------------------------------------------------- business profile
  function renderProfile(el, prof, r) {
    if (!prof) {
      el.innerHTML = `<h2 style="margin-top:22px">Business profile</h2><div class="placeholder">Profile data not yet available. Run the pipeline to generate it.</div>`;
      return;
    }
    const seg = (prof.segments || []).map(s =>
      `<div class="tile"><div class="k">${esc(s.name)}</div><div class="v">${s.pct_rev != null ? nf(s.pct_rev, 0) + '%' : '—'}</div><div class="s">${esc(s.note || '')}</div></div>`
    ).join('');
    const drivers = (prof.earnings_drivers || []).map(d => `<li>${esc(d)}</li>`).join('');
    el.innerHTML = `
      <h2 style="margin-top:22px">Business profile</h2>
      <div class="card">
        <p style="margin:0 0 12px">${esc(prof.what || '')}</p>
        ${seg ? `<h3 style="margin:0 0 8px;font-size:13px;text-transform:uppercase;letter-spacing:.05em;color:var(--text-secondary)">Segments</h3><div class="tiles">${seg}</div>` : ''}
        ${drivers ? `<h3 style="margin:12px 0 6px;font-size:13px;text-transform:uppercase;letter-spacing:.05em;color:var(--text-secondary)">Key earnings drivers</h3><ul style="margin:0;padding-left:20px;line-height:1.7">${drivers}</ul>` : ''}
        <div class="note" style="margin-top:10px">Source: pipeline-generated draft. Verify against latest annual report and earnings call.</div>
      </div>`;
  }

  // ---------------------------------------------------------------- news / filings
  function renderNews(el, news, sym) {
    if (!news || !news.items || news.items.length === 0) {
      el.innerHTML = `<h2 style="margin-top:22px">News and filings</h2>
        <div class="placeholder">No recent NSE announcements fetched yet.
          <div style="margin-top:8px">
            <a class="chip" href="https://www.nseindia.com/companies-listing/corporate-filings-announcements?symbol=${encodeURIComponent(sym)}" target="_blank" rel="noopener">NSE Announcements ↗</a>
            <a class="chip" href="https://www.screener.in/company/${encodeURIComponent(sym)}/consolidated/#documents" target="_blank" rel="noopener">Screener.in filings ↗</a>
          </div>
        </div>`;
      return;
    }
    const rows = news.items.slice(0, 15).map(item => {
      const badge = item.category ? `<span class="chip" style="font-size:11px">${esc(item.category)}</span>` : '';
      return `<div style="padding:8px 0;border-bottom:1px solid var(--border)">
        <div style="display:flex;align-items:center;gap:6px;flex-wrap:wrap">
          ${badge}
          <span class="muted" style="font-size:12px">${esc(item.date || '')}</span>
        </div>
        <div style="margin-top:3px">${item.url ? `<a href="${esc(item.url)}" target="_blank" rel="noopener" style="color:inherit">${esc(item.title)}</a>` : esc(item.title)}</div>
      </div>`;
    }).join('');
    el.innerHTML = `<h2 style="margin-top:22px">News and filings</h2>
      <div class="card">
        <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:4px">
          <span class="muted">Last fetched: ${esc(news.fetched_on || 'unknown')}</span>
          <a class="chip" href="https://www.nseindia.com/companies-listing/corporate-filings-announcements?symbol=${encodeURIComponent(sym)}" target="_blank" rel="noopener">All NSE filings ↗</a>
        </div>
        ${rows}
      </div>`;
  }

  // ---------------------------------------------------------------- macro sensitivity
  function renderMacro(el, prof) {
    if (!prof || !prof.macro_sensitivity || prof.macro_sensitivity.length === 0) {
      el.innerHTML = `<h2 style="margin-top:22px">Macro sensitivity</h2><div class="placeholder">Macro sensitivity data not yet available.</div>`;
      return;
    }
    const dirColor = { positive: 'var(--up)', negative: 'var(--down)', mixed: 'var(--text-secondary)' };
    const dirIcon  = { positive: '▲', negative: '▼', mixed: '↔' };
    const rows = prof.macro_sensitivity.map(m => {
      const col = dirColor[m.direction] || 'var(--text-secondary)';
      const icon = dirIcon[m.direction] || '↔';
      return `<div class="tile">
        <div class="k">${esc(m.factor)}</div>
        <div class="v" style="color:${col}">${icon} ${esc(m.direction || '')}</div>
        ${m.note ? `<div class="s">${esc(m.note)}</div>` : ''}
      </div>`;
    }).join('');
    el.innerHTML = `<h2 style="margin-top:22px">Macro sensitivity</h2>
      <div class="card">
        <div class="note" style="margin-bottom:10px">How key macro factors affect this stock's earnings. ▲ = higher factor is positive for earnings; ▼ = negative.</div>
        <div class="tiles">${rows}</div>
      </div>`;
  }

  // ---------------------------------------------------------------- watchlist page
  function watchlistPage(app) {
    const wl = wlGet();
    if (wl.length === 0) {
      app.innerHTML = `<h1>★ Watchlist</h1><div class="card"><p class="muted" style="margin:0">Your watchlist is empty. Click the ☆ star on any stock to add it here.</p></div>`;
      return;
    }
    const rows = wl.map(sym => S.bySym[sym]).filter(Boolean);
    const missing = wl.filter(sym => !S.bySym[sym]);
    app.innerHTML = `<h1>★ Watchlist</h1><div class="muted" style="margin-bottom:10px">${rows.length} stocks · saved in your browser · ${esc(S.market.date)}</div>
      <div class="card"><div class="tablewrap" id="wl-tbl"></div></div>
      ${missing.length ? `<div class="note" style="margin-top:8px">Not in today's F&amp;O list: ${missing.map(esc).join(', ')}</div>` : ''}`;
    const cols = [
      ['sym', 'Stock', r => `<a href="#/stock/${encodeURIComponent(r.sym)}">${esc(r.sym)}</a>${banBadge(r.sym)}`, 'l'],
      ['_rm', '✕', r => `<button class="star on" data-wl="${esc(r.sym)}" title="Remove from watchlist" style="color:var(--down)">✕</button>`, 'l'],
      ['close', 'Close', r => nf(r.close)], ['chg', 'Chg', r => pct(r.chg)],
      ['oi_chg', 'OI chg', r => pct(r.oi_chg)],
      ['oi_trend', 'OI trend', r => `${trendBadge(r.oi_trend)}${streakBadge(r)}`, 'l'],
      ['pcr', 'PCR', r => nf(r.pcr)], ['vol_mult', 'Vol ×', r => mult(r.vol_mult)],
      ['roll', 'Rollover %', r => r.roll == null ? '–' : nf(r.roll, 1)],
      ['r_1w', '1W', r => pct(r.r_1w, 1)], ['r_1m', '1M', r => pct(r.r_1m, 1)],
      ['rsi', 'RSI', r => nf(r.rsi, 0)], ['dist_hi52', 'From 52W high', r => pct(r.dist_hi52, 1)],
    ];
    const redraw = () => {
      const wlNow = wlGet();
      const rr = wlNow.map(s => S.bySym[s]).filter(Boolean);
      $('#wl-tbl').innerHTML = `<table><thead><tr>${cols.map(c => `<th class="${c[3] || ''}">${c[1]}</th>`).join('')}</tr></thead><tbody>${rr.map(r => `<tr>${cols.map(c => `<td class="${c[3] || ''}">${c[2](r)}</td>`).join('')}</tr>`).join('')}</tbody></table>`;
      $('#wl-tbl').querySelectorAll('[data-wl]').forEach(btn => btn.onclick = (e) => { e.preventDefault(); wlToggle(btn.dataset.wl); redraw(); });
      if (wlNow.length === 0) watchlistPage(app);
    };
    redraw();
  }

  // ---------------------------------------------------------------- expiry / rollover cross-section
  function expiryPage(app) {
    const rows = S.latest.filter(r => r.roll != null).slice();
    // sector median rollover
    const secMed = {};
    S.sectors.forEach(s => { secMed[s.sector] = s.syms ? (() => { const vals = s.syms.map(sym => S.bySym[sym]?.roll).filter(v => v != null); vals.sort((a, b) => a - b); const m = Math.floor(vals.length / 2); return vals.length ? (vals.length % 2 ? vals[m] : (vals[m - 1] + vals[m]) / 2) : null; })() : null; });
    rows.sort((a, b) => (b.roll || 0) - (a.roll || 0));
    const allRolls = rows.map(r => r.roll);
    const p75 = allRolls[Math.floor(allRolls.length * 0.25)]; // sorted desc so 25% from top = 75th pctile
    const p25 = allRolls[Math.floor(allRolls.length * 0.75)];
    const expiryDate = S.market.expiry || '–';
    const dte = S.market.dte;
    app.innerHTML = `<h1>Expiry: Rollover cross-section</h1>
      <div class="muted" style="margin-bottom:10px">Near expiry: ${esc(expiryDate)}${dte != null ? ` · ${dte} days left` : ''} · Sorted by rollover % (share of OI beyond near month)</div>
      ${dte != null && dte <= 5 ? `<div class="note" style="margin-bottom:12px">⚠ Expiry week: OI changes are distorted by rollover. High rollover = traders carried positions forward.</div>` : ''}
      <div class="card"><div class="tablewrap" id="exp-tbl"></div></div>`;
    const pct2 = v => v == null ? '–' : `${v > 0 ? '+' : ''}${nf(v, 1)}%`;
    const rollBar = v => v == null ? '' : `<div class="mini-roll" style="--pct:${Math.min(100, v).toFixed(1)}%"></div>`;
    const vs = (r) => { const med = secMed[r.sector]; if (med == null || r.roll == null) return '<span class="muted">–</span>'; const d = r.roll - med; return `<span class="${d > 2 ? 'up' : d < -2 ? 'down' : ''}">${d > 0 ? '+' : ''}${nf(d, 1)}</span>`; };
    const rollClass = v => v == null ? '' : v >= p75 ? 'up' : v <= p25 ? 'down' : '';
    $('#exp-tbl').innerHTML = `<table><thead><tr>
      <th class="l">Stock</th><th class="l">Sector</th><th>Rollover %</th><th></th><th>vs Sector</th>
      <th>OI trend</th><th>OI chg</th><th>Close</th><th>Chg</th><th>Expiry</th>
    </tr></thead><tbody>${rows.map(r => `<tr>
      <td class="l"><a href="#/stock/${encodeURIComponent(r.sym)}">${esc(r.sym)}</a>${banBadge(r.sym)}</td>
      <td class="l"><a href="#/sector/${encodeURIComponent(r.sector)}">${esc(r.sector)}</a></td>
      <td class="${rollClass(r.roll)}">${r.roll == null ? '–' : nf(r.roll, 1) + '%'}</td>
      <td style="min-width:80px">${rollBar(r.roll)}</td>
      <td>${vs(r)}</td>
      <td class="l">${trendBadge(r.oi_trend)}${streakBadge(r)}</td>
      <td>${pct(r.oi_chg)}</td><td>${nf(r.close)}</td><td>${pct(r.chg)}</td>
      <td>${r.expiry ? esc(r.expiry.slice(5)) : '–'}</td>
    </tr>`).join('')}</tbody></table>`;
  }

  boot();
})();
