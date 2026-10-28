'use strict';
/* TruePilot web app. Plain JavaScript, no build step. */
const $ = (s, r = document) => r.querySelector(s);
const h = (tag, attrs, ...kids) => {
  const el = document.createElement(tag); let pending;
  for (const [k, v] of Object.entries(attrs || {})) {
    if (v == null || v === false) continue;
    if (k === 'class') el.className = v; else if (k === 'value') pending = v;
    else if (k === 'checked' || k === 'disabled' || k === 'selected') el[k] = !!v;
    else if (k.startsWith('on')) el.addEventListener(k.slice(2), v);
    else el.setAttribute(k, v === true ? '' : v);
  }
  for (const kid of kids.flat(Infinity)) { if (kid == null || kid === false) continue; el.append(kid.nodeType ? kid : document.createTextNode(kid)); }
  if (pending !== undefined) el.value = pending; return el;
};
const NS = 'http://www.w3.org/2000/svg';
const sv = (tag, attrs, ...kids) => { const el = document.createElementNS(NS, tag); for (const [k, v] of Object.entries(attrs || {})) el.setAttribute(k, v); kids.forEach(k => k && el.append(k)); return el; };
const PATHS = { dash: 'M3 3h7v9H3z M14 3h7v5h-7z M14 12h7v9h-7z M3 16h7v5H3z', apps: 'M4 4h6v6H4z M14 4h6v6h-6z M4 14h6v6H4z M14 14h6v6h-6z',
  power: 'M12 3v9 M6.3 6.3a8 8 0 1 0 11.4 0', cal: 'M4 6h16v14H4z M4 10h16 M8 3v4 M16 3v4 M12 13v3l2 1', settings: 'M4 7h10 M18 7h2 M4 17h2 M10 17h10 M14 5v4 M6 15v4',
  bell: 'M6 17v-6a6 6 0 0 1 12 0v6l1.5 2h-15z M10 21h4', activity: 'M3 12h4l3-8 4 16 3-8h4', user: 'M12 12a4 4 0 1 0 0-8 4 4 0 0 0 0 8z M4 21c0-4 4-6 8-6s8 2 8 6',
  down: 'M6 9l6 6 6-6', right: 'M9 6l6 6-6 6', up: 'M6 15l6-6 6 6', plus: 'M12 5v14 M5 12h14', pencil: 'M4 20l4-1 11-11-3-3L5 16z', refresh: 'M20 11a8 8 0 0 0-14-4L4 9 M4 4v5h5 M4 13a8 8 0 0 0 14 4l2-2 M20 20v-5h-5',
  copy: 'M9 9h11v11H9z M5 15V4h11', menu: 'M4 6h16 M4 12h16 M4 18h16', arrowUp: 'M12 19V5 M6 11l6-6 6 6', arrowDown: 'M12 5v14 M6 13l6 6 6-6', moon: 'M20 14a8 8 0 1 1-10-10 6 6 0 0 0 10 10z', logout: 'M10 4H5v16h5 M15 8l4 4-4 4 M9 12h10', history: 'M3 12a9 9 0 1 0 3-7L3 8 M3 3v5h5 M12 8v5l3 2', lock: 'M6 11h12v9H6z M8 11V8a4 4 0 0 1 8 0v3', approve: 'M12 21a9 9 0 1 0 0-18 9 9 0 0 0 0 18z M8 12l3 3 5-6', bot: 'M7 8h10a3 3 0 0 1 3 3v6a3 3 0 0 1-3 3H7a3 3 0 0 1-3-3v-6a3 3 0 0 1 3-3z M12 4v4 M9 13h.01 M15 13h.01', star: 'M12 3l2.7 5.6 6.1.9-4.4 4.3 1 6.1L12 17l-5.4 2.9 1-6.1L3.2 9.5l6.1-.9z', logs: 'M6 3h9l4 4v14H6z M14 3v5h5 M9 12h7 M9 16h7', search: 'M11 4a7 7 0 1 0 0 14 7 7 0 0 0 0-14z M20 20l-4-4',
  key: 'M15 7a4 4 0 1 1-3.6 5.7L5 19H3v-3l1.5-1.5H7V12h2.4', eye: 'M2 12s4-7 10-7 10 7 10 7-4 7-10 7S2 12 2 12z M12 9.5a2.5 2.5 0 1 0 0 5 2.5 2.5 0 0 0 0-5z' };
const icon = n => sv('svg', { class: 'ic', viewBox: '0 0 24 24', 'aria-hidden': 'true' }, sv('path', { d: PATHS[n] }));

const S = { auth: null, me: {}, devices: [], pcs: [], webapps: [], tasks: [], devId: Number(localStorage.getItem('tp.dev')) || null, res: null, page: 'dash', open: new Set(),
  seen: {}, fastUntil: 0, panel: null, cfg: null, err: '', last: 0, busy: false, collapsed: localStorage.getItem('tp.collapsed') === '1' };

/* ---------- formatting ---------- */
const split = (n, base, units) => { if (n == null) return ['-', '']; let i = 0; while (n >= base && i < units.length - 1) { n /= base; i++; } return [(n >= 100 || i === 0 ? n.toFixed(0) : n.toFixed(1)), units[i]]; };
const bin = n => split(n, 1024, ['B', 'KiB', 'MiB', 'GiB', 'TiB', 'PiB']);
const dec = n => split(n, 1000, ['B', 'KB', 'MB', 'GB', 'TB', 'PB']);
const jn = ([v, u]) => (u ? `${v} ${u}` : v);
const uptime = s => { if (s == null) return '-'; const d = Math.floor(s / 86400), hh = Math.floor(s % 86400 / 3600), m = Math.floor(s % 3600 / 60); return d ? `${d} days, ${hh} h` : hh ? `${hh} h ${m} min` : `${m} min`; };
const ago = ms => { if (!ms) return ''; const s = Math.max(0, (Date.now() - ms) / 1000); if (s < 90) return 'just now'; if (s < 5400) return `${Math.round(s / 60)} min ago`; if (s < 129600) return `${Math.round(s / 3600)} h ago`; return `${Math.round(s / 86400)} days ago`; };
const when = t => (t ? new Date(t * 1000).toLocaleString([], { weekday: 'short', day: 'numeric', month: 'short', hour: '2-digit', minute: '2-digit' }) : '-');
const DOW = ['Sun', 'Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat'], p2 = n => String(n).padStart(2, '0');
function describeCron(c) {
  let m = /^(\d+) (\d+) \* \* \*$/.exec(c); if (m) return `Every day at ${p2(m[2])}:${p2(m[1])}`;
  m = /^(\d+) (\d+) \* \* 1-5$/.exec(c); if (m) return `Weekdays at ${p2(m[2])}:${p2(m[1])}`;
  m = /^(\d+) (\d+) \* \* (0,6|6,0)$/.exec(c); if (m) return `Weekends at ${p2(m[2])}:${p2(m[1])}`;
  m = /^(\d+) (\d+) \* \* ([0-6](?:,[0-6])*)$/.exec(c); if (m) return `Every ${m[3].split(',').map(d => DOW[+d]).join(', ')} at ${p2(m[2])}:${p2(m[1])}`;
  return c;
}

/* ---------- plumbing ---------- */
async function api(path, { method = 'GET', body } = {}) {
  const r = await fetch('/api' + path, { method, credentials: 'same-origin', headers: body ? { 'Content-Type': 'application/json' } : {}, body: body ? JSON.stringify(body) : undefined });
  const data = await r.json().catch(() => ({}));
  if (r.status === 401 && S.auth === 'in') { S.auth = 'login'; render(); throw new Error('Signed out'); }
  if (!r.ok) throw new Error(typeof data.detail === 'string' ? data.detail : `Request failed (${r.status})`);
  return data;
}
function toast(msg, bad) { const t = h('div', { class: 'toast' + (bad ? ' bad' : '') }, msg); $('#toasts').append(t); setTimeout(() => t.remove(), bad ? 7000 : 4000); }
function modal(title, body, actions) {
  const d = $('#dlg'); d.style.width = ''; d.replaceChildren(h('div', { class: 'dhd' }, h('h2', {}, title)), h('div', { class: 'dbd' }, body), h('div', { class: 'dft' }, actions));
  if (!d.open) d.showModal(); return d;
}
const wait = ms => new Promise(r => setTimeout(r, ms));
const closeDlg = () => { const d = $('#dlg'); if (d.open) d.close(); };
const dev = () => S.devices.find(d => d.id === S.devId) || S.devices.find(d => d.kind !== 'wake') || null;
const wakeOnly = () => !S.devices.length;
const label = () => /Android/.test(navigator.userAgent) ? 'Android phone' : /iPhone|iPad/.test(navigator.userAgent) ? 'iPhone' : /Windows/.test(navigator.userAgent) ? 'Windows browser' : 'Browser';
const lamp = (s, extra = '') => h('span', { class: `l ${s} ${extra}`, 'aria-hidden': 'true' });
const copyTxt = async t => { try { await navigator.clipboard.writeText(t); toast('Copied ' + t); } catch { toast(t); } };
const copyBtn = t => h('button', { class: 'copy mono', title: 'Tap to copy', onclick: () => copyTxt(t) }, t);
const PAGES = () => (wakeOnly() ? [['power', 'Power', 'power'], ['sched', 'Schedules', 'cal'], ['settings', 'Settings', 'settings']]
  : [['dash', 'Dashboard', 'dash'], ['apps', 'Apps', 'apps'], ['power', 'Power', 'power'], ['sched', 'Schedules', 'cal'], ['settings', 'Settings', 'settings']]);
const sysOf = () => S.res?.snapshot?.system || {};

/* ---------- data ---------- */
async function loadDevices() { S.devices = await api('/devices'); if (!S.devices.find(d => d.id === S.devId)) S.devId = (S.devices.find(d => d.kind !== 'wake') || {}).id || null; }
async function pollNow() {
  if (S.auth !== 'in' || S.busy) return; S.busy = true;
  try {
    const d = dev();
    const [snap, pcs, act, apv, wap] = await Promise.all([d ? api(`/devices/${d.id}/snapshot`).catch(e => { if (e.message !== 'Signed out') S.err = e.message; return null; }) : null, api('/pcs').catch(() => null), api('/activity').catch(() => null), S.me.app ? null : api('/approvals').catch(() => null), api('/webapps').catch(() => null)]);
    if (snap) { S.res = snap; S.err = ''; } if (pcs) S.pcs = pcs; if (apv) S.approvals = apv; if (wap) S.webapps = wap;
    if (act) { for (const t of act.tasks) { const prev = S.seen[t.id]; S.seen[t.id] = t.status; if (prev === 'running' && t.status !== 'running') toast(t.status === 'done' ? t.message : `${t.title} failed: ${t.message}`, t.status === 'failed'); } S.tasks = act.tasks; }
    S.last = Date.now();
  } finally { S.busy = false; }
  if (S.auth === 'in') { renderBar(); if (S.panel !== 'se') renderPanel(); if (['dash', 'apps', 'power'].includes(S.page) && !$('#dlg').open) renderMain(); }
}
setInterval(() => { if (S.auth !== 'in' || document.hidden) return; const every = Date.now() < S.fastUntil ? 1500 : (S.me.refresh || 5) * 1000; if (Date.now() - S.last >= every) pollNow(); }, 500);

/* ---------- gate screens ---------- */
const gateWrap = (...kids) => h('div', { class: 'gate' }, h('div', { class: 'logo' }, 'TruePilot'), ...kids);
const pwField = (text, id, ac) => h('label', { class: 'f' }, text, h('input', { type: 'password', id, autocomplete: ac || 'current-password' }));
function msgBox() { const m = h('div'); m.set = (t, bad = true) => m.replaceChildren(t ? h('p', { class: 'note' + (bad ? ' bad' : ' ok') }, t) : ''); return m; }

function gateSetup() {
  const m = msgBox(), a = pwField('New password (8 or more characters)', 'pw', 'new-password'), b = pwField('Repeat password', 'pw2', 'new-password');
  const go = async () => {
    const v = $('#pw').value; if (v !== $('#pw2').value) return m.set('The two passwords don\'t match.');
    try { await api('/auth/setup', { method: 'POST', body: { password: v, label: label() } }); await start(); } catch (e) { m.set(e.message); }
  };
  return gateWrap(h('p', { class: 'lead' }, 'Choose a password for TruePilot. It only protects this app, and it isn\'t your TrueNAS password.'), h('div', { class: 'card' }, h('div', { class: 'cb' }, a, b, m, h('button', { class: 'btn', onclick: go }, 'Set password and continue'))));
}
function gateLogin() {
  const m = msgBox(), a = pwField('Password', 'pw');
  const go = async () => { try { await api('/auth/login', { method: 'POST', body: { password: $('#pw').value, label: label() } }); await start(); } catch (e) { m.set(e.message); } };
  return gateWrap(h('p', { class: 'lead' }, 'Sign in to see your NAS.'), h('div', { class: 'card' }, h('div', { class: 'cb' }, a, m, h('button', { class: 'btn', onclick: go }, 'Sign in'),
    h('div', { class: 'links' }, h('button', { class: 'link', onclick: () => { S.auth = 'forgot'; render(); } }, 'Forgot password?')))));
  }
