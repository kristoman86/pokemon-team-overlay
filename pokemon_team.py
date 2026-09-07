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
import sys
import secrets
import os
from pathlib import Path
import re
import threading
import webbrowser
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlsplit

ROOT = Path(sys.executable if getattr(sys, 'frozen', False) else __file__).resolve().parent
STATE_FILE = ROOT / 'pokemon-team-data.json'
CHANGED = threading.Condition()
STATE = {'slots': [None] * 6, 'layout': 'vertical', 'presets': {}}
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
  <header><div><small>STREAM TOOLS / PMDCOLLAB · V2</small><h1>Pokémon Team</h1></div>
    <a href="overlay.html" target="_blank" rel="noopener">Open overlay ↗</a></header>
  <main class="workspace">
    <section class="panel controls">
      <h2>ADD POKEMON TO TEAM</h2>
      <form id="add-form"><fieldset id="entry-fields">
        <label for="slot">Slot Position</label>
        <select id="slot"><option>1</option><option>2</option><option>3</option><option>4</option><option>5</option><option>6</option></select>
        <label for="dex">Dex Number</label><input id="dex" type="number" min="1" max="9999" step="1" value="1" required>
        <label for="nickname">Nickname (optional)</label><input id="nickname" maxlength="24" placeholder="Leave blank for species name">
<label for="level">Level (optional)</label><input id="level" type="number" min="1" max="100" step="1" placeholder="1–100">
<label for="form">Form Number <span>(optional)</span></label>
        <input id="form" type="number" min="0" max="9999" step="1" placeholder="Base form" list="form-options">
        <datalist id="form-options"></datalist>
        <label class="shiny-toggle"><input id="shiny" type="checkbox"> Shiny</label>
        <label for="known-forms">Repository forms</label><select id="known-forms"><option value="">Base form</option></select>
        <p id="form-help" class="muted">Blank or 0 checks the base portrait, then folder 0000.</p>
        <div class="candidate"><div id="candidate-image" class="portrait"></div><div><strong id="candidate-name">#0001</strong><p id="candidate-detail" class="muted">Check a portrait before adding.</p></div></div>
        <button type="button" id="check" class="secondary">Check portrait</button>
        <button type="submit">Add / update slot</button><button type="button" id="set-target" class="secondary">Use as hunt target</button>
      </fieldset></form>
      <p id="message" role="status" aria-live="polite">Choose a Pokémon or browse the database.</p>
      <a id="portrait-link" hidden target="_blank" rel="noopener">View source portrait ↗</a>
    </section>
    <section class="panel team-panel">
      <div class="section-head"><h2>YOUR TEAM</h2><span id="connection" role="status">Connecting…</span></div>
      <p class="muted">Drag a portrait onto another slot to swap them, or use its Move menu. Edit keeps existing details.</p><div id="team-editor" class="team-editor"></div>
      <label for="layout">Overlay layout</label><select id="layout"><option value="vertical">Vertical · 1 × 6</option><option value="grid">Grid · 3 × 2</option><option value="horizontal">Horizontal · 6 × 1</option></select>
      <details><summary>Overlay styling</summary><form id="style-form">
