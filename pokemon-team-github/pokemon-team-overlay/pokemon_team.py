#!/usr/bin/env python3
"""Pokémon Team: single-file app. Python 3.9+; no extra packages.

Run: python pokemon_team.py (Windows: py pokemon_team.py).
Controller and OBS URLs: use the exact addresses printed at startup.
Default port 8765; falls back to another free port if occupied.
Default OBS dimensions: 88 x 528. Keep this process running.
All HTML, CSS and JavaScript are embedded below. Internet access is needed
for PMDCollab portraits. Team data is saved beside this script.
Asset credits and license: https://github.com/PMDCollab/SpriteCollab

GET /api/state: snapshot. GET /api/events: Server-Sent Events.
POST /api/state: atomic slot or layout patch; persists before publishing.
"""
import copy
import json
import argparse
import http.client
import socket
import secrets
import os
from pathlib import Path
import re
import threading
import webbrowser
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlsplit

ROOT = Path(__file__).resolve().parent
STATE_FILE = ROOT / 'pokemon-team-data.json'
CHANGED = threading.Condition()
STATE = {'slots': [None] * 6, 'layout': 'vertical'}
REVISION = 0
INSTANCE_ID = secrets.token_hex(16)
LAYOUTS = {'vertical', 'grid', 'horizontal'}
FILES = {'/': 'settings.html', '/settings.html': 'settings.html',
         '/overlay.html': 'overlay.html', '/app.js': 'app.js', '/styles.css': 'styles.css'}

