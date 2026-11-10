"""Builds the n8n workflow and the agent prompts from your context file and .env settings.
Run: python scripts/build.py
"""
import csv, json, pathlib, secrets, urllib.parse, uuid

ROOT = pathlib.Path(__file__).resolve().parent.parent

def load_env():
    """Reads settings from .env. The API key is never read here and never written into any file."""
    cfg = {}
    p = ROOT / ".env"
    if p.exists():
        for line in p.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                k, v = line.split("=", 1)
                cfg[k.strip()] = v.strip().strip('"').strip("'")
    return cfg

cfg = load_env()
OWNER = cfg.get("OWNER_NAME") or "the owner"
SIGNATURE = cfg.get("SIGNATURE") or OWNER
COMPANY = cfg.get("COMPANY_NAME") or "us"
ALERT_EMAIL = cfg.get("ALERT_EMAIL") or "you@example.com"
MINIMAL_ALERT = (cfg.get("ALERT_DETAILS") or "").lower() == "minimal"  # keep lead details out of the alert email
CONTEXT_FILE = ROOT / (cfg.get("CONTEXT_FILE") or "context/example-bycn-studios.md")
# Your website, for the form webhook (only this site may post to it) and the overview links.
SITE_ORIGIN = (cfg.get("SITE_ORIGIN") or "https://example.com").rstrip("/")
# The webhook's path: long and random so it can't be guessed (it is still public once it's in your
# site's code). Made once and saved to .env, so the address stays the same every time you rebuild.
WEBHOOK_PATH = cfg.get("WEBHOOK_PATH")
if not WEBHOOK_PATH:
    WEBHOOK_PATH = "lead-loop-" + secrets.token_hex(10)
    env = ROOT / ".env"
    if env.exists():
        with env.open("a", encoding="utf-8") as f:
            f.write(f"\n# Made by scripts/build.py. Keep it, or your website's form address changes.\nWEBHOOK_PATH={WEBHOOK_PATH}\n")
# Weekly overview
GA4_PROPERTY_ID = cfg.get("GA4_PROPERTY_ID") or "000000000"
SEARCH_CONSOLE_SITE = cfg.get("SEARCH_CONSOLE_SITE") or "sc-domain:example.com"
NOTION_DATABASE_ID = cfg.get("NOTION_DATABASE_ID") or "your-notion-database-id"
HUBSPOT_APP_URL = (cfg.get("HUBSPOT_APP_URL") or "https://app.hubspot.com").rstrip("/")
TIMEZONE = cfg.get("TIMEZONE") or "Europe/Oslo"
context = CONTEXT_FILE.read_text(encoding="utf-8")
HERE = ROOT

SYSTEM = (ROOT / "agents" / "lead.md").read_text(encoding="utf-8").replace("{{OWNER_NAME}}", OWNER).replace("{{SIGNATURE}}", SIGNATURE).replace("{{CONTEXT}}", context)

# test leads in the same shape as the form fields
leads = []
with open(ROOT / "test-data" / "test-leads.csv", encoding="utf-8") as f:
    for r in csv.DictReader(f):
        leads.append({
            "First name": r["First Name"], "Last name": r["Last Name"], "Email": r["Email"],
            "Company": r["Company Name"], "Job title": r["Job Title"], "Company size": r["Company Size"],
            "Country": r["Country"], "Website": r["Website URL"], "Message": r["Message"],
            "Source": r.get("Source", ""), "Medium": r.get("Medium", ""),
        })

# Sorts a visit or a lead into a channel from its source and medium (a UTM tag or the site it came
# from). The Lead Loop and the weekly overview use the same rules, so their numbers line up.
CHANNEL_JS = r"""function channelOf(source, medium) {
  const s = String(source || '').toLowerCase().trim();
  const m = String(medium || '').toLowerCase().trim();
  if (!s || s === '(not set)') return 'Unknown';
  if (s === '(direct)' || s === 'direct') return 'Direct';
  const t = new Set(s.split(/[^a-z0-9]+/).filter(Boolean));
  const any = (...w) => w.some(x => t.has(x));
  if (any('chatgpt', 'openai', 'perplexity', 'claude', 'anthropic', 'gemini', 'bard', 'copilot', 'deepseek', 'grok', 'mistral', 'phind', 'poe') || s === 'you.com' || s === 'meta.ai') return 'AI assistants';
  if (any('linkedin', 'lnkd')) return 'LinkedIn';
  if (m === 'email' || any('mail', 'newsletter', 'outlook')) return 'Email';
  if (any('instagram', 'facebook', 'fb', 'threads', 'tiktok', 'twitter', 'youtube', 'pinterest', 'reddit') || s === 't.co' || s === 'x' || s === 'x.com') return 'Other social';
  if (m === 'organic' || any('google', 'bing', 'duckduckgo', 'yahoo', 'ecosia', 'brave', 'yandex', 'baidu', 'startpage', 'qwant')) return 'Search engines';
  if (m === 'referral') return 'Other websites';
  return 'Other';
}
"""

prepare_js = f"""// Prepare lead: turns a form fill (or a test lead) into a clean lead and the request for Claude.
const SYSTEM = {json.dumps(SYSTEM)};
{CHANNEL_JS}
const f = $json;
// Clean every field: plain text only, with a length cap, so one huge or tricky form fill can't run up API costs.
const clean = (v, max) => String(v || '').replace(/[\u0000-\u0008\u000B-\u001F\u007F\u200B-\u200F\u202A-\u202E]/g, '').trim().slice(0, max);
const lead = {{
  firstName: clean(f['First name'], 80),
  lastName: clean(f['Last name'], 80),
  email: clean(f['Email'], 200).toLowerCase(),
  company: clean(f['Company'], 150),
  jobTitle: clean(f['Job title'], 150),
  companySize: clean(f['Company size'], 20),
  country: clean(f['Country'], 80),
  website: clean(f['Website'], 200),
  message: clean(f['Message'], 3000),
  source: clean(f['Source'], 80),
  medium: clean(f['Medium'], 80),
  campaign: clean(f['Campaign'], 120),
  landingPage: clean(f['Landing page'], 200),
  receivedAt: new Date().toISOString(),
}};
lead.channel = channelOf(lead.source, lead.medium);
lead.sourceDetail = [lead.source, lead.medium, lead.campaign].filter(Boolean).join(' / ') + (lead.landingPage ? ` (landed on ${{lead.landingPage}})` : '');
const leadForClaude = {{
  name: `${{lead.firstName}} ${{lead.lastName}}`.trim(),
  email: lead.email, company: lead.company, job_title: lead.jobTitle,
  company_size: lead.companySize, country: lead.country, website: lead.website, message: lead.message,
}};
const body = {{
  model: 'claude-haiku-5-5',
  max_tokens: 4000,
  system: SYSTEM,
  messages: [{{ role: 'user', content: 'New lead:\\n' + JSON.stringify(leadForClaude, null, 2) }}],
}};
return {{ json: {{ lead, body }} }};
"""

