# Company context file: [Company name]

Version 0.1 · [date] · Owner: [name]

Every agent reads this file before it does anything. Change the business here once, and every agent follows. Keep the section numbers, because the agents refer to them.

## 1. The business

- **Name:**
- **Website:**
- **What it does:** (one sentence a customer would understand)
- **Run by:**
- **Based in:**

## 2. Ideal client

- **Who:**
- **Strong fit, first priority:**
- **Also a good fit:**
- **Where:**
- **Not a fit:**

## 3. Buying roles

| Role | What they care about | What they need to hear |
| --- | --- | --- |
| | | |

## 4. Services and prices

| Package | What it is | Price |
| --- | --- | --- |
| | | |

- **Rule:** Agents never quote a price that isn't in this table.

## 5. Brand voice

- How you sound:
- **Never use:**

## 6. Approved claims

Agents may only use facts from this list. Anything else is flagged for a person.

-

## 7. Rules for every agent

1. A person approves anything that goes to a customer for the first time, quotes a number or makes a claim.
2. No invented facts, clients, results or testimonials.
3. Customer data stays in the CRM. Agents only read what their job needs.
4. AI-made images and videos are labeled where the platform or the law asks for it.
5. When unsure, flag it for a person instead of guessing.

## 8. Tools connected

| Job | Tool |
| --- | --- |
| CRM | |
| Automation | n8n |
| Analytics | |
| AI | Claude API |
| Alerts | Email to the address in ALERT_EMAIL (set in .env) |

## 9. Lead scoring guide (used by the Lead agent)

Start at 0 and add or subtract points.

| Signal | Points |
| --- | --- |
| Decision maker | +25 |
| Company size you serve best | +20 |
| Asks for a listed service | +20 |
| Mentions a budget, timeline or start date | +15 |
| Industry you serve best | +10 |
| Region you serve | +10 |
| Company far too big for you | -20 |
| Student, job seeker or wants free help | -30 |
| Asks for something you don't offer | -30 |
| Spam, unrelated sales pitch or link-dropping | Score 0, no reply |

The highest score is 100. A real person who scores below 1 counts as cold (score 1), not spam.

**Score bands**

| Score | What happens |
| --- | --- |
| 70 and above (hot) | Alert the owner now, with a reply draft offering a short call |
| 40 to 69 (warm) | Reply draft with the right package and one question |
| 1 to 39 (cold) | Polite reply draft |
| 0 (spam) | Tag it as spam, no reply |
