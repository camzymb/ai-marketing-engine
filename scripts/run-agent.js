// Generic agent runner for the Claude Messages API with server tools (web search, web fetch).
// Usage: node scripts/run-agent.js <config.json>   (reads ANTHROPIC_API_KEY from .env)
// config: { model, max_tokens, system_file, user_file, tools, out_prefix }
const fs = require('fs');
const path = require('path');
require('./env.js');

const PRICES = { // USD per token, list prices from platform.claude.com pricing page (Nov 2026)
  'claude-opus-5-5': [4 / 1e6, 20 / 1e6],
  'claude-sonnet-5-5': [2 / 1e6, 10 / 1e6],
  'claude-haiku-5-5': [0.10 / 1e6, 0.50 / 1e6],
};
const SEARCH_PRICE = 0.01;

(async () => {
  const cfgPath = process.argv[2];
  const cfg = JSON.parse(fs.readFileSync(cfgPath, 'utf8'));
  const dir = path.dirname(path.resolve(cfgPath));
  const system = fs.readFileSync(path.join(dir, cfg.system_file), 'utf8');
  const user = fs.readFileSync(path.join(dir, cfg.user_file), 'utf8');
  const messages = [{ role: 'user', content: user }];
  let inTok = 0, outTok = 0, searches = 0, fetches = 0, turns = 0;
  const t0 = Date.now();
  let finalText = '';
  for (;;) {
    turns++;
    const body = { model: cfg.model, max_tokens: cfg.max_tokens, system, messages, tools: cfg.tools || [] };
    if (cfg.thinking) body.thinking = cfg.thinking;
    if (cfg.output_config) body.output_config = cfg.output_config;
    const resp = await fetch('https://api.anthropic.com/v1/messages', {
      method: 'POST',
      headers: { 'x-api-key': process.env.ANTHROPIC_API_KEY, 'anthropic-version': '2023-06-01', 'content-type': 'application/json' },
      body: JSON.stringify(body),
    });
    const data = await resp.json();
    if (!resp.ok) { console.error('API error', resp.status, JSON.stringify(data).slice(0, 500)); process.exit(1); }
    inTok += (data.usage.input_tokens || 0) + (data.usage.cache_read_input_tokens || 0) + (data.usage.cache_creation_input_tokens || 0);
    outTok += data.usage.output_tokens || 0;
    searches += (data.usage.server_tool_use && data.usage.server_tool_use.web_search_requests) || 0;
    fetches += (data.usage.server_tool_use && data.usage.server_tool_use.web_fetch_requests) || 0;
    fs.writeFileSync(path.join(dir, `${cfg.out_prefix}-turn${turns}.json`), JSON.stringify(data, null, 1));
    const text = data.content.filter(c => c.type === 'text').map(c => c.text).join('');
    finalText += text;
    if (data.stop_reason === 'pause_turn' && turns < 6) {
      messages.push({ role: 'assistant', content: data.content });
      continue;
    }
    console.log('stop_reason', data.stop_reason);
    break;
  }
  const [pi, po] = PRICES[cfg.model];
  const cost = inTok * pi + outTok * po + searches * SEARCH_PRICE;
  fs.writeFileSync(path.join(dir, `${cfg.out_prefix}.md`), finalText);
  const stats = { model: cfg.model, inTok, outTok, searches, fetches, turns, cost: Number(cost.toFixed(4)), seconds: (Date.now() - t0) / 1000 };
  fs.writeFileSync(path.join(dir, `${cfg.out_prefix}-stats.json`), JSON.stringify(stats, null, 2));
  console.log('DONE', JSON.stringify(stats));
})();
