# Step 4 · Build the lead loop in n8n

This takes about 45 minutes. You'll import one workflow file, connect three accounts, and run 20 test leads with one click.

## What the workflow does

Each new lead runs through the same steps.

1. A lead arrives, either from the contact form or from the 20 test leads.
2. **Prepare lead** tidies the details and adds the company context file.
3. **Lead agent (Haiku 5.5)** checks whether it's spam, scores it with the scoring guide and writes a reply draft in the lead's own language.
4. **Read Claude answer** works out the score band (hot, warm, cold or spam) and flags any banned words in the draft.
5. Leads that aren't spam are saved to HubSpot with their score, band, summary and reply draft.
6. If a lead is hot, you get an email alert with the draft to check.

Nothing is ever sent to the lead automatically. You always read the draft first.

## A. Add six custom fields in HubSpot (10 minutes)

These fields hold what the agent writes about each lead.

1. In your test HubSpot account, click the **gear icon** (Settings).
2. Go to **Data Management → Properties**, make sure **Contact properties** is selected, then click **Create property**.
3. Create these six fields, one at a time.

| Label (type it exactly) | Field type |
| --- | --- |
| AI lead score | Number |
| AI lead band | Single-line text |
| AI lead summary | Multi-line text |
| AI reply draft | Multi-line text |
| Lead channel | Single-line text |
| Lead source detail | Single-line text |

4. When you create each field, check that HubSpot shows the internal name as `ai_lead_score`, `ai_lead_band`, `ai_lead_summary`, `ai_reply_draft`, `lead_channel` and `lead_source_detail`. The workflow uses those exact names.

The last two hold where the lead came from, like LinkedIn or an AI assistant. The weekly overview uses them to show which channels bring hot leads.

## B. Make a HubSpot service key (5 minutes)

A service key is like a password that lets n8n write to your HubSpot.

1. In HubSpot, go to **Development → Keys → Service Keys** and click **Create service key**.
2. Name it `n8n lead loop`.
3. Add these three scopes:
   - `crm.objects.contacts.read`
   - `crm.objects.contacts.write`
   - `crm.schemas.contacts.read`
4. Create the key, click **Show** and copy it.

If you don't see Service Keys, tell me what you see and I'll guide you to the older "private app" option.

## C. Import the workflow into n8n (5 minutes)

1. In n8n, create a new workflow.
2. Click the **three dots (⋯)** at the top right and choose **Import from file**.
3. Choose `n8n/lead-loop.json` (made by `python scripts/build.py`). You should see 11 boxes connected left to right.

## D. Connect your three accounts (10 minutes)

Open each of these boxes (double-click), pick **Create new credential**, and save.

| Box | Credential | What to paste or click |
| --- | --- | --- |
| Lead agent (Haiku 5.5) | **Anthropic** | A Claude API key made just for n8n, from the Claude Console. Don't choose Gateway credits. |
| Save to HubSpot | **HubSpot Service Key** | The service key from step B |
| Alert owner | **Gmail** | Click **Sign in with Google** |

In the **Save to HubSpot** box, open the custom properties. If a property name shows in red, pick it from the dropdown list (for example AI lead score).

## E. Run the 20 test leads (5 minutes)

1. Click the **Run 20 test leads** box, then click **Execute workflow** at the bottom.
2. Wait about a minute while all 20 leads go through Claude.
3. Click the **Read Claude answer** box to see every lead's score, band, reasons and reply draft.

## F. Check it against the answer key (10 minutes)

Open `test-leads-answer-key.csv` next to the n8n results.

**It passes when all of these are true:**
- [ ] Every lead lands in the right band (hot, warm, cold or spam).
- [ ] Each score is within about 15 points of the answer key.
- [ ] No reply draft invents a fact, a client or a price that isn't in the context file.
- [ ] The voice check says "none" for every draft.
- [ ] You get 6 alert emails, one for each hot lead.
- [ ] HubSpot shows 17 new contacts with their AI fields filled in, since the 3 spam leads are skipped.

**If something fails:** copy the error or the result here and I'll fix it with you. A wrong score usually means we tweak the scoring guide in the context file, not the workflow.

## G. Save the proof

- Take a screenshot of the workflow canvas after the run, with all green ticks.
- Take a screenshot of one hot lead's alert email.
- Take a screenshot of the HubSpot contact list showing the AI lead band column.
- Check the cost in Claude Console → Usage. It should be about one cent for all 20 leads.

## H. Connect your own website's form

The workflow's **Website form** box is a webhook: an address your site's contact form can send a copy of each enquiry to.

1. In `.env`, set `SITE_ORIGIN=https://yourdomain.com`. Only your site may send to the webhook from a browser.
2. Run `python scripts/build.py` again and import the new `n8n/lead-loop.json`. The build prints the webhook path and saves it in `.env`, so it stays the same.
3. In n8n, open **Website form** and copy the **Production URL**. Turn the workflow on.
4. In your site's form code, after the message has been sent the usual way, also `POST` this JSON to that URL:
   ```json
   {
     "answers": { "Name": "", "Email": "", "Brand or company": "", "Website or social link": "", "Message": "",
                  "Services interested in": "", "Package interested in": "", "When to start": "", "How they heard": "" },
     "source": "linkedin", "medium": "social", "campaign": "", "landing": "/services", "page": "/contact"
   }
   ```
   Only Email and Message are required. Send `source`, `medium` and `campaign` from the visit's UTM tag or referring site, and only if the visitor accepted analytics.
5. Send one test from your site and check that the contact appears in HubSpot with a Lead channel.

Keep your normal email delivery as well. If n8n is ever down, no message is lost.

The webhook address ends up in your site's public code, so anyone could call it. The **Website to lead** box drops any call without a real-looking email and a message before it reaches Claude. Keep a spend limit on your Claude API key too.
