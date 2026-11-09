# AI Marketing Engine

Two connected teams of Claude agents for small B2B companies. The **Demand Engine** helps the right people find you, and the **Lead Loop** makes sure nobody who reaches out gets lost. A person approves everything before it goes out.

Built by Camille Nicole Brattli ([bycamillenicole.com](https://bycamillenicole.com)). First tested on her own studio, BYCN.studios, as "client zero".

> **Status:** prototype, November 2026. It works end to end on test data, but it isn't production software. It's shared as-is under the MIT license, with no warranty. n8n itself has its own Sustainable Use License. This repo only contains a workflow file that you import into your own n8n.

## Part 1: the Lead Loop and helper agents

| Agent | Model | Job | Output |
| --- | --- | --- | --- |
| Lead agent | Claude Haiku 5.5 | Reads each new lead, flags spam, scores it against your rules and drafts a reply in the lead's language | Score, band (hot, warm, cold or spam) and reply draft, saved to HubSpot |
| Audit agent | Claude Opus 5.5 | Finds the places on your website where interested people get lost | Ranked leak table, quick wins and baseline numbers |
| Reporting agent | Claude Opus 5.5 | Turns the week's numbers into plain words | Weekly report with three actions |
| Content agent | Claude Sonnet 5.5 | Turns the week's findings into LinkedIn post drafts | 5 drafts with their sources |
| Review agent | Claude Sonnet 5.5 | Checks every draft for invented facts, voice and risk | Pass, fix or reject for each draft |

Every agent reads one **company context file**: your business, ideal client, prices, voice, approved claims and lead scoring rules. Change the file and every agent follows.

## Part 2: the Demand Engine

| Agent | Model | Job |
| --- | --- | --- |
| AEO probe | Claude Haiku 5.5 | Asks Claude the questions your buyers ask and checks if your brand comes up |
| Market researcher | Claude Sonnet 5.5 | Best-fit segments, what makes them look for help, where they look |
| Competitor analyst | Claude Sonnet 5.5 | Comparison table, where you win and lose, positioning options |
| SEO agent | Claude Sonnet 5.5 | Keyword clusters, page title and copy fixes, new pages, measurement setup |
| AEO and GEO agent | Claude Sonnet 5.5 | How to show up in AI assistants' answers |
| Strategist | Claude Opus 5.5 | One focused 30-day plan with owners, numbers and baselines |
| Content and social | Claude Sonnet 5.5 | Two-week LinkedIn plan and drafts |
| Outbound and ABM | Claude Sonnet 5.5 | One-to-one outreach templates, consent notes, logging template |
| Review | Claude Sonnet 5.5 | Checks every draft for invented facts, voice and risk |

The agents work only from your context file and an evidence pack you fill in (`demand-engine/evidence/template.md`). They never invent search volumes, rankings or results. One run cost about $1.80 in November 2026.

**How the two parts connect:** every link the Demand Engine suggests carries a UTM tag, so each enquiry lands in HubSpot with its source, the Lead agent scores it, and the weekly report shows which channel brought the good leads.

## How the lead loop works

```
Contact form ─► Prepare lead ─► Lead agent (Haiku 5.5) ─► Read answer ─► Spam? ── yes ─► No action
                                                                           │
                                                                           no
                                                                           ▼
                                                                  Save to HubSpot ─► Hot? ── yes ─► Email alert with the draft
```

Nothing is sent to a lead automatically. The reply draft waits in HubSpot and in the alert email until a person sends it.

## How the words flow

The SEO agent picks the words buyers search for (from your Search Console export when you add one) and writes page titles and descriptions with them. The AEO and GEO agent asks an AI assistant the questions buyers ask, checks whether you're mentioned, and lists the questions your site should answer. The Content and social agent uses both, so your website, your posts and your captions all use the same words and the same description of your company. That consistency is what helps Google, its AI Overviews and chatbots like ChatGPT describe you correctly. Each month, export the latest searches from Search Console and run the Demand Engine again.

## The weekly overview

Every Monday, or whenever you click run, a third workflow reads last week's visits by channel from Google Analytics, your searches from Search Console and your new leads from HubSpot. It joins them by channel, so you can see which channels bring the leads that score hot, including visits from AI assistants like ChatGPT and Perplexity. Claude writes a few plain-English sentences on what changed. The overview is saved as a Notion page, and you get an email with the link. It holds counts only, never names or messages. Setup: [docs/weekly-overview-setup.md](docs/weekly-overview-setup.md).

## Test results (made-up leads)

These come from 20 made-up test leads in English, German and Norwegian, with an answer key. They show how the system behaves, not how a market behaves.

| Run | Change | Right band | Score within 15 of the key | Time | Cost |
| --- | --- | --- | --- | --- | --- |
| 1 | Answer cap 4,000 tokens | 19 of 20 | 15 of 20 | 110 s | $0.016 |
| 2 | One scoring rule written more clearly | 20 of 20 | 19 of 20 | 112 s | $0.016 |
| 2, repeated | Same | 20 of 20 | 19 of 20 | 107 s | $0.016 |

That is about $0.0008 and 5 seconds per lead.

## Quick start

You need Node.js 18 or newer, Python 3.10 or newer and your own Claude API key. Step-by-step guides for **Windows, macOS and Linux** are in [INSTALL.md](INSTALL.md).

```bash
cp .env.example .env               # then open .env and fill it in
python scripts/build.py            # builds the agent prompts and the n8n workflow
node demo/server.js --mock         # dry run with no API calls, open http://127.0.0.1:8787/dashboard.html
node demo/server.js                # real run on the 20 test leads (costs about $0.02)
```

To use it with real leads, import `n8n/lead-loop.json` into n8n and follow [docs/lead-loop-setup.md](docs/lead-loop-setup.md). For the weekly overview, import `n8n/weekly-overview.json` and follow [docs/weekly-overview-setup.md](docs/weekly-overview-setup.md).

To run the Demand Engine, copy `demand-engine/evidence/template.md` to `demand-engine/evidence/my-evidence.md`, fill it in, then run:

```bash
python demand-engine/run.py --dry   # check inputs and cost, no API calls
python demand-engine/run.py         # real run, results in demand-engine/runs/<date>/
```

## Make it yours

1. Copy `context/template.md` to `context/my-company.md` and fill it in.
2. Set `CONTEXT_FILE=context/my-company.md` in `.env`.
3. Run `python scripts/build.py` again.
4. Edit `test-data/` with leads that look like yours and run the demo until the bands match your answer key.

## Security

- Your API key lives only in `.env` on your computer. `.env` is in `.gitignore`, and nothing in this repo contains a key.
- In n8n the key is stored as an n8n credential, not inside the workflow file.
- The demo server only listens on `127.0.0.1`, so other computers can't reach it.
- Use a key with a low spend limit, and delete it when you're done testing.

Read [SECURITY.md](SECURITY.md) before you publish a fork, and [PRIVACY.md](PRIVACY.md) before you use it with real leads. It covers GDPR, IP addresses and email consent.

## Rules the agents follow

- A person approves anything that goes to a customer, quotes a number or makes a claim.
- No invented facts, clients, results or testimonials.
- AI-made content is labeled where the platform or the law asks for it.
- Email outreach follows the consent rules where you sell. In Germany and Switzerland, for example, advertising email generally needs consent, even between businesses.

## License

MIT. See [LICENSE](LICENSE).