# Embedded browser assets. No dist folder or separate web files needed.
ASSETS = {
'settings.html': r'''<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Pokémon Team • Controller</title>
  <link rel="stylesheet" href="styles.css"><script src="app.js" defer></script>
</head>
<body data-page="settings">
  <header><div><small>STREAM TOOLS / PMDCOLLAB</small><h1>Pokémon Team</h1></div>
    <a href="overlay.html" target="_blank" rel="noopener">Open overlay ↗</a></header>
  <main class="workspace">
    <section class="panel controls">
      <h2>ADD POKEMON TO TEAM</h2>
      <form id="add-form"><fieldset id="entry-fields">
        <label for="slot">Slot Position</label>
        <select id="slot"><option>1</option><option>2</option><option>3</option><option>4</option><option>5</option><option>6</option></select>
        <label for="dex">Dex Number</label><input id="dex" type="number" min="1" max="9999" step="1" value="1" required>
        <label for="form">Form Number <span>(optional)</span></label>
        <input id="form" type="number" min="0" max="9999" step="1" placeholder="Base form" list="form-options">
        <datalist id="form-options"></datalist>
        <label class="shiny-toggle"><input id="shiny" type="checkbox"> Shiny</label>
        <label for="known-forms">Repository forms</label><select id="known-forms"><option value="">Base form</option></select>
        <p id="form-help" class="muted">Blank or 0 checks the base portrait, then folder 0000.</p>
        <div class="candidate"><div id="candidate-image" class="portrait"></div><div><strong id="candidate-name">#0001</strong><p id="candidate-detail" class="muted">Check a portrait before adding.</p></div></div>
        <button type="button" id="check" class="secondary">Check portrait</button>
        <button type="submit">Add / update slot</button>
      </fieldset></form>
      <p id="message" role="status" aria-live="polite">Choose a Pokémon or browse the database.</p>
      <a id="portrait-link" hidden target="_blank" rel="noopener">View source portrait ↗</a>
    </section>
    <section class="panel team-panel">
      <div class="section-head"><h2>YOUR TEAM</h2><span id="connection" role="status">Connecting…</span></div>
      <div id="team-editor" class="team-editor"></div>
      <label for="layout">Overlay layout</label><select id="layout"><option value="vertical">Vertical · 1 × 6</option><option value="grid">Grid · 3 × 2</option><option value="horizontal">Horizontal · 6 × 1</option></select>
      <p id="dimensions" class="muted"></p>
      <p class="muted">Use a Browser Source URL in OBS. Keep the local server running.</p>
    </section>
    <section class="panel database">
      <div class="section-head"><h2>PORTRAIT DATABASE</h2><button id="reload-catalog" class="secondary">Reload catalog</button></div>
      <label for="search">Search by name or Dex number</label><input id="search" type="search" placeholder="Meowth, Growlithe, 0052…">
      <p id="catalog-status" role="status" class="muted">Loading repository catalog…</p>
      <div id="catalog" class="catalog"></div>
      <nav class="pagination" aria-label="Catalog pages"><button id="previous" class="secondary">Previous</button><span id="page-label"></span><button id="next" class="secondary">Next</button></nav>
    </section>
  </main>
  <footer>Portraits: <a href="https://github.com/PMDCollab/SpriteCollab" target="_blank" rel="noopener">PMDCollab / SpriteCollab</a>. <a href="https://github.com/PMDCollab/SpriteCollab/blob/master/LICENSE.md" target="_blank" rel="noopener">Asset license</a>. Check individual artist credits before use.</footer>
</body>
</html>
''',
'overlay.html': r'''<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Pokémon Team • OBS Overlay</title>
  <link rel="stylesheet" href="styles.css"><script src="app.js" defer></script>
</head>
<body data-page="overlay"><main id="team" class="overlay-team vertical" aria-label="Pokémon team"></main></body>
</html>
''',
'styles.css': r''':root { color-scheme: dark; font: 16px/1.5 system-ui, sans-serif; --gold: #edc969; --ink: #0e1117; --muted: #aab5c6; }
* { box-sizing: border-box; }
body { margin: 0; background: var(--ink); color: #edf3fb; }
header, footer { max-width: 1380px; margin: auto; padding: 26px 28px; }
header, .section-head { display: flex; align-items: center; justify-content: space-between; gap: 16px; flex-wrap: wrap; }
small { color: var(--gold); letter-spacing: .15em; font-size: .75rem; }
h1 { font-size: 2rem; margin: 3px 0 0; letter-spacing: -.04em; }
h2 { font-size: .88rem; letter-spacing: .1em; margin: 0 0 20px; }
a { color: var(--gold); text-underline-offset: 4px; }
.workspace { max-width: 1380px; margin: auto; padding: 0 28px; display: grid; grid-template-columns: 320px minmax(0,1fr); gap: 20px; align-items: start; }
.panel { padding: 24px; border: 1px solid #344050; background: #171d27; border-radius: 14px; }
.controls { grid-row: span 2; border-top: 3px solid var(--gold); }
.database { grid-column: 2; }
fieldset { border: 0; padding: 0; margin: 0; min-width: 0; }
label { display: block; font-size: .9rem; font-weight: 650; margin: 14px 0 6px; }
label span { color: var(--muted); font-weight: 400; }
input, select, button { font: inherit; border-radius: 7px; min-height: 44px; }
input, select { width: 100%; padding: 10px 12px; color: #edf3fb; background: #0e141e; border: 1px solid #566174; }
button { cursor: pointer; border: 1px solid transparent; padding: 9px 16px; background: var(--gold); color: #161718; font-weight: 700; }
button.secondary { background: #232d3b; color: #edf3fb; border-color: #566174; }
button:disabled { opacity: .45; cursor: default; }
button:hover:not(:disabled) { filter: brightness(1.12); }
:focus-visible { outline: 3px solid #89d3ef; outline-offset: 3px; }
.shiny-toggle { display: flex; align-items: center; gap: 10px; }
.shiny-toggle input { width: 20px; height: 20px; min-height: 20px; accent-color: var(--gold); }
fieldset > button { width: 100%; margin-top: 10px; }
.muted, footer { color: var(--muted); font-size: .875rem; }
#message { font-size: .9rem; overflow-wrap: anywhere; }
#message.error { color: #ffb2b2; }
.candidate { display: flex; gap: 14px; align-items: center; margin: 20px 0; }
.candidate p { margin: 4px 0; }
.portrait { flex-shrink: 0; width: 80px; height: 80px; background: #68a8c0; border: 6px solid #565955; outline: 1px solid #85908e; position: relative; display: grid; place-items: center; color: #233c4a; font-size: .75rem; }
.portrait:empty::after { content: '—'; color: #285c77; font-size: 2rem; }
.portrait img { width: 100%; height: 100%; object-fit: contain; image-rendering: pixelated; }
.team-editor { display: grid; grid-template-columns: repeat(6,minmax(0,1fr)); gap: 12px; }
.team-card { min-width: 0; display: grid; gap: 9px; justify-items: center; text-align: center; }
.team-card strong { font-size: .875rem; overflow-wrap: anywhere; }
.team-card button { width: 100%; font-size: .875rem; padding: 5px; }
#connection { font-size: .875rem; color: var(--muted); }
.catalog { display: grid; grid-template-columns: repeat(auto-fill,minmax(112px,1fr)); gap: 12px; }
.catalog-item { display: flex; flex-direction: column; align-items: center; gap: 8px; background: #0e141e; color: #eaf3ff; border: 1px solid #344050; padding: 14px 8px; font-size: .875rem; }
.catalog-item small { color: var(--muted); letter-spacing: 0; }
.pagination { display: flex; justify-content: space-between; align-items: center; gap: 8px; margin-top: 20px; }
/* OBS canvas stays transparent. 80px tiles + 8px gaps + 4px padding. */
body[data-page="overlay"] { background: transparent; overflow: hidden; }
.overlay-team { display: grid; gap: 8px; padding: 4px; width: max-content; }
.overlay-team.vertical { grid-template-columns: 80px; }
.overlay-team.grid { grid-template-columns: repeat(3,80px); }
.overlay-team.horizontal { grid-template-columns: repeat(6,80px); }
@media(max-width:1100px) { .team-editor { grid-template-columns: repeat(3,minmax(0,1fr)); } }
@media(max-width:760px) { .workspace { grid-template-columns: minmax(0,1fr); padding: 0 16px; } .controls { grid-row: auto; } .database { grid-column: 1; } .panel { padding: 18px; } header, footer { padding: 22px 16px; } }
''',
'app.js': r'''/* Shared, build-free client. The local server is authoritative across OBS
   and normal browsers; EventSource pushes updates without page refreshes. */
'use strict';
const BASE = 'https://raw.githubusercontent.com/PMDCollab/SpriteCollab/master/portrait/';
const TRACKER = 'https://raw.githubusercontent.com/PMDCollab/SpriteCollab/master/tracker.json';
const pad = value => String(Number(value)).padStart(4, '0');
const $ = id => document.getElementById(id);
const isSettings = document.body.dataset.page === 'settings';
let state = {slots: Array(6).fill(null), layout: 'vertical'};
let tracker = {}, entries = [], page = 0, checking = false;
const PAGE_SIZE = 24;

function portraitURL(dex, form = '', shiny = false) {
  // Shiny portraits require a form folder, including 0000 for the base.
  if (shiny) return BASE + pad(dex) + '/' + pad(form || 0) + '/0001/Normal.png';
  return BASE + pad(dex) + '/' + (form === '' ? '' : pad(form) + '/') + 'Normal.png';
}
function candidates(dex, form, shiny = false) {
  if (shiny) return [portraitURL(dex, form, true)];
  // Only base forms fall back. An unavailable alternate never silently
  // becomes a different Pokémon/form.
  return form === '' || Number(form) === 0
    ? [portraitURL(dex), portraitURL(dex, 0)] : [portraitURL(dex, form)];
}
function loadImage(url) {
  return new Promise((resolve, reject) => {
    const img = new Image();
    const timer = setTimeout(() => finish(false), 8000);
    function finish(ok) {
      clearTimeout(timer); img.onload = img.onerror = null;
      if (ok) resolve(url); else reject(new Error('Portrait unavailable'));
    }
    img.onload = () => finish(true); img.onerror = () => finish(false); img.src = url;
  });
}
async function resolvePortrait(dex, form, shiny = false) {
  for (const url of candidates(dex, form, shiny)) {
    try { await loadImage(url); return url; } catch { /* try base-folder alternative */ }
  }
  throw new Error((shiny ? 'Shiny portrait unavailable. ' : '') + 'No portrait could be loaded. Check the Dex/form number and internet connection. Your team has not changed.');
}
function makePortrait(slot, lazy = false) {
  const box = document.createElement('div'); box.className = 'portrait';
  if (!slot) { box.setAttribute('aria-label', 'Empty slot'); return box; }
  const img = new Image(); img.alt = slot.name || `Pokémon #${pad(slot.dex)}`;
  if (lazy) img.loading = 'lazy';
  let urls = slot.form === null ? candidates(slot.dex, '', slot.shiny) : [portraitURL(slot.dex, slot.form, slot.shiny)];
  img.onerror = () => {
    if (urls.length > 1) { urls.shift(); img.src = urls[0]; }
    else { box.textContent = 'Unavailable'; box.title = img.alt + ' portrait unavailable'; }
  };
  img.src = urls[0]; box.append(img); return box;
}
function message(text, error = false) { $('message').textContent = text; $('message').classList.toggle('error', error); }
function render() {
  if (!isSettings) {
    const team = $('team'); team.className = 'overlay-team ' + state.layout;
    // Avoid reloading unchanged images on layout updates or SSE reconnect.
    state.slots.forEach((slot, i) => {
      const key = JSON.stringify(slot); const old = team.children[i];
      if (old?.dataset.key === key) return;
      const node = makePortrait(slot); node.dataset.key = key;
      if (old) old.replaceWith(node); else team.append(node);
    }); return;
  }
  $('team-editor').replaceChildren();
  state.slots.forEach((slot, i) => {
    const card = document.createElement('div'); card.className = 'team-card';
    const name = document.createElement('strong'); name.textContent = `${i + 1} · ${slot?.name || (slot ? '#' + pad(slot.dex) : 'Empty')}`;
    const remove = document.createElement('button'); remove.className = 'secondary';
    remove.textContent = 'Clear'; remove.disabled = !slot; remove.setAttribute('aria-label', `Clear slot ${i + 1}`);
    remove.onclick = async () => { remove.disabled = true; try { await update({slot: i, value: null}); message(`Slot ${i + 1} cleared.`); } catch(e) { message(e.message, true); remove.disabled = false; } };
    card.append(makePortrait(slot), name, remove); $('team-editor').append(card);
  });
  $('layout').value = state.layout;
  const sizes = {vertical: '88 × 528', grid: '264 × 176', horizontal: '528 × 88'};
  $('dimensions').textContent = `OBS Browser Source size: ${sizes[state.layout]} pixels.`;
}
async function update(patch) {
  const controller = new AbortController(), timer = setTimeout(() => controller.abort(), 8000);
  try {
    const r = await fetch('/api/state', {method: 'POST', headers: {'Content-Type': 'application/json'}, body: JSON.stringify(patch), signal: controller.signal});
    if (!r.ok) throw new Error('Save failed. Check that pokemon_team.py is running.');
    // SSE owns rendering: a delayed POST response must not overwrite a
    // newer update from another controller.
    await r.json();
  } catch(e) { throw new Error(e.name === 'AbortError' ? 'Save timed out. Check connection status before retrying.' : e.message); }
  finally { clearTimeout(timer); }
}
function connect() {
  render();
  if (location.protocol === 'file:') {
    if (isSettings) message('Start pokemon_team.py and open http://127.0.0.1:8765/settings.html. Double-clicking HTML files cannot sync with OBS.', true);
    return;
  }
  const stream = new EventSource('/api/events');
  stream.onmessage = e => {
    try { state = JSON.parse(e.data); render(); if (isSettings) $('connection').textContent = 'Live sync connected'; } catch { /* retain last valid team */ }
  };
  stream.onerror = () => { if (isSettings) $('connection').textContent = 'Disconnected · retrying…'; };
  // EventSource reconnects automatically and receives the complete latest team.
}
function updateForms() {
  const record = tracker[pad($('dex').value)];
  $('known-forms').replaceChildren(new Option('Base form', ''));
  $('form-options').replaceChildren();
  for (const [id, form] of Object.entries(record?.subgroups || {})) {
    if (id === '0000') continue;
    const label = `${id} · ${form.name || 'Alternate form'}`;
    $('known-forms').add(new Option(label, String(Number(id))));
    const option = document.createElement('option'); option.value = Number(id); option.label = label; $('form-options').append(option);
  }
  $('candidate-name').textContent = record?.name || '#' + pad($('dex').value);
}
function invalidatePreview() {
  $('candidate-image').replaceChildren(); $('candidate-detail').textContent = 'Check a portrait before adding.'; $('portrait-link').hidden = true;
}
async function checkAndMaybeSave(save) {
  if (checking || !$('add-form').reportValidity()) return;
  checking = true; $('entry-fields').disabled = true;
  const dex = Number($('dex').value), form = $('form').value, slot = Number($('slot').value) - 1;
  message('Checking portrait…');
  try {
    const shiny = $('shiny').checked;
    const url = await resolvePortrait(dex, form, shiny);
    const folder = url.slice(BASE.length).split('/');
    const resolvedForm = folder.length === 2 ? '' : folder[1];
    const record = tracker[pad(dex)], formName = record?.subgroups?.[pad(form || 0)]?.name;
    const name = (shiny ? 'Shiny ' : '') + (record?.name || '#' + pad(dex)) + (formName ? ' · ' + formName : '');
    const value = {dex, form: resolvedForm, name, shiny};
    const preview = makePortrait(value); $('candidate-image').replaceChildren(...preview.childNodes);
    $('candidate-name').textContent = name;
    $('candidate-detail').textContent = `#${pad(dex)} · ${resolvedForm === '' ? 'base' : 'form ' + resolvedForm}`;
    $('portrait-link').href = url; $('portrait-link').hidden = false;
    if (save) { await update({slot, value}); message(`${name} added to slot ${slot + 1}.`); }
    else message('Portrait found. Ready to add.');
  } catch(e) { message(e.message, true); }
  finally { checking = false; $('entry-fields').disabled = false; }
}
function renderCatalog() {
  const query = $('search').value.trim().toLowerCase();
  const filtered = entries.filter(([id, item]) => item.name.toLowerCase().includes(query) || (query && /^\d+$/.test(query) ? Number(id) === Number(query) : id.includes(query)));
  const pages = Math.max(1, Math.ceil(filtered.length / PAGE_SIZE)); page = Math.min(page, pages - 1);
  $('catalog').replaceChildren();
  for (const [id, item] of filtered.slice(page * PAGE_SIZE, (page + 1) * PAGE_SIZE)) {
    const button = document.createElement('button'); button.className = 'catalog-item'; button.type = 'button';
    const label = document.createElement('span'); label.textContent = item.name;
    const number = document.createElement('small'); number.textContent = '#' + id;
    button.append(makePortrait({dex: Number(id), form: null, name: item.name}, true), label, number);
    button.onclick = () => {
      if (checking) return;
      $('dex').value = Number(id); $('form').value = ''; updateForms(); invalidatePreview();
      $('dex').focus(); checkAndMaybeSave(false);
    }; $('catalog').append(button);
  }
  $('page-label').textContent = entries.length ? `${filtered.length} results · ${page + 1} / ${pages}` : 'Catalog unavailable';
  $('previous').disabled = page === 0; $('next').disabled = page >= pages - 1;
}
async function loadCatalog() {
  $('reload-catalog').disabled = true; $('catalog-status').textContent = 'Loading repository catalog…';
  const controller = new AbortController(), timer = setTimeout(() => controller.abort(), 20000);
  try {
    const r = await fetch(TRACKER, {signal: controller.signal}); if (!r.ok) throw new Error();
    tracker = await r.json();
    entries = Object.entries(tracker).filter(([id, item]) => /^\d{4}$/.test(id) && Number(id) > 0 && typeof item.name === 'string');
    entries.sort((a,b) => Number(a[0]) - Number(b[0]));
    $('catalog-status').textContent = `${entries.length} Pokémon from SpriteCollab. Select a portrait to check it; use Repository forms for alternatives.`;
    updateForms(); renderCatalog();
  } catch {
    $('catalog-status').textContent = 'Catalog could not load. You can still enter Dex and form numbers manually.'; renderCatalog();
  } finally { clearTimeout(timer); $('reload-catalog').disabled = false; }
}
if (isSettings) {
  $('add-form').onsubmit = e => { e.preventDefault(); checkAndMaybeSave(true); };
  $('check').onclick = () => checkAndMaybeSave(false);
  $('shiny').onchange = invalidatePreview;
  $('dex').oninput = () => { $('form').value = ''; updateForms(); invalidatePreview(); };
  $('form').oninput = () => { $('known-forms').value = String(Number($('form').value)) === '0' ? '' : String(Number($('form').value)); invalidatePreview(); };
  $('known-forms').onchange = () => { $('form').value = $('known-forms').value; invalidatePreview(); };
  $('layout').onchange = async () => { const layout = $('layout').value; $('layout').disabled = true; try { await update({layout}); } catch(e) { message(e.message, true); render(); } finally { $('layout').disabled = false; } };
  $('search').oninput = () => { page = 0; renderCatalog(); };
  $('previous').onclick = () => { page--; renderCatalog(); };
  $('next').onclick = () => { page++; renderCatalog(); };
  $('reload-catalog').onclick = loadCatalog;
  loadCatalog();
}
connect();
''',
}

