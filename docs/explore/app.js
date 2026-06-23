const DATA_DIR = 'data/';
const state = { index: null, cache: new Map(), step: 0, timer: null, current: null };
const $ = (id) => document.getElementById(id);

async function loadJson(path) {
  if (state.cache.has(path)) return state.cache.get(path);
  const res = await fetch(path);
  if (!res.ok) throw new Error(`Failed to load ${path}: ${res.status}`);
  const data = await res.json();
  state.cache.set(path, data);
  return data;
}

function fmt(x, digits = 3) {
  if (x === null || x === undefined || Number.isNaN(x)) return 'n/a';
  return Number(x).toFixed(digits);
}

function setChip(el, verdict) {
  el.textContent = verdict;
  el.className = `chip ${verdict}`;
}

function configBy(predicate) {
  return state.index.configs.find(predicate);
}

function pressureId(world, pressure) {
  // Emitter filenames keep one decimal (pressure_1_0, pressure_0_6); JS would
  // otherwise stringify 1.0 -> "1", asking for a file that does not exist.
  return `${world}__boundary__pressure_${Number(pressure).toFixed(1).replace('.', '_')}`;
}

async function loadConfig(configId) {
  return loadJson(`${DATA_DIR}${configId}.json`);
}

// Read the active colour scheme from CSS variables so the charts and the zone
// grid follow the light / dark (neon) theme. Falls back to the light palette.
function palette() {
  const cs = getComputedStyle(document.documentElement);
  const g = (n, d) => (cs.getPropertyValue(n).trim() || d);
  const attr = document.documentElement.getAttribute('data-theme');
  const dark = attr === 'dark' || (!attr && matchMedia('(prefers-color-scheme: dark)').matches);
  return {
    dark,
    chartBg: g('--chart-bg', '#ffffff'), grid: g('--chart-grid', '#eef2f0'),
    axis: g('--chart-axis', '#cbd5e1'), tick: g('--chart-tick', '#94a3b8'),
    legend: g('--chart-legend', '#334155'), marker: g('--chart-marker', '#111827'),
    band: parseFloat(g('--chart-band', '0.10')) || 0.10,
    metric: {
      welfare: g('--c-welfare', '#9ca3af'),
      minimum_zone_welfare: g('--c-minwelfare', '#0f766e'),
      capture_index: g('--c-capture', '#b42318'),
      exploitative_strategy_mass: g('--c-exploit', '#c2410c'),
      containment_events_this_step: g('--c-containment', '#a16207'),
    },
    zoneBg: g('--zone-bg', '#f8fafc'), zoneStroke: g('--zone-stroke', '#334155'),
    zonePulse: g('--zone-pulse', '#a16207'), zoneText: g('--zone-text', '#0f172a'),
    zoneSub: g('--zone-subtext', '#334155'),
  };
}

function drawZones(payload, step) {
  const canvas = $('zoneCanvas');
  if (!canvas) return;
  const pal = palette();
  const ctx = canvas.getContext('2d');
  const w = canvas.width;
  const h = canvas.height;
  ctx.clearRect(0, 0, w, h);
  ctx.fillStyle = pal.zoneBg;
  ctx.fillRect(0, 0, w, h);
  const masses = payload.rep.zone_mass[step];
  const welfare = payload.rep.zone_welfare[step];
  const maxMass = Math.max(...masses, 1);
  const pulse = payload.rep.containment_events_this_step[step] > 0;
  const pad = 34;
  const gap = 16;
  const cell = (w - pad * 2 - gap * 2) / 3;
  for (let i = 0; i < 9; i += 1) {
    const row = Math.floor(i / 3);
    const col = i % 3;
    const x = pad + col * (cell + gap);
    const y = pad + row * (cell + gap);
    const wf = Math.max(0, Math.min(1, welfare[i]));
    const mass = Math.max(0.08, Math.min(1, masses[i] / maxMass));
    const hue = 8 + wf * 165;
    const light = pal.dark ? (24 + wf * 26) : (78 - wf * 24);
    const sat = pal.dark ? 78 : 62;
    ctx.fillStyle = `hsl(${hue}, ${sat}%, ${light}%)`;
    ctx.strokeStyle = pulse ? pal.zonePulse : pal.zoneStroke;
    ctx.lineWidth = pulse ? 5 : 2;
    const inset = (1 - mass) * cell * 0.28;
    roundRect(ctx, x + inset, y + inset, cell - inset * 2, cell - inset * 2, 8, true, true);
    ctx.fillStyle = pal.zoneText;
    ctx.font = '14px system-ui, sans-serif';
    ctx.fillText(`Z${i + 1}`, x + 10, y + 22);
    ctx.fillStyle = pal.zoneSub;
    ctx.font = '12px system-ui, sans-serif';
    ctx.fillText(`w ${fmt(wf, 2)}`, x + 10, y + cell - 14);
  }
  if (pulse) {
    ctx.fillStyle = pal.dark ? 'rgba(255, 210, 63, 0.06)' : 'rgba(161, 98, 7, 0.10)';
    ctx.fillRect(0, 0, w, h);
  }
}