<div class="control-grid"><label>Frame color<input id="frame-color" type="color" value="#565955"></label><label>Tile color<input id="tile-color" type="color" value="#68a8c0"></label>
<label>Portrait size (px)<input id="tile-size" type="number" min="40" max="240" value="80" required></label><label>Gap (px)<input id="tile-gap" type="number" min="0" max="40" value="8" required></label></div>
<label class="shiny-toggle"><input id="hide-empty" type="checkbox">Hide empty slots</label>
<label class="shiny-toggle"><input id="show-labels" type="checkbox">Show nicknames and levels</label>
<button>Apply styling</button><button id="reset-style" type="button" class="secondary">Reset styling</button></form></details>
<details open><summary>Saved teams &amp; backups</summary><form id="save-team-form"><label for="team-name">Team name</label><input id="team-name" maxlength="48" placeholder="Scarlet Nuzlocke" required><button>Save current team</button></form>
<label for="saved-teams">Saved teams</label><select id="saved-teams"></select><div class="button-row"><button id="load-team">Load team</button><button id="delete-team" class="secondary">Delete saved team</button></div>
<p class="muted">Saved teams include portraits, styling, Nuzlocke progress, and hunt progress. Save again to update a named team.</p>
<div class="button-row"><button id="export-team" class="secondary">Export current team</button><button id="export-all" class="secondary">Export full backup</button></div>
<label for="import-file">Import team or backup (.json)</label><input id="import-file" type="file" accept=".json,application/json"><p id="import-status" class="muted"></p></details>
<details><summary>Nuzlocke tracker</summary><form id="challenge-form"><label class="shiny-toggle"><input id="challenge-enabled" type="checkbox">Show Nuzlocke stats in overlay</label><div class="control-grid"><label>Deaths<input id="deaths" type="number" min="0" max="9999" value="0" required></label><label>Badges<input id="badges" type="number" min="0" max="99" value="0" required></label></div><button>Apply Nuzlocke stats</button></form><p class="muted">Marking a Pokémon fainted adds one death when tracking is enabled. Reviving does not erase past deaths.</p></details>
<details open><summary>Shiny hunt counter</summary><label class="shiny-toggle"><input id="hunt-enabled" type="checkbox">Show hunt in overlay</label><div id="hunt-summary"></div><div class="button-row"><button id="hunt-minus" class="secondary">−1</button><button id="hunt-plus">+1 encounter</button><button id="hunt-reset" class="secondary">Reset count</button></div>
<label for="hunt-hotkey">Counter hotkey (controller focused)</label><select id="hunt-hotkey"><option value="KeyH">H</option><option value="Space">Space</option><option value="KeyE">E</option></select><p class="muted">Hotkeys work while this controller is focused, outside text fields. Use the editor’s “Use as hunt target” button to choose a Pokémon.</p></details>
<details><summary>Portrait artist credits</summary><button id="refresh-credits" class="secondary">Load team credits</button><div id="artist-credits" aria-live="polite"></div><p class="muted">Credits are read from each selected portrait folder. Review the linked records and asset license before use; the app’s MIT license does not cover artwork.</p></details>
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