function gateForgot() {
  const m = msgBox(), box = h('div'); let devs = [];
  const sel = h('select', {}), user = h('input', { type: 'text', autocomplete: 'username' }), pw = h('input', { type: 'password', autocomplete: 'off' }), otp = h('input', { type: 'text', autocomplete: 'one-time-code' });
  const otpWrap = h('label', { class: 'f', style: 'display:none' }, 'Two-step code', otp);
  const verify = async () => {
    m.set('');
    try { const r = await api('/auth/forgot/verify', { method: 'POST', body: { device_id: Number(sel.value), username: user.value, password: pw.value, otp: otp.value } });
      if (r.otp_required) { otpWrap.style.display = ''; return m.set('Enter the code from your authenticator app.', false); }
      newPw(r.reset_token); } catch (e) { m.set(e.message); }
  };
  const newPw = tok => {
    const a = pwField('New password (8 or more characters)', 'np1', 'new-password'), b = pwField('Repeat password', 'np2', 'new-password');
    box.replaceChildren(h('p', { class: 'note ok' }, 'TrueNAS confirmed you\'re an admin. Choose a new password.'), a, b, m, h('button', { class: 'btn', onclick: async () => {
      if ($('#np1').value !== $('#np2').value) return m.set('The two passwords don\'t match.');
      try { await api('/auth/forgot/reset', { method: 'POST', body: { reset_token: tok, new_password: $('#np1').value, label: label() } }); await start(); } catch (e) { m.set(e.message); } } }, 'Set new password'));
  };
  api('/auth/forgot/devices').then(d => { devs = d; sel.replaceChildren(...d.map(x => h('option', { value: x.id }, x.name)));
    box.replaceChildren(...(d.length ? [h('p', { class: 'lead', style: 'margin:0 0 12px' }, 'Sign in with your TrueNAS admin details to choose a new password. TruePilot checks them with TrueNAS and doesn\'t keep them.'),
      h('label', { class: 'f' }, 'Check with this NAS', sel), h('label', { class: 'f' }, 'TrueNAS admin username', user), h('label', { class: 'f' }, 'TrueNAS admin password', pw), otpWrap, m,
      h('button', { class: 'btn', onclick: verify }, 'Check and continue')] : [h('p', { class: 'note' }, 'No NAS is saved in TruePilot, so there is nothing to check with. Use "Start fresh" below.')])); });
  return gateWrap(h('div', { class: 'card' }, h('div', { class: 'cb' }, box, h('div', { class: 'links' }, h('button', { class: 'link', onclick: () => { S.auth = 'login'; render(); } }, 'Back to sign in'),
    h('button', { class: 'link', onclick: () => { S.auth = 'fresh'; render(); } }, 'I can\'t remember these: Start fresh')))));
}
function freshPanel(onDone) {
  const box = h('div'), m = msgBox(); let tok = '';
  const text = h('input', { type: 'text', autocomplete: 'off', placeholder: 'RESET' }), go = h('button', { class: 'btn danger', disabled: true }, 'Wait 10 seconds');
  api('/auth/fresh/start', { method: 'POST' }).then(r => {
    tok = r.token; let left = r.wait_seconds;
    box.replaceChildren(h('p', {}, 'This wipes TruePilot: your password, saved NAS and keys, schedules, wake list and signed-in devices. The activity log is kept. You\'ll set it up again from the start.'),
      r.cron_jobs.length ? h('p', { class: 'note' }, 'These restart or shutdown jobs live inside TrueNAS and will keep running. Delete them in TrueNAS under System > Advanced > Cron Jobs if you don\'t want them: ' + r.cron_jobs.map(j => `${j.name} (${j.device})`).join(', ') + '.') : '',
      h('p', { class: 'note' }, 'Your old API keys stay valid in TrueNAS. If you\'re resetting because of a leak, delete them under Credentials > API Keys.'),
      h('label', { class: 'f' }, 'Type RESET to confirm', text), m);
    const tick = () => { if (left > 0) { go.textContent = `Wait ${left} seconds`; left--; setTimeout(tick, 1000); } else { go.textContent = 'Wipe and start fresh'; go.disabled = false; } }; tick();
  }).catch(e => box.replaceChildren(h('p', { class: 'note bad' }, e.message)));
  go.onclick = async () => { try { await api('/auth/fresh/confirm', { method: 'POST', body: { token: tok, confirm_text: text.value } }); closeDlg(); onDone(); } catch (e) { m.set(e.message); } };
  return { box, go };
}
function gateFresh() {
  const p = freshPanel(() => { S.devices = []; S.res = null; start(); });
  return gateWrap(h('div', { class: 'card' }, h('div', { class: 'cb' }, h('h3', { style: 'margin-bottom:8px' }, 'Start fresh'), p.box, h('div', { class: 'acts', style: 'margin-top:8px' }, p.go, h('button', { class: 'btn ghost', onclick: () => { S.auth = 'forgot'; render(); } }, 'Cancel')))));
}
function gateNas() {
  const f = deviceFormEl(null, async () => { await start(); });
  return gateWrap(h('p', { class: 'lead' }, 'Add your NAS to get started. You need its address and a read-only API key from TrueNAS.'), h('div', { class: 'card' }, h('div', { class: 'cb' }, f.el, h('div', { class: 'acts' }, f.test, f.save)),
    h('div', { class: 'cb', style: 'border-top:1px solid var(--line)' }, h('p', { class: 'mute small', style: 'margin:0 0 8px' }, 'This copy runs on a PC that stays on, only to wake your NAS and PCs?'),
      h('button', { class: 'btn ghost', onclick: async () => { await api('/settings', { method: 'PUT', body: { wake_only: true } }); await start(); } }, 'Skip: use this copy only for waking things'))));
}

/* ---------- shell ---------- */
function render() {
  const root = $('#app'); root.replaceChildren();
  const g = { setup: gateSetup, login: gateLogin, forgot: gateForgot, fresh: gateFresh, nas: gateNas }[S.auth];
  if (g) { root.append(g()); return; }
  if (S.auth !== 'in') return;
  root.className = S.collapsed ? 'collapsed' : '';
  const pages = PAGES();
  if (!pages.find(p => p[0] === S.page)) S.page = pages[0][0];
  root.append(h('header', { class: 'tb', id: 'tb' }), h('nav', { class: 'side', 'aria-label': 'Sections' }, pages.map(([k, t, i]) => h('a', { href: '#/' + k, 'aria-current': S.page === k ? 'page' : null }, icon(i), h('span', {}, t)))),
    h('main', { class: 'main', id: 'main' }), h('nav', { class: 'tabs', style: `grid-template-columns:repeat(${pages.length},1fr)`, 'aria-label': 'Sections' }, pages.map(([k, t, i]) => h('a', { href: '#/' + k, 'aria-current': S.page === k ? 'page' : null }, icon(i), t))), h('div', { id: 'popHost' }));
  renderBar(); renderMain();
}
const pendingApprovals = () => (S.approvals || []).filter(r => r.status === 'pending');
async function resolveApproval(r, status, task) { try { const res = await api(`/approvals/${r.request_id}/resolve`, { method: 'POST', body: { status, task: task || '' } }); if (res.ok === false) toast(res.error, true); else if (res.result) toast(res.result); S.approvals = (S.approvals || []).filter(x => x.request_id !== r.request_id); S.last = 0; renderBar(); pollNow(); } catch (e) { toast(e.message, true); } }
function approveFlow(r) {
  const host = r.action !== 'upgrade_app', verb = r.action === 'restart_nas' ? 'Restart' : 'Shut down';
  confirmAction({ title: host ? `${verb} ${r.nas}` : `Upgrade ${r.app}`, endpoint: host ? `/devices/${r.device_id}/host/${r.action === 'restart_nas' ? 'restart' : 'shutdown'}` : `/devices/${r.device_id}/apps/${r.app}/upgrade`, confirmLabel: host ? verb : 'Upgrade', danger: host, onStarted: t => resolveApproval(r, 'approved', t) });
}
function renderBar() {
  const tb = $('#tb'); if (!tb) return; const d = dev(), res = S.res, s = res?.snapshot, sys = s?.system || {};
  const running = S.tasks.filter(t => t.status === 'running').length, alerts = (s?.alerts || []).filter(a => ['WARNING', 'ERROR', 'CRITICAL', 'ALERT', 'EMERGENCY'].includes(a.level)).length;
  const status = !d ? S.me.computer || 'Wake-only copy' : !s ? 'Connecting...' : !s.ok ? 'Offline' : `TrueNAS ${(sys.version || '').replace(/^TrueNAS-/, '')}, up ${uptime(sys.uptime)}`;
  const sw = (k, n, ic, badge, am) => h('button', { class: 'ib' + (S.panel === k ? ' open' : ''), 'aria-label': n, onclick: () => { S.panel = S.panel === k ? null : k; renderBar(); renderPanel(); } }, icon(ic), badge ? h('span', { class: 'bd' + (am ? ' am' : '') }, badge) : '');
  tb.replaceChildren(...[h('button', { class: 'ib menu-btn', 'aria-label': 'Collapse menu', onclick: () => { S.collapsed = !S.collapsed; localStorage.setItem('tp.collapsed', S.collapsed ? '1' : '0'); $('#app').className = S.collapsed ? 'collapsed' : ''; } }, icon('menu')),
    h('span', { class: 'brand' }, 'TruePilot'), h('button', { class: 'nm', onclick: () => { if (S.devices.length > 1) { S.panel = S.panel === 'dev' ? null : 'dev'; renderPanel(); } } }, h('b', {}, d ? d.name : 'TruePilot'), h('span', {}, status)),
    sw('se', 'Search', 'search', ''), pendingApprovals().length > 0 && sw('ap', 'Approvals', 'approve', pendingApprovals().length, true), sw('act', 'Running tasks', 'activity', running || '', true), d && sw('al', 'Alerts', 'bell', alerts || ''), sw('pw', 'Power', 'power'), sw('us', 'Account', 'user')].filter(Boolean));
}
function renderPanel() {
  const host = $('#popHost'); if (!host) return; host.replaceChildren(); const k = S.panel; if (!k) return;
  const close = () => { S.panel = null; renderBar(); renderPanel(); }, d = dev(), s = S.res?.snapshot;
  const go = (page, fn) => () => { close(); if (page) location.hash = '#/' + page; if (fn) fn(); };
  let pop;
  if (k === 'act') pop = h('div', { class: 'pop' }, h('h4', {}, 'Running now'), S.tasks.length ? S.tasks.map(t => h('div', { class: 'prow' }, lamp(t.status === 'running' ? 'run' : t.status === 'done' ? 'ok' : 'bad'), h('div', {}, t.title),
      h('span', { class: 'mute small' }, t.status === 'running' ? `${Math.round(Date.now() / 1000 - t.started)} s` : t.status), h('div', { class: 'sub' }, t.status === 'running' ? 'Working' : t.message))) : h('p', { class: 'empty' }, 'Nothing running.'), h('div', { class: 'sep' }), h('button', { class: 'it', onclick: () => { close(); auditDialog(); } }, icon('history'), 'Activity log'));
  else if (k === 'al') pop = h('div', { class: 'pop' }, h('h4', {}, 'Alerts'), (s?.alerts || []).length ? s.alerts.slice(0, 6).map(a => h('div', { class: 'prow' }, lamp(LV[a.level] || 'unk'), h('div', {}, a.text), h('span'), h('div', { class: 'sub' }, a.level.toLowerCase() + (a.when ? ', ' + ago(a.when) : '')))) : h('p', { class: 'empty' }, 'No active alerts.'), h('div', { class: 'sep' }), h('button', { class: 'it', onclick: go('dash') }, icon('dash'), 'Open dashboard'));
  else if (k === 'pw') pop = h('div', { class: 'pop' }, d && [h('h4', {}, 'This NAS'), h('button', { class: 'it', onclick: go(null, () => hostAction('restart')) }, icon('refresh'), 'Restart'), h('button', { class: 'it dg', onclick: go(null, () => hostAction('shutdown')) }, icon('power'), 'Shut down'), h('div', { class: 'sep' })],
    h('h4', {}, 'Wake a device'), S.pcs.length ? S.pcs.map(p => pcRow(p, true)) : h('p', { class: 'empty' }, 'No PCs yet.'), h('div', { class: 'sep' }), h('button', { class: 'it', onclick: go('power') }, icon('settings'), 'Manage PCs', h('span', { class: 'r' }, icon('right'))));
  else if (k === 'us') pop = h('div', { class: 'pop' }, h('h4', {}, 'Signed in on this device'), h('button', { class: 'it', onclick: go('settings') }, icon('settings'), 'Settings'),
    h('button', { class: 'it', onclick: () => { const t = localStorage.getItem('tp.theme') || '', n = t === '' ? 'light' : t === 'light' ? 'dark' : ''; n ? localStorage.setItem('tp.theme', n) : localStorage.removeItem('tp.theme'); applyTheme(); renderPanel(); } }, icon('moon'), 'Theme', h('span', { class: 'r' }, ({ '': 'Match device', light: 'Light', dark: 'Dark' })[localStorage.getItem('tp.theme') || ''])),
    h('div', { class: 'sep' }), S.me.app ? h('button', { class: 'it', onclick: () => { close(); window.TPNative.lockNow(); } }, icon('lock'), 'Lock now') : h('button', { class: 'it', onclick: async () => { await api('/auth/logout', { method: 'POST' }); S.auth = 'login'; render(); } }, icon('logout'), 'Sign out'));
  else if (k === 'ap') { const list = pendingApprovals(); pop = h('div', { class: 'pop' }, h('h4', {}, 'Waiting for your approval'), list.length ? list.map(r => h('div', { style: 'padding:10px 14px;border-top:1px solid var(--line)' },
      h('div', { style: 'font-weight:600' }, `${r.agent} wants to ${r.kind === 'config' ? r.summary : r.action === 'upgrade_app' ? 'upgrade ' + r.app : r.action === 'restart_nas' ? 'restart ' + r.nas : 'shut down ' + r.nas}`),
      r.reason && h('div', { class: 'mute small', style: 'margin:2px 0 8px' }, '"' + r.reason + '"'), h('div', { class: 'acts' }, h('button', { class: 'btn small', onclick: () => { close(); r.kind === 'config' ? resolveApproval(r, 'approved') : approveFlow(r); } }, r.kind === 'config' ? 'Approve' : 'Review and approve'), h('button', { class: 'btn small ghost', onclick: () => { close(); resolveApproval(r, 'denied'); } }, 'Deny')))) : h('p', { class: 'empty' }, 'Nothing is waiting.')); }
  else if (k === 'se') pop = searchPanel(close);
  else if (k === 'dev') pop = h('div', { class: 'pop', style: 'left:8px;right:auto' }, h('h4', {}, 'NAS units'), S.devices.map(x => h('button', { class: 'it', onclick: () => { S.devId = x.id; localStorage.setItem('tp.dev', x.id); S.res = null; close(); pollNow(); } }, x.name)));
  host.append(h('div', { class: 'scrim', onclick: close }), pop);
  if (k === 'se') setTimeout(() => { const i = $('#gq'); if (i) i.focus(); }, 0);
}
function searchPanel(close) {
  const input = h('input', { type: 'search', id: 'gq', placeholder: 'Search apps, PCs and screens', autocomplete: 'off', value: S.searchQ || '', class: 'sel', style: 'width:100%;margin:10px 0' }), box = h('div'); let first = null;
  const draw = () => {
    S.searchQ = input.value; const q = input.value.trim().toLowerCase(), d = dev(), out = []; first = null;
    if (q) {
      for (const a of (S.res?.snapshot?.apps || []).filter(a => a.title.toLowerCase().includes(q) || a.name.toLowerCase().includes(q)).slice(0, 6)) {
        const acts = []; if (a.state === 'RUNNING' && appLinks(a).length) acts.push(['Open', () => openApp(d, a)]); acts.push(['Logs', () => logsDialog(d, a)]);
        if (writeOn(d, S.res) && a.state !== 'STOPPED') acts.push(['Restart', () => confirmAction({ title: `Restart ${a.title}`, endpoint: `/devices/${d.id}/apps/${a.name}/restart`, confirmLabel: 'Restart' })]);
        out.push({ t: a.title, s: 'App, ' + appWord(a).toLowerCase(), acts, a });
      }
      for (const w of S.webapps.filter(w => w.name.toLowerCase().includes(q) || w.host.includes(q)).slice(0, 4)) out.push({ t: w.name, s: 'Web App, ' + (w.state === 'on' ? 'answering' : 'not answering'), acts: [['Open', () => openWebApp(w)]] });
      for (const p of S.pcs.filter(p => p.name.toLowerCase().includes(q)).slice(0, 4)) out.push({ t: p.name, s: 'PC, ' + p.state, acts: (p.state === 'off' || p.state === 'unknown') ? [['Wake', () => wakePc(p)]] : [] });
      for (const [k, t] of PAGES().filter(x => x[1].toLowerCase().includes(q))) out.push({ t, s: 'Screen', acts: [['Go', () => { location.hash = '#/' + k; }]] });
    }
    first = out[0] && out[0].acts[0] ? out[0].acts[0] : null;
    box.replaceChildren(...(out.length ? out.map(r => h('div', { class: 'prow' }, h('span'), h('div', {}, r.t), h('span'), h('div', { class: 'sub' }, r.s), h('div', { class: 'acts', style: 'grid-column:3;grid-row:span 2;justify-content:flex-end' }, r.acts.map(([t, fn]) => h('button', { class: 'btn small ghost', onclick: () => { close(); fn(); } }, t))))) : [h('p', { class: 'empty' }, q ? 'Nothing found.' : 'Type to search. Shortcut: Ctrl+K or /')]));
  };
  input.addEventListener('input', draw); input.addEventListener('keydown', e => { if (e.key === 'Escape') close(); if (e.key === 'Enter' && first) { close(); first[1](); } }); draw();
  return h('div', { class: 'pop', style: 'padding:0 12px 6px;width:460px' }, input, box);
}
document.addEventListener('keydown', e => { if (S.auth !== 'in') return; const typing = /^(INPUT|TEXTAREA|SELECT)$/.test((document.activeElement || {}).tagName || '');
  if (((e.ctrlKey || e.metaKey) && String(e.key).toLowerCase() === 'k') || (e.key === '/' && !typing && !$('#dlg').open)) { e.preventDefault(); S.panel = 'se'; renderBar(); renderPanel(); } });