def validate_slot(value):
    if value is None:
        return None
    if not isinstance(value, dict):
        raise ValueError('Invalid slot')
    dex, form, name = value.get('dex'), value.get('form'), value.get('name')
    if type(dex) is not int or not 1 <= dex <= 9999:
        raise ValueError('Dex must be an integer from 1 to 9999')
    if not isinstance(form, str) or not re.fullmatch(r'(?:\d{4})?', form):
        raise ValueError('Form must be blank or four digits')
    if not isinstance(name, str) or len(name) > 160:
        raise ValueError('Invalid name')
    shiny = value.get('shiny', False)
    if type(shiny) is not bool:
        raise ValueError('Shiny must be true or false')
    return {'dex': dex, 'form': form, 'name': name, 'shiny': shiny}

def load_state():
    global STATE
    if STATE_FILE.exists():
        data = json.loads(STATE_FILE.read_text(encoding='utf-8'))
        if not isinstance(data, dict) or data.get('layout') not in LAYOUTS or not isinstance(data.get('slots'), list) or len(data['slots']) != 6:
            raise ValueError('Invalid saved team; back up and repair pokemon-team-data.json')
        STATE = {'slots': [validate_slot(s) for s in data['slots']], 'layout': data['layout']}

def patch_state(patch):
    global STATE, REVISION
    if not isinstance(patch, dict):
        raise ValueError('Expected object')
    with CHANGED:
        new = copy.deepcopy(STATE)
        if set(patch) == {'slot', 'value'}:
            slot = patch['slot']
            if type(slot) is not int or not 0 <= slot < 6:
                raise ValueError('Invalid slot index')
            new['slots'][slot] = validate_slot(patch['value'])
        elif set(patch) == {'layout'} and isinstance(patch['layout'], str) and patch['layout'] in LAYOUTS:
            new['layout'] = patch['layout']
        else:
            raise ValueError('Expected a slot/value or layout patch')
        STATE_FILE.parent.mkdir(exist_ok=True)
        temporary = STATE_FILE.with_suffix('.tmp')
        with temporary.open('w', encoding='utf-8') as f:
            json.dump(new, f, ensure_ascii=False, indent=2)
            f.flush()
            os.fsync(f.fileno())
        os.replace(temporary, STATE_FILE)
        STATE = new
        REVISION += 1
        CHANGED.notify_all()
        return copy.deepcopy(new)