read_js = r"""// Read Claude answer: turns Claude's JSON into a score, a band and a reply draft.
const resp = $json;
const lead = $('Prepare lead').item.json.lead;
const text = (resp.content || []).filter(c => c.type === 'text').map(c => c.text).join('');
let out = null;
try { out = JSON.parse(text); } catch (e) {
  const m = text.match(/\{[\s\S]*\}/);
  if (m) { try { out = JSON.parse(m[0]); } catch (e2) { out = null; } }
}
if (!out) {
  return { json: { ...lead, score: 0, band: 'error', summary: 'Could not read the answer from Claude', replyDraft: '', raw: text } };
}
const signals = Array.isArray(out.signals) ? out.signals : [];
const rawScore = signals.reduce((s, x) => s + Number(x.points || 0), 0);
let score, band;
if (out.is_spam === true) { score = 0; band = 'spam'; }
else {
  score = Math.max(1, Math.min(100, rawScore));
  band = score >= 70 ? 'hot' : score >= 40 ? 'warm' : 'cold';
}
const draft = String(out.reply_draft || '');
const banned = [['—', 'em dash'], ["let's dive in", "let's dive in"], ['game-changer', 'game-changer'], ['game changer', 'game changer'], ['elevate', 'elevate'], ['unlock', 'unlock']];
const voiceFlags = banned.filter(([b]) => draft.toLowerCase().includes(b.toLowerCase())).map(([, label]) => label);
// Safety checks: a reply should never carry links or addresses the agent wasn't given.
if (/https?:\/\/|www\./i.test(draft)) voiceFlags.push('contains a link, check it');
if (/[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[a-z]{2,}/i.test(draft)) voiceFlags.push('contains an email address, check it');
if (draft.length > 1500) voiceFlags.push('longer than expected');
const inTok = (resp.usage && resp.usage.input_tokens) || 0;
const outTok = (resp.usage && resp.usage.output_tokens) || 0;
const costUsd = inTok * 0.10 / 1e6 + outTok * 0.50 / 1e6; // Haiku 5.5 list price per token
return { json: {
  ...lead,
  score, band,
  signalsText: signals.map(s => `${s.signal} (${Number(s.points) > 0 ? '+' : ''}${s.points})`).join(', '),
  matchingService: out.matching_service || 'none',
  summary: out.summary || '',
  replyLanguage: out.reply_language || '',
  replySubject: out.reply_subject || '',
  replyDraft: draft,
  voiceFlags: voiceFlags.length ? voiceFlags.join(', ') : 'none',
  inputTokens: inTok, outputTokens: outTok, costUsd: Number(costUsd.toFixed(5)),
} };
"""

website_js = r"""// Website form: turns what your site's contact form sends into the same fields as the form above.
// Anyone on the internet can call this address, so it keeps only the fields it knows and drops any
// call without a real-looking email and a message before it reaches Claude (and your API bill).
const str = (v) => (typeof v === 'string' ? v : '');
const EMAIL = /^[^\s@]{1,64}@[^\s@]{1,190}\.[a-z]{2,}$/i;
const out = [];
for (const item of $input.all()) {
  const b = (item.json && item.json.body) || {};
  const a = (b && typeof b.answers === 'object' && b.answers) || {};
  const email = str(a['Email']).trim();
  const msg = str(a['Message']).trim();
  if (!EMAIL.test(email) || !msg) continue;
  const name = str(a['Name']).trim();
  const [first, ...rest] = name.split(/\s+/);
  const extras = [
    ['Services interested in', a['Services interested in']],
    ['Package interested in', a['Package interested in']],
    ['When to start', a['When to start']],
    ['How they heard about us', a['How they heard about bycn.studios'] || a['How they heard']],
  ].filter(([, v]) => str(v).trim()).map(([k, v]) => `${k}: ${str(v).trim()}`);
  out.push({ json: {
    'First name': first || '',
    'Last name': rest.join(' '),
    'Email': email,
    'Company': str(a['Brand or company']),
    'Website': str(a['Website or social link']),
    'Message': [msg, ...extras].join('\n\n'),
    'Source': str(b.source),
    'Medium': str(b.medium),
    'Campaign': str(b.campaign),
    'Landing page': str(b.landing) || str(b.page),
  } });
}
return out;
"""

test_js = "// Test leads: 20 made-up leads with fake .example emails, so nothing reaches a real person.\nconst leads = " + json.dumps(leads, ensure_ascii=False, indent=1) + ";\nreturn leads.map(l => ({ json: l }));\n"

R = "$('Read Claude answer').item.json"
alert_text = (
    "=A hot lead just came in.\n\n"
    f"Name: {{{{ {R}.firstName }}}} {{{{ {R}.lastName }}}}\n"
    f"Company: {{{{ {R}.company }}}} ({{{{ {R}.companySize }}}} people, {{{{ {R}.country }}}})\n"
    f"Email: {{{{ {R}.email }}}}\n"
    f"Score: {{{{ {R}.score }}}} ({{{{ {R}.band }}}})\n"
    f"Why: {{{{ {R}.signalsText }}}}\n"
    f"Best match: {{{{ {R}.matchingService }}}}\n"
    f"Came from: {{{{ {R}.channel }}}} ({{{{ {R}.sourceDetail || 'not known' }}}})\n\n"
    f"What they wrote:\n{{{{ {R}.message }}}}\n\n"
    f"Summary: {{{{ {R}.summary }}}}\n\n"
    f"Reply draft ({{{{ {R}.replyLanguage }}}}), check it before you send:\n"
    f"Subject: {{{{ {R}.replySubject }}}}\n\n{{{{ {R}.replyDraft }}}}\n\n"
    f"Voice check: {{{{ {R}.voiceFlags }}}}\n"
)