window.addEventListener('hashchange', () => { S.page = location.hash.replace('#/', '') || PAGES()[0][0]; if (S.auth === 'in') { render(); pollNow(); if (S.page === 'power') loadSched().then(renderMain).catch(() => {}); } });

/* ---------- shared pieces ---------- */
const LV = { INFO: 'unk', NOTICE: 'unk', WARNING: 'warn', ERROR: 'bad', CRITICAL: 'bad', ALERT: 'bad', EMERGENCY: 'bad' };
const writeOn = (d, res) => !!(d && d.write_enabled && d.has_write_key && !res?.read_only);
const wakeSecs = p => Math.round(Date.now() / 1000 - (p.wake_started || Date.now() / 1000));
async function wakePc(p) { if (p.kind === 'nas') { const nd = S.devices.find(x => x.id === p.device_id); if (nd) return wakeDevice(nd); } try { await api(`/pcs/${p.id}/wake`, { method: 'POST' }); toast(`Wake packet sent to ${p.name}`); S.fastUntil = Date.now() + 120000; pollNow(); } catch (e) { toast(e.message, true); } }
async function wakeDevice(d) { try { const r = await api(`/devices/${d.id}/wake`, { method: 'POST' }); toast(`Wake packet sent to ${d.name}`); S.fastUntil = Date.now() + 180000; if (r.task) S.seen[r.task] = 'running'; pollNow(); } catch (e) { toast(e.message, true); } }
const pcState = p => ({ on: 'On', off: 'Off', waking: `Waking, ${wakeSecs(p)} s`, unknown: 'Status unknown. Add an IP to see it' })[p.state];
function pcRow(p, compact, edit) {
  const btn = (p.state === 'off' || p.state === 'unknown') ? h('button', { class: 'btn small', onclick: () => wakePc(p) }, 'Wake') : h('span', { class: 'mute small' }, p.state === 'on' ? 'On' : 'Waking');
  const nas = p.kind === 'nas';
  const kids = [lamp(p.state), h('div', { class: 't' }, p.name, nas && h('span', { class: 'chip', style: 'margin-left:8px' }, 'NAS')), edit ? h('div', { class: 'acts' }, btn, h('button', { class: 'btn small ghost', 'aria-label': 'Edit ' + p.name, onclick: () => (nas ? deviceDialog(S.devices.find(x => x.id === p.device_id)) : pcForm(p)) }, icon('pencil'))) : btn,
    h('div', { class: 'sub s' }, pcState(p)), p.state === 'waking' && h('div', { class: 'bar', style: 'grid-column:1/-1' }, h('i', { style: `width:${Math.min(100, wakeSecs(p) / 90 * 100)}%` }))];
  return h('div', { class: compact ? 'prow' : 'row' }, kids);
}
function spark(vals, color, fixedMax) {
  const v = (vals || []).map(x => (x == null ? 0 : x)); if (v.length < 2) return h('div', { style: 'height:44px' });
  const max = fixedMax || Math.max(...v, 1) * 1.15, pts = v.map((x, i) => `${(i * 100 / (v.length - 1)).toFixed(1)},${(42 - x / max * 40).toFixed(1)}`).join(' ');
  return sv('svg', { class: 'sp', viewBox: '0 0 100 44', preserveAspectRatio: 'none', 'aria-hidden': 'true' }, sv('polyline', { points: pts, fill: 'none', stroke: color || 'var(--acc)', 'stroke-width': '1.6', 'vector-effect': 'non-scaling-stroke' }));
}
function ring(p, color, pct) {
  const r = 28, C = 2 * Math.PI * r;
  return sv('svg', { viewBox: '0 0 70 70', role: 'img', 'aria-label': `${p}% full` }, sv('circle', { cx: 35, cy: 35, r, fill: 'none', stroke: 'var(--track)', 'stroke-width': 8 }),
    sv('circle', { cx: 35, cy: 35, r, fill: 'none', stroke: color, 'stroke-width': 8, 'stroke-dasharray': `${(C * Math.min(100, pct) / 100).toFixed(1)} ${C.toFixed(1)}`, transform: 'rotate(-90 35 35)' }),
    sv('text', { x: 35, y: 40, 'text-anchor': 'middle', 'font-size': 14, fill: 'var(--ink)', 'font-weight': 600 }, Math.round(pct) + '%'));
}
const kv = (a, b) => h('div', { class: 'kv' }, h('span', {}, a), h('span', {}, b));

async function confirmAction({ title, endpoint, confirmLabel, danger, onStarted }) {
  const body = h('p', { class: 'mute' }, 'Checking...'), cancel = h('button', { class: 'btn ghost', onclick: closeDlg }, 'Cancel'), go = h('button', { class: 'btn' + (danger ? ' danger' : ''), disabled: true }, confirmLabel);
  modal(title, body, [cancel, go]);
  let pre; try { pre = await api(endpoint, { method: 'POST', body: { dry_run: true } }); } catch (e) { body.replaceChildren(h('p', { class: 'note bad' }, e.message)); return; }
  const text = h('input', { type: 'text', autocomplete: 'off', 'aria-label': 'Type the hostname' }), any = h('input', { type: 'checkbox' });
  const sync = () => { go.disabled = (pre.blocked.length && !(pre.needs_text && any.checked)) || (pre.needs_text && text.value.trim().toLowerCase() !== pre.needs_text.toLowerCase()); };
  body.replaceChildren(h('div', {}, h('ul', { style: 'margin:0 0 12px;padding-left:20px' }, pre.plan.map(p => h('li', {}, p))),
    pre.blocked.length > 0 && h('p', { class: 'note' }, `Right now ${pre.blocked.join(' and ')}. ${pre.needs_text ? 'It is safer to wait.' : 'Try again when it has finished.'}`),
    pre.blocked.length > 0 && pre.needs_text && h('label', { class: 'check' }, any, 'Run it anyway'), pre.needs_text && h('label', { class: 'f' }, `Type ${pre.needs_text} to confirm`, text)));
  text.oninput = sync; any.onchange = sync; sync();
  go.onclick = async () => { go.disabled = true; try { const r = await api(endpoint, { method: 'POST', body: { confirm: true, confirm_text: text.value, run_anyway: any.checked } }); S.seen[r.task] = 'running'; S.fastUntil = Date.now() + 90000; closeDlg(); toast(title + ' started'); if (onStarted) onStarted(r.task); pollNow(); }
    catch (e) { body.prepend(h('p', { class: 'note bad' }, e.message)); go.disabled = false; } };
}
function hostAction(action) { const d = dev(); if (!d) return; const n = sysOf().hostname || d.name; confirmAction({ title: `${action === 'restart' ? 'Restart' : 'Shut down'} ${n}`, endpoint: `/devices/${d.id}/host/${action}`, confirmLabel: action === 'restart' ? 'Restart' : 'Shut down', danger: true }); }