function roundRect(ctx, x, y, width, height, radius, fill, stroke) {
  ctx.beginPath();
  ctx.moveTo(x + radius, y);
  ctx.lineTo(x + width - radius, y);
  ctx.quadraticCurveTo(x + width, y, x + width, y + radius);
  ctx.lineTo(x + width, y + height - radius);
  ctx.quadraticCurveTo(x + width, y + height, x + width - radius, y + height);
  ctx.lineTo(x + radius, y + height);
  ctx.quadraticCurveTo(x, y + height, x, y + height - radius);
  ctx.lineTo(x, y + radius);
  ctx.quadraticCurveTo(x, y, x + radius, y);
  ctx.closePath();
  if (fill) ctx.fill();
  if (stroke) ctx.stroke();
}

// Colour by MEANING, not by position: danger signals (capture, exploit) are red
// and drawn boldest/on top; the protected floor (min-zone welfare) is calm teal;
// average welfare is a muted dashed grey so the comfortable curve never reads as
// "healthy" on its own.
const METRIC_STYLE = {
  welfare: { color: '#9ca3af', width: 1.5, dash: '5 4', label: 'avg welfare (can look fine)' },
  minimum_zone_welfare: { color: '#0f766e', width: 2, dash: '', label: 'min-zone welfare (the floor)' },
  capture_index: { color: '#b42318', width: 2.6, dash: '', label: 'capture' },
  exploitative_strategy_mass: { color: '#c2410c', width: 2.6, dash: '', label: 'exploit mass' },
  containment_events_this_step: { color: '#a16207', width: 2, dash: '', label: 'containment (sword firing)' },
};