class LocalServer(ThreadingHTTPServer):
    # Windows SO_REUSEADDR may allow multiple listeners on the same port.
    # Reserve it exclusively instead; never share another process's listener.
    allow_reuse_address = False
    allow_reuse_port = False

    def server_bind(self):
        if os.name == 'nt':
            self.socket.setsockopt(socket.SOL_SOCKET, socket.SO_EXCLUSIVEADDRUSE, 1)
        super().server_bind()

    def get_request(self):
        connection, address = super().get_request()
        print('[CONNECT] Local client connected.', flush=True)
        return connection, address


def create_server(port=8765):
    candidates = [port] if port == 0 else list(dict.fromkeys([port, 8766, 0]))
    for index, candidate in enumerate(candidates):
        try:
            return LocalServer(('127.0.0.1', candidate), Handler)
        except OSError:
            if index == len(candidates) - 1:
                raise
            print(f'[PORT] Could not reserve port {candidate}; trying another port.', flush=True)


class Handler(BaseHTTPRequestHandler):
    def allowed(self):
        # Reject foreign web origins and DNS-rebinding hosts. No CORS access.
        port = self.server.server_port
        hosts = {f'127.0.0.1:{port}', f'localhost:{port}'}
        host = self.headers.get('Host', '')
        origin = self.headers.get('Origin')
        return host in hosts and (origin is None or origin == 'http://' + host)

    def reply(self, status, body, content_type='application/json'):
        raw = body if isinstance(body, bytes) else json.dumps(body).encode()
        self.send_response(status)
        self.send_header('Content-Type', content_type)
        self.send_header('Content-Length', str(len(raw)))
        self.send_header('Cache-Control', 'no-store')
        self.send_header('X-Pokemon-Team-Instance', INSTANCE_ID)
        self.send_header('X-Content-Type-Options', 'nosniff')
        self.end_headers()
        self.wfile.write(raw)

    def do_GET(self):
        if not self.allowed():
            return self.reply(403, {'error': 'Local origin required'})
        path = urlsplit(self.path).path
        if path == '/api/state':
            with CHANGED:
                snapshot = copy.deepcopy(STATE)
            return self.reply(200, snapshot)
        if path == '/api/events':
            self.send_response(200)
            self.send_header('Content-Type', 'text/event-stream')
            self.send_header('Cache-Control', 'no-cache')
            self.end_headers()
            last = -1
            try:
                while True:
                    with CHANGED:
                        if REVISION == last:
                            CHANGED.wait(timeout=15)
                        if last != REVISION:
                            payload = 'data: ' + json.dumps(STATE) + '\n\n'
                            last = REVISION
                        else:
                            payload = ': heartbeat\n\n'
                    self.wfile.write(payload.encode())
                    self.wfile.flush()
            except (BrokenPipeError, ConnectionResetError, TimeoutError):
                return
        if path in FILES:
            name = FILES[path]
            return self.reply(200, ASSETS[name].encode('utf-8'), {'html': 'text/html; charset=utf-8', 'css': 'text/css; charset=utf-8', 'js': 'text/javascript; charset=utf-8'}[name.rsplit('.', 1)[-1]])
        self.reply(404, {'error': 'Not found'})

    def do_POST(self):
        if not self.allowed():
            return self.reply(403, {'error': 'Local origin required'})
        if urlsplit(self.path).path != '/api/state':
            return self.reply(404, {'error': 'Not found'})
        if self.headers.get('Content-Type', '').split(';')[0] != 'application/json':
            return self.reply(415, {'error': 'Expected application/json'})
        try:
            length = int(self.headers.get('Content-Length', '0'))
            if not 0 < length <= 4096:
                raise ValueError('Invalid request size')
            self.connection.settimeout(10)
            patch = json.loads(self.rfile.read(length))
            self.reply(200, patch_state(patch))
        except (ValueError, UnicodeDecodeError, TimeoutError):
            self.reply(400, {'error': 'Invalid team update'})
        except OSError:
            self.reply(500, {'error': 'Could not save team'})

    def log_message(self, fmt, *args):
        print('[HTTP] ' + (fmt % args), flush=True)

