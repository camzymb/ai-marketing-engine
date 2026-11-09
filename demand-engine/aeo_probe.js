// AEO probe: asks Claude Haiku 5.5 the questions a buyer might ask, with no web search and no context,
// and records whether your brand is mentioned. Questions live in probe-questions.json.
// Usage: node demand-engine/aeo_probe.js <output.json>   (reads ANTHROPIC_API_KEY and BRAND_NAMES from .env)
require('../scripts/env.js');
const fs = require('fs');
const path = require('path');
const QUESTIONS = JSON.parse(fs.readFileSync(path.join(__dirname, 'probe-questions.json'), 'utf8'));
const NAMES = (process.env.BRAND_NAMES || '').split(',').map(s => s.trim()).filter(Boolean)
  .map(s => new RegExp(s.replace(/[.*+?^${}()|[\]\\]/g, '\\$&'), 'i'));
const out = process.argv[2] || path.join(__dirname, 'aeo-probe.json');
(async () => {
  const results = []; let inTok = 0, outTok = 0;
  for (const q of QUESTIONS) {
    const r = await fetch('https://api.anthropic.com/v1/messages', {
      method: 'POST',
      headers: { 'x-api-key': process.env.ANTHROPIC_API_KEY, 'anthropic-version': '2023-06-01', 'content-type': 'application/json' },
      body: JSON.stringify({ model: 'claude-haiku-5-5', max_tokens: 2000, messages: [{ role: 'user', content: q }] }),
    });
    const d = await r.json();
    if (!r.ok) { console.error('API error', r.status, JSON.stringify(d).slice(0, 300)); process.exit(1); }
    const text = (d.content || []).filter(c => c.type === 'text').map(c => c.text).join('');
    inTok += d.usage.input_tokens; outTok += d.usage.output_tokens;
    const hit = NAMES.some(n => n.test(text));
    results.push({ question: q, mentionsBrand: hit, answer: text });
    console.log((hit ? 'MENTION ' : 'no      ') + q);
  }
  const cost = inTok * 0.10 / 1e6 + outTok * 0.50 / 1e6;
  fs.writeFileSync(out, JSON.stringify({ date: new Date().toISOString(), model: 'claude-haiku-5-5', webSearch: false, cost, results }, null, 2));
  console.log('DONE cost', cost.toFixed(4));
})();