function drawBandChart(container, payload, metricNames, step) {
  const pal = palette();
  const width = 920, height = 440;
  const ml = 58, mr = 18, mt = 24, mb = 42;
  let ymax = 1.0;
  for (const m of metricNames) {
    for (const p of payload.band[m]) ymax = Math.max(ymax, p.hi || 0);
  }
  ymax = Math.max(1.0, ymax * 1.05);
  const sx = (i) => ml + i / (payload.steps - 1) * (width - ml - mr);
  const sy = (v) => height - mb - Math.max(0, Math.min(ymax, v)) / ymax * (height - mt - mb);
  let svg = `<svg viewBox="0 0 ${width} ${height}" role="img" aria-label="trajectory bands">`;
  if (pal.dark) svg += '<defs><filter id="glow" x="-20%" y="-20%" width="140%" height="140%"><feGaussianBlur stdDeviation="2.2" result="b"/><feMerge><feMergeNode in="b"/><feMergeNode in="SourceGraphic"/></feMerge></filter></defs>';
  svg += `<rect width="${width}" height="${height}" fill="${pal.chartBg}"/>`;
  for (let g = 0; g <= 4; g += 1) {
    const yy = sy(g / 4 * ymax);
    svg += `<line x1="${ml}" y1="${yy.toFixed(1)}" x2="${width - mr}" y2="${yy.toFixed(1)}" stroke="${pal.grid}"/>`;
    svg += `<text x="${ml - 8}" y="${(yy + 4).toFixed(1)}" text-anchor="end" font-family="system-ui" font-size="11" fill="${pal.tick}">${(g / 4 * ymax).toFixed(1)}</text>`;
  }
  svg += `<line x1="${ml}" y1="${height - mb}" x2="${width - mr}" y2="${height - mb}" stroke="${pal.axis}"/>`;
  svg += `<line x1="${ml}" y1="${mt}" x2="${ml}" y2="${height - mb}" stroke="${pal.axis}"/>`;
  metricNames.forEach((m, idx) => {
    const st = METRIC_STYLE[m] || { width: 2, dash: '', label: m };
    const color = pal.metric[m] || st.color || '#64748b';
    const pts = payload.band[m];
    const upper = pts.map((p, i) => `${sx(i).toFixed(1)},${sy(p.hi).toFixed(1)}`).join(' ');
    const lower = pts.slice().reverse().map((p, ri) => {
      const i = pts.length - 1 - ri;
      return `${sx(i).toFixed(1)},${sy(p.lo).toFixed(1)}`;
    }).join(' ');
    const line = pts.map((p, i) => `${i === 0 ? 'M' : 'L'} ${sx(i).toFixed(1)} ${sy(p.mean).toFixed(1)}`).join(' ');
    const dash = st.dash ? ` stroke-dasharray="${st.dash}"` : '';
    const glow = pal.dark ? ' filter="url(#glow)"' : '';
    svg += `<polygon points="${upper} ${lower}" fill="${color}" opacity="${pal.band}"/>`;
    svg += `<path d="${line}" fill="none" stroke="${color}" stroke-width="${st.width}"${dash}${glow}/>`;
    svg += `<rect x="${width - 268}" y="${mt + 8 + idx * 20}" width="14" height="3" fill="${color}"/>`;
    svg += `<text x="${width - 248}" y="${mt + 13 + idx * 20}" fill="${pal.legend}" font-family="system-ui" font-size="13">${st.label}</text>`;
  });
  svg += `<line x1="${sx(step).toFixed(1)}" y1="${mt}" x2="${sx(step).toFixed(1)}" y2="${height - mb}" stroke="${pal.marker}" stroke-dasharray="4 4"/>`;
  svg += `<text x="${sx(step).toFixed(1)}" y="${mt - 8}" text-anchor="middle" font-family="system-ui" font-size="11" fill="${pal.marker}">step ${step}</text>`;
  svg += `</svg>`;
  container.innerHTML = svg;
}

function lastBand(payload, m) {
  const arr = payload.band[m];
  return arr && arr.length ? arr[arr.length - 1].mean : null;
}

function statsHtml(payload) {
  const f = payload.final;
  // Capture and exploit mass lead: a collapsed run can still show a comfortable
  // average welfare — what distinguishes it is that exploiters have taken over.
  return [
    ['permanence mean', fmt(f.permanence_mean)],
    ['collapse mean', fmt(f.collapse_mean)],
    ['final capture', fmt(lastBand(payload, 'capture_index'))],
    ['exploit mass', fmt(lastBand(payload, 'exploitative_strategy_mass'))],
    ['final welfare', fmt(f.welfare_mean)],
    ['min-zone welfare', fmt(f.minimum_zone_welfare_mean)],
    ['containment events', fmt(f.containment_events_mean, 2)],
    ['rep seed', payload.rep_seed],
  ].map(([k, v]) => `<div class="stat"><span>${k}</span><b>${v}</b></div>`).join('');
}

async function updatePlayground() {
  const world = $('worldSelect').value;
  const scales = $('scalesToggle').checked ? 'on' : 'off';
  const sword = $('swordToggle').checked ? 'on' : 'off';
  const cfg = `${world}__scales_${scales}__sword_${sword}`;
  const payload = await loadConfig(cfg);
  state.current = payload;
  setChip($('playgroundVerdict'), payload.verdict);
  $('playgroundStats').innerHTML = statsHtml(payload);
  drawZones(payload, state.step);
  drawBandChart($('lineChart'), payload, ['welfare', 'minimum_zone_welfare', 'capture_index', 'exploitative_strategy_mass'], state.step);
}