if MINIMAL_ALERT:
    alert_text = f"=A hot lead just came in with a score of {{{{ {R}.score }}}}.\n\nOpen HubSpot to read the lead, the summary and the reply draft.\n"

def nid():
    return str(uuid.uuid4())

nodes = [
    {"id": nid(), "name": "Contact form", "type": "n8n-nodes-base.formTrigger", "typeVersion": 2.2,
     "position": [0, 0], "webhookId": nid(),
     "parameters": {
         "formTitle": f"Work with {COMPANY}",
         "formDescription": "Tell me a little about you and what you need, and I'll get back to you soon.",
         "formFields": {"values": [
             {"fieldLabel": "First name", "requiredField": True},
             {"fieldLabel": "Last name"},
             {"fieldLabel": "Email", "fieldType": "email", "requiredField": True},
             {"fieldLabel": "Company"},
             {"fieldLabel": "Job title"},
             {"fieldLabel": "Company size", "fieldType": "dropdown", "fieldOptions": {"values": [
                 {"option": "1-10"}, {"option": "11-50"}, {"option": "51-200"}, {"option": "201+"}]}},
             {"fieldLabel": "Country"},
             {"fieldLabel": "Website"},
             {"fieldLabel": "Message", "fieldType": "textarea", "requiredField": True},
         ]},
         "responseMode": "onReceived",
         "options": {},
     }},
    {"id": nid(), "name": "Website form", "type": "n8n-nodes-base.webhook", "typeVersion": 2,
     "position": [0, -220], "webhookId": nid(),
     "parameters": {
         "httpMethod": "POST",
         "path": WEBHOOK_PATH,
         "responseMode": "onReceived",
         "options": {"allowedOrigins": SITE_ORIGIN},
     }},
    {"id": nid(), "name": "Website to lead", "type": "n8n-nodes-base.code", "typeVersion": 2,
     "position": [220, -220], "parameters": {"jsCode": website_js}},
    {"id": nid(), "name": "Run 20 test leads", "type": "n8n-nodes-base.manualTrigger", "typeVersion": 1,
     "position": [0, 220], "parameters": {}},
    {"id": nid(), "name": "Test leads", "type": "n8n-nodes-base.code", "typeVersion": 2,
     "position": [220, 220], "parameters": {"jsCode": test_js}},
    {"id": nid(), "name": "Prepare lead", "type": "n8n-nodes-base.code", "typeVersion": 2,
     "position": [460, 100], "parameters": {"mode": "runOnceForEachItem", "jsCode": prepare_js}},
    {"id": nid(), "name": "Lead agent (Haiku 5.5)", "type": "n8n-nodes-base.httpRequest", "typeVersion": 4.2,
     "position": [680, 100], "retryOnFail": True, "maxTries": 3, "waitBetweenTries": 3000,
     "parameters": {
         "method": "POST",
         "url": "https://api.anthropic.com/v1/messages",
         "authentication": "predefinedCredentialType",
         "nodeCredentialType": "anthropicApi",
         "sendHeaders": True,
         "headerParameters": {"parameters": [
             {"name": "anthropic-version", "value": "2023-06-01"},
             {"name": "content-type", "value": "application/json"}]},
         "sendBody": True,
         "specifyBody": "json",
         "jsonBody": "={{ JSON.stringify($json.body) }}",
         "options": {},
     }},
    {"id": nid(), "name": "Read Claude answer", "type": "n8n-nodes-base.code", "typeVersion": 2,
     "position": [900, 100], "parameters": {"mode": "runOnceForEachItem", "jsCode": read_js}},
    {"id": nid(), "name": "Not spam?", "type": "n8n-nodes-base.if", "typeVersion": 2.2,
     "position": [1120, 100], "parameters": {
         "conditions": {"options": {"caseSensitive": True, "leftValue": "", "typeValidation": "strict", "version": 2},
                        "conditions": [{"id": nid(), "leftValue": "={{ $json.band }}", "rightValue": "spam",
                                        "operator": {"type": "string", "operation": "notEquals"}}],
                        "combinator": "and"},
         "options": {}}},
    {"id": nid(), "name": "Save to HubSpot", "type": "n8n-nodes-base.hubspot", "typeVersion": 2.1,
     "position": [1340, 0], "parameters": {
         "authentication": "appToken",
         "resource": "contact",
         "operation": "upsert",
         "email": "={{ $json.email }}",
         "additionalFields": {
             "firstName": "={{ $json.firstName }}",
             "lastName": "={{ $json.lastName }}",
             "companyName": "={{ $json.company }}",
             "jobTitle": "={{ $json.jobTitle }}",
             "websiteUrl": "={{ $json.website }}",
             "country": "={{ $json.country }}",
             "message": "={{ $json.message }}",
             "lifeCycleStage": "lead",
             "customPropertiesUi": {"customPropertiesValues": [
                 {"property": "ai_lead_score", "value": "={{ $json.score }}"},
                 {"property": "ai_lead_band", "value": "={{ $json.band }}"},
                 {"property": "ai_lead_summary", "value": "={{ $json.summary }}"},
                 {"property": "ai_reply_draft", "value": "={{ $json.replyDraft }}"},
                 {"property": "lead_channel", "value": "={{ $json.channel }}"},
                 {"property": "lead_source_detail", "value": "={{ $json.sourceDetail }}"},
             ]},
         },
         "options": {},
     }},
    {"id": nid(), "name": "Spam, no action", "type": "n8n-nodes-base.noOp", "typeVersion": 1,
     "position": [1340, 220], "parameters": {}},
    {"id": nid(), "name": "Is it hot?", "type": "n8n-nodes-base.if", "typeVersion": 2.2,
     "position": [1560, 0], "parameters": {
         "conditions": {"options": {"caseSensitive": True, "leftValue": "", "typeValidation": "strict", "version": 2},
                        "conditions": [{"id": nid(), "leftValue": "={{ " + R + ".band }}", "rightValue": "hot",
                                        "operator": {"type": "string", "operation": "equals"}}],
                        "combinator": "and"},
         "options": {}}},
    {"id": nid(), "name": "Alert owner", "type": "n8n-nodes-base.gmail", "typeVersion": 2.1,
     "position": [1780, -100], "parameters": {
         "resource": "message",
         "operation": "send",
         "sendTo": ALERT_EMAIL,
         "subject": ("=Hot lead (score {{ " + R + ".score }})" if MINIMAL_ALERT else "=Hot lead: {{ " + R + ".firstName }} {{ " + R + ".lastName }}, {{ " + R + ".company }} (score {{ " + R + ".score }})"),
         "emailType": "text",
         "message": alert_text,
         "options": {"appendAttribution": False},
     }},
]

