'use strict';
const token = '__TOKEN__';
const $ = id => document.getElementById(id);
const selected = new Set();
let state = {sources: [], projects: [], google: {}}, prepared = null, preview = null, lastAnswer = null;
let busy = 0;
const project = () => $('project').value ? Number($('project').value) : null;
function node(tag, text, className) {
  const n = document.createElement(tag);
  if (text !== undefined) n.textContent = text;
  if (className) n.className = className;
  return n;
}
function notice(message, error = false) {
  $('notice').hidden = false;
  $('notice').classList.toggle('error', error);
  $('notice').textContent = message;
  const dialog = document.querySelector('dialog[open]');
  if (dialog) {
    let status = dialog.querySelector('.dialog-status');
    if (!status) { status = node('p', '', 'dialog-status'); status.setAttribute('role', 'status'); dialog.querySelector('.dialog-heading').after(status); }
    status.textContent = message;
    status.classList.toggle('error', error);
  }
}
async function api(path, body) {
  const options = {headers: {'X-Session-Token': token}};
  if (body !== undefined) {
    options.method = 'POST'; options.headers['Content-Type'] = 'application/json';
    options.body = JSON.stringify(body);
  }
  const response = await fetch(path, options);
  const data = await response.json();
  if (!response.ok) throw new Error(data.error || 'Požadavek selhal.');
  return data;
}
async function work(fn, button) {
  if (busy) { notice('Nejdříve vyčkej na dokončení předchozí akce.'); return; }
  busy++;
  const label = button?.textContent;
  if (button) { button.disabled = true; button.textContent = 'Pracuji…'; }
  try { await fn(); }
  catch (error) { notice(error.message, true); }
  finally {
    busy--;
    if (button) { button.disabled = false; button.textContent = label; }
    $('ask').disabled = !prepared || !document.querySelector('#evidence-list input:checked');
    $('google-connect').disabled = !!state.google.authorizing;
  }
}
function showView(name) {
  const names = {library: 'Knihovna', ask: 'Zeptat se kolegy', gmail: 'Gmail', calendar: 'Kalendář'};
  for (const key of Object.keys(names)) $(key + '-view').hidden = key !== name;
  document.querySelectorAll('[data-view]').forEach(n => n.classList.toggle('active', n.dataset.view === name));
  $('breadcrumb').textContent = names[name];
}
function invalidate() { prepared = null; $('ask').disabled = true; }
function updateSettings() {
  $('api-status').textContent = state.api_configured ? 'API klíč je nastavený pro tuto relaci.' : 'API klíč zatím není nastavený.';
  $('google-status').textContent = state.google.message || (state.google.connected ? 'Google účet je připojený.' : 'Google účet zatím není připojený.');
  $('google-connect').disabled = !!state.google.authorizing;
}
async function refresh() {
  state = await api('/api/state');
  const value = $('project').value;
  $('project').replaceChildren(node('option', 'Všechny zdroje'));
  $('project').firstChild.value = '';
  for (const p of state.projects) { const opt = node('option', p.name); opt.value = p.id; $('project').append(opt); }
  $('project').value = value;
  if ($('project').selectedIndex < 0) $('project').value = '';
  const ids = new Set(state.sources.map(s => s.id));
  for (const id of selected) if (!ids.has(id)) selected.delete(id);
  $('source-count').textContent = state.sources.length;
  updateSettings(); renderSources();
}
function renderSources() {
  const sources = state.sources.filter(s => (project() === null || s.project_id === project()) &&
    s.title.toLocaleLowerCase('cs').includes($('source-filter').value.toLocaleLowerCase('cs')));
  const list = $('source-list'); list.replaceChildren();
  $('library-count').textContent = `${sources.length} zdrojů`;
  if (!sources.length) {
    const empty = node('div', undefined, 'empty');
    empty.append(node('div', '≋', 'empty-icon'), node('h3', 'Dobré myšlenky potřebují místo.'),
      node('p', 'Přidej první poznámku, dokument nebo e-mail. Postupně z nich vznikne paměť tvých projektů.'));
    list.append(empty);
  }
  for (const source of sources) {
    const card = node('article', undefined, 'source-card' + (selected.has(source.id) ? ' selected' : ''));
    const check = document.createElement('input'); check.type = 'checkbox'; check.checked = selected.has(source.id);
    check.setAttribute('aria-label', 'Vybrat zdroj ' + source.title);
    check.onchange = () => { if (check.checked) selected.add(source.id); else selected.delete(source.id); invalidate(); renderSources(); };
    const open = node('button', undefined, 'source-open');
    const kind = source.title.startsWith('Gmail:') ? 'E-MAIL' : source.title.startsWith('Kalendář:') ? 'UDÁLOST' : 'POZNÁMKA / DOKUMENT';
    const name = state.projects.find(p => p.id === source.project_id)?.name || 'Bez projektu';
    const meta = node('div', undefined, 'meta');
    meta.append(node('span', name), node('span', `${source.characters.toLocaleString('cs')} znaků`),
      node('span', new Date(source.created_at).toLocaleDateString('cs')));
    open.append(node('span', kind, 'source-kind'), node('h3', source.title), meta);
    open.onclick = () => work(() => openSource(source.id));
    card.append(check, open); list.append(card);
  }
  $('selection-bar').hidden = !selected.size;
  $('selection-count').textContent = `Vybráno zdrojů: ${selected.size} (nejvýše 6 pro jeden dotaz)`;
}
function download(name, text) {
  const url = URL.createObjectURL(new Blob([text], {type: 'text/markdown;charset=utf-8'}));
  const a = document.createElement('a'); a.href = url; a.download = name; a.click();
  setTimeout(() => URL.revokeObjectURL(url), 1000);
}
async function openSource(id) {
  preview = await api('/api/source?id=' + id);
  $('preview-title').textContent = preview.title;
  $('preview-text').textContent = preview.body;
  $('delete-source').hidden = $('export-source').hidden = false;
  $('preview-dialog').showModal();
}
function openPassage(passage) {
  $('preview-title').textContent = passage.title + ' · podklad ' + passage.passage_id;
  $('preview-text').textContent = passage.text;
  $('delete-source').hidden = $('export-source').hidden = true;
  $('preview-dialog').showModal();
}
function renderEvidence(evidence) {
  $('evidence-list').replaceChildren();
  $('evidence-hint').textContent = evidence.length ?
    `Vybráno ${evidence.length} pasáží. Zkontroluj, co odešleš. U dlouhých zdrojů se vybírá nejvýše 12 pasáží, nikoli celý dokument.` :
    'Nenašel jsem podklady podle zadaných slov. Zkus konkrétnější slova nebo vyber zdroj v knihovně.';
  for (const p of evidence) {
    const row = node('div', undefined, 'evidence');
    const input = document.createElement('input'); input.type = 'checkbox'; input.checked = true;
    input.value = p.passage_id; input.id = 'passage-' + p.passage_id;
    input.onchange = () => { $('ask').disabled = !document.querySelector('#evidence-list input:checked'); };
    const label = document.createElement('label'); label.htmlFor = input.id;
    label.append(node('strong', `[${p.passage_id}] ${p.title}`), node('p', p.text));
    const view = node('button', 'Otevřít celou pasáž', 'citation'); view.onclick = () => openPassage(p);
    label.append(view); row.append(input, label); $('evidence-list').append(row);
  }
  $('ask').disabled = !evidence.length;
}
function renderAnswer(answer) {
  lastAnswer = answer;
  $('answer').replaceChildren();
  const heading = node('div', undefined, 'answer-header');
  const exportButton = node('button', 'Exportovat ↓', 'secondary');
  exportButton.onclick = () => download('second-brain-odpoved.md', answerMarkdown());
  heading.append(node('h2', 'Co z podkladů vyplývá'), exportButton); $('answer').append(heading);
  for (const s of answer.statements) {
    const article = node('article', undefined, 'statement ' + s.kind);
    const labels = {fact: 'PODLE PODKLADŮ', suggestion: 'NÁVRH KOLEGY', uncertain: 'NEJISTOTA / CHYBĚJÍCÍ PODKLAD'};
    article.append(node('span', labels[s.kind], 'statement-kind'), node('p', s.text));
    for (const id of s.passage_ids) {
      const p = answer.evidence.find(p => p.passage_id === id);
      if (!p) continue;
      const link = node('button', `[${id}] ${p.title}`, 'citation');
      link.onclick = () => openPassage(p); article.append(link);
    }
    $('answer').append(article);
  }
  if (answer.follow_up.length) {
    const follow = node('div', undefined, 'follow-up'), ul = document.createElement('ul');
    follow.append(node('h3', 'Co si ještě vyjasnit'));
    for (const q of answer.follow_up) ul.append(node('li', q));
    follow.append(ul); $('answer').append(follow);
  }
  $('answer').append(node('p', 'Citace ukazují použité podklady. Nezaručují správnou interpretaci — důležitá rozhodnutí ověř.', 'footnote'));
}
function answerMarkdown() {
  const labels = {fact: 'Podle podkladů', suggestion: 'Návrh', uncertain: 'Nejistota'};
  return '# ' + lastAnswer.question + '\n\n' + lastAnswer.statements.map(s =>
    `**${labels[s.kind]}:** ${s.text} ${s.passage_ids.map(id => `[${id}]`).join(' ')}`).join('\n\n') +
    '\n\n## Podklady\n\n' + lastAnswer.evidence.map(p => `[${p.passage_id}] ${p.title}\n\n${p.text}`).join('\n\n');
}
document.querySelectorAll('[data-view]').forEach(n => n.onclick = () => showView(n.dataset.view));
document.querySelectorAll('[data-close]').forEach(n => n.onclick = () => $(n.dataset.close).close());
$('source-filter').oninput = renderSources;
$('project').onchange = () => { selected.clear(); invalidate(); renderSources(); $('answer').replaceChildren(); renderEvidence([]); };
$('question').oninput = invalidate;
$('add-source').onclick = () => $('source-dialog').showModal();
$('new-project').onclick = () => $('project-dialog').showModal();
$('settings').onclick = () => { $('model').value = state.model || 'gpt-4.1'; updateSettings(); $('settings-dialog').showModal(); };
$('ask-selected').onclick = () => { showView('ask'); $('question').focus(); };
$('project-form').onsubmit = event => { event.preventDefault(); work(async () => {
  const result = await api('/api/projects', {name: $('project-name').value});
  await refresh(); $('project').value = result.id; selected.clear(); invalidate(); renderSources();
  $('project-form').reset(); $('project-dialog').close(); notice('Projekt vytvořen.');
}, event.submitter); };
$('source-form').onsubmit = event => { event.preventDefault(); work(async () => {
  const file = $('source-file').files[0];
  const title = $('source-title').value, text = $('source-text').value;
  if (file && text.trim()) throw new Error('Vyber soubor, nebo vlož text. Pro dva zdroje použij dva samostatné importy.');
  if (file && file.size > 8000000) throw new Error('Soubor může mít nejvýše 8 MB.');
  if (file && file.name.toLowerCase().endsWith('.pdf')) {
    const bytes = new Uint8Array(await file.arrayBuffer()); let binary = '';
    for (let i = 0; i < bytes.length; i += 32768) binary += String.fromCharCode(...bytes.subarray(i, i + 32768));
    await api('/api/pdf', {title, data: btoa(binary), project_id: project()});
  } else {
    await api('/api/sources', {title, text: file ? await file.text() : text, project_id: project()});
  }
  $('source-form').reset(); $('source-dialog').close(); await refresh(); invalidate(); notice('Zdroj uložený na Macu.');
}, event.submitter); };
$('source-file').onchange = () => { if (!$('source-title').value && $('source-file').files[0]) $('source-title').value = $('source-file').files[0].name; };
$('export-source').onclick = () => { if (preview) download('zdroj-' + preview.id + '.md', '# ' + preview.title + '\n\n' + preview.body); };
$('delete-source').onclick = () => { if (preview && confirm('Smazat tento zdroj z knihovny? Exportované kopie zůstanou zachované.')) work(async () => {
  await api('/api/delete-source', {id: preview.id}); $('preview-dialog').close(); invalidate(); await refresh(); notice('Zdroj smazán z knihovny.');
}, $('delete-source')); };
$('prepare').onclick = () => work(async () => {
  const question = $('question').value.trim();
  if (!question) throw new Error('Nejdříve napiš otázku.');
  if (selected.size > 6) throw new Error('Pro jeden dotaz vyber nejvýše šest zdrojů.');
  const scope = project(), ids = [...selected];
  invalidate();
  const result = await api('/api/prepare', {question, source_ids: ids, project_id: scope});
  if (question !== $('question').value.trim() || scope !== project() || ids.join(',') !== [...selected].join(',')) throw new Error('Změnil se dotaz, projekt nebo výběr. Najdi podklady znovu.');
  prepared = {question, project: scope, evidence: result.evidence};
  renderEvidence(result.evidence); notice('Podklady připravené místně. Do AI zatím nic neodešlo.');
}, $('prepare'));
$('ask').onclick = () => work(async () => {
  if (!prepared || prepared.question !== $('question').value.trim() || prepared.project !== project()) throw new Error('Nejdříve znovu připrav podklady.');
  const question = prepared.question;
  const scope = prepared.project;
  const ids = [...document.querySelectorAll('#evidence-list input:checked')].map(n => Number(n.value));
  if (!ids.length) throw new Error('Vyber alespoň jednu pasáž.');
  notice('Odesílám otázku a vybrané pasáže do OpenAI…');
  const answer = await api('/api/ask', {question, passage_ids: ids, project_id: scope});
  if (scope !== project() || question !== $('question').value.trim()) throw new Error('Mezitím se změnil projekt nebo dotaz. Odpověď pro původní zadání nebyla zobrazena.');
  renderAnswer({...answer, question}); notice('Odpověď připravena. Otevři citace pro kontrolu podkladů.');
}, $('ask'));
$('settings-form').onsubmit = event => { event.preventDefault(); work(async () => {
  await api('/api/settings', {api_key: $('api-key').value, model: $('model').value}); $('api-key').value = '';
  await refresh(); notice('Nastavení použité. API klíč zůstává pouze v paměti této relace.');
}, event.submitter); };
$('forget-key').onclick = () => work(async () => { await api('/api/settings', {forget_key: true}); await refresh(); notice('API klíč odstraněn z této relace.'); }, $('forget-key'));
$('google-client').onchange = () => work(async () => {
  const file = $('google-client').files[0]; if (!file) return;
  if (file.size > 50000) throw new Error('Soubor nevypadá jako Google OAuth JSON.');
  await api('/api/google/configure', {config: JSON.parse(await file.text())}); $('google-client').value = ''; await refresh();
  notice('Google OAuth klient připraven. Nyní připoj účet.');
});
$('google-connect').onclick = () => work(async () => { await api('/api/google/connect', {}); await refresh(); notice('Dokonči přihlášení v nově otevřeném okně.'); }, $('google-connect'));
$('google-disconnect').onclick = () => work(async () => { await api('/api/google/disconnect', {}); await refresh(); notice(state.google.message); }, $('google-disconnect'));
function importRow(title, subtitle, onImport) {
  const row = node('div', undefined, 'import-row'), details = document.createElement('div');
  details.append(node('h3', title), node('p', subtitle));
  const button = node('button', 'Uložit do knihovny', 'secondary'); button.onclick = () => work(() => onImport(), button);
  row.append(details, button); return row;
}
$('mail-search-form').onsubmit = event => { event.preventDefault(); work(async () => {
  const result = await api('/api/gmail/search', {query: $('mail-query').value}); $('mail-list').replaceChildren();
  for (const message of result.messages) $('mail-list').append(importRow(message.title, message.sender + ' · ' + message.date, async () => {
    await api('/api/gmail/import', {id: message.id, project_id: project()}); await refresh(); notice('E-mail uložen místně.');
  }));
  if (!result.messages.length) $('mail-list').append(node('p', 'Žádné odpovídající zprávy.', 'footnote'));
}, event.submitter); };
$('load-calendar').onclick = () => work(async () => {
  const result = await api('/api/calendar/list', {}); $('event-list').replaceChildren();
  for (const event of result.events) $('event-list').append(importRow(event.title, event.start, async () => {
    await api('/api/calendar/import', {id: event.id, project_id: project()}); await refresh(); notice('Událost uložená místně.');
  }));
  if (!result.events.length) $('event-list').append(node('p', 'V příštích sedmi dnech nejsou události.', 'footnote'));
}, $('load-calendar'));
work(refresh);
setInterval(async () => { if (state.google.authorizing && !busy) { try { await refresh(); } catch (_) {} } }, 2500);
