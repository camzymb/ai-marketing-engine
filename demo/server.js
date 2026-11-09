// Live lead-loop run: calls the real Claude API (or a mock for dry runs) and streams progress to a dashboard.
// Usage: node demo/server.js [--mock] [--port=8787]   (reads ANTHROPIC_API_KEY from .env)
const http = require('http');
const fs = require('fs');
const path = require('path');
require('../scripts/env.js');

const ROOT = path.join(__dirname, '..');
const MOCK = process.argv.includes('--mock');
const PORT = Number((process.argv.find(a => a.startsWith('--port=')) || '--port=8787').split('=')[1]);
const MODEL = 'claude-haiku-5-5';
const PRICE_IN = 0.10 / 1e6, PRICE_OUT = 0.50 / 1e6; // Haiku 5.5 list prices, prompts under 100k tokens

const SYSTEM = fs.readFileSync(path.join(ROOT, 'agents', 'built', 'lead.md'), 'utf8');

function parseCsv(text) {
  const rows = []; let row = [], field = '', q = false;
  for (let i = 0; i < text.length; i++) {
    const c = text[i];
    if (q) { if (c === '"' && text[i + 1] === '"') { field += '"'; i++; } else if (c === '"') q = false; else field += c; }
    else if (c === '"') q = true;
    else if (c === ',') { row.push(field); field = ''; }
    else if (c === '\n') { row.push(field); rows.push(row); row = []; field = ''; }
    else if (c !== '\r') field += c;
  }
  if (field || row.length) { row.push(field); rows.push(row); }
  const [head, ...body] = rows.filter(r => r.length > 1);
  return body.map(r => Object.fromEntries(head.map((h, i) => [h, r[i] || ''])));
}

const leads = parseCsv(fs.readFileSync(path.join(ROOT, 'test-data', 'test-leads.csv'), 'utf8'));
const key = parseCsv(fs.readFileSync(path.join(ROOT, 'test-data', 'test-leads-answer-key.csv'), 'utf8'));

const clients = new Set();
const history = [];
function send(event, data) {
  const msg = `event: ${event}\ndata: ${JSON.stringify(data)}\n\n`;
  history.push(msg);
  for (const res of clients) res.write(msg);
}

function scoreFrom(out) {
  const signals = Array.isArray(out.signals) ? out.signals : [];
  const raw = signals.reduce((s, x) => s + Number(x.points || 0), 0);
  if (out.is_spam === true) return { score: 0, band: 'spam', signals };
  const score = Math.max(1, Math.min(100, raw));
  return { score, band: score >= 70 ? 'hot' : score >= 40 ? 'warm' : 'cold', signals };
}

function parseAnswer(text) {
  try { return JSON.parse(text); } catch (e) {
    const m = text.match(/\{[\s\S]*\}/);
    if (m) { try { return JSON.parse(m[0]); } catch (e2) { return null; } }
    return null;
  }
}

async function callClaude(lead, onDelta, onThink) {
  const leadForClaude = {
    name: `${lead['First Name']} ${lead['Last Name']}`.trim(), email: lead['Email'], company: lead['Company Name'],
    job_title: lead['Job Title'], company_size: lead['Company Size'], country: lead['Country'],
    website: lead['Website URL'], message: lead['Message'],
  };
  const body = {
    model: MODEL, max_tokens: 4000, stream: true, system: SYSTEM,
    thinking: { type: 'adaptive', display: 'summarized' },
    messages: [{ role: 'user', content: 'New lead:\n' + JSON.stringify(leadForClaude, null, 2) }],
  };
  const resp = await fetch('https://api.anthropic.com/v1/messages', {
    method: 'POST',
    headers: { 'x-api-key': process.env.ANTHROPIC_API_KEY, 'anthropic-version': '2023-06-01', 'content-type': 'application/json' },
    body: JSON.stringify(body),
  });
  if (!resp.ok) throw new Error(`API ${resp.status}: ${(await resp.text()).slice(0, 300)}`);
  const reader = resp.body.getReader();
  const dec = new TextDecoder();
  let buf = '', text = '', thinking = '', inTok = 0, outTok = 0;
  for (;;) {
    const { value, done } = await reader.read();
    if (done) break;
    buf += dec.decode(value, { stream: true });
    let i;
    while ((i = buf.indexOf('\n\n')) >= 0) {
      const chunk = buf.slice(0, i); buf = buf.slice(i + 2);
      const line = chunk.split('\n').find(l => l.startsWith('data: '));
      if (!line) continue;
      const ev = JSON.parse(line.slice(6));
      if (ev.type === 'message_start') inTok = ev.message.usage.input_tokens || 0;
      if (ev.type === 'content_block_delta' && ev.delta.type === 'text_delta') { text += ev.delta.text; onDelta(ev.delta.text); }
      if (ev.type === 'content_block_delta' && ev.delta.type === 'thinking_delta' && ev.delta.thinking) { thinking += ev.delta.thinking; onThink(ev.delta.thinking); }
      if (ev.type === 'message_delta' && ev.usage) outTok = ev.usage.output_tokens || outTok;
    }
  }
  return { text, thinking, inTok, outTok };
}