conn = lambda name: {"node": name, "type": "main", "index": 0}
connections = {
    "Contact form": {"main": [[conn("Prepare lead")]]},
    "Website form": {"main": [[conn("Website to lead")]]},
    "Website to lead": {"main": [[conn("Prepare lead")]]},
    "Run 20 test leads": {"main": [[conn("Test leads")]]},
    "Test leads": {"main": [[conn("Prepare lead")]]},
    "Prepare lead": {"main": [[conn("Lead agent (Haiku 5.5)")]]},
    "Lead agent (Haiku 5.5)": {"main": [[conn("Read Claude answer")]]},
    "Read Claude answer": {"main": [[conn("Not spam?")]]},
    "Not spam?": {"main": [[conn("Save to HubSpot")], [conn("Spam, no action")]]},
    "Save to HubSpot": {"main": [[conn("Is it hot?")]]},
    "Is it hot?": {"main": [[conn("Alert owner")], []]},
}

workflow = {"name": "Lead Loop", "nodes": nodes, "connections": connections,
            "settings": {"executionOrder": "v1"}, "pinData": {}}
(ROOT / "n8n").mkdir(exist_ok=True)  # git doesn't keep empty folders, so a fresh clone has no n8n/
(ROOT / "n8n" / "lead-loop.json").write_text(json.dumps(workflow, ensure_ascii=False, indent=2), encoding="utf-8")

# ---------------------------------------------------------------------------------------------
# Weekly overview: every Monday (or when you click run) it reads last week's visits by channel
# from Google Analytics, your Google searches from Search Console and your new leads from HubSpot,
# joins them by channel, asks Claude for a short summary, saves the page in Notion and emails you.
# It holds counts only, never names or messages, so no personal data goes to Notion or the email.
# ---------------------------------------------------------------------------------------------
# The latest Demand Engine plan, so the weekly word ideas build on it: the SEO agent's "words to use"
# and the AEO and GEO agent's buyer questions. Each is kept with the date of the run it came from.
def latest_section(agent, heading):
    runs = sorted((ROOT / "demand-engine" / "runs").glob(f"*/{agent}-out.md"))
    if not runs:
        return "", ""
    text = runs[-1].read_text(encoding="utf-8")
    i = text.lower().find(heading)
    return (text[i:i + 3000] if i >= 0 else ""), runs[-1].parent.name
PLAN_WORDS, PLAN_WORDS_DATE = latest_section("seo", "words to use")
PLAN_QUESTIONS, PLAN_QUESTIONS_DATE = latest_section("aeo", "make it citable")
if cfg.get("WORDS_FILE") and (ROOT / cfg["WORDS_FILE"]).exists():
    PLAN_WORDS, PLAN_WORDS_DATE = (ROOT / cfg["WORDS_FILE"]).read_text(encoding="utf-8")[:3000], "your words file"

OVERVIEW_SYSTEM = (ROOT / "agents" / "overview.md").read_text(encoding="utf-8").replace("{{OWNER_NAME}}", OWNER).replace("{{CONTEXT}}", context)
SC_ENC = urllib.parse.quote(SEARCH_CONSOLE_SITE, safe="")
LINKS = {
    "hubspot": HUBSPOT_APP_URL,
    "ga4": f"https://analytics.google.com/analytics/web/#/p{GA4_PROPERTY_ID}/reports/intelligenthome",
    "searchConsole": f"https://search.google.com/search-console/performance/search-analytics?resource_id={SC_ENC}",
}

dates_js = r"""// Dates: last 7 days (ending yesterday) and the 7 days before, for comparison.
const day = 86400000;
const now = new Date();
const today = Date.UTC(now.getUTCFullYear(), now.getUTCMonth(), now.getUTCDate());
const iso = (t) => new Date(t).toISOString().slice(0, 10);
return [{ json: {
  start: iso(today - 7 * day), end: iso(today - day),
  prevStart: iso(today - 14 * day), prevEnd: iso(today - 8 * day),
  // Search Console data arrives 2 to 3 days late, so its week ends 3 days ago.
  scStart: iso(today - 9 * day), scEnd: iso(today - 3 * day),
  scPrevStart: iso(today - 16 * day), scPrevEnd: iso(today - 10 * day),
  startMs: today - 7 * day, prevStartMs: today - 14 * day,
} }];
"""