async function updateTwist() {
  const world = $('twistWorld').value;
  const variant = $('twistVariant').value;
  const payload = await loadConfig(`${world}__twist__${variant}`);
  setChip($('twistVerdict'), payload.verdict);
  $('twistStats').innerHTML = statsHtml(payload);
  drawBandChart($('twistChart'), payload, ['welfare', 'minimum_zone_welfare', 'containment_events_this_step'], state.step);
}

async function updateBoundary() {
  const world = $('boundaryWorld').value;
  const p = state.index.boundary_pressures[Number($('pressureRange').value)];
  $('pressureLabel').textContent = p.toFixed(1);
  const configId = state.index.robust_worlds.includes(world) ? pressureId(world, p) : `${world}__scales_on__sword_on`;
  const payload = await loadConfig(configId);
  setChip($('boundaryVerdict'), payload.verdict);
  $('boundaryStats').innerHTML = statsHtml(payload);
  drawBandChart($('boundaryChart'), payload, ['welfare', 'minimum_zone_welfare', 'capture_index'], state.step);
}

function setStep(step) {
  state.step = Math.max(0, Math.min(99, step));
  $('stepRange').value = String(state.step);
  $('stepLabel').textContent = String(state.step);
  if (state.current) drawZones(state.current, state.step);
  updatePlayground();
  updateTwist();
  updateBoundary();
}

function populateControls() {
  for (const w of state.index.worlds) $('worldSelect').append(new Option(w, w));
  for (const w of state.index.robust_worlds) {
    $('twistWorld').append(new Option(w, w));
    $('boundaryWorld').append(new Option(w, w));
  }
  for (const w of state.index.control_worlds) {
    $('boundaryWorld').append(new Option(`${w} (control)`, w));
  }
  const variants = [
    ['C_dyn_no_consequence', 'scales never wait'],
    ['C_dyn_only', 'consequence-gated scales'],
    ['C_full', '+ redundant cap'],
  ];
  for (const [v, label] of variants) $('twistVariant').append(new Option(label, v));
  $('scalesToggle').checked = true;
  $('swordToggle').checked = true;
  $('worldSelect').value = 'W6_mutation_corridor';
  $('twistWorld').value = 'W6_mutation_corridor';
  $('boundaryWorld').value = 'W6_mutation_corridor';
}

function bindEvents() {
  ['worldSelect', 'scalesToggle', 'swordToggle'].forEach((id) => $(id).addEventListener('change', updatePlayground));
  ['twistWorld', 'twistVariant'].forEach((id) => $(id).addEventListener('change', updateTwist));
  ['boundaryWorld', 'pressureRange'].forEach((id) => $(id).addEventListener('input', updateBoundary));
  $('stepRange').addEventListener('input', (e) => setStep(Number(e.target.value)));
  $('playButton').addEventListener('click', () => {
    if (state.timer) {
      clearInterval(state.timer);
      state.timer = null;
      $('playButton').textContent = 'Play';
      return;
    }
    $('playButton').textContent = 'Pause';
    state.timer = setInterval(() => {
      const next = state.step >= 99 ? 0 : state.step + 1;
      setStep(next);
    }, 220);
  });
}

async function init() {
  state.index = await loadJson(`${DATA_DIR}index.json`);
  populateControls();
  bindEvents();
  await updatePlayground();
  await updateTwist();
  await updateBoundary();
  // Re-render the charts and zone grid when the colour scheme is toggled.
  new MutationObserver(() => { if (state.current) setStep(state.step); })
    .observe(document.documentElement, { attributes: true, attributeFilter: ['data-theme'] });
  const gate = state.index.recording_gate.passed ? 'passed' : 'failed';
  $('dataStatus').textContent = `Data: ${state.index.configs.length} configs, ${state.index.n_seeds} seeds each. record_trajectory gate: ${gate}.`;
}

init().catch((err) => {
  console.error(err);
  $('dataStatus').textContent = `Failed to load explorable data: ${err.message}. Run python3 model/emit_explorable.py first and serve web/ over HTTP.`;
});