def check_local_server(port):
    """Test actual HTTP responses without browser, VPN or proxy settings."""
    for path in ['/settings.html', '/overlay.html', '/styles.css', '/app.js', '/api/state']:
        connection = http.client.HTTPConnection('127.0.0.1', port, timeout=8)
        try:
            connection.request('GET', path)
            response = connection.getresponse()
            body = response.read()
            if response.getheader('X-Pokemon-Team-Instance') != INSTANCE_ID:
                raise RuntimeError('The connection reached a different server instance.')
            if response.status != 200 or not body:
                raise RuntimeError(f'{path}: HTTP {response.status}, {len(body)} bytes')
        finally:
            connection.close()
    print('[CHECK] All pages and API returned HTTP 200 with content.', flush=True)

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='Single-file Pokémon team controller and OBS overlay')
    parser.add_argument('--no-browser', action='store_true', help='Do not open the browser automatically')
    parser.add_argument('--self-test', action='store_true', help='Check startup and HTTP responses on a temporary port, then exit')
    args = parser.parse_args()
    load_state()
    server = create_server(0 if args.self_test else 8765)
    base_url = f'http://127.0.0.1:{server.server_port}'
    worker = threading.Thread(target=server.serve_forever, daemon=True)
    worker.start()
    try:
        check_local_server(server.server_port)
        if not args.self_test:
            print('Controller: ' + base_url + '/settings.html', flush=True)
            print('OBS URL:    ' + base_url + '/overlay.html', flush=True)
            print('Keep this window open. Press Ctrl+C to stop.', flush=True)
            print('If the browser fails, try another browser and include the [HTTP] lines when reporting the problem.', flush=True)
            if not args.no_browser:
                threading.Thread(target=lambda: webbrowser.open(base_url + '/settings.html'), daemon=True).start()
            while worker.is_alive():
                worker.join(timeout=0.5)
    except KeyboardInterrupt:
        pass
    finally:
        server.shutdown()
        server.server_close()