together_js = CHANNEL_JS + r"""
// Put it together: joins visits (Google Analytics), searches (Search Console) and leads (HubSpot)
// by channel. A source that failed or isn't connected yet becomes a note instead of stopping the run.
const D = $('Dates').first().json;
const LINKS = __LINKS__;
const get = (name) => { try { return $(name).first().json; } catch (e) { return { error: { message: 'did not run' } }; } };
const notes = [];
const failed = (x, label) => {
  if (!x || x.error) {
    const why = (x && x.error && (x.error.message || x.error.description || JSON.stringify(x.error))) || 'no data';
    notes.push(`${label} couldn't be read this time (${String(why).slice(0, 160)}). Check its connection in n8n.`);
    return true;
  }
  return false;
};
const rows = {};
const row = (c) => (rows[c] = rows[c] || { channel: c, visits: 0, visitsLast: 0, engaged: 0, keyEvents: 0, leads: 0, hot: 0, warm: 0, cold: 0, leadsLast: 0 });

// Visits by channel, this week and last week.
const ga = get('GA4 visits by channel');
const gaOk = !failed(ga, 'Google Analytics');
if (gaOk) {
  const dh = (ga.dimensionHeaders || []).map((h) => h.name);
  const mh = (ga.metricHeaders || []).map((h) => h.name);
  const di = (n) => dh.indexOf(n);
  const mi = (n) => mh.indexOf(n);
  for (const r of ga.rows || []) {
    const dv = (r.dimensionValues || []).map((v) => v.value);
    const mv = (r.metricValues || []).map((v) => Number(v.value) || 0);
    const c = row(channelOf(dv[di('sessionSource')], dv[di('sessionMedium')]));
    const range = di('dateRange') >= 0 ? dv[di('dateRange')] : 'this';
    if (range === 'last' || range === 'date_range_1') c.visitsLast += mv[mi('sessions')] || 0;
    else {
      c.visits += mv[mi('sessions')] || 0;
      c.engaged += mv[mi('engagedSessions')] || 0;
      c.keyEvents += mi('keyEvents') >= 0 ? mv[mi('keyEvents')] || 0 : 0;
    }
  }
}

// Leads by channel and band, from the fields the Lead Loop writes in HubSpot.
const hs = get('HubSpot leads');
const hsOk = !failed(hs, 'HubSpot');
if (hsOk) {
  for (const r of hs.results || []) {
    const p = r.properties || {};
    const t = Date.parse(p.createdate || r.createdAt || '');
    const c = row(p.lead_channel || 'Unknown');
    if (t >= D.startMs) {
      c.leads++;
      const b = String(p.ai_lead_band || '').toLowerCase();
      if (b === 'hot') c.hot++;
      else if (b === 'warm') c.warm++;
      else if (b === 'cold') c.cold++;
    } else c.leadsLast++;
  }
}

// Google searches.
const scTot = get('Search Console totals');
const scOk = !failed(scTot, 'Search Console');
const scRow = scOk ? (scTot.rows || [])[0] || { clicks: 0, impressions: 0, position: 0 } : null;
const scQ = scOk ? get('Search Console searches') : null;
const topSearches = scOk && scQ && !scQ.error
  ? (scQ.rows || []).slice(0, 10).map((r) => ({ query: r.keys[0], clicks: r.clicks, impressions: r.impressions, position: Math.round(r.position * 10) / 10 }))
  : [];
// Searches rising for you: new this week, or shown clearly more often than the week before.
const scPrev = scOk ? get('Search Console searches week before') : null;
const before = {};
if (scPrev && !scPrev.error) for (const r of scPrev.rows || []) before[r.keys[0]] = r.impressions;
const risingSearches = scOk && scQ && !scQ.error
  ? (scQ.rows || [])
      .map((r) => ({ query: r.keys[0], shown: r.impressions, shownBefore: before[r.keys[0]] || 0, clicks: r.clicks }))
      .filter((r) => r.shown - r.shownBefore >= 2 && (r.shownBefore === 0 || r.shown >= r.shownBefore * 1.5))
      .sort((a, b) => (b.shown - b.shownBefore) - (a.shown - a.shownBefore))
      .slice(0, 8)
  : [];

// Top landing pages.
const pg = get('GA4 top landing pages');
const topPages = gaOk && !pg.error
  ? (pg.rows || []).map((r) => ({ page: r.dimensionValues[0].value, visits: Number(r.metricValues[0].value) || 0 }))
  : [];

const channels = Object.values(rows)
  .filter((c) => c.visits || c.visitsLast || c.leads || c.leadsLast)
  .sort((a, b) => b.hot - a.hot || b.leads - a.leads || b.visits - a.visits);
const sum = (k) => channels.reduce((s, c) => s + (c[k] || 0), 0);
const ai = rows['AI assistants'] || { visits: 0, leads: 0, hot: 0 };
const fmt = (d) => new Date(d + 'T00:00:00Z').toLocaleDateString('en-GB', { day: 'numeric', month: 'short', timeZone: 'UTC' });

return [{ json: {
  title: `Week of ${fmt(D.start)} to ${fmt(D.end)} ${D.end.slice(0, 4)}`,
  week: { start: D.start, end: D.end },
  totals: { visits: sum('visits'), visitsLast: sum('visitsLast'), keyEvents: sum('keyEvents'), leads: sum('leads'), leadsLast: sum('leadsLast'), hot: sum('hot'), warm: sum('warm'), cold: sum('cold') },
  channels,
  aiAssistants: { visits: ai.visits, leads: ai.leads, hot: ai.hot },
  search: scRow ? { clicks: scRow.clicks, impressions: scRow.impressions, position: Math.round((scRow.position || 0) * 10) / 10, from: D.scStart, to: D.scEnd } : null,
  topSearches,
  risingSearches,
  allSearches: scOk && scQ && !scQ.error ? (scQ.rows || []).map((r) => r.keys[0]) : [],
  scRange: { from: D.scStart, to: D.scEnd, prevFrom: D.scPrevStart, prevTo: D.scPrevEnd },
  topPages,
  notes,
  links: LINKS,
} }];
""".replace("__LINKS__", json.dumps(LINKS))

summary_req_js = f"""// Ask Claude for the short summary at the top of the page.
const f = $json;
const facts = {{ week: f.week, totals: f.totals, channels: f.channels, aiAssistants: f.aiAssistants, search: f.search, topSearches: f.topSearches, risingSearches: f.risingSearches, topPages: f.topPages, notes: f.notes }};
const planWords = {json.dumps(PLAN_WORDS)};
const planQuestions = {json.dumps(PLAN_QUESTIONS)};
return [{{ json: {{ body: {{
  model: 'claude-haiku-5-5',
  max_tokens: 3000,
  system: {json.dumps(OVERVIEW_SYSTEM)},
  messages: [{{ role: 'user', content: 'Last week\\'s numbers:\\n' + JSON.stringify(facts, null, 2) + '\\n\\nWords to use from the latest Demand Engine plan (SEO agent):\\n' + (planWords || 'none yet') + '\\n\\nBuyer questions from the latest Demand Engine plan (AEO and GEO agent):\\n' + (planQuestions || 'none yet') }}],
}} }} }}];
"""