/* ---------- Dashboard ---------- */
const ORDER = ['fav', 'sys', 'cpu', 'net', 'sto', 'disks', 'apps', 'pcs', 'al'];
function layout() {
  try { const l = JSON.parse(localStorage.getItem('tp.layout')); if (l && Array.isArray(l.order)) { const hid = (l.hidden || []).filter(i => ORDER.includes(i)), ord = l.order.filter(i => ORDER.includes(i)); ORDER.forEach(i => { if (!ord.includes(i) && !hid.includes(i)) ord.push(i); }); return { order: ord, hidden: hid }; } } catch (e) { /* fall through */ }
  return { order: ORDER.slice(), hidden: [] };
}
const cfgOn = () => { S.cfgDraft = layout(); renderMain(); };
const cfgSave = () => { localStorage.setItem('tp.layout', JSON.stringify(S.cfgDraft)); S.cfgDraft = null; renderMain(); toast('Dashboard saved'); };
const cfgCancel = () => { S.cfgDraft = null; renderMain(); };
const noNas = () => h('div', {}, h('h1', {}, 'Add your NAS'), h('p', { class: 'mute' }, 'TruePilot needs the address of your TrueNAS and a read-only API key.'), h('button', { class: 'btn', onclick: () => deviceDialog() }, 'Add device'));
function offlineView(d, s) {
  return h('div', {}, h('div', { class: 'dh' }, h('h1', {}, d.name)), h('div', { class: 'card' }, h('div', { class: 'cb' }, h('div', { style: 'display:flex;gap:12px;align-items:center;margin-bottom:8px' }, lamp('bad'), h('b', {}, 'Can\'t reach this NAS')),
    h('p', { class: 'mute', style: 'margin:0 0 12px' }, s.error), h('div', { class: 'acts' }, d.mac && h('button', { class: 'btn', onclick: () => wakeDevice(d) }, 'Send Wake-on-LAN'),
      h('button', { class: 'btn ghost', onclick: () => { S.last = 0; pollNow(); } }, 'Try again'), h('button', { class: 'btn ghost', onclick: () => deviceDialog(d) }, 'Check settings')))));
}
const cardLink = (t, href) => h('a', { class: 'link', href: '#/' + href, style: 'text-decoration:none' }, t);
const CARDS = {
  fav: { t: 'Favourites', flush: true, link: ['Apps', 'apps'], body: (s, res, d) => { const fl = sortApps((s.apps || []).filter(a => a.fav)); return !fl.length ? h('p', { class: 'empty' }, 'Star an app on the Apps page to pin it here.') :
    fl.map(a => h('div', { class: 'row' }, lamp(appLamp(a)), h('div', { class: 't', style: 'display:flex;gap:8px;align-items:center' }, a.icon && avatarOf(a, true), a.title),
      h('span', { class: 'tail', style: 'display:flex;gap:12px;align-items:center' }, a.state === 'RUNNING' && appLinks(a).length > 0 ? h('button', { class: 'btn small', 'aria-label': 'Open ' + a.title, onclick: () => openApp(d, a) }, 'Open') : h('span', { class: 'mute small' }, appWord(a))), h('div', { class: 's' }, a.version ? 'Version ' + a.version : ''))); } },
  sys: { t: 'System information', body: (s) => { const y = s.system; return [kv('Hostname', y.hostname || '-'), kv('Version', 'TrueNAS ' + (y.version || '').replace(/^TrueNAS-/, '')), kv('Uptime', uptime(y.uptime)), kv('Model', y.model || '-'), kv('Timezone', y.timezone || '-'),
    y.update?.available && h('p', { style: 'margin:8px 0 0' }, h('span', { class: 'chip acc' }, 'Update available' + (y.update.version ? ' ' + y.update.version : '')))]; } },
  cpu: { t: 'CPU and memory', body: (s, res) => { const y = s.system, hs = res.history || {}, mu = y.mem_used, mt = y.mem_total;
    return [h('div', { style: 'display:flex;justify-content:space-between;align-items:baseline' }, h('span', { class: 'big num' }, y.cpu != null ? Math.round(y.cpu) + '%' : (y.load ? y.load[0].toFixed(2) : '-')), h('span', { class: 'mute small' }, `${y.cores || '?'} cores${y.cpu == null ? ', load average' : ''}`)),
      spark(hs.cpu, 'var(--acc)', 100), kv('Memory', mu != null ? `${jn(bin(mu))} of ${jn(bin(mt))}` : (mt ? jn(bin(mt)) + ' installed' : '-')), mu != null && h('div', { class: 'prog' }, h('i', { style: `width:${Math.round(100 * mu / mt)}%` }))]; } },
  net: { t: 'Network', wide: true, body: (s, res, d) => { const y = s.system, n = s.network, hs = res.history || {}, main = n && (n.ports.find(p => p.up && p.addrs.length) || n.ports[0]), a0 = main && main.addrs[0];
    const traffic = h('div', { style: 'display:flex;gap:18px;flex-wrap:wrap' }, h('div', {}, h('div', { class: 'mute small' }, 'In'), h('span', { class: 'big num' }, y.net_rx != null ? jn(bin(y.net_rx)) + '/s' : '-')), h('div', {}, h('div', { class: 'mute small' }, 'Out'), h('span', { class: 'big num' }, y.net_tx != null ? jn(bin(y.net_tx)) + '/s' : '-')));
    if (!n) return [traffic, spark(hs.rx, 'var(--acc)')];
    const portEl = p => h('div', { class: 'port' }, h('div', { style: 'display:flex;gap:8px;align-items:center' }, lamp(p.up ? 'ok' : 'off'), h('b', {}, p.name), h('span', { class: 'mute small' }, p.up ? (p.speed || 'up') : 'down')),
      p.addrs.map(a => h('div', { class: 'kv' }, h('span', {}, 'IP address'), copyBtn(`${a.ip}${a.prefix ? '/' + a.prefix : ''}`))), p.mac && h('div', { class: 'kv' }, h('span', {}, 'MAC address'), copyBtn(p.mac)),
      p.mac && h('button', { class: 'btn small ghost', style: 'margin-top:6px', onclick: async () => { try { await api(`/devices/${d.id}/wol`, { method: 'PATCH', body: { mac: p.mac, broadcast: (p.addrs[0] || {}).broadcast || '' } }); await loadDevices(); toast('Saved for Wake-on-LAN'); } catch (e) { toast(e.message, true); } } }, 'Use for Wake-on-LAN'));
    return [traffic, spark(hs.rx, 'var(--acc)'), main && h('div', { class: 'kv' }, h('span', {}, `${main.name}${main.speed ? ', ' + main.speed : ''}`), a0 ? copyBtn(`${a0.ip}${a0.prefix ? '/' + a0.prefix : ''}`) : h('span', { class: 'mute' }, 'no address')),
      h('details', { open: S.open.has('net'), ontoggle: e => (e.target.open ? S.open.add('net') : S.open.delete('net')) }, h('summary', {}, 'All ports, gateway and DNS'), n.ports.map(portEl),
        h('div', { style: 'border-top:1px solid var(--line);margin-top:6px;padding-top:6px' }, n.gateway && h('div', { class: 'kv' }, h('span', {}, 'Gateway'), copyBtn(n.gateway)), n.dns.length > 0 && h('div', { class: 'kv' }, h('span', {}, 'DNS servers'), h('span', {}, n.dns.map((x, i) => [i ? ', ' : '', copyBtn(x)]))), kv('Hostname', [n.hostname, n.domain].filter(Boolean).join('.') || '-')))]; } },
  sto: { t: 'Storage', wide: true, body: (s) => !s.pools ? h('p', { class: 'mute' }, 'Pool details could not be loaded.') : !s.pools.length ? h('p', { class: 'mute' }, 'No pools yet.') :
    [h('div', { class: 'rings' }, s.pools.map(p => { const bad = p.status !== 'ONLINE' || p.healthy === false, col = bad ? 'var(--bad)' : p.pct >= 85 ? 'var(--warn)' : 'var(--acc)';
      return h('div', {}, h('div', { class: 'ringb' }, ring(p.name, col, p.pct), h('div', {}, h('div', { style: 'font-weight:600' }, p.name), h('div', { class: 'mute small num' }, `${jn(bin(p.allocated))} of ${jn(bin(p.size))}`), h('div', {}, h('span', { class: 'chip' + (bad ? ' bad' : '') }, p.status.toLowerCase()), p.scan?.state === 'SCANNING' && h('span', { class: 'chip acc', style: 'margin-left:4px' }, `${p.scan.function === 'RESILVER' ? 'Resilvering' : 'Scrubbing'} ${p.scan.pct != null ? Math.round(p.scan.pct) + '%' : ''}`)))),
        p.vdevs.length > 0 && h('details', { open: S.open.has('p:' + p.name), ontoggle: e => (e.target.open ? S.open.add('p:' + p.name) : S.open.delete('p:' + p.name)) }, h('summary', {}, 'Layout'), p.vdevs.map(v => h('div', { class: 'small', style: 'margin:4px 0' }, `${v.role === 'data' ? '' : v.role + ' '}${v.name || v.type || ''}: ${(v.disks || []).map(k => k.name).join(', ')}`))));
    }))] },
  disks: { t: 'Disks', flush: true, body: (s) => !s.disks ? h('p', { class: 'empty' }, 'Disk details could not be loaded.') : !s.disks.length ? h('p', { class: 'empty' }, 'No disks found.') : s.disks.map(d => { const [w, b] = d.type === 'SSD' ? [70, 80] : [50, 60], t = d.temp, st = d.smart === 'fail' ? 'bad' : typeof t !== 'number' ? 'unk' : t >= b ? 'bad' : t >= w ? 'warn' : 'ok';
    return h('div', { class: 'row' }, lamp(st), h('div', { class: 't' }, d.name), h('span', { class: 'num', style: 'grid-row:span 2;grid-column:3;font-weight:600' }, typeof t === 'number' ? t.toFixed(0) + '°C' : '-'), h('div', { class: 's' }, `${d.model || 'Unknown'}, ${jn(dec(d.size))}${d.pool ? ', ' + d.pool : ''}${d.smart === 'fail' ? ', last test failed' : ''}`)); }) },
  apps: { t: 'Apps', flush: true, link: ['Manage', 'apps'], body: (s, res, d) => !s.apps ? h('p', { class: 'empty' }, 'Apps could not be loaded.') : !s.apps.length ? h('p', { class: 'empty' }, 'No apps installed.') : sortApps(s.apps).map(a => h('div', { class: 'row' }, lamp(appLamp(a)), h('div', { class: 't', style: 'display:flex;gap:8px;align-items:center' }, a.icon && avatarOf(a, true), a.title),
    h('span', { class: 'tail', style: 'display:flex;gap:12px;align-items:center' }, a.state === 'RUNNING' && appLinks(a).length > 0 && h('button', { class: 'link', 'aria-label': 'Open ' + a.title, onclick: () => openApp(d, a) }, 'Open'), a.upgrade ? h('span', { class: 'chip acc' }, 'Update') : h('span', { class: 'mute small' }, appWord(a))), h('div', { class: 's' }, a.version ? 'Version ' + a.version : ''))) },
  pcs: { t: 'Your PCs', flush: true, link: ['Manage', 'power'], body: () => S.pcs.length ? S.pcs.map(p => pcRow(p, false)) : h('p', { class: 'empty' }, 'No PCs yet. Add one in the Power tab.') },
  al: { t: 'Alerts', flush: true, body: (s) => !s.alerts ? h('p', { class: 'empty' }, 'Alerts could not be loaded.') : !s.alerts.length ? h('p', { class: 'empty' }, 'No active alerts.') : s.alerts.map(a => h('div', { class: 'row' }, lamp(LV[a.level] || 'unk'), h('div', {}, a.text), h('span'), h('div', { class: 's' }, a.level.toLowerCase() + (a.when ? ', ' + ago(a.when) : '')))) },
};
const appLamp = a => ({ RUNNING: 'ok', STOPPED: 'off', DEPLOYING: 'run', CRASHED: 'bad' })[a.state] || 'off';
const appWord = a => ({ RUNNING: 'Running', STOPPED: 'Stopped', DEPLOYING: 'Working', CRASHED: 'Crashed' })[a.state] || a.state.toLowerCase();
function pageDash() {
  const d = dev(); if (!d) return noNas(); if (S.err) return h('p', { class: 'note bad' }, 'TruePilot can\'t be reached: ' + S.err);
  const res = S.res; if (!res) return h('p', { class: 'empty' }, 'Loading...'); const s = res.snapshot; if (!s.ok) return offlineView(d, s);
  const cfgMode = !!S.cfgDraft, lay = S.cfgDraft || layout(), L = s.lamps, names = { link: 'Connection', pools: 'Pools', disks: 'Disks', apps: 'Apps', alerts: 'Alerts' }, target = { link: 'top', pools: 'c-sto', disks: 'c-disks', apps: 'c-apps', alerts: 'c-al' };
  const mv = (id, dlt) => { const o = S.cfgDraft.order, i = o.indexOf(id), j = i + dlt; if (j < 0 || j >= o.length) return; o.splice(i, 1); o.splice(j, 0, id); renderMain(); };
  const card = (id, ix) => { const c = CARDS[id];
    return h('section', { class: 'card' + (c.wide ? ' wide' : ''), id: 'c-' + id },
      cfgMode && h('div', { class: 'cfgbar' }, h('b', {}, c.t), h('button', { class: 'btn small ghost', disabled: ix === 0, 'aria-label': 'Move up', onclick: () => mv(id, -1) }, icon('arrowUp')), h('button', { class: 'btn small ghost', disabled: ix === lay.order.length - 1, 'aria-label': 'Move down', onclick: () => mv(id, 1) }, icon('arrowDown')),
        h('button', { class: 'btn small ghost', onclick: () => { lay.order.splice(lay.order.indexOf(id), 1); lay.hidden.push(id); renderMain(); } }, 'Hide')),
      h('div', { class: 'ch' }, h('h3', {}, c.t), c.link && cardLink(c.link[0], c.link[1])), h('div', { class: 'cb' + (c.flush ? ' flush' : '') }, c.body(s, res, d))); };
  return h('div', { id: 'top' }, h('div', { class: 'dh' }, h('h1', {}, 'Dashboard'), cfgMode ? h('div', { class: 'acts' }, h('button', { class: 'btn small', onclick: cfgSave }, 'Save'), h('button', { class: 'btn small ghost', onclick: cfgCancel }, 'Cancel')) : h('button', { class: 'btn small ghost', onclick: cfgOn }, 'Configure')),
    h('div', { class: 'lamps' }, Object.keys(names).map(k => h('button', { class: 'lp', title: L[k].text, onclick: () => { document.getElementById(target[k])?.scrollIntoView({ behavior: 'smooth', block: 'start' }); toast(`${names[k]}: ${L[k].text}`); } }, lamp(L[k].state), names[k], h('small', {}, L[k].text)))),
    Object.keys(s.errors || {}).length > 0 && h('p', { class: 'note' }, 'Some readings could not be loaded: ' + Object.entries(s.errors).map(([k, v]) => `${k} (${v})`).join('; ') + '. Settings > Run diagnostics shows more.'),
    h('div', { class: 'grid' }, lay.order.map(card)),
    cfgMode && lay.hidden.length > 0 && h('div', { class: 'hidbox' }, h('p', { class: 'mute small', style: 'margin:0 0 6px' }, 'Hidden cards'), lay.hidden.map(id => h('div', { style: 'display:flex;justify-content:space-between;align-items:center;padding:3px 0' }, CARDS[id].t,
      h('button', { class: 'btn small ghost', onclick: () => { lay.hidden.splice(lay.hidden.indexOf(id), 1); lay.order.push(id); renderMain(); } }, 'Add back')))));
}

