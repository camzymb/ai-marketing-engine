"""Runs the AI Demand Engine once.
Order: AEO probe -> Market, Competitor, SEO and AEO agents (in parallel) -> Strategist -> Content and Outbound (in parallel) -> Review.
Usage:  python demand-engine/run.py          (real run, about $1 to $2 on the Claude API)
        python demand-engine/run.py --dry    (builds every input and prints a cost estimate, calls nothing)
Reads settings from .env: ANTHROPIC_API_KEY, OWNER_NAME, COMPANY_NAME, CONTEXT_FILE, EVIDENCE_FILE, BRAND_NAMES,
and optionally AUDIT_FILE and REPORT_FILE (outputs from the Audit and Reporting agents) and SEARCH_CONSOLE_FILE
(Queries.csv exported from Search Console, Performance, Export, so the SEO agent works from real searches).
"""
import concurrent.futures as cf, datetime, json, os, pathlib, subprocess, sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
D = ROOT / 'demand-engine'
DRY = '--dry' in sys.argv

def load_env():
    cfg = dict(os.environ)
    p = ROOT / '.env'
    if p.exists():
        for line in p.read_text(encoding='utf-8').splitlines():
            line = line.strip()
            if line and not line.startswith('#') and '=' in line:
                k, v = line.split('=', 1); cfg.setdefault(k.strip(), v.strip().strip('"').strip("'"))
    return cfg

cfg = load_env()
read = lambda rel, default='': (ROOT / rel).read_text(encoding='utf-8') if rel and (ROOT / rel).exists() else default
ctx = read(cfg.get('CONTEXT_FILE', 'context/example-bycn-studios.md'))
evidence = read(cfg.get('EVIDENCE_FILE', 'demand-engine/evidence/my-evidence.md'), 'No evidence pack yet. Treat everything outside the context file as unknown.')
audit = read(cfg.get('AUDIT_FILE', ''), 'No website audit yet.')
report = read(cfg.get('REPORT_FILE', ''), 'No lead loop report yet.')
# Real searches from Search Console, if exported. Capped so a big export can't run up the bill.
searches = read(cfg.get('SEARCH_CONSOLE_FILE', ''), '')[:12000] or 'No Search Console export yet. Volumes are unknown.'
rules = (D / 'prompts' / '_rules.md').read_text(encoding='utf-8')
owner, company = cfg.get('OWNER_NAME', 'the owner'), cfg.get('COMPANY_NAME', 'the company')
today = datetime.date.today().strftime('%d %B %Y')
RUN = D / 'runs' / datetime.date.today().isoformat(); RUN.mkdir(parents=True, exist_ok=True)
PRICE = {'claude-opus-5-5': (4, 20), 'claude-sonnet-5-5': (2, 10)}
est = []

def fill(s): return s.replace('{{RULES}}', rules).replace('{{CONTEXT}}', ctx).replace('{{OWNER_NAME}}', owner).replace('{{COMPANY_NAME}}', company)

def build(name, model, user, max_tokens=20000, system=None):
    s = fill(system or (D / 'prompts' / f'{name}.md').read_text(encoding='utf-8'))
    (RUN / f'{name}-system.md').write_text(s, encoding='utf-8'); (RUN / f'{name}-user.md').write_text(user, encoding='utf-8')
    json.dump({'model': model, 'max_tokens': max_tokens, 'system_file': f'{name}-system.md', 'user_file': f'{name}-user.md',
               'tools': [], 'out_prefix': f'{name}-out'}, open(RUN / f'{name}-config.json', 'w'), indent=2)
    t = (len(s) + len(user)) / 4; p = PRICE[model]; est.append((name, model, t * p[0] / 1e6 + 6000 * p[1] / 1e6))

def run(name):
    if DRY: (RUN / f'{name}-out.md').write_text(f'[dry run placeholder for {name}]', encoding='utf-8'); return
    r = subprocess.run(['node', str(ROOT / 'scripts' / 'run-agent.js'), str(RUN / f'{name}-config.json')], capture_output=True, text=True)
    print(name, (r.stdout.strip().splitlines() or [''])[-1], r.stderr[-300:])
    if r.returncode != 0: raise SystemExit(f'{name} failed')

out = lambda n: (RUN / f'{n}-out.md').read_text(encoding='utf-8')

if not DRY: subprocess.run(['node', str(D / 'aeo_probe.js'), str(RUN / 'aeo-probe.json')], check=True)
probe = (RUN / 'aeo-probe.json').read_text(encoding='utf-8') if (RUN / 'aeo-probe.json').exists() else '{"note": "dry run, no probe"}'

d = f'Today is {today}.'
build('market', 'claude-sonnet-5-5', f'{d} Research the market using this evidence pack.\n\n{evidence}')
build('competitor', 'claude-sonnet-5-5', f'{d} Compare the company with its alternatives using this evidence pack.\n\n{evidence}')
build('seo', 'claude-sonnet-5-5', f'{d} Plan SEO using the evidence pack, the website audit and the real searches from Search Console.\n\n# Evidence pack\n\n{evidence}\n\n# Website audit\n\n{audit}\n\n# Search Console queries\n\n{searches}', 24000)
build('aeo', 'claude-sonnet-5-5', f'{d} Plan AEO and GEO. Here is the probe of Claude\'s answers (JSON), then the evidence pack.\n\n# Probe\n\n{probe}\n\n# Evidence pack\n\n{evidence}')
with cf.ThreadPoolExecutor(4) as ex: list(ex.map(run, ['market', 'competitor', 'seo', 'aeo']))

research = '\n\n'.join(f'# {n.upper()} AGENT\n\n{out(n)}' for n in ['market', 'competitor', 'seo', 'aeo'])
build('strategist', 'claude-opus-5-5', f'{d} Write the 30-day demand plan starting this week.\n\n{research}\n\n# Website audit\n\n{audit}\n\n# Lead loop report\n\n{report}', 24000)
run('strategist')

plan = out('strategist')
build('social', 'claude-sonnet-5-5', f'{d} Write the two-week LinkedIn plan from this strategy, using the SEO agent\'s words to use and the buyer questions from the AEO and GEO plan.\n\n# Strategy\n\n{plan}\n\n# SEO plan and words to use\n\n{out("seo")}\n\n# AEO and GEO plan\n\n{out("aeo")}\n\n# Evidence pack\n\n{evidence}')
build('outbound', 'claude-sonnet-5-5', f'{d} Prepare one-to-one outreach from this strategy and market research.\n\n# Strategy\n\n{plan}\n\n# Market research\n\n{out("market")}')
with cf.ThreadPoolExecutor(2) as ex: list(ex.map(run, ['social', 'outbound']))

build('review', 'claude-sonnet-5-5', f'{d} Review the LinkedIn drafts and the outreach templates. The allowed facts are the context file, the strategy and the evidence pack.\n\n# LinkedIn plan and drafts\n\n{out("social")}\n\n# Outreach\n\n{out("outbound")}\n\n# Strategy\n\n{plan}\n\n# Evidence pack\n\n{evidence}',
      system=(ROOT / 'agents' / 'review.md').read_text(encoding='utf-8'))
run('review')

print('\n'.join(f'{n:11s} {m:18s} ~${c:.3f}' for n, m, c in est)); print(f'Estimated total ~${sum(c for *_, c in est):.2f}. Outputs are in {RUN}')