page_js = r"""// Notion page and email: the summary on top, then the tables, then where to look next.
const f = $('Put it together').first().json;
const resp = $json || {};
const raw = ((resp.content || []).filter((c) => c.type === 'text').map((c) => c.text).join('')).trim();
// The agent answers in JSON (summary + word ideas). If that fails, the text is used as the summary.
let answer = null;
try { answer = JSON.parse(raw); } catch (e) {
  const m = raw.match(/\{[\s\S]*\}/);
  if (m) { try { answer = JSON.parse(m[0]); } catch (e2) { answer = null; } }
}
let summary = String((answer && answer.summary) || (answer ? '' : raw)).trim();
if (!summary) summary = 'The summary could not be written this week, but the numbers below are complete.';
// Every word gets a source the code checks itself, not one the AI claims: is the phrase really in
// this week's searches, or in the Demand Engine plan? If neither, it is labelled as Claude's own idea.
const PLAN = { words: __PLAN_WORDS__, wordsDate: __PLAN_WORDS_DATE__, questions: __PLAN_QUESTIONS__, questionsDate: __PLAN_QUESTIONS_DATE__ };
const norm = (x) => String(x || '').toLowerCase().replace(/[^a-z0-9\u00c0-\u024f]+/g, ' ').trim();
const tokens = (x) => norm(x).split(' ').filter((t) => t.length > 2);
const inText = (phrase, text) => { const t = tokens(phrase); const n = ' ' + norm(text) + ' '; return t.length > 0 && t.every((k) => n.includes(' ' + k + ' ') || n.includes(' ' + k)); };
const rising = new Set(f.risingSearches.map((r) => r.query));
const sourceOf = (phrase) => {
  const hit = f.allSearches.find((q) => inText(phrase, q) || inText(q, phrase));
  if (hit) return { label: `${rising.has(hit) ? 'Rising search' : 'Search'} "${hit}" in Search Console, ${f.scRange.from} to ${f.scRange.to}`, link: f.links.searchConsole, data: true };
  if (inText(phrase, PLAN.words)) return { label: `Demand Engine plan, SEO agent (run ${PLAN.wordsDate})`, data: true };
  if (inText(phrase, PLAN.questions)) return { label: `Demand Engine plan, AEO and GEO agent (run ${PLAN.questionsDate})`, data: true };
  return { label: "Claude's own idea, not found in your data", data: false };
};
const FOR = { seo: 'SEO (Google results)', aeo: 'AEO (answer boxes, Google AI Overviews)', geo: 'GEO (AI chatbots)' };
const words = (answer && Array.isArray(answer.words) ? answer.words : []).slice(0, 8).map((w) => ({
  phrase: String(w.phrase || '').slice(0, 80), why: String(w.why || '').slice(0, 200),
  idea: String(w.idea || '').slice(0, 300), where: String(w.where || '').slice(0, 120),
  for: FOR[String(w.for || '').toLowerCase()] || 'SEO (Google results)',
})).filter((w) => w.phrase).map((w) => ({ ...w, source: sourceOf(w.phrase) }))
  .sort((a, b) => Number(b.source.data) - Number(a.source.data));
summary = summary.replace(/—/g, ',');

const txt = (s, link) => ({ type: 'text', text: { content: String(s).slice(0, 1900), link: link ? { url: link } : null } });
const para = (s, link) => ({ object: 'block', type: 'paragraph', paragraph: { rich_text: [txt(s, link)] } });
const h2 = (s) => ({ object: 'block', type: 'heading_2', heading_2: { rich_text: [txt(s)] } });
const bullet = (s, link) => ({ object: 'block', type: 'bulleted_list_item', bulleted_list_item: { rich_text: [txt(s, link)] } });
const table = (head, body) => ({ object: 'block', type: 'table', table: {
  table_width: head.length, has_column_header: true, has_row_header: false,
  children: [head, ...body].map((r) => ({ type: 'table_row', table_row: { cells: r.map((c) => [txt(c)]) } })),
} });

const T = f.totals;
// "1 visit", "2 visits": the word follows the number.
const count = (n, word) => `${n} ${Number(n) === 1 ? word : word + 's'}`;
const blocks = [];
for (const p of summary.split(/\n\s*\n/)) blocks.push(para(p.trim()));
blocks.push(h2('Visits and leads by channel'));
if (f.channels.length) {
  blocks.push(table(
    ['Channel', 'Visits', 'Visits last week', 'Leads', 'Hot', 'Warm', 'Cold'],
    [...f.channels.map((c) => [c.channel, c.visits, c.visitsLast, c.leads, c.hot, c.warm, c.cold]),
     ['Total', T.visits, T.visitsLast, T.leads, T.hot, T.warm, T.cold]],
  ));
} else blocks.push(para('No visits or leads were recorded this week.'));
blocks.push(h2('From AI assistants'));
blocks.push(para(`${count(f.aiAssistants.visits, 'visit')} and ${count(f.aiAssistants.leads, 'lead')} came from AI assistants like ChatGPT, Claude, Perplexity and Gemini, and ${f.aiAssistants.hot} of those leads ${Number(f.aiAssistants.hot) === 1 ? 'was' : 'were'} hot.`));
blocks.push(h2('Google searches'));
if (f.search) {
  blocks.push(para(`From ${f.search.from} to ${f.search.to}, the site showed up ${count(f.search.impressions, 'time')} in Google and got ${count(f.search.clicks, 'click')}, at an average position of ${f.search.position}.`));
  if (f.topSearches.length) blocks.push(table(['Search', 'Clicks', 'Shown', 'Position'], f.topSearches.map((q) => [q.query, q.clicks, q.impressions, q.position])));
} else blocks.push(para('Search Console is not connected yet.'));
if (f.risingSearches.length) {
  blocks.push(h2('Searches rising for you'));
  blocks.push(table(['Search', 'Shown this week', 'Shown the week before', 'Clicks'], f.risingSearches.map((r) => [r.query, r.shown, r.shownBefore, r.clicks])));
}
blocks.push(h2('Words for this week'));
if (words.length) {
  blocks.push(para('Words and phrases to use on your website and in the posts you write yourself, with an idea for each. They come from the searches that found you and your Demand Engine plan, not from social media trend lists, so check each platform\'s own trends too.'));
  blocks.push(table(['Words', 'For', 'Why now', 'Source', 'Idea', 'Where to use it'], words.map((w) => [w.phrase, w.for, w.why, w.source.label, w.idea, w.where])));
  blocks.push(para(`Sources: your Google searches from Search Console (${f.scRange.from} to ${f.scRange.to}, compared with ${f.scRange.prevFrom} to ${f.scRange.prevTo})` + (PLAN.wordsDate ? `, and the Demand Engine plan from ${PLAN.wordsDate}` : '') + '. The source column is checked by the workflow itself, not written by the AI.', f.links.searchConsole));
} else blocks.push(para('No word ideas this week. They need search data from Search Console or a Demand Engine plan.'));
if (f.topPages.length) {
  blocks.push(h2('Pages people landed on'));
  for (const p of f.topPages) blocks.push(bullet(`${p.page}: ${count(p.visits, 'visit')}`));
}
if (f.notes.length) {
  blocks.push(h2('Missing this week'));
  for (const n of f.notes) blocks.push(bullet(n));
}
blocks.push(h2('Where to look next'));
blocks.push(bullet('HubSpot, for each lead, its score and the reply draft', f.links.hubspot));
blocks.push(bullet('Google Analytics, for all the visit numbers', f.links.ga4));
blocks.push(bullet('Search Console, for every search the site showed up in', f.links.searchConsole));
blocks.push(para('Made by the AI Marketing Engine. This page holds counts only, never names or messages.'));

const notion = { parent: { database_id: __DB__ }, properties: { Name: { title: [txt(f.title)] } }, children: blocks.slice(0, 100) };

const esc = (s) => String(s).replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;');
const td = 'style="padding:6px 10px;border-bottom:1px solid #e6e1d8;text-align:left"';
const rowsHtml = f.channels.map((c) => `<tr><td ${td}>${esc(c.channel)}</td><td ${td}>${c.visits}</td><td ${td}>${c.leads}</td><td ${td}>${c.hot}</td></tr>`).join('');
const emailHtml = `<div style="font-family:Arial,sans-serif;font-size:15px;line-height:1.55;color:#1d1b18;max-width:620px">
<p style="font-size:13px;color:#6b655c;margin:0 0 4px">${esc(f.title)}</p>
${summary.split(/\n\s*\n/).map((p) => `<p>${esc(p.trim())}</p>`).join('')}
<table style="border-collapse:collapse;margin:8px 0 16px"><tr><th ${td}>Channel</th><th ${td}>Visits</th><th ${td}>Leads</th><th ${td}>Hot</th></tr>${rowsHtml}<tr><td ${td}><b>Total</b></td><td ${td}><b>${T.visits}</b></td><td ${td}><b>${T.leads}</b></td><td ${td}><b>${T.hot}</b></td></tr></table>
${words.length ? `<p style="margin:16px 0 6px"><b>Words for this week</b></p><ul style="margin:0 0 16px;padding-left:20px">${words.slice(0, 5).map((w) => `<li><b>${esc(w.phrase)}</b>: ${esc(w.idea)} <span style="color:#6b655c">(${esc(w.where)}. Source: ${esc(w.source.label)})</span></li>`).join('')}</ul>` : ''}
<p><a href="%NOTION_URL%">Open the full overview in Notion</a></p>
<p style="font-size:13px;color:#6b655c">Or go straight to <a href="${f.links.hubspot}">HubSpot</a>, <a href="${f.links.ga4}">Google Analytics</a> or <a href="${f.links.searchConsole}">Search Console</a>.</p>
</div>`;
return [{ json: { notion, emailHtml, subject: `Your week: ${count(T.visits, 'visit')}, ${count(T.leads, 'lead')}, ${T.hot} hot (${f.title})` } }];
""".replace("__DB__", json.dumps(NOTION_DATABASE_ID)).replace("__PLAN_WORDS__", json.dumps(PLAN_WORDS)).replace("__PLAN_WORDS_DATE__", json.dumps(PLAN_WORDS_DATE)).replace("__PLAN_QUESTIONS__", json.dumps(PLAN_QUESTIONS)).replace("__PLAN_QUESTIONS_DATE__", json.dumps(PLAN_QUESTIONS_DATE))

