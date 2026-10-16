'use strict';
const token = '__TOKEN__';
const el = id => document.getElementById(id);
let notes = '';
let pending = false;
let errorMessage = '';
let running = false;
let renderedNotes = '';
const emptyNotes = el('notes').innerHTML;
const emptySteps = el('next-steps').innerHTML;
async function request(path, body) {
  const options = {headers: {'X-Session-Token': token}};
  if (body !== undefined) {
    options.method = 'POST';
    options.headers['Content-Type'] = 'application/json';
    options.body = JSON.stringify(body);
  }
  const response = await fetch(path, options);
  const data = await response.json();
  if (!response.ok) throw new Error(data.error || 'Požadavek selhal.');
  return data;
}
function renderText(target, text) {
  target.replaceChildren();
  let list = null;
  const headings = /^(Hlavní myšlenky|Co zůstává nejasné|Vysvětlení pro učení|Možnosti a doporučení.*|Navržené úkoly|Otázky na příště)$/i;
  for (let line of text.split('\n')) {
    line = line.trim();
    if (!line) { list = null; continue; }
    const clean = line.replace(/^#{1,6}\s*/, '').replace(/\*\*/g, '').replace(/:$/, '');
    if (/^#{1,6}\s/.test(line) || headings.test(clean)) {
      const heading = document.createElement('h3');
      heading.textContent = clean;
      target.append(heading); list = null;
    } else if (/^[-*•]\s|^\d+[.)]\s/.test(line)) {
      if (!list) { list = document.createElement('ul'); target.append(list); }
      const item = document.createElement('li');
      item.textContent = line.replace(/^([-*•]|\d+[.)])\s*/, '').replace(/\*\*/g, '');
      list.append(item);
    } else {
      const paragraph = document.createElement('p');
      paragraph.textContent = line.replace(/\*\*/g, '');
      target.append(paragraph); list = null;
    }
  }
}
function nextSteps(text, mainNotes = false) {
  const lines = [];
  let include = mainNotes;
  for (const line of text.split('\n')) {
    const clean = line.trim().replace(/^#{1,6}\s*/, '').replace(/\*\*/g, '').replace(/:$/, '');
    if (/^(Hlavní myšlenky|Co zůstává nejasné|Vysvětlení pro učení|Možnosti a doporučení.*|Navržené úkoly|Otázky na příště)$/i.test(clean)) {
      const isStep = /^(Možnosti|Navržené|Otázky)/i.test(clean);
      include = mainNotes ? !isStep : isStep;
    }
    if (include) lines.push(line);
  }
  return lines.join('\n').trim();
}
function render(state) {
  notes = state.notes;
  running = state.running;
  if (notes !== renderedNotes) {
    if (notes) renderText(el('notes'), nextSteps(notes, true) || 'Další kroky najdeš v panelu Co dál?.');
    else el('notes').innerHTML = emptyNotes;
    const steps = nextSteps(notes);
    el('next-steps').classList.toggle('note-content', !!steps);
    if (steps) renderText(el('next-steps'), steps);
    else el('next-steps').innerHTML = emptySteps;
    renderedNotes = notes;
  }
  el('status').textContent = errorMessage || state.status;
  el('session-label').textContent = errorMessage ? 'Něco se nepovedlo' : running ? 'Kolega poslouchá' : 'Poslech je vypnutý';
  el('session-indicator').classList.toggle('listening', running);
  el('session-indicator').classList.toggle('has-error', !!errorMessage);
  el('update-count').textContent = state.chunks ? `Zpracovaných vstupů: ${state.chunks}` : 'Zatím bez poznámek';
  el('level').value = state.level;
  el('start').hidden = running;
  el('stop').hidden = !running;
  el('start').disabled = pending;
  el('add').disabled = pending;
  el('export').disabled = !notes;
}
async function action(path, body) {
  pending = true;
  errorMessage = '';
  el('start').disabled = el('add').disabled = true;
  try { render(await request(path, body)); }
  catch (error) { errorMessage = error.message; el('status').textContent = errorMessage; }
  finally { pending = false; el('start').disabled = el('add').disabled = false; }
}
el('start').onclick = () => action('/api/start', {goals: el('goals').value});
el('stop').onclick = () => action('/api/stop', {});
el('clear').onclick = async () => {
  if (confirm('Zastavit poslech a vymazat poznámky z paměti aplikace? Exportované soubory zůstanou zachované.')) {
    el('input').value = el('goals').value = '';
    await action('/api/clear', {});
  }
};
el('add').onclick = async () => {
  await action('/api/note', {text: el('input').value, goals: el('goals').value});
  if (!errorMessage) el('input').value = '';
};
el('export').onclick = () => {
  if (!notes) return;
  const url = URL.createObjectURL(new Blob(['# Poznámky ze semináře\n\n' + notes], {type: 'text/markdown;charset=utf-8'}));
  const a = document.createElement('a');
  a.href = url; a.download = 'seminar-' + new Date().toISOString().slice(0, 10) + '.md';
  a.click(); setTimeout(() => URL.revokeObjectURL(url), 1000);
};
async function poll() {
  try { render(await request('/api/state')); }
  catch (_) { el('status').textContent = 'Aplikace není dostupná. Ověř Terminál a znovu načti stránku.'; }
  setTimeout(poll, 1000);
}
window.addEventListener('beforeunload', event => {
  if (running) { event.preventDefault(); event.returnValue = ''; }
});
el('settings').onclick = () => el('settings-dialog').showModal();
el('close-settings').onclick = () => el('settings-dialog').close();
el('input').addEventListener('keydown', event => {
  if ((event.metaKey || event.ctrlKey) && event.key === 'Enter' && !pending) {
    event.preventDefault(); el('add').click();
  }
});
poll();