/* ---------- Apps ---------- */
S.appFilter = 'all'; S.appView = localStorage.getItem('tp.appview') || 'cards'; S.appSort = localStorage.getItem('tp.appsort') || 'az';
const byName = (x, y) => x.title.localeCompare(y.title, undefined, { sensitivity: 'base', numeric: true });
const favFirst = x => [...x.filter(a => a.fav), ...x.filter(a => !a.fav)];
function sortApps(list) {
  const l = list.slice(), rank = a => (a.state === 'RUNNING' ? 0 : a.state === 'STOPPED' ? 2 : 1);
  if (S.appSort === 'za') l.sort((x, y) => byName(y, x)); else if (S.appSort === 'status') l.sort((x, y) => rank(x) - rank(y) || byName(x, y));
  else if (S.appSort === 'updates') l.sort((x, y) => (y.upgrade - x.upgrade) || byName(x, y)); else l.sort(byName);
  return favFirst(l);
}
const appLinks = a => [...(a.custom ? [{ name: 'My link', url: a.custom, source: 'custom' }] : []), ...(a.links || [])];
function openApp(d, a) { const ls = appLinks(a); if (ls.length === 1) openUrl(ls[0].url); else linkDialog(d, a); }
function linkDialog(d, a) {
  const ls = appLinks(a), msg = msgBox(), url = h('input', { type: 'text', autocomplete: 'off', value: a.custom || '', placeholder: 'http://192.168.1.50:8123' });
  const save = h('button', { class: 'btn' }, 'Save my link'), del = a.custom && h('button', { class: 'btn ghost danger', style: 'margin-right:auto' }, 'Remove my link');
  save.onclick = async () => { try { await api(`/devices/${d.id}/apps/${encodeURIComponent(a.name)}/link`, { method: 'PUT', body: { url: url.value } }); closeDlg(); S.last = 0; pollNow(); toast('Link saved'); } catch (e) { msg.set(e.message); } };
  if (del) del.onclick = async () => { await api(`/devices/${d.id}/apps/${encodeURIComponent(a.name)}/link`, { method: 'DELETE' }); closeDlg(); S.last = 0; pollNow(); };
  modal(a.title, h('div', {}, ls.length ? h('div', { style: 'margin:-6px -16px 10px' }, ls.map(l => h('a', { class: 'it', href: l.url, target: '_blank', rel: 'noopener', style: 'text-decoration:none' }, icon('right'), l.name, h('span', { class: 'r mono' }, l.source === 'guess' ? 'guessed' : l.source === 'custom' ? 'mine' : '')))) : h('p', { class: 'note' }, 'TrueNAS doesn\'t list a web address for this app. Type one below and TruePilot will remember it.'),
    h('label', { class: 'f' }, 'My own link', url, h('small', {}, 'Optional. It is added to the list above, and is used by the Open buttons.')), msg), [del, h('button', { class: 'btn ghost', onclick: closeDlg }, 'Close'), save]);
  const dl = $('#dlg'); dl.tabIndex = -1; dl.focus();
}
S.iconOk = new Set(); S.iconBad = new Set();
const hueOf = t => { let x = 0; for (const c of String(t)) x = (x * 31 + c.charCodeAt(0)) % 360; return x; };
function avatarOf(a, small) {
  const words = a.title.split(/\s+/), letters = (words.length > 1 ? words.map(x => x[0]).join('').slice(0, 2) : a.title.slice(0, 2)).replace(/^./, c => c.toUpperCase());
  const hue = hueOf(a.name || a.title), el = h('span', { class: 'avatar' + (small ? ' sm' : ''), style: `background:hsl(${hue} 45% 32% / .35);color:hsl(${hue} 70% 68%)` }, small ? '' : letters);
  if (a.icon && !S.iconBad.has(a.icon)) {
    const img = new Image(); img.alt = ''; img.referrerPolicy = 'no-referrer';
    const show = () => { el.classList.add('logo'); el.style.cssText = ''; el.replaceChildren(img); };
    img.onload = () => { S.iconOk.add(a.icon); show(); }; img.onerror = () => S.iconBad.add(a.icon);
    img.src = a.icon; if (S.iconOk.has(a.icon)) show();
  }
  return el;
}
const openUrl = u => (window.TPNative ? window.TPNative.openUrl(u) : window.open(u, '_blank', 'noopener'));
document.addEventListener('click', e => { const a = window.TPNative && e.target.closest && e.target.closest('a[href^="http"]'); if (a) { e.preventDefault(); openUrl(a.href); } });
S.appQuery = ''; S.appSelect = false; S.appSel = new Set();
async function toggleFav(d, a) {
  const was = !!a.fav; a.fav = !was; renderMain();
  try { await api(`/devices/${d.id}/apps/${encodeURIComponent(a.name)}/favourite`, { method: was ? 'DELETE' : 'PUT' }); S.last = 0; } catch (e) { a.fav = was; renderMain(); toast(e.message, true); }
}
function logsDialog(d, a) {
  let cid = '';
  const pre = h('pre', { class: 'logs' }, 'Loading...'), cs = h('select', { class: 'sel', style: 'display:none', 'aria-label': 'Container' }), n = h('select', { class: 'sel', 'aria-label': 'Lines' }, [100, 200, 500].map(v => h('option', { value: v, selected: v === 200 }, v + ' lines')));
  const note = h('p', { class: 'note', style: 'display:none' }), auto = h('input', { type: 'checkbox' });
  async function load() {
    try { const r = await api(`/devices/${d.id}/apps/${encodeURIComponent(a.name)}/logs?lines=${n.value}` + (cid ? `&container=${encodeURIComponent(cid)}` : ''));
      cid = r.container; cs.replaceChildren(...r.containers.map(c => h('option', { value: c.id, selected: c.id === cid }, c.name))); cs.style.display = r.containers.length > 1 ? '' : 'none';
      pre.textContent = r.lines.length ? r.lines.join('\n') : '(no lines)'; note.style.display = r.note ? '' : 'none'; note.textContent = r.note + (r.debug && r.debug.length ? ' ' + JSON.stringify(r.debug) : ''); pre.scrollTop = pre.scrollHeight; }
    catch (e) { pre.textContent = e.message; }
  }
  cs.onchange = () => { cid = cs.value; load(); }; n.onchange = load;
  const timer = setInterval(() => { if (!$('#dlg').open) clearInterval(timer); else if (auto.checked) load(); }, 6000);
  const dlg = modal(`${a.title}: logs`, h('div', {}, h('div', { class: 'acts', style: 'align-items:center;margin-bottom:6px' }, cs, n, h('label', { class: 'check', style: 'margin:0' }, auto, 'Keep refreshing')), note, pre),
    [h('button', { class: 'btn ghost', onclick: async () => { try { await navigator.clipboard.writeText(pre.textContent); toast('Logs copied'); } catch (e) { toast('Could not copy', true); } } }, 'Copy'), h('button', { class: 'btn ghost', onclick: load }, 'Refresh now'), h('button', { class: 'btn', onclick: closeDlg }, 'Close')]);
  dlg.style.width = 'min(900px, calc(100vw - 24px))'; dlg.tabIndex = -1; dlg.focus(); load();
}
async function bulkAction(d, act, names) {
  const all = (S.res?.snapshot?.apps || []).filter(x => names.includes(x.name));
  const fits = { start: x => x.state === 'STOPPED', stop: x => x.state !== 'STOPPED', restart: x => x.state !== 'STOPPED', upgrade: x => x.upgrade }[act];
  const targets = all.filter(fits), label = act[0].toUpperCase() + act.slice(1);
  if (!targets.length) return toast(`None of the selected apps can be ${act}${act.endsWith('e') ? 'd' : 'ed'} right now.`, true);
  const list = h('div', {}), cancel = h('button', { class: 'btn ghost', onclick: closeDlg }, 'Cancel'), go = h('button', { class: 'btn', disabled: true }, `${label} ${targets.length} app${targets.length > 1 ? 's' : ''}`);
  modal(`${label} ${targets.length} app${targets.length > 1 ? 's' : ''}`, h('div', {}, h('p', { class: 'mute', id: 'bulkhint' }, 'Checking...'), list), [cancel, go]);
  const plans = await Promise.all(targets.map(a => api(`/devices/${d.id}/apps/${a.name}/${act}`, { method: 'POST', body: { dry_run: true } }).then(r => ({ a, r }), e => ({ a, err: e.message }))));
  const rows = new Map(), line = (a, st, text) => { const r = rows.get(a.name) || h('div', { class: 'row', style: 'padding-left:0;padding-right:0' }); r.replaceChildren(lamp(st), h('div', { class: 't' }, a.title), h('span'), h('div', { class: 's' }, text)); rows.set(a.name, r); return r; };
  const runnable = plans.filter(p => p.r && p.r.can_run);
  list.replaceChildren(...plans.map(p => line(p.a, p.r && p.r.can_run ? 'unk' : 'warn', p.err ? p.err : p.r.can_run ? p.r.plan[0] : 'Skipped: ' + p.r.blocked.join(' and '))));
  all.filter(x => !fits(x)).forEach(x => list.append(h('div', { class: 'row', style: 'padding-left:0;padding-right:0' }, lamp('off'), h('div', { class: 't' }, x.title), h('span'), h('div', { class: 's' }, 'Not changed: ' + (act === 'start' ? 'already running' : act === 'upgrade' ? 'no update' : 'already stopped')))));
  $('#bulkhint').textContent = runnable.length ? 'They run one at a time. Nothing starts until you confirm.' : 'None of them can run right now.'; go.disabled = !runnable.length;
  go.onclick = async () => {
    go.disabled = true; cancel.disabled = true; $('#bulkhint').textContent = 'Working, please keep this open...'; let okN = 0, bad = 0;
    for (const p of runnable) {
      line(p.a, 'run', 'Working...');
      try { const r = await api(`/devices/${d.id}/apps/${p.a.name}/${act}`, { method: 'POST', body: { confirm: true } }); let t = null;
        for (let i = 0; i < 1800; i++) { await wait(1500); const ac = await api('/activity'); t = ac.tasks.find(x => x.id === r.task); if (t && t.status !== 'running') break; }
        if (t && t.status === 'done') { okN++; line(p.a, 'ok', t.message); } else { bad++; line(p.a, 'bad', t ? t.message : 'No answer from TrueNAS'); } }
      catch (e) { bad++; line(p.a, 'bad', e.message); }
    }
    $('#bulkhint').textContent = `Finished: ${okN} done${bad ? ', ' + bad + ' failed' : ''}.`; cancel.disabled = false; cancel.textContent = 'Close'; S.appSel.clear(); S.last = 0; pollNow();
  };
}
function pageApps() {
  const d = dev(); if (!d) return noNas(); if (S.err) return h('p', { class: 'note bad' }, 'TruePilot can\'t be reached: ' + S.err);
  const res = S.res; if (!res) return h('p', { class: 'empty' }, 'Loading...'); const s = res.snapshot; if (!s.ok) return offlineView(d, s);
  const can = writeOn(d, res), running = S.tasks.filter(t => t.status === 'running'), apps = s.apps || [], f = S.appFilter, q = S.appQuery.trim().toLowerCase();
  const cnt = { all: apps.length, run: apps.filter(a => a.state !== 'STOPPED').length, stop: apps.filter(a => a.state === 'STOPPED').length, up: apps.filter(a => a.upgrade).length };
  const list = sortApps(apps.filter(a => (f === 'all' || (f === 'run' && a.state !== 'STOPPED') || (f === 'stop' && a.state === 'STOPPED') || (f === 'up' && a.upgrade)) && (!q || a.title.toLowerCase().includes(q) || a.name.toLowerCase().includes(q))));
  const btn = (txt, a, act, off) => h('button', { class: 'btn small ghost', disabled: !can || off, onclick: () => confirmAction({ title: `${txt} ${a.title}`, endpoint: `/devices/${d.id}/apps/${a.name}/${act}`, confirmLabel: txt }) }, txt);
  const openBtn = a => { const n = appLinks(a).length; return n ? h('button', { class: 'btn small', disabled: a.state === 'STOPPED', title: a.state === 'STOPPED' ? 'Start the app first' : '', onclick: () => openApp(d, a) }, 'Open', n > 1 ? ' ...' : '') : h('button', { class: 'btn small ghost', onclick: () => linkDialog(d, a) }, 'Add link'); };
  const acts = (a, work, cls) => { if (work || S.appSelect) return false;
    if (cls === 'inl') return h('div', { class: 'acts inl' }, openBtn(a), a.state === 'STOPPED' ? btn('Start', a, 'start') : btn('Restart', a, 'restart'), a.state === 'STOPPED' ? h('span', { class: 'slot' }) : btn('Stop', a, 'stop'), a.upgrade ? btn('Upgrade', a, 'upgrade') : h('span', { class: 'slot' }));
    return h('div', { class: 'acts ' + cls }, openBtn(a), a.state === 'STOPPED' ? btn('Start', a, 'start') : [btn('Restart', a, 'restart'), btn('Stop', a, 'stop')], a.upgrade && btn('Upgrade', a, 'upgrade')); };
  const status = (a, work) => h('div', { class: 's', style: 'display:flex;gap:6px;align-items:center;white-space:nowrap' }, lamp(work ? 'run' : appLamp(a)), `${work ? 'Working' : appWord(a)}${a.version ? ', ' + a.version : ''}`);
  const isWork = a => a.state === 'DEPLOYING' || running.some(t => t.target === 'app:' + a.name);
  const star = a => h('button', { class: 'star' + (a.fav ? ' on' : ''), 'aria-label': (a.fav ? 'Remove ' : 'Add ') + a.title + (a.fav ? ' from favourites' : ' to favourites'), 'aria-pressed': String(!!a.fav), onclick: () => toggleFav(d, a) }, icon('star'));
  const logsBtn = a => h('button', { class: 'star', 'aria-label': 'Logs for ' + a.title, title: 'Logs', onclick: () => logsDialog(d, a) }, icon('logs'));
  const pick = a => S.appSelect && h('input', { type: 'checkbox', class: 'pick', 'aria-label': 'Select ' + a.title, checked: S.appSel.has(a.name), onchange: e => { e.target.checked ? S.appSel.add(a.name) : S.appSel.delete(a.name); renderMain(); } });
  const cards = h('div', { class: 'tiles' }, list.map(a => { const work = isWork(a);
    return h('section', { class: 'card' }, h('div', { class: 'row', style: 'border-top:0' }, avatarOf(a), h('div', { class: 't' }, pick(a), a.title, star(a), logsBtn(a)), a.upgrade ? h('span', { class: 'chip acc', style: 'grid-row:span 2' }, 'Update') : h('span'), status(a, work)), acts(a, work, 'pin')); }));
  const rows = h('section', { class: 'card applist' }, list.map(a => { const work = isWork(a);
    return h('div', { class: 'row approw' }, avatarOf(a), h('div', { class: 't' }, pick(a), a.title, star(a), logsBtn(a), a.upgrade && h('span', { class: 'chip acc', style: 'margin-left:8px' }, 'Update')), acts(a, work, 'inl') || h('span'), status(a, work)); }));
  const sel = h('select', { class: 'sel', 'aria-label': 'Sort apps', onchange: e => { S.appSort = e.target.value; localStorage.setItem('tp.appsort', S.appSort); renderMain(); } },
    [['az', 'Name A to Z'], ['za', 'Name Z to A'], ['status', 'Running first'], ['updates', 'Updates first']].map(([v, t]) => h('option', { value: v, selected: S.appSort === v }, t)));
  const chosen = apps.filter(a => S.appSel.has(a.name)), has = fn => chosen.some(fn);
  const bar = S.appSelect && h('div', { class: 'selbar' }, h('b', {}, `${chosen.length} selected`), h('span', { class: 'acts', style: 'margin-left:auto' },
    ...[['Start', 'start', a => a.state === 'STOPPED'], ['Restart', 'restart', a => a.state !== 'STOPPED'], ['Stop', 'stop', a => a.state !== 'STOPPED'], ['Upgrade', 'upgrade', a => a.upgrade]].map(([t, act, fn]) => h('button', { class: 'btn small', disabled: !can || !has(fn), onclick: () => bulkAction(d, act, chosen.map(x => x.name)) }, t)),
    h('button', { class: 'btn small ghost', onclick: () => { S.appSelect = false; S.appSel.clear(); renderMain(); } }, 'Done')));
  return h('div', {}, h('div', { class: 'dh' }, h('h1', {}, 'Apps'), h('span', { class: 'mute' }, d.name)),
    !can && h('p', { class: 'note' }, res.read_only ? 'Read-only mode is on, so actions are disabled. Turn it off in Settings.' : 'Actions are off for this NAS. Add a write key and turn them on in Settings. Open buttons still work.'),
    h('div', { class: 'bar2' }, h('div', { class: 'chips' }, [['all', 'All'], ['run', 'Running'], ['stop', 'Stopped'], ['up', 'Updates']].map(([k, t]) => h('button', { class: 'fchip', 'aria-pressed': String(f === k), onclick: () => { S.appFilter = k; renderMain(); } }, `${t} ${cnt[k]}`))),
      h('div', { class: 'acts', style: 'align-items:center' }, h('input', { type: 'search', id: 'appq', class: 'sel', placeholder: 'Search apps', 'aria-label': 'Search apps', value: S.appQuery, oninput: e => { S.appQuery = e.target.value; renderMain(); } }), sel,
        h('button', { class: 'btn small ' + (S.appSelect ? '' : 'ghost'), 'aria-pressed': String(S.appSelect), onclick: () => { S.appSelect = !S.appSelect; if (!S.appSelect) S.appSel.clear(); renderMain(); } }, 'Select'),
        h('div', { class: 'seg', role: 'group', 'aria-label': 'View' }, [['cards', 'Cards'], ['list', 'List']].map(([v, t]) => h('button', { 'aria-pressed': String(S.appView === v), onclick: () => { S.appView = v; localStorage.setItem('tp.appview', v); renderMain(); } }, t))))),
    list.length ? (S.appView === 'list' ? rows : cards) : h('p', { class: 'empty' }, q ? 'No apps match your search.' : 'Nothing to show.'), bar);
}