google_http = lambda name, pos, url, body: {
    "id": nid(), "name": name, "type": "n8n-nodes-base.httpRequest", "typeVersion": 4.2,
    "position": pos, "onError": "continueRegularOutput", "alwaysOutputData": True,
    "parameters": {
        "method": "POST", "url": url,
        "authentication": "predefinedCredentialType", "nodeCredentialType": "googleApi",
        "sendBody": True, "specifyBody": "json", "jsonBody": body, "options": {},
    }}
D = "$('Dates').first().json"
ov_nodes = [
    {"id": nid(), "name": "Every Monday at 8", "type": "n8n-nodes-base.scheduleTrigger", "typeVersion": 1.2,
     "position": [0, 0], "parameters": {"rule": {"interval": [{"field": "weeks", "triggerAtDay": [1], "triggerAtHour": 8}]}}},
    {"id": nid(), "name": "Run the overview now", "type": "n8n-nodes-base.manualTrigger", "typeVersion": 1,
     "position": [0, 200], "parameters": {}},
    {"id": nid(), "name": "Dates", "type": "n8n-nodes-base.code", "typeVersion": 2,
     "position": [220, 100], "parameters": {"jsCode": dates_js}},
    google_http("GA4 visits by channel", [440, 100],
        f"https://analyticsdata.googleapis.com/v1beta/properties/{GA4_PROPERTY_ID}:runReport",
        "={{ JSON.stringify({ dateRanges: [{ startDate: " + D + ".start, endDate: " + D + ".end, name: 'this' }, { startDate: " + D + ".prevStart, endDate: " + D + ".prevEnd, name: 'last' }], dimensions: [{ name: 'sessionSource' }, { name: 'sessionMedium' }], metrics: [{ name: 'sessions' }, { name: 'engagedSessions' }, { name: 'keyEvents' }], limit: 250 }) }}"),
    google_http("GA4 top landing pages", [660, 100],
        f"https://analyticsdata.googleapis.com/v1beta/properties/{GA4_PROPERTY_ID}:runReport",
        "={{ JSON.stringify({ dateRanges: [{ startDate: " + D + ".start, endDate: " + D + ".end }], dimensions: [{ name: 'landingPage' }], metrics: [{ name: 'sessions' }], orderBys: [{ metric: { metricName: 'sessions' }, desc: true }], limit: 5 }) }}"),
    google_http("Search Console totals", [880, 100],
        f"https://www.googleapis.com/webmasters/v3/sites/{SC_ENC}/searchAnalytics/query",
        "={{ JSON.stringify({ startDate: " + D + ".scStart, endDate: " + D + ".scEnd }) }}"),
    google_http("Search Console searches", [1100, 100],
        f"https://www.googleapis.com/webmasters/v3/sites/{SC_ENC}/searchAnalytics/query",
        "={{ JSON.stringify({ startDate: " + D + ".scStart, endDate: " + D + ".scEnd, dimensions: ['query'], rowLimit: 50 }) }}"),
    google_http("Search Console searches week before", [1210, 260],
        f"https://www.googleapis.com/webmasters/v3/sites/{SC_ENC}/searchAnalytics/query",
        "={{ JSON.stringify({ startDate: " + D + ".scPrevStart, endDate: " + D + ".scPrevEnd, dimensions: ['query'], rowLimit: 100 }) }}"),
    {"id": nid(), "name": "HubSpot leads", "type": "n8n-nodes-base.httpRequest", "typeVersion": 4.2,
     "position": [1320, 100], "onError": "continueRegularOutput", "alwaysOutputData": True,
     "parameters": {
         "method": "POST", "url": "https://api.hubapi.com/crm/v3/objects/contacts/search",
         "authentication": "predefinedCredentialType", "nodeCredentialType": "hubspotAppToken",
         "sendBody": True, "specifyBody": "json",
         "jsonBody": "={{ JSON.stringify({ filterGroups: [{ filters: [{ propertyName: 'createdate', operator: 'GTE', value: String(" + D + ".prevStartMs) }] }], properties: ['createdate', 'ai_lead_band', 'ai_lead_score', 'lead_channel'], sorts: [{ propertyName: 'createdate', direction: 'DESCENDING' }], limit: 100 }) }}",
         "options": {},
     }},
    {"id": nid(), "name": "Put it together", "type": "n8n-nodes-base.code", "typeVersion": 2,
     "position": [1540, 100], "parameters": {"jsCode": together_js}},
    {"id": nid(), "name": "Summary request", "type": "n8n-nodes-base.code", "typeVersion": 2,
     "position": [1760, 100], "parameters": {"jsCode": summary_req_js}},
    {"id": nid(), "name": "Overview agent (Haiku 5.5)", "type": "n8n-nodes-base.httpRequest", "typeVersion": 4.2,
     "position": [1980, 100], "onError": "continueRegularOutput", "alwaysOutputData": True,
     "retryOnFail": True, "maxTries": 3, "waitBetweenTries": 3000,
     "parameters": {
         "method": "POST", "url": "https://api.anthropic.com/v1/messages",
         "authentication": "predefinedCredentialType", "nodeCredentialType": "anthropicApi",
         "sendHeaders": True,
         "headerParameters": {"parameters": [
             {"name": "anthropic-version", "value": "2023-06-01"},
             {"name": "content-type", "value": "application/json"}]},
         "sendBody": True, "specifyBody": "json", "jsonBody": "={{ JSON.stringify($json.body) }}", "options": {},
     }},
    {"id": nid(), "name": "Notion page and email", "type": "n8n-nodes-base.code", "typeVersion": 2,
     "position": [2200, 100], "parameters": {"jsCode": page_js}},
    {"id": nid(), "name": "Save in Notion", "type": "n8n-nodes-base.httpRequest", "typeVersion": 4.2,
     "position": [2420, 100], "onError": "continueRegularOutput", "alwaysOutputData": True,
     "parameters": {
         "method": "POST", "url": "https://api.notion.com/v1/pages",
         "authentication": "predefinedCredentialType", "nodeCredentialType": "notionApi",
         "sendHeaders": True,
         "headerParameters": {"parameters": [{"name": "Notion-Version", "value": "2022-06-28"}]},
         "sendBody": True, "specifyBody": "json", "jsonBody": "={{ JSON.stringify($json.notion) }}", "options": {},
     }},
    {"id": nid(), "name": "Email the overview", "type": "n8n-nodes-base.gmail", "typeVersion": 2.1,
     "position": [2640, 100], "parameters": {
         "resource": "message", "operation": "send", "sendTo": ALERT_EMAIL,
         "subject": "={{ $('Notion page and email').first().json.subject }}",
         "emailType": "html",
         "message": "={{ $('Notion page and email').first().json.emailHtml.replace('%NOTION_URL%', $json.url || '" + LINKS["hubspot"] + "') }}",
         "options": {"appendAttribution": False},
     }},
]
order = ["Dates", "GA4 visits by channel", "GA4 top landing pages", "Search Console totals", "Search Console searches", "Search Console searches week before",
         "HubSpot leads", "Put it together", "Summary request", "Overview agent (Haiku 5.5)", "Notion page and email",
         "Save in Notion", "Email the overview"]