/* v2 controls and live overlay customization */
details { border-top:1px solid #344050; margin-top:18px; padding-top:14px; }
summary { cursor:pointer; font-weight:700; margin-bottom:12px; }
.control-grid { display:grid; grid-template-columns:repeat(2,minmax(0,1fr)); gap:12px; }
.button-row { display:flex; flex-wrap:wrap; gap:8px; margin:12px 0; }
input[type=color] { height:44px; padding:4px; }
.team-card select { font-size:.8rem; padding:5px; }
.team-card[draggable=true] .portrait { cursor:grab; }
.team-card.drag-over { outline:3px solid var(--gold); outline-offset:3px; }
.team-card .portrait { background:var(--tile-color,#68a8c0); border-color:var(--frame-color,#565955); }
.team-card .fainted img { filter:grayscale(1); opacity:.45; }
.team-card button { min-height:36px; }
#hunt-summary { display:flex; gap:12px; align-items:center; margin:12px 0; }
#artist-credits { font-size:.9rem; overflow-wrap:anywhere; }
#artist-credits article { padding:10px 0; border-bottom:1px solid #344050; }
.overlay-team { display:block; padding:4px; width:max-content; }
.overlay-grid { display:grid; gap:var(--tile-gap); grid-template-columns:repeat(var(--columns),var(--tile-size)); }
.overlay-team .portrait { width:var(--tile-size); height:var(--tile-size); background:var(--tile-color); border-color:var(--frame-color); }
.overlay-label { height:26px; font:600 12px/13px system-ui,sans-serif; text-align:center; color:white; text-shadow:0 1px 3px black; overflow:hidden; padding-top:2px; overflow-wrap:anywhere; }
.overlay-cell.fainted img { filter:grayscale(1); opacity:.4; }
.overlay-cell { position:relative; }
.faint-badge { position:absolute; top:6px; right:6px; color:white; background:#6e2020; padding:1px 4px; font-size:11px; }
.overlay-stats { height:36px; margin-top:8px; background:#171d27; border:2px solid var(--frame-color); color:white; display:flex; align-items:center; justify-content:center; gap:8px; font:600 12px system-ui,sans-serif; }
.overlay-hunt { height:80px; margin-top:8px; background:#171d27; border:2px solid var(--frame-color); color:white; display:flex; align-items:center; gap:8px; padding:6px; font:600 12px system-ui,sans-serif; }
.overlay-hunt .portrait { width:56px; height:56px; flex-shrink:0; }
.overlay-hunt > div:last-child { min-width:0; overflow:hidden; max-height:64px; overflow-wrap:anywhere; }
.overlay-hunt strong { display:block; font-size:20px; }
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
function renderLegacy() {
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
    if (!r.ok) { const error = await r.json().catch(() => ({})); throw new Error(error.error || 'Save failed. Check that the app is running.'); }
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
    const value = {dex, form: resolvedForm, name, shiny, nickname: $('nickname').value.trim(), level: $('level').value === '' ? null : Number($('level').value), fainted: false};
    const preview = makePortrait(value); $('candidate-image').replaceChildren(...preview.childNodes);
    $('candidate-name').textContent = name;
    $('candidate-detail').textContent = `#${pad(dex)} · ${resolvedForm === '' ? 'base' : 'form ' + resolvedForm}`;
    $('portrait-link').href = url; $('portrait-link').hidden = false;
    if (save === 'hunt') { await update({huntTarget: value}); message(`${name} set as hunt target. Count reset to zero.`); }
    else if (save) { await update({slot, value}); message(`${name} added to slot ${slot + 1}.`); }
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
      $('dex').value = Number(id); $('nickname').value = ''; $('level').value = ''; $('form').value = ''; updateForms(); invalidatePreview();
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
// v2 features use atomic server operations so simultaneous controllers cannot
// accidentally replace unrelated slots or lose encounter increments.
const DEFAULT_STYLE = {frame:'#565955', fill:'#68a8c0', size:80, gap:8, hideEmpty:false, labels:false};
let dragSlot = null;
let overlayKey = '';
let creditRequest = 0;
function styleState() { return {...DEFAULT_STYLE, ...state.style}; }
function challengeState() { return {enabled:false, deaths:0, badges:0, ...state.challenge}; }
function huntState() { return {enabled:false, target:null, count:0, hotkey:'KeyH', ...state.hunt}; }
function displayName(slot) { return slot.nickname || slot.name; }
function dimensions() {
  const s = styleState(), count = s.hideEmpty ? state.slots.filter(Boolean).length : 6;
  const columns = Math.min(count || 1, {vertical:1, grid:3, horizontal:6}[state.layout]);
  const rows = Math.ceil(count / columns);
  const hunt = huntState(), challenge = challengeState();
  const huntVisible = hunt.enabled && hunt.target;
  const width = Math.max(count ? columns*s.size + (columns-1)*s.gap : 0, challenge.enabled || huntVisible ? 180 : 0);
  const height = rows*(s.size + (s.labels ? 26 : 0)) + Math.max(0,rows-1)*s.gap + (challenge.enabled ? 44 : 0) + (huntVisible ? 88 : 0);
  return {width:width+8, height:height+8, columns};
}
function setStyleVars(element) {
  const s = styleState();
  element.style.setProperty('--tile-size', s.size+'px');
  element.style.setProperty('--tile-gap', s.gap+'px');
  element.style.setProperty('--frame-color', s.frame);
  element.style.setProperty('--tile-color', s.fill);
}
function renderOverlay() {
  const key = JSON.stringify([state.slots,state.layout,state.style,state.challenge,state.hunt]);
  if (overlayKey === key) return;
  overlayKey = key;
  const root = $('team'), s = styleState(), size = dimensions();
  root.className = 'overlay-team'; setStyleVars(root); root.style.width = size.width+'px';
  // Build stable cells only when team/style changes. Counter updates keep them.
  const teamKey = JSON.stringify([state.slots,state.layout,state.style]);
  let grid = root.querySelector('.overlay-grid');
  if (!grid || grid.dataset.key !== teamKey) {
    const fresh = document.createElement('div'); fresh.className = 'overlay-grid'; fresh.dataset.key = teamKey;
    fresh.style.setProperty('--columns', size.columns);
    for (const slot of state.slots) {
      if (!slot && s.hideEmpty) continue;
      const cell = document.createElement('div'); cell.className = 'overlay-cell' + (slot?.fainted ? ' fainted' : '');
      cell.append(makePortrait(slot));
      if (slot?.fainted) { const badge = document.createElement('span'); badge.className='faint-badge'; badge.textContent='OUT'; cell.append(badge); }
      if (s.labels) { const label=document.createElement('div'); label.className='overlay-label'; label.textContent=slot ? displayName(slot)+(slot.level ? ' · Lv. '+slot.level : '') : ''; cell.append(label); }
      fresh.append(cell);
    }
    if (grid) grid.replaceWith(fresh); else root.prepend(fresh);
  }
  root.querySelectorAll('.overlay-stats,.overlay-hunt').forEach(el=>el.remove());
  const c=challengeState(), h=huntState();
  if(c.enabled) { const line=document.createElement('div'); line.className='overlay-stats'; line.textContent=`Deaths ${c.deaths} · Badges ${c.badges}`; root.append(line); }
  if(h.enabled && h.target) { const box=document.createElement('div');box.className='overlay-hunt'; const text=document.createElement('div'); text.append(document.createTextNode(displayName(h.target))); const count=document.createElement('strong');count.textContent=h.count.toLocaleString();text.append(count,document.createTextNode('encounters'));box.append(makePortrait(h.target),text);root.append(box); }
}
function setIdleValue(id,value,checkbox=false) {
  const input=$(id); if(document.activeElement===input) return;
  if(checkbox) input.checked=value; else input.value=value;
}
function render() {
  if(!isSettings) { renderOverlay(); return; }
  renderLegacy();
  setStyleVars($('team-editor'));
  Array.from($('team-editor').children).forEach((card,i)=>{
    const slot=state.slots[i]; card.draggable=Boolean(slot); card.dataset.slot=i;
    card.querySelector('strong').textContent=`${i+1} · ${slot ? displayName(slot)+(slot.level ? ' · Lv. '+slot.level : '') : 'Empty'}`;
    if(slot?.fainted) card.querySelector('.portrait').classList.add('fainted');
    card.ondragstart=e=>{dragSlot=i;e.dataTransfer.effectAllowed='move';e.dataTransfer.setData('text/plain',String(i));};
    card.ondragend=()=>{dragSlot=null;document.querySelectorAll('.drag-over').forEach(el=>el.classList.remove('drag-over'));};
    card.ondragover=e=>{if(dragSlot!==null){e.preventDefault();e.dataTransfer.dropEffect='move';card.classList.add('drag-over');}};
    card.ondragleave=()=>card.classList.remove('drag-over');
    card.ondrop=async e=>{e.preventDefault();card.classList.remove('drag-over');const from=dragSlot;dragSlot=null;if(Number.isInteger(from)&&from!==i)await perform({swap:[from,i]},`Swapped slots ${from+1} and ${i+1}.`);};
    if(!slot)return;
    const edit=document.createElement('button');edit.className='secondary';edit.textContent='Edit';edit.setAttribute('aria-label',`Edit slot ${i+1}`);
    edit.onclick=()=>{if(checking)return;$('slot').value=i+1;$('dex').value=slot.dex;$('form').value=slot.form;$('shiny').checked=slot.shiny;$('nickname').value=slot.nickname||'';$('level').value=slot.level||'';updateForms();$('known-forms').value=Number(slot.form) ? String(Number(slot.form)) : '';invalidatePreview();$('nickname').focus();};
    const move=document.createElement('select');move.setAttribute('aria-label',`Move slot ${i+1}`);move.add(new Option('Move / swap…',''));for(let j=0;j<6;j++)if(j!==i)move.add(new Option(`Slot ${j+1}`,j));
    move.onchange=()=>perform({swap:[i,Number(move.value)]},`Slot ${i+1} moved.`);
    const faint=document.createElement('button');faint.className='secondary';faint.textContent=slot.fainted?'Revive':'Mark fainted';faint.setAttribute('aria-label',`${slot.fainted?'Revive':'Mark fainted'} slot ${i+1}`);faint.onclick=()=>perform({fainted:{slot:i,value:!slot.fainted}},slot.fainted?'Pokémon revived.':'Pokémon marked fainted.');
    card.append(edit,move,faint);
  });
  const s=styleState(), c=challengeState(), h=huntState(), size=dimensions();
  $('dimensions').textContent=`OBS Browser Source size: ${size.width} × ${size.height} pixels. Update OBS dimensions after changing style or hiding slots.`;
  setIdleValue('frame-color',s.frame);setIdleValue('tile-color',s.fill);setIdleValue('tile-size',s.size);setIdleValue('tile-gap',s.gap);setIdleValue('hide-empty',s.hideEmpty,true);setIdleValue('show-labels',s.labels,true);
  setIdleValue('challenge-enabled',c.enabled,true);setIdleValue('deaths',c.deaths);setIdleValue('badges',c.badges);
  setIdleValue('hunt-enabled',h.enabled,true);setIdleValue('hunt-hotkey',h.hotkey);
  $('hunt-summary').replaceChildren();
  if(h.target)$('hunt-summary').append(makePortrait(h.target));
  const count=document.createElement('strong');count.textContent=(h.target?displayName(h.target):'No target selected')+` · ${h.count.toLocaleString()} encounters`;$('hunt-summary').append(count);
  $('hunt-plus').disabled=!h.target;$('hunt-minus').disabled=!h.target||h.count===0;
  const selected=$('saved-teams').value;const names=Object.keys(state.presets||{});
  $('saved-teams').replaceChildren(new Option(names.length?'Select a saved team…':'No saved teams',''));for(const name of names)$('saved-teams').add(new Option(name,name));$('saved-teams').value=names.includes(selected)?selected:'';
  $('load-team').disabled=!names.length;$('delete-team').disabled=!names.length;
}
async function perform(patch,success) { try {await update(patch); if(success)message(success);return true;}catch(e){message(e.message,true);return false;} }
function downloadJSON(value,name) {
  const blob=new Blob([JSON.stringify(value,null,2)],{type:'application/json'}),url=URL.createObjectURL(blob),a=document.createElement('a');a.href=url;a.download=name;a.click();setTimeout(()=>URL.revokeObjectURL(url),1000);
}
function currentTeam() {return {slots:state.slots,layout:state.layout,style:styleState(),challenge:challengeState(),hunt:huntState()};}
async function textFetch(url) {const r=await fetch(url,{signal:AbortSignal.timeout(15000)});if(!r.ok)throw new Error('Source unavailable');return r.text();}
async function loadCredits() {
  const request=++creditRequest;const root=$('artist-credits');root.textContent='Loading credit records…';$('refresh-credits').disabled=true;
  const records=[...state.slots,huntState().target].filter(Boolean);const unique=[...new Map(records.map(s=>[portraitURL(s.dex,s.form,s.shiny),s])).values()];
  try {
    let names=new Map();try{const rows=(await textFetch('https://raw.githubusercontent.com/PMDCollab/SpriteCollab/master/credit_names.txt')).split('\n');for(const row of rows.slice(1)){const cells=row.split('\t');if(cells[0]&&cells[1])names.set(cells[1],cells[0]);}}catch{/* Show raw credited identifiers if name directory is unavailable. */}
    const blocks=await Promise.all(unique.map(async slot=>{
      const article=document.createElement('article'),title=document.createElement('strong');title.textContent=slot.name;article.append(title);
      const url=portraitURL(slot.dex,slot.form,slot.shiny).replace('Normal.png','credits.txt');
      const p=document.createElement('p');
      try{const rows=(await textFetch(url)).trim().split('\n').map(row=>row.split('\t'));const normal=rows.filter(c=>c[4]?.split(',').includes('Normal'));const identifiers=[...new Set((normal.length?normal:rows).map(c=>c[1]).filter(Boolean))];p.textContent=(normal.length?'Normal portrait contributors: ':'Folder contributors (Normal not specified): ')+identifiers.map(id=>names.get(id)||id).join(', ');if(!identifiers.length)p.textContent='No contributor records found.';}catch{p.textContent='Credits could not load. Open the source record to check.';}
      const link=document.createElement('a');link.href=url;link.target='_blank';link.rel='noopener';link.textContent='Source credit record ↗';article.append(p,link);return article;
    }));
    if(request===creditRequest){root.replaceChildren(...blocks);if(!unique.length)root.textContent='Add a Pokémon to view its credits.';}
  } finally {if(request===creditRequest)$('refresh-credits').disabled=false;}
}
function wireFeatures() {
  $('style-form').onsubmit=e=>{e.preventDefault();perform({style:{frame:$('frame-color').value,fill:$('tile-color').value,size:Number($('tile-size').value),gap:Number($('tile-gap').value),hideEmpty:$('hide-empty').checked,labels:$('show-labels').checked}},'Overlay styling updated.');};
  $('reset-style').onclick=()=>perform({style:DEFAULT_STYLE},'Styling reset.');
  $('save-team-form').onsubmit=e=>{e.preventDefault();const name=$('team-name').value.trim();if(!name)return;if(Object.hasOwn(state.presets||{},name)&&!confirm(`Replace saved team “${name}”?`))return;perform({saveTeam:name},`Saved “${name}”.`);};
  $('load-team').onclick=()=>{const name=$('saved-teams').value;if(!name)return message('Select a saved team first.',true);if(confirm(`Load “${name}”? Unsaved changes to the current team will be replaced.`))perform({loadTeam:name},`Loaded “${name}”.`);};
  $('delete-team').onclick=()=>{const name=$('saved-teams').value;if(name&&confirm(`Delete saved team “${name}”? The current team stays unchanged.`))perform({deleteTeam:name},`Deleted “${name}”.`);};
  $('export-team').onclick=()=>downloadJSON({format:'pokemon-team',version:2,team:currentTeam()},'pokemon-team.json');
  $('export-all').onclick=()=>downloadJSON({format:'pokemon-team-backup',version:2,state},'pokemon-team-backup.json');
  $('import-file').onchange=async()=>{const file=$('import-file').files[0];if(!file)return;try{if(file.size>500000)throw new Error('File is too large (maximum 500 KB).');const data=JSON.parse(await file.text());if(!confirm('Import this file? A team replaces the current team; a full backup replaces current and saved teams. Export a backup first if needed.'))return;const ok=await perform({importData:data},'Import complete.');$('import-status').textContent=ok?'Imported successfully.':'Import rejected; existing data preserved.';}catch(e){message(e.message,true);$('import-status').textContent='Import failed; existing data preserved.';}finally{$('import-file').value='';}};
  $('challenge-form').onsubmit=e=>{e.preventDefault();perform({challenge:{enabled:$('challenge-enabled').checked,deaths:Number($('deaths').value),badges:Number($('badges').value)}},'Nuzlocke stats updated.');};
  $('hunt-enabled').onchange=()=>perform({huntOptions:{enabled:$('hunt-enabled').checked}},'Hunt visibility updated.');
  $('hunt-hotkey').onchange=()=>perform({huntOptions:{hotkey:$('hunt-hotkey').value}},'Counter hotkey updated.');
  $('hunt-plus').onclick=()=>perform({huntDelta:1});$('hunt-minus').onclick=()=>perform({huntDelta:-1});
  $('hunt-reset').onclick=()=>{if(confirm('Reset the encounter count to zero?'))perform({huntReset:true},'Encounter count reset.');};
  document.addEventListener('keydown',e=>{if(e.repeat||e.ctrlKey||e.metaKey||e.altKey||e.shiftKey||e.target.closest('input,textarea,select,button,[contenteditable=true]'))return;const h=huntState();if(h.target&&e.code===h.hotkey){e.preventDefault();perform({huntDelta:1});}});
  $('refresh-credits').onclick=loadCredits;
}

if (isSettings) {
  $('add-form').onsubmit = e => { e.preventDefault(); checkAndMaybeSave(true); };
  $('check').onclick = () => checkAndMaybeSave(false);
  $('set-target').onclick = () => checkAndMaybeSave('hunt');
  $('shiny').onchange = invalidatePreview;
  $('dex').oninput = () => { $('nickname').value = ''; $('level').value = ''; $('form').value = ''; updateForms(); invalidatePreview(); };
  $('form').oninput = () => { $('known-forms').value = String(Number($('form').value)) === '0' ? '' : String(Number($('form').value)); invalidatePreview(); };
  $('known-forms').onchange = () => { $('form').value = $('known-forms').value; invalidatePreview(); };
  $('layout').onchange = async () => { const layout = $('layout').value; $('layout').disabled = true; try { await update({layout}); } catch(e) { message(e.message, true); render(); } finally { $('layout').disabled = false; } };
  $('search').oninput = () => { page = 0; renderCatalog(); };
  $('previous').onclick = () => { page--; renderCatalog(); };
  $('next').onclick = () => { page++; renderCatalog(); };
  $('reload-catalog').onclick = loadCatalog;
  wireFeatures();
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
    nickname = value.get('nickname', '')
    level = value.get('level')
    fainted = value.get('fainted', False)
    if not isinstance(nickname, str) or len(nickname) > 24:
        raise ValueError('Nickname must be 24 characters or fewer')
    if level is not None and (type(level) is not int or not 1 <= level <= 100):
        raise ValueError('Level must be 1 to 100 or blank')
    if type(fainted) is not bool:
        raise ValueError('Invalid fainted flag')
    return {'dex': dex, 'form': form, 'name': name, 'shiny': shiny,
            'nickname': nickname, 'level': level, 'fainted': fainted}

DEFAULT_STYLE = {'frame': '#565955', 'fill': '#68a8c0', 'size': 80, 'gap': 8, 'hideEmpty': False, 'labels': False}

def integer(value, low, high):
    if type(value) is not int or not low <= value <= high:
        raise ValueError(f'Expected an integer from {low} to {high}')
    return value

def boolean(value):
    if type(value) is not bool:
        raise ValueError('Expected true or false')
    return value

def validate_style(value):
    if not isinstance(value, dict) or set(value) - set(DEFAULT_STYLE):
        raise ValueError('Invalid styling settings')
    style = dict(DEFAULT_STYLE, **value)
    for key in ('frame', 'fill'):
        if not isinstance(style[key], str) or not re.fullmatch(r'#[0-9a-fA-F]{6}', style[key]):
            raise ValueError('Color must be a six-digit hex value')
    integer(style['size'], 40, 240); integer(style['gap'], 0, 40)
    boolean(style['hideEmpty']); boolean(style['labels'])
    return style

def validate_team(data):
    if not isinstance(data, dict) or not isinstance(data.get('layout'), str) or data['layout'] not in LAYOUTS or not isinstance(data.get('slots'), list) or len(data['slots']) != 6:
        raise ValueError('A team must contain six slots and a valid layout')
    c = data.get('challenge', {})
    h = data.get('hunt', {})
    if not isinstance(c, dict) or not isinstance(h, dict):
        raise ValueError('Invalid challenge or hunt settings')
    hotkey = h.get('hotkey', 'KeyH')
    if hotkey not in ('KeyH', 'KeyE', 'Space'):
        raise ValueError('Invalid hunt hotkey')
    return {'slots': [validate_slot(s) for s in data['slots']], 'layout': data['layout'],
            'style': validate_style(data.get('style', {})),
            'challenge': {'enabled': boolean(c.get('enabled', False)), 'deaths': integer(c.get('deaths', 0), 0, 9999), 'badges': integer(c.get('badges', 0), 0, 99)},
            'hunt': {'enabled': boolean(h.get('enabled', False)), 'target': validate_slot(h.get('target')), 'count': integer(h.get('count', 0), 0, 9999999), 'hotkey': hotkey}}

def team_name(value):
    if not isinstance(value, str) or not value.strip() or len(value.strip()) > 48 or value.strip() in ('__proto__', 'constructor', 'prototype'):
        raise ValueError('Team name must contain 1–48 characters')
    return value.strip()

def validate_state(data):
    team = validate_team(data)
    presets = data.get('presets', {})
    if not isinstance(presets, dict) or len(presets) > 30:
        raise ValueError('Maximum 30 saved teams')
    team['presets'] = {team_name(name): validate_team(value) for name, value in presets.items()}
    return team

def load_state():
    global STATE
    if STATE_FILE.exists():
        STATE = validate_state(json.loads(STATE_FILE.read_text(encoding='utf-8')))
    else:
        STATE = validate_state(STATE)

def patch_state(patch):
    global STATE, REVISION
    if not isinstance(patch, dict):
        raise ValueError('Expected object')
    with CHANGED:
        new = validate_state(copy.deepcopy(STATE))
        keys = set(patch)
        if keys == {'slot', 'value'}:
            index = integer(patch['slot'], 0, 5)
            value = validate_slot(patch['value'])
            # Editing details of an existing Pokémon keeps its fainted status.
            old = new['slots'][index]
            if old and value and (old['dex'], old['form'], old['shiny']) == (value['dex'], value['form'], value['shiny']):
                value['fainted'] = old['fainted']
            new['slots'][index] = value
        elif keys == {'layout'}:
            if not isinstance(patch['layout'], str) or patch['layout'] not in LAYOUTS:
                raise ValueError('Invalid layout')
            new['layout'] = patch['layout']
        elif keys == {'swap'}:
            pair = patch['swap']
            if not isinstance(pair, list) or len(pair) != 2:
                raise ValueError('Expected two slot indices')
            a, b = [integer(i, 0, 5) for i in pair]
            new['slots'][a], new['slots'][b] = new['slots'][b], new['slots'][a]
        elif keys == {'style'}:
            new['style'] = validate_style(patch['style'])
        elif keys == {'saveTeam'}:
            name = team_name(patch['saveTeam'])
            if len(new['presets']) >= 30 and name not in new['presets']:
                raise ValueError('Maximum 30 saved teams; delete one first')
            new['presets'][name] = validate_team(copy.deepcopy(new))
        elif keys == {'loadTeam'}:
            name = team_name(patch['loadTeam'])
            if name not in new['presets']:
                raise ValueError('Saved team no longer exists')
            new = dict(copy.deepcopy(new['presets'][name]), presets=new['presets'])
        elif keys == {'deleteTeam'}:
            name = team_name(patch['deleteTeam'])
            if name not in new['presets']:
                raise ValueError('Saved team no longer exists')
            del new['presets'][name]
        elif keys == {'fainted'}:
            value = patch['fainted']
            if not isinstance(value, dict):
                raise ValueError('Invalid fainted update')
            index = integer(value.get('slot'), 0, 5)
            flag = boolean(value.get('value'))
            slot = new['slots'][index]
            if not slot:
                raise ValueError('That slot is empty')
            if flag and not slot['fainted'] and new['challenge']['enabled']:
                new['challenge']['deaths'] = min(9999, new['challenge']['deaths'] + 1)
            slot['fainted'] = flag
        elif keys == {'challenge'}:
            new['challenge'] = validate_team(dict(new, challenge=patch['challenge']))['challenge']
        elif keys == {'huntTarget'}:
            target = validate_slot(patch['huntTarget'])
            if not target:
                raise ValueError('Choose a hunt target')
            target['fainted'] = False
            new['hunt'].update(target=target, count=0, enabled=True)
        elif keys == {'huntDelta'}:
            delta = integer(patch['huntDelta'], -1, 1)
            if not new['hunt']['target']:
                raise ValueError('Choose a hunt target first')
            new['hunt']['count'] = max(0, min(9999999, new['hunt']['count'] + delta))
        elif keys == {'huntReset'} and patch['huntReset'] is True:
            new['hunt']['count'] = 0
        elif keys == {'huntOptions'}:
            options = patch['huntOptions']
            if not isinstance(options, dict) or set(options) - {'enabled', 'hotkey'}:
                raise ValueError('Invalid hunt options')
            new['hunt'].update(options)
        elif keys == {'importData'}:
            data = patch['importData']
            if not isinstance(data, dict):
                raise ValueError('Invalid import file')
            if data.get('format') == 'pokemon-team' and data.get('version') == 2:
                new = dict(validate_team(data.get('team')), presets=new['presets'])
            elif data.get('format') == 'pokemon-team-backup' and data.get('version') == 2:
                new = validate_state(data.get('state'))
            elif 'slots' in data and 'layout' in data:
                new = validate_state(data)  # Import an older raw save file.
            else:
                raise ValueError('Unsupported team file or version')
        else:
            raise ValueError('Unknown team update')
        new = validate_state(new)
        STATE_FILE.parent.mkdir(exist_ok=True)
        temporary = STATE_FILE.with_suffix('.tmp')
        with temporary.open('w', encoding='utf-8') as f:
            json.dump(new, f, ensure_ascii=False, indent=2)
            f.flush(); os.fsync(f.fileno())
        os.replace(temporary, STATE_FILE)
        STATE = new; REVISION += 1; CHANGED.notify_all()
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
            if not 0 < length <= 524288:
                raise ValueError('Invalid request size')
            self.connection.settimeout(10)
            patch = json.loads(self.rfile.read(length))
            self.reply(200, patch_state(patch))
        except (ValueError, UnicodeDecodeError, TimeoutError) as error:
            self.reply(400, {'error': str(error) or 'Invalid team update'})
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