/* ---------- Power ---------- */
function pagePower() {
  const d = dev(), res = S.res, s = res?.snapshot, can = writeOn(d, res), on = !!(s && s.ok), wj = (S.sched?.jobs || []).filter(j => j.kind === 'wake'), anyOff = S.pcs.some(p => p.state === 'off' || p.state === 'unknown');
  const pcs = h('section', { class: 'card' }, h('div', { class: 'ch' }, h('h3', {}, 'Your PCs', h('span', { class: 'sub' }, 'Wake-on-LAN list')), h('button', { class: 'link', onclick: () => pcForm() }, 'Add a PC')),
    h('div', { class: 'cb flush' }, S.pcs.length ? S.pcs.map(p => pcRow(p, false, true)) : h('p', { class: 'empty' }, 'No PCs yet. Add one with its MAC address.')),
    wakeOnly() && h('p', { class: 'note', style: 'margin:12px 14px 0' }, 'Add your NAS here too: enter its IP address, press Find MAC while it is on, then save. Or add the NAS as a device in Settings and TruePilot finds its MAC by itself.'),
    h('div', { class: 'cb foot' }, ['on', 'off', 'waking'].map(x => h('span', { class: 'mute small', style: 'display:flex;gap:6px;align-items:center' }, lamp(x), x[0].toUpperCase() + x.slice(1))),
      h('span', { style: 'margin-left:auto' }, h('button', { class: 'btn small ghost', disabled: !anyOff, onclick: () => S.pcs.filter(p => p.state === 'off' || p.state === 'unknown').forEach(wakePc) }, 'Wake all that are off'))));
  const nas = d && h('section', { class: 'card' }, h('div', { class: 'ch' }, h('h3', {}, 'This NAS', h('span', { class: 'sub' }, d.name))),
    h('div', { class: 'row', style: 'border-top:0' }, lamp(!s ? 'unk' : on ? 'ok' : 'bad'), h('div', { class: 't' }, !s ? 'Connecting...' : on ? 'Online' : 'Offline'), h('span'), h('div', { class: 's' }, on ? 'Up ' + uptime(sysOf().uptime) : 'Not answering')),
    h('div', { class: 'acts pin' }, on ? [h('button', { class: 'btn small ghost', disabled: !can, onclick: () => hostAction('restart') }, 'Restart'), h('button', { class: 'btn small danger', disabled: !can, onclick: () => hostAction('shutdown') }, 'Shut down')] : (d.mac ? h('button', { class: 'btn small', onclick: () => wakeDevice(d) }, 'Wake') : h('span', { class: 'mute small' }, 'Its MAC address is saved the first time it connects.'))),
    !can && on && h('p', { class: 'note', style: 'margin:0 14px 12px' }, 'Actions are off for this NAS. Turn them on in Settings.'));
  const sched = h('section', { class: 'card' + (d ? '' : ' wide') }, h('div', { class: 'ch' }, h('h3', {}, 'Scheduled wake'), cardLink('Open Schedules', 'sched')),
    wj.length ? wj.map(j => h('div', { class: 'row' }, lamp(j.enabled ? 'ok' : 'off'), h('div', { class: 't' }, j.target_name), h('span'), h('div', { class: 's' }, `${describeCron(j.cron)}${j.last_result ? ', last: ' + j.last_result.replace(/^ok: /, '') : ''}`))) : h('p', { class: 'empty' }, 'No wake schedules yet.'));
  const web = h('section', { class: 'card' }, h('div', { class: 'ch' }, h('h3', {}, 'Web Apps', h('span', { class: 'sub' }, 'Open anything on your network')), h('button', { class: 'link', onclick: () => webForm() }, 'Add')),
    h('div', { class: 'cb flush' }, S.webapps.length ? S.webapps.map(webRow) : h('p', { class: 'empty' }, 'No web apps yet. Add the address of anything running on your network.')));
  return h('div', {}, h('div', { class: 'dh' }, h('h1', {}, 'Power')), h('div', { class: 'grid' }, nas, pcs, web, sched));
}
function openWebApp(a) { if (S.me.app && window.TPNative && window.TPNative.openWebApp) window.TPNative.openWebApp({ url: a.url, name: a.name, kind: a.kind }); else window.open(a.url, '_blank', 'noopener'); }
function webRow(a) {
  const pc = a.wake_id != null ? S.pcs.find(p => p.id === a.wake_id) : null, canWake = !!pc && (pc.state === 'off' || pc.state === 'unknown');
  return h('div', { class: 'row wrow', role: 'link', tabindex: '0', 'aria-label': 'Open ' + a.name, onclick: () => openWebApp(a), onkeydown: e => { if (e.key === 'Enter') openWebApp(a); } },
    lamp(a.state === 'on' ? 'ok' : 'bad'), h('div', { class: 't' }, a.name, a.kind === 'truepilot' && h('span', { class: 'chip', style: 'margin-left:8px' }, 'TruePilot')),
    h('span', { class: 'tail', style: 'display:flex;gap:6px;align-items:center' }, canWake && h('button', { class: 'btn small', onclick: e => { e.stopPropagation(); wakePc(pc); } }, 'Wake'), h('button', { class: 'btn small ghost', 'aria-label': 'Edit ' + a.name, onclick: e => { e.stopPropagation(); webForm(a); } }, 'Edit')),
    h('div', { class: 's' }, `${a.host}:${a.port}${a.runs_on_name ? ', runs on ' + a.runs_on_name : ''}`));
}
function webForm(a) {
  const f = {}, out = msgBox(), inp = (k, v, o = {}) => (f[k] = h('input', Object.assign({ type: 'text', autocomplete: 'off', value: v == null ? '' : v }, o)));
  inp('name', a?.name || '', { placeholder: 'TrueNAS' }); inp('host', a ? a.host : '', { placeholder: '192.168.1.50' }); inp('port', a ? a.port : '', { inputmode: 'numeric', placeholder: '8080' });
  let secure = !!a?.secure, touched = !!a, kind = a?.kind || 'other';
  const sec = h('input', { type: 'checkbox', checked: secure, onchange: e => { secure = e.target.checked; touched = true; } });
  const runs = h('select', {}, [['', 'Nothing'], ...S.devices.filter(d => d.kind !== 'demo').map(d => ['dev:' + d.id, d.name + ' (NAS)']), ...S.pcs.filter(p => p.kind === 'pc').map(p => ['pc:' + p.id, p.name])].map(([v, t]) => h('option', { value: v, selected: v === (a?.runs_on || '') }, t)));
  const norm = () => { let t = f.host.value.trim(); const m = t.match(/^(https?):\/\/(.*)$/i); if (m) { secure = m[1].toLowerCase() === 'https'; touched = true; sec.checked = secure; t = m[2]; } t = t.split(/[\/?#]/)[0]; const pm = t.match(/^([^:]+):(\d{1,5})$/); if (pm) { t = pm[1]; f.port.value = pm[2]; } f.host.value = t; if (!touched) { secure = ['443', '8443'].includes(f.port.value.trim()); sec.checked = secure; } };
  f.host.addEventListener('change', norm); f.port.addEventListener('change', norm);
  const body = () => { norm(); return { name: f.name.value, host: f.host.value, port: Number(f.port.value) || null, secure, kind, runs_on: runs.value }; };
  const seg = h('div', { class: 'seg', role: 'group', 'aria-label': 'Type' }, [['truepilot', 'TruePilot'], ['other', 'Other']].map(([v, t]) => h('button', { type: 'button', 'aria-pressed': String(kind === v), onclick: e => { kind = v; [...e.currentTarget.parentNode.children].forEach(b => b.setAttribute('aria-pressed', String(b === e.currentTarget))); } }, t)));
  const test = h('button', { class: 'btn ghost', type: 'button' }, 'Test');
  test.onclick = async () => { const b = body(); if (!b.host) return out.set('Enter the IP address or name first.'); test.disabled = true; out.set('Checking...', false);
    try { const r = await api('/webapps/test', { method: 'POST', body: b }); if (r.up) out.set(`Answering at ${r.address}.`, false); else out.set(`No answer at ${r.address}. It may be off, or the port may be different.`); } catch (e) { out.set(e.message); } test.disabled = false; };
  const save = h('button', { class: 'btn' }, 'Save'); save.onclick = async () => { try { await api(a ? '/webapps/' + a.id : '/webapps', { method: a ? 'PUT' : 'POST', body: body() }); closeDlg(); S.last = 0; pollNow(); toast('Saved'); } catch (e) { out.set(e.message); } };
  const del = a && h('button', { class: 'btn ghost danger', style: 'margin-right:auto', onclick: async () => { if (confirm(`Remove ${a.name}?`)) { await api('/webapps/' + a.id, { method: 'DELETE' }); closeDlg(); S.last = 0; pollNow(); } } }, 'Remove');
  const L = (t, el, help) => h('label', { class: 'f' }, t, el, help && h('small', {}, help));
  modal(a ? 'Edit Web App' : 'Add a Web App', h('div', {}, L('Name', f.name), L('IP address or name', f.host, 'You can also type 192.168.1.50:8080 here and the port moves to its own box.'), L('Port', f.port, 'Optional. Leave blank for 80, or 443 when Secure is ticked.'),
    h('label', { class: 'check' }, sec, 'Secure (https)'), h('div', { class: 'f', style: 'display:flex;flex-direction:column;align-items:flex-start;gap:4px;margin-bottom:12px' }, 'Type', seg, h('small', {}, 'In the phone app, TruePilot opens inside the app. Anything else opens in the browser.')), L('Runs on', runs, 'Optional. Lets you wake that machine from here and pick it in schedules.'), out), [del, h('button', { class: 'btn ghost', onclick: closeDlg }, 'Cancel'), test, save]);
}
function pcForm(p) {
  const f = {}, inp = (k, v, o = {}) => (f[k] = h('input', Object.assign({ type: 'text', autocomplete: 'off', value: v == null ? '' : v }, o))), out = msgBox();
  inp('name', p?.name || '', { placeholder: 'Office PC' }); inp('mac', p?.mac || '', { placeholder: 'AA:BB:CC:DD:EE:FF', class: 'mono' }); inp('ip', p?.ip || '', { placeholder: '192.168.1.20' }); inp('port', p?.port || '', { inputmode: 'numeric', placeholder: 'Optional, e.g. 3389' }); inp('broadcast', p?.broadcast || '', { placeholder: '192.168.1.255 (optional)' });
  const L = (t, el, help) => h('label', { class: 'f' }, t, el, help && h('small', {}, help)), body = () => ({ name: f.name.value, mac: f.mac.value, ip: f.ip.value, port: Number(f.port.value) || null, broadcast: f.broadcast.value });
  const find = S.me.app ? h('span') : h('button', { class: 'btn small ghost', type: 'button' }, 'Find MAC from IP');
  if (!S.me.app) find.onclick = async () => { const ip = f.ip.value.trim(); if (!ip) return out.set('Enter the IP address first.'); find.disabled = true; out.set('Looking...', false);
    try { const r = await api('/net/find-mac?ip=' + encodeURIComponent(ip)); if (r.found) { f.mac.value = r.mac; out.set('Found ' + r.mac, false); } else out.set('Not found. Make sure it is on and on the same network as this computer, then try again.'); } catch (e) { out.set(e.message); } find.disabled = false; };
  const save = h('button', { class: 'btn' }, 'Save'); save.onclick = async () => { try { await api(p ? '/pcs/' + p.id : '/pcs', { method: p ? 'PUT' : 'POST', body: body() }); closeDlg(); S.last = 0; pollNow(); toast('Saved'); } catch (e) { out.set(e.message); } };
  const del = p && h('button', { class: 'btn ghost danger', style: 'margin-right:auto', onclick: async () => { if (confirm(`Remove ${p.name}?`)) { await api('/pcs/' + p.id, { method: 'DELETE' }); closeDlg(); S.last = 0; pollNow(); } } }, 'Remove');
  modal(p ? 'Edit PC' : 'Add a PC', h('div', {}, L('Name', f.name), L('IP address', f.ip, 'Used for the on/off light and to watch it start.'), L('MAC address (wired network port)', f.mac), h('div', { style: 'margin:-4px 0 12px' }, find), L('Port to check', f.port, 'Optional. Leave blank to try ping first.'), L('Broadcast address', f.broadcast), out), [del, h('button', { class: 'btn ghost', onclick: closeDlg }, 'Cancel'), save]);
}

/* ---------- Schedules ---------- */
async function loadSched() { S.sched = await api('/schedules'); return S.sched; }
async function pageSched() {
  let data; try { data = await loadSched(); } catch (e) { return h('p', { class: 'note bad' }, e.message); }
  const d = dev(), can = writeOn(d, S.res), jobs = data.jobs, refresh = () => renderMain();
  const row = j => h('div', { class: 'row' }, lamp(j.enabled ? 'ok' : 'off'), h('div', { class: 't' }, j.name), h('button', { class: 'sw', role: 'switch', 'aria-checked': String(!!j.enabled), 'aria-label': (j.enabled ? 'Pause ' : 'Resume ') + j.name, style: 'grid-row:span 3;grid-column:3',
    onclick: async () => { try { await api('/schedules/' + j.id, { method: 'PATCH', body: { enabled: !j.enabled } }); refresh(); } catch (e) { toast(e.message, true); } } }),
    h('div', { class: 's' }, `${describeCron(j.cron)}${j.target_name ? ', ' + j.target_name : ''}`), h('div', { class: 's' }, j.enabled ? 'Next: ' + when(j.next_run) : 'Paused'), j.last_result && h('div', { class: 's' }, 'Last: ' + j.last_result.replace(/^ok: /, '')),
    h('div', { class: 's', style: 'display:flex;gap:10px' }, j.command && h('details', {}, h('summary', {}, 'Command'), h('div', { class: 'mono' }, j.command)), h('button', { class: 'link', onclick: async () => { if (confirm(`Delete "${j.name}"?`)) { try { await api('/schedules/' + j.id, { method: 'DELETE' }); refresh(); } catch (e) { toast(e.message, true); } } } }, 'Delete')));
  const local = jobs.filter(j => j.kind !== 'host'), host = jobs.filter(j => j.kind === 'host');
  return h('div', {}, h('div', { class: 'dh' }, h('h1', {}, 'Schedules'), h('button', { class: 'btn small', onclick: () => schedForm(refresh) }, 'New schedule')),
    h('div', { class: 'grid' }, !S.me.app && h('section', { class: 'card' + (wakeOnly() ? ' wide' : '') }, h('div', { class: 'ch' }, h('h3', {}, 'Runs on this computer', h('span', { class: 'sub' }, `${data.computer}. TruePilot must stay running.`))), local.length ? local.map(row) : h('p', { class: 'empty' }, 'Nothing here yet.')),
      !wakeOnly() && h('section', { class: 'card' + (S.me.app ? ' wide' : '') }, h('div', { class: 'ch' }, h('h3', {}, 'Runs inside TrueNAS', h('span', { class: 'sub' }, S.me.app ? 'Cron jobs. They keep running when your phone is off.' : 'Cron jobs. They still run if TruePilot is stopped.'))), host.length ? host.map(row) : h('p', { class: 'empty' }, 'Nothing here yet.'))),
    !can && !wakeOnly() && h('p', { class: 'note', style: 'margin-top:12px' }, 'App and NAS schedules need write access. Add a write key and turn on actions in Settings. Wake schedules always work.'));
}
function schedForm(done) {
  const d = dev(), apps = S.res?.snapshot?.apps || [], wo = wakeOnly();
  const name = h('input', { type: 'text', placeholder: 'Nightly Plex restart' });
  const acts = [...(wo ? [] : [['restart_app', 'Restart an app'], ['start_app', 'Start an app'], ['stop_app', 'Stop an app']]), ['wake_device', 'Wake a device'], ...(wo ? [] : [['restart_host', 'Restart the NAS'], ['shutdown_host', 'Shut down the NAS']])];
  const action = h('select', {}, acts.map(([v, t]) => h('option', { value: v }, t))), target = h('select', {});
  const tWrap = h('label', { class: 'f' }, 'Which', target);
  const freq = h('select', {}, [['daily', 'Every day'], ['wd', 'Weekdays'], ['we', 'Weekends'], ['days', 'Certain days'], ['custom', 'Custom (cron)']].map(([v, t]) => h('option', { value: v }, t)));
  const time = h('input', { type: 'time', value: '07:30' }), cron = h('input', { type: 'text', value: '30 7 * * *', class: 'mono' });
  const days = DOW.map((n, i) => h('label', { class: 'check', style: 'margin:0' }, h('input', { type: 'checkbox', value: i, checked: i === 1 }), n)), dayWrap = h('div', { style: 'display:flex;flex-wrap:wrap;gap:4px 14px;margin-bottom:12px' }, days);
  const cronWrap = h('label', { class: 'f' }, 'Cron (minute hour day month weekday)', cron), timeWrap = h('label', { class: 'f' }, 'At what time', time), warn = h('div'), prev = h('p', { class: 'mute small' }), msg = msgBox();
  const build = () => { if (freq.value === 'custom') return cron.value.trim(); const [hh, mm] = (time.value || '07:30').split(':').map(Number), dw = { daily: '*', wd: '1-5', we: '0,6', days: days.filter(l => l.firstChild.checked).map(l => l.firstChild.value).join(',') || '*' }[freq.value]; return `${mm} ${hh} * * ${dw}`; };
  let tm; const showPrev = () => { clearTimeout(tm); tm = setTimeout(async () => { try { const r = await api('/schedules/preview?cron=' + encodeURIComponent(build())); prev.textContent = r.ok ? 'Next runs: ' + r.runs.map(when).join(', ') : 'That schedule isn\'t valid yet.'; } catch (e) { /* ignore */ } }, 250); };
  const sync = () => { const a = action.value, host = a.endsWith('_host');
    target.replaceChildren(...(a === 'wake_device' ? [...S.pcs.map(p => h('option', { value: p.id }, p.name)), ...S.webapps.filter(w => w.wake_id != null).map(w => h('option', { value: w.wake_id }, `${w.name} (runs on ${w.runs_on_name})`))] : apps.map(x => h('option', { value: x.name }, x.title)))); tWrap.style.display = host ? 'none' : '';
    dayWrap.style.display = freq.value === 'days' ? '' : 'none'; cronWrap.style.display = freq.value === 'custom' ? '' : 'none'; timeWrap.style.display = freq.value === 'custom' ? 'none' : '';
    warn.replaceChildren(host ? h('p', { class: 'note' }, 'This creates a cron job inside TrueNAS, so it still runs if TruePilot is stopped. It skips itself while a scrub, replication or upgrade is running.' + (a === 'shutdown_host' ? ' After a shutdown the NAS stays off until you wake it.' : '')) : a === 'wake_device' ? h('p', { class: 'note ok' }, S.me.app ? 'TrueNAS sends the wake packet, so the NAS must be on at that time. It skips the wake if the PC is already on.' : 'Runs on this computer. TruePilot must be running at that time, and it skips the wake if the PC is already on.') : ''); showPrev(); };
  [action, freq, time, cron].forEach(e => e.addEventListener('input', sync)); days.forEach(l => l.addEventListener('change', sync));
  const save = h('button', { class: 'btn' }, 'Save schedule');
  save.onclick = async () => { save.disabled = true; msg.set(''); const a = action.value; try { await api('/schedules', { method: 'POST', body: { device_id: a === 'wake_device' ? null : d?.id, name: name.value || action.selectedOptions[0].text, action: a, target: a.endsWith('_host') ? '' : String(target.value || ''), cron: build() } }); closeDlg(); toast('Schedule saved'); done(); } catch (e) { msg.set(e.message); save.disabled = false; } };
  modal('New schedule', h('div', {}, h('label', { class: 'f' }, 'Name (optional)', name), h('label', { class: 'f' }, 'What to do', action), tWrap, h('label', { class: 'f' }, 'How often', freq), dayWrap, timeWrap, cronWrap, warn, prev, msg), [h('button', { class: 'btn ghost', onclick: closeDlg }, 'Cancel'), save]); sync();
}

/* ---------- Settings ---------- */
const grp = (title, sub, ...rows) => h('section', { class: 'card' }, h('div', { class: 'ch' }, h('h3', {}, title, sub && h('span', { class: 'sub' }, sub))), rows);
const srow = (ic, text, right, onclick, cls = '') => h('button', { class: 'row srow ' + cls, onclick }, ic ? icon(ic) : h('span'), h('div', { class: 't' }, text), h('span', { class: 'mute' }, right || icon('right')));
const wide = g => { g.classList.add('wide'); return g; };
async function pageSettings() {
  const [set, sess, toks] = await Promise.all([api('/settings'), api('/sessions'), S.me.app ? [] : api('/agent-tokens')]), theme = localStorage.getItem('tp.theme') || '';
  const ro = h('button', { class: 'sw', role: 'switch', 'aria-checked': String(set.read_only), 'aria-label': 'Read-only mode', onclick: async e => { try { const v = e.currentTarget.getAttribute('aria-checked') !== 'true'; await api('/settings', { method: 'PUT', body: { read_only: v } }); e.currentTarget.setAttribute('aria-checked', String(v)); toast(v ? 'Read-only mode on' : 'Read-only mode off'); } catch (x) { toast(x.message, true); } } });
  return h('div', {}, h('div', { class: 'dh' }, h('h1', {}, 'Settings')), h('div', { class: 'grid' },
    grp('Devices', 'NAS units TruePilot watches', S.devices.length ? S.devices.map(d => h('div', { class: 'row' }, lamp('ok'), h('div', { class: 't' }, d.name), h('div', { class: 'acts wrap' },
      d.kind !== 'demo' && h('button', { class: 'btn small ghost', onclick: () => deviceDialog(d) }, 'Edit'), h('button', { class: 'btn small ghost', onclick: () => diagnostics(d) }, 'Diagnostics'),
      h('button', { class: 'btn small ghost', onclick: async () => { if (confirm(`Remove ${d.name} from TruePilot? Nothing changes on the NAS itself.`)) { await api('/devices/' + d.id, { method: 'DELETE' }); await loadDevices(); S.res = null; render(); pollNow(); } } }, 'Remove')),
      h('div', { class: 's' }, d.kind === 'demo' ? 'Demo data, no real NAS' : `${d.host}:${d.port}, ${d.write_enabled ? 'actions on' : 'read only'}`))) : h('p', { class: 'empty' }, 'No NAS added. This copy only wakes things.'), srow('plus', 'Add device', '', () => deviceDialog())),
    grp('Security', '', S.me.app ? srow('lock', 'App lock', '', lockDialog) : srow('key', 'Change password', '', changePw), h('div', { class: 'row' }, icon('eye'), h('div', {}, h('div', { class: 't' }, 'Read-only mode'), h('div', { class: 's' }, 'Blocks every action')), ro),
      !S.me.app && srow('user', 'Signed-in devices', String(sess.length), () => sessionsDialog(sess))),
    !S.me.app && grp('Agent access', 'Let an AI agent such as Hermes look after your NAS', toks.map(t => h('div', { class: 'row' }, lamp(t.last_used ? 'ok' : 'off'), h('div', { class: 't' }, t.name), h('button', { class: 'btn small ghost', style: 'grid-row:span 2;grid-column:3', onclick: async () => { if (confirm(`Revoke ${t.name}? It stops working at once.`)) { await api('/agent-tokens/' + t.id, { method: 'DELETE' }); renderMain(); } } }, 'Revoke'),
      h('div', { class: 's' }, `${t.level === 'control' ? 'Read, wake, start/stop/restart apps' : 'Read only'}, ${t.last_used ? 'used ' + ago(t.last_used * 1000) : 'never used'}`))), srow('bot', 'Create agent token', '', agentDialog)),
    grp('Appearance', '', h('div', { class: 'row' }, icon('moon'), h('div', { class: 't' }, 'Theme'), h('div', { class: 'seg', role: 'group', 'aria-label': 'Theme' }, [['', 'Match device'], ['light', 'Light'], ['dark', 'Dark']].map(([v, t]) => h('button', { 'aria-pressed': String(theme === v), onclick: () => { v ? localStorage.setItem('tp.theme', v) : localStorage.removeItem('tp.theme'); applyTheme(); renderMain(); } }, t))))),
    grp('History and help', '', srow('history', 'Activity log', '', auditDialog), srow('refresh', 'About TruePilot', 'Version ' + (S.me.version || '1.0'), () => toast('TruePilot ' + (S.me.version || '1.0') + ' on ' + (S.me.computer || '')))),
    wide(grp('Danger zone', '', srow('power', S.me.app ? 'Erase app data' : 'Start fresh', '', startFresh, 'dg')))));
}
function lockDialog() {
  const N = window.TPNative; N.lockGet().then(cfg => {
    const method = h('select', {}, [['both', 'Fingerprint and password'], ['fingerprint', 'Fingerprint only'], ['password', 'Password only']].map(([v, t]) => h('option', { value: v, selected: cfg.method === v }, t)));
    const delay = h('select', {}, [[0, 'Immediately'], [1, 'After 1 minute'], [5, 'After 5 minutes'], [10, 'After 10 minutes'], [15, 'After 15 minutes'], [-1, 'Never']].map(([v, t]) => h('option', { value: v, selected: Number(cfg.delay) === v }, t)));
    const hide = h('input', { type: 'checkbox', checked: !!cfg.hideRecents }), pw = h('input', { type: 'password', autocomplete: 'new-password', placeholder: cfg.hasPassword ? 'Leave blank to keep it' : 'Choose a password' }), pw2 = h('input', { type: 'password', autocomplete: 'new-password' }), m = msgBox();
    const save = h('button', { class: 'btn' }, 'Save');
    save.onclick = async () => { if (pw.value !== pw2.value) return m.set('The two passwords don\'t match.'); const r = await N.lockSet({ method: method.value, delay: Number(delay.value), hideRecents: hide.checked, password: pw.value }); if (r.ok) { closeDlg(); toast('Lock settings saved'); } else m.set(r.error); };
    modal('App lock', h('div', {}, h('label', { class: 'f' }, 'Unlock with', method), h('label', { class: 'f' }, 'Lock again', delay, h('small', {}, 'Never means the app opens straight away every time.')),
      h('label', { class: 'check' }, hide, 'Hide TruePilot in recent apps and block screenshots'), h('label', { class: 'f' }, 'Password', pw), h('label', { class: 'f' }, 'Repeat password', pw2), m),
      [h('button', { class: 'btn ghost', style: 'margin-right:auto', onclick: () => { closeDlg(); N.lockNow(); } }, 'Lock now'), h('button', { class: 'btn ghost', onclick: closeDlg }, 'Cancel'), save]);
  });
}
function agentDialog() {
  const name = h('input', { type: 'text', value: 'Hermes', autocomplete: 'off' }), level = h('select', {}, [['control', 'Read, wake PCs, start/stop/restart apps. Asks me for the rest'], ['read', 'Read only']].map(([v, t]) => h('option', { value: v }, t))), m = msgBox();
  const make = h('button', { class: 'btn' }, 'Create token');
  make.onclick = async () => { try { const r = await api('/agent-tokens', { method: 'POST', body: { name: name.value, level: level.value } });
    const cfg = `mcp_servers:\n  truepilot:\n    command: "python"\n    args: ["C:\\path\\to\\truepilot\\agent\\truepilot_mcp.py"]\n    env:\n      TRUEPILOT_URL: "${location.origin}"\n      TRUEPILOT_TOKEN: "${r.token}"`;
    modal('Token created', h('div', {}, h('p', { class: 'note' }, 'Copy it now. TruePilot shows it only once.'), h('label', { class: 'f' }, 'Token', h('input', { type: 'text', readonly: true, value: r.token, class: 'mono', onfocus: e => e.target.select() })),
      h('p', { class: 'mute small' }, 'Add this to the agent\'s config (Hermes: its MCP servers section), changing the path to where you unzipped TruePilot:'), h('pre', { class: 'logs', style: 'max-height:none;min-height:0' }, cfg)),
      [h('button', { class: 'btn ghost', onclick: async () => { try { await navigator.clipboard.writeText(cfg); toast('Config copied'); } catch (e) { toast('Could not copy', true); } } }, 'Copy config'), h('button', { class: 'btn', onclick: () => { closeDlg(); renderMain(); } }, 'Done')]); } catch (e) { m.set(e.message); } };
  modal('Create agent token', h('div', {}, h('p', { class: 'mute' }, 'A token lets an AI agent use TruePilot through a small, limited interface. It can never do more than the level you choose, and risky actions (upgrades, restarting or shutting down the NAS) always wait for your approval.'),
    h('label', { class: 'f' }, 'Name', name), h('label', { class: 'f' }, 'What it may do on its own', level), m), [h('button', { class: 'btn ghost', onclick: closeDlg }, 'Cancel'), make]);
}
function startFresh() { const p = freshPanel(() => { S.devices = []; S.res = null; start(); }); modal('Start fresh', p.box, [h('button', { class: 'btn ghost', onclick: closeDlg }, 'Cancel'), p.go]); }
function changePw() {
  const a = pwField('Current password', 'c0'), b = pwField('New password (8 or more characters)', 'c1', 'new-password'), c = pwField('Repeat new password', 'c2', 'new-password'), all = h('input', { type: 'checkbox' }), m = msgBox();
  const go = h('button', { class: 'btn' }, 'Change password'); go.onclick = async () => { if ($('#c1').value !== $('#c2').value) return m.set('The two new passwords don\'t match.'); try { await api('/auth/change', { method: 'POST', body: { current: $('#c0').value, new: $('#c1').value, sign_out_others: all.checked } }); closeDlg(); toast('Password changed'); } catch (e) { m.set(e.message); } };
  modal('Change password', h('div', {}, a, b, c, h('label', { class: 'check' }, all, 'Sign out my other phones and PCs'), m), [h('button', { class: 'btn ghost', onclick: closeDlg }, 'Cancel'), go]);
}
function sessionsDialog(list) {
  modal('Signed-in devices', h('div', {}, list.map(s => h('div', { class: 'row', style: 'padding-left:0;padding-right:0' }, lamp(s.current ? 'ok' : 'off'), h('div', { class: 't' }, s.label + (s.current ? ' (this one)' : '')), !s.current ? h('button', { class: 'btn small ghost', onclick: async () => { await api('/sessions/' + s.id, { method: 'DELETE' }); closeDlg(); renderMain(); } }, 'Sign out') : h('span'), h('div', { class: 's' }, `${s.ip}, last seen ${ago(s.last_seen * 1000)}`)))), [h('button', { class: 'btn', onclick: closeDlg }, 'Close')]);
}
async function diagnostics(d) {
  const body = h('p', { class: 'mute' }, 'Calling TrueNAS...'); modal('Diagnostics: ' + d.name, body, [h('button', { class: 'btn', onclick: closeDlg }, 'Close')]);
  try { const r = await api(`/devices/${d.id}/diagnostics`); body.replaceChildren(h('p', { class: 'note' }, 'Each line is one TrueNAS call. Red lines failed. Send them to Claude and the app can be adjusted.'), r.results.map(x => h('div', { style: 'margin-bottom:10px' }, h('div', { style: 'display:flex;gap:8px;align-items:center' }, lamp(x.ok ? 'ok' : 'bad'), h('b', {}, x.method)), h('div', { class: 'mono mute' }, x.text)))); }
  catch (e) { body.replaceChildren(h('p', { class: 'note bad' }, e.message)); }
}
async function auditDialog() {
  const body = h('p', { class: 'mute' }, 'Loading...'); modal('Activity log', body, [h('button', { class: 'btn', onclick: closeDlg }, 'Close')]);
  const rows = await api('/audit'); body.replaceChildren(!rows.length ? h('p', {}, 'Nothing yet.') : rows.map(r => h('div', { style: 'margin-bottom:8px' }, h('b', {}, r.action.replace(/_/g, ' ')), ' ' + (r.target || ''), h('span', { class: 'chip' + (r.result === 'ok' ? '' : ' bad'), style: 'margin-left:6px' }, r.result),
    h('div', { class: 'mute small' }, `${new Date(r.ts * 1000).toLocaleString()}, ${r.who}${r.detail ? ', ' + r.detail : ''}`))));
}

/* ---------- Add / edit device ---------- */
function deviceFormEl(d, onSaved) {
  const edit = !!d, f = {}, inp = (k, v, o = {}) => (f[k] = h('input', Object.assign({ type: 'text', autocomplete: 'off', value: v == null ? '' : v }, o))), chk = (k, v) => (f[k] = h('input', { type: 'checkbox', checked: v })), out = msgBox();
  inp('name', d?.name || 'Home NAS'); inp('host', d?.host || '', { placeholder: '192.168.1.50', inputmode: 'url' }); inp('port', d?.port || 443, { inputmode: 'numeric' }); inp('username', d?.username || 'truepilot');
  inp('api_key', '', { type: 'password', placeholder: edit ? 'Saved. Leave blank to keep it.' : 'Paste the read-only key' }); inp('write_username', d?.wuser || '', { placeholder: 'Same as above if blank' });
  inp('write_key', '', { type: 'password', placeholder: d?.has_write_key ? 'Saved. Leave blank to keep it.' : 'Optional' }); inp('mac', d?.mac || '', { placeholder: 'AA:BB:CC:DD:EE:FF', class: 'mono' }); inp('broadcast', d?.broadcast || '', { placeholder: '192.168.1.255 (optional)' });
  chk('selfsigned', d ? !d.verify_tls : true); chk('write_enabled', d?.write_enabled || false); chk('clear_write_key', false);
  const body = () => ({ id: d?.id, name: f.name.value, host: f.host.value, port: Number(f.port.value) || 443, username: f.username.value, api_key: f.api_key.value, write_username: f.write_username.value, write_key: f.write_key.value,
    clear_write_key: f.clear_write_key.checked, verify_tls: !f.selfsigned.checked, write_enabled: f.write_enabled.checked, mac: f.mac.value, broadcast: f.broadcast.value });
  const test = h('button', { class: 'btn ghost' }, 'Test connection'), save = h('button', { class: 'btn' }, 'Save');
  test.onclick = async () => { test.disabled = true; out.set('Connecting...', false); try { const r = await api('/devices/test', { method: 'POST', body: body() });
    out.replaceChildren(r.ok ? h('p', { class: 'note ok' }, `Connected. ${r.hostname} is running TrueNAS ${(r.version || '').replace(/^TrueNAS-/, '')}.` + (r.write_ok === true ? ' The write key works too.' : '')) : h('p', { class: 'note bad' }, r.error), r.write_ok === false && h('p', { class: 'note bad' }, 'Write key failed: ' + r.write_error)); } catch (e) { out.set(e.message); } test.disabled = false; };
  save.onclick = async () => { save.disabled = true; try { await api(edit ? '/devices/' + d.id : '/devices', { method: edit ? 'PUT' : 'POST', body: body() }); await loadDevices(); if (!edit) { S.devId = S.devices.at(-1).id; localStorage.setItem('tp.dev', S.devId); } S.res = null; closeDlg(); toast('Device saved'); await onSaved(); } catch (e) { out.set(e.message); save.disabled = false; } };
  const L = (t, el, help) => h('label', { class: 'f' }, t, el, help && h('small', {}, help)), C = (el, t, help) => h('label', { class: 'check' }, el, h('span', {}, t, help && h('small', { style: 'display:block;color:var(--mute)' }, help)));
  const el = h('div', {}, h('p', { class: 'note' }, 'In TrueNAS, make a user with the Readonly Admin role, then add an API key for it under Credentials > API Keys. The key is shown once. TruePilot stores it encrypted and never shows it again.'),
    L('Name', f.name), h('div', { class: 'grid2' }, L('IP address or hostname', f.host), L('Port', f.port)), L('Username that owns the key', f.username), L('Read-only API key', f.api_key),
    C(f.selfsigned, 'My NAS uses its default self-signed certificate', 'Leave ticked for a typical home setup. The connection is still encrypted.'),
    h('details', { open: !!(d?.has_write_key || d?.mac) }, h('summary', {}, 'Write access and Wake-on-LAN (optional)'), h('div', { style: 'margin-top:10px' }, L('Write key username', f.write_username),
      L('Write API key', f.write_key, 'A separate key whose user can manage apps and cron jobs. Needed for restart, schedules and upgrades.'), C(f.write_enabled, 'Allow actions on this NAS', 'Every action still asks you to confirm first.'),
      d?.has_write_key && C(f.clear_write_key, 'Remove the saved write key'), L('NAS MAC address (wired port)', f.mac, 'The Dashboard network card can fill this in for you.'), L('Broadcast address', f.broadcast))), out);
  return { el, test, save };
}
function deviceDialog(d) { const f = deviceFormEl(d, async () => { render(); pollNow(); }); modal(d ? 'Edit device' : 'Add device', f.el, [h('button', { class: 'btn ghost', onclick: closeDlg }, 'Cancel'), f.test, f.save]); }

/* ---------- main render + start ---------- */
function renderMain() {
  const m = $('#main'); if (!m) return; const ae = document.activeElement, keep = ae && ae.id === 'appq' ? [ae.selectionStart, ae.selectionEnd] : null; const y = window.scrollY, pages = { dash: pageDash, apps: pageApps, power: pagePower, sched: pageSched, settings: pageSettings }, out = (pages[S.page] || pageDash)();
  if (out.then) out.then(n => { if ($('#main') === m) m.replaceChildren(n); }); else { m.replaceChildren(out); window.scrollTo(0, y); if (keep) { const e = $('#appq'); if (e) { e.focus(); try { e.setSelectionRange(keep[0], keep[1]); } catch (x) { /* ignore */ } } } }
}
function applyTheme() { const t = localStorage.getItem('tp.theme'); t ? document.documentElement.dataset.theme = t : delete document.documentElement.dataset.theme; }
async function start() {
  applyTheme(); closeDlg();
  const a = await fetch('/api/auth/state').then(r => r.json()); S.me = a;
  if (a.setup_needed) S.auth = 'setup'; else if (!a.authed) S.auth = ['forgot', 'fresh'].includes(S.auth) ? S.auth : 'login';
  else { S.auth = 'in'; await loadDevices(); if (!S.devices.length && !a.wake_only) S.auth = 'nas'; }
  S.page = location.hash.replace('#/', '') || (wakeOnly() ? 'power' : 'dash'); if (S.auth === 'in' && !PAGES().find(p => p[0] === S.page)) S.page = PAGES()[0][0];
  render(); if (S.auth === 'in') { pollNow(); if (S.page === 'power') loadSched().then(renderMain).catch(() => {}); }
}
S.sched = null; start();
if ('serviceWorker' in navigator && !window.TPNative && (location.protocol === 'https:' || location.hostname === 'localhost')) navigator.serviceWorker.register('/sw.js').catch(() => {});