ov_conn = {"Every Monday at 8": {"main": [[conn("Dates")]]}, "Run the overview now": {"main": [[conn("Dates")]]}}
for a, b in zip(order, order[1:]):
    ov_conn[a] = {"main": [[conn(b)]]}
overview_wf = {"name": "Weekly Overview", "nodes": ov_nodes, "connections": ov_conn,
               "settings": {"executionOrder": "v1", "timezone": TIMEZONE}, "pinData": {}}
(ROOT / "n8n" / "weekly-overview.json").write_text(json.dumps(overview_wf, ensure_ascii=False, indent=2), encoding="utf-8")

# Build every agent prompt with the context file inserted, for the demo and the runner.
built = ROOT / "agents" / "built"
built.mkdir(exist_ok=True)
for name in ["lead", "audit", "report", "content", "review", "overview"]:
    t = (ROOT / "agents" / f"{name}.md").read_text(encoding="utf-8")
    t = t.replace("{{OWNER_NAME}}", OWNER).replace("{{SIGNATURE}}", SIGNATURE).replace("{{CONTEXT}}", context)
    (built / f"{name}.md").write_text(t, encoding="utf-8")
print("Built n8n/lead-loop.json, n8n/weekly-overview.json and agents/built/. Context file:", CONTEXT_FILE.name)
print("Website form address (put it in your site's form code):", "https://<your-n8n-address>/webhook/" + WEBHOOK_PATH)