async function mockClaude(lead, idx, onDelta) {
  // Dry-run only: fake output shaped like a real answer, used to test the dashboard and recorder.
  const k = key[idx];
  const out = { is_spam: k['Expected band'] === 'spam', signals: k['Expected band'] === 'spam' ? [] : [{ signal: 'Mock signal', points: Number(k['Expected score']) }], matching_service: 'Mock', summary: 'MOCK RUN, not real output.', reply_language: 'English', reply_subject: 'Mock', reply_draft: k['Expected band'] === 'spam' ? '' : 'MOCK draft for testing the dashboard only. This is not a real Claude answer.' };
  const text = JSON.stringify(out, null, 1);
  for (let i = 0; i < text.length; i += 6) { onDelta(text.slice(i, i + 6)); await new Promise(r => setTimeout(r, 15)); }
  return { text, inTok: 2400, outTok: 250 };
}

async function run() {
  await new Promise(r => setTimeout(r, Number(process.env.START_DELAY_MS || 4000)));
  send('start', { total: leads.length, model: MODEL, mock: MOCK, startedAt: new Date().toISOString() });
  const results = [];
  const t0 = Date.now();
  const LIMIT = Number(process.env.LIMIT || leads.length);
  for (let i = 0; i < Math.min(LIMIT, leads.length); i++) {
    const lead = leads[i];
    send('lead_start', { i, lead });
    const t1 = Date.now();
    let r;
    try {
      r = MOCK ? await mockClaude(lead, i, d => send('delta', { i, d })) : await callClaude(lead, d => send('delta', { i, d }), t => send('think', { i, t }));
    } catch (e) {
      send('lead_error', { i, error: String(e.message || e) });
      results.push({ i, error: String(e.message || e) });
      continue;
    }
    const out = parseAnswer(r.text);
    const s = out ? scoreFrom(out) : { score: 0, band: 'error', signals: [] };
    const cost = r.inTok * PRICE_IN + r.outTok * PRICE_OUT;
    const res = {
      i, name: `${lead['First Name']} ${lead['Last Name']}`.trim(), company: lead['Company Name'],
      score: s.score, band: s.band, signals: s.signals,
      expectedScore: Number(key[i]['Expected score']), expectedBand: key[i]['Expected band'],
      summary: out ? out.summary : '', replyLanguage: out ? out.reply_language : '', replySubject: out ? out.reply_subject : '',
      replyDraft: out ? out.reply_draft : '', matchingService: out ? out.matching_service : '',
      inTok: r.inTok, outTok: r.outTok, cost, seconds: (Date.now() - t1) / 1000, raw: out ? undefined : r.text, thinking: r.thinking,
    };
    results.push(res);
    send('lead_done', res);
  }
  const done = results.filter(r => !r.error);
  const summary = {
    total: Math.min(Number(process.env.LIMIT || leads.length), leads.length), ok: done.length, seconds: (Date.now() - t0) / 1000,
    cost: done.reduce((s, r) => s + r.cost, 0),
    bandMatches: done.filter(r => r.band === r.expectedBand).length,
    within15: done.filter(r => Math.abs(r.score - r.expectedScore) <= 15).length,
    bands: done.reduce((m, r) => (m[r.band] = (m[r.band] || 0) + 1, m), {}),
    mock: MOCK,
  };
  send('summary', summary);
  fs.writeFileSync(path.join(__dirname, MOCK ? 'results-mock.json' : 'results.json'), JSON.stringify({ summary, results }, null, 2));
  console.log('RUN DONE', JSON.stringify(summary));
}

http.createServer((req, res) => {
  if (req.url === '/events') {
    res.writeHead(200, { 'content-type': 'text/event-stream', 'cache-control': 'no-cache', connection: 'keep-alive' });
    for (const m of history) res.write(m);
    clients.add(res);
    req.on('close', () => clients.delete(res));
    return;
  }
  // Only the dashboard page is served. Nothing else in the folder can be read through the server.
  if (req.url !== '/' && req.url !== '/dashboard.html') { res.writeHead(404); res.end(); return; }
  res.writeHead(200, { 'content-type': 'text/html; charset=utf-8', 'x-content-type-options': 'nosniff', 'content-security-policy': "default-src 'self' 'unsafe-inline'" });
  res.end(fs.readFileSync(path.join(__dirname, 'dashboard.html')));
}).listen(PORT, '127.0.0.1', () => { console.log('listening', PORT, MOCK ? '(mock)' : '(live API)'); run(); });
