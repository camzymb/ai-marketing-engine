"""Builds the n8n workflow and the agent prompts from your context file and .env settings.
Run: python scripts/build.py
"""
import csv, json, uuid, pathlib

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
        })

prepare_js = f"""// Prepare lead: turns a form fill (or a test lead) into a clean lead and the request for Claude.
const SYSTEM = {json.dumps(SYSTEM)};
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
  receivedAt: new Date().toISOString(),
}};
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

test_js = "// Test leads: 20 made-up leads with fake .example emails, so nothing reaches a real person.\nconst leads = " + json.dumps(leads, ensure_ascii=False, indent=1) + ";\nreturn leads.map(l => ({ json: l }));\n"

R = "$('Read Claude answer').item.json"
alert_text = (
    "=A hot lead just came in.\n\n"
    f"Name: {{{{ {R}.firstName }}}} {{{{ {R}.lastName }}}}\n"
    f"Company: {{{{ {R}.company }}}} ({{{{ {R}.companySize }}}} people, {{{{ {R}.country }}}})\n"
    f"Email: {{{{ {R}.email }}}}\n"
    f"Score: {{{{ {R}.score }}}} ({{{{ {R}.band }}}})\n"
    f"Why: {{{{ {R}.signalsText }}}}\n"
    f"Best match: {{{{ {R}.matchingService }}}}\n\n"
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

# Build every agent prompt with the context file inserted, for the demo and the runner.
built = ROOT / "agents" / "built"
built.mkdir(exist_ok=True)
for name in ["lead", "audit", "report", "content", "review"]:
    t = (ROOT / "agents" / f"{name}.md").read_text(encoding="utf-8")
    t = t.replace("{{OWNER_NAME}}", OWNER).replace("{{SIGNATURE}}", SIGNATURE).replace("{{CONTEXT}}", context)
    (built / f"{name}.md").write_text(t, encoding="utf-8")
print("Built n8n/lead-loop.json and agents/built/. Context file:", CONTEXT_FILE.name)
