# Weekly overview setup

The weekly overview answers the question small teams rarely get answered: **which channels bring visitors, and which bring the leads that score hot.** Every Monday at 8, or whenever you click run, it:

1. Reads last week's visits by channel from **Google Analytics 4**, compared with the week before
2. Reads the Google searches your site showed up in from **Search Console**
3. Reads last week's new leads from **HubSpot**, with the channel and score band the Lead Loop saved on each
4. Joins them by channel. LinkedIn, search engines, AI assistants like ChatGPT and Perplexity, email and direct visits each get one row.
5. Asks Claude for a few plain-English sentences about what changed
6. Picks **words for this week**: 3 to 8 words or questions to use on your website and in the posts you write yourself on LinkedIn, Instagram, Facebook or TikTok, each marked SEO, AEO or GEO, with an idea and where to use it
7. Saves the overview as a page in **Notion** and emails you a short version with the link

The overview holds counts only, never names or messages. So no personal data goes to Notion or into the email.

Plan for about 45 minutes the first time. You need the Lead Loop running first ([lead-loop-setup.md](lead-loop-setup.md)), because the overview reads the channel it saves on each lead.

## A. Measure your website with consent

Google Analytics needs a tag on your website, and in the EU and EEA it may only load after a visitor agrees. Norway has required that since 1 January 2025.

1. In Google Analytics, create a property for your site and a **Web** data stream. Copy the **Measurement ID** (`G-...`) and the **Property ID** (a number under Admin, then Property details).
2. Add the tag behind a cookie banner, so nothing loads before the visitor clicks Accept, and make Decline just as easy.
3. Under Admin, then Data display, then Events, mark `generate_lead` as a **key event** if your site sends it when a form goes out.
4. Update your privacy notice to cover analytics. See [PRIVACY.md](../PRIVACY.md).

To see which channel each **lead** came from, your form also has to send the visit's source along. The example site does this after consent, from the UTM tag or the referring site. The Lead Loop's **Website form** webhook turns it into a channel.

## B. Search Console (5 minutes)

1. Go to search.google.com/search-console and add a **Domain** property for your site.
2. If your domain is on Cloudflare, Google can add the check record for you. Otherwise, add the TXT record it shows at your domain host.
3. Submit your sitemap under **Sitemaps**.

## C. A Google service account for n8n (15 minutes)

n8n Cloud's simple "Sign in with Google" button doesn't cover Analytics or Search Console. A service account is a robot Google user that can only read what you share with it. Its key doesn't expire after a week like a test sign-in does.

1. Go to console.cloud.google.com and create a project, for example `marketing-engine`.
2. Under **APIs & Services, then Library**, enable the **Google Analytics Data API** and the **Google Search Console API**.
3. Under **IAM & Admin, then Service Accounts**, click **Create service account**. Name it `n8n-overview`, skip the roles and click **Done**.
4. Open it, go to **Keys**, then **Add key, Create new key, JSON**. A key file downloads. Treat it like a password.
5. Give it read-only access:
   - **Google Analytics:** Admin, then Property access management, then **+**, Add users. Paste the service account's email and choose **Viewer**.
   - **Search Console:** Settings, then Users and permissions, then Add user. Paste the same email and choose **Restricted**.
6. In n8n, create a **Google Service Account API** credential:
   - Paste the email, and the private key from the JSON file.
   - Turn on **Set up for use in HTTP Request node**.
   - Scopes: `https://www.googleapis.com/auth/analytics.readonly https://www.googleapis.com/auth/webmasters.readonly`
7. Delete the JSON file from your computer once it's saved in n8n.

If Google says key creation is turned off for your organisation, an admin has to allow it for this project. This happens with some Google Workspace accounts, not personal ones.

## D. Notion (5 minutes)

1. Go to notion.so/profile/integrations and click **New integration**. Make it internal, name it `AI Marketing Engine`, give it **Read content** and **Insert content**, and copy the secret.
2. In Notion, create a full-page **database** called `Marketing overview`. Keep its title column named **Name**.
3. On the database, click **...**, then **Connections**, and add your integration.
4. Copy the database ID from its link: the 32 characters after your workspace name and before `?v=`.
5. In n8n, create a **Notion API** credential with the secret.

## E. Build, import and run

1. Add these to `.env`:
   ```
   GA4_PROPERTY_ID=123456789
   SEARCH_CONSOLE_SITE=sc-domain:yourdomain.com
   NOTION_DATABASE_ID=your32characterdatabaseid
   HUBSPOT_APP_URL=https://app-eu1.hubspot.com
   ```
   Use `https://app.hubspot.com` if your HubSpot account isn't in the EU.
2. Run `python scripts/build.py`. It writes `n8n/weekly-overview.json`.
3. In n8n, import it as a new workflow. Open each box below and pick its credential:

| Box | Credential |
| --- | --- |
| GA4 visits by channel, GA4 top landing pages, Search Console totals, Search Console searches | Google Service Account API |
| HubSpot leads | Your HubSpot credential from the Lead Loop |
| Overview agent (Haiku 5.5) | Anthropic |
| Save in Notion | Notion API |
| Email the overview | Gmail |

4. Click **Run the overview now**. Each run costs well under a cent in Claude credits.
5. Turn the workflow **on** (top right) so it runs every Monday at 8.

A source that isn't connected yet doesn't stop the run. It shows up under **Missing this week** in the overview, with the error, so you know what to fix. A new site has little data in its first weeks, and the summary says so instead of guessing.

## Where the words for this week come from

Every word idea shows its source, and the workflow checks that source itself instead of trusting the AI:

- **Rising search** or **Search**: the phrase is in your own Search Console data for that week. Rising means it's new, or shown at least one and a half times as often as the week before.
- **Demand Engine plan**: the phrase is in the SEO agent's words to use, or the AEO and GEO agent's buyer questions, from your latest run (the date is shown).
- **Claude's own idea, not found in your data**: shown last, so you can judge it yourself.

These are your own search data and your plan, not social media trend lists. Google's official Trends API is still in a limited test, and the platforms don't offer a simple free trends feed, so check each platform's own trends before you post. The words get better as Search Console collects data and you run the Demand Engine again each month.

## How channels are decided

The same rules run in the Lead Loop and the overview, so the two sets of numbers line up. The rules are `channelOf` in `scripts/build.py`.

| Channel | Comes from |
| --- | --- |
| AI assistants | chatgpt.com, perplexity.ai, claude.ai, gemini.google.com, copilot.microsoft.com and similar |
| LinkedIn | linkedin.com, lnkd.in, or `utm_source=linkedin` |
| Search engines | Google, Bing, DuckDuckGo and others, or `utm_medium=organic` |
| Other social | Instagram, Facebook, TikTok, X, YouTube, Reddit and others |
| Email | `utm_medium=email`, or mail and newsletter sources |
| Other websites | Any other site that links to you |
| Direct | Typed in, bookmarked, or the source is hidden |
| Unknown | No source, for example when the visitor declined analytics |

Visits from AI assistants only show up when the assistant passes a link the visitor clicks. A visitor who reads your name in an answer and types it in later counts as Direct or Search. So this number shows the floor, not the full picture.
