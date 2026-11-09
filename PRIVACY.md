# Privacy and GDPR guide

The Lead Loop handles personal data: names, email addresses, job titles and whatever people write in your contact form. If you or your leads are in the EU, EEA (including Norway) or Switzerland, data protection law applies. This guide lists what to set up before you use the engine with real leads.

> This is general information, not legal advice. Laws and vendor terms change, so check the current versions and ask a lawyer if you're unsure.

## Where the data goes

Contact form → n8n (runs the workflow) → Claude API (scores the lead and drafts a reply) → HubSpot (stores the contact) → Gmail (sends you the alert)

Each of these services is a **processor** that handles data on your behalf.

## Checklist before going live

1. **Privacy notice at the form.** Tell people who you are and why you collect their details (to answer their enquiry). Name the services that process the data (n8n, Anthropic, HubSpot, Google), and say how long you keep it and how they can ask for access or deletion. Put a short line under the form with a link to the full notice.
2. **Say that AI helps.** Mention in the notice that an AI tool helps sort enquiries and draft replies, and that a person reads and sends every reply.
3. **A person decides.** GDPR Article 22 limits decisions made *solely* by automated means that have legal or similarly significant effects. In this engine the score only helps you prioritise, and a person reviews every lead. Keep it that way.
4. **Lawful basis.** Answering someone who contacted you is usually covered by steps before a contract or by legitimate interest (GDPR Article 6(1)(b) and (f)). Write down which one you rely on.
5. **Collect only what you need.** Don't add fields you won't use, and never ask for sensitive data such as health or beliefs.
6. **Data processing agreements.** Check that each processor offers a data processing agreement (DPA) and accept it. Most include one in their terms or account settings.
7. **Transfers outside Europe.** Most of these vendors are US companies. Check that each is certified under the EU-US Data Privacy Framework, or relies on Standard Contractual Clauses.
8. **Retention.** Pick a period, for example 12 months for leads that didn't become clients, and delete old contacts in HubSpot. Delete test leads when you're done testing.
9. **Provider settings.** Read how your AI provider handles API inputs, including whether they're used for training and how long they're kept. Note it in your notice.
10. **Keep a simple record** of what you process, why, where and for how long. A one-page document is enough for a small business.

## Your website

- **IP addresses can be personal data.** The EU Court of Justice said so in *Breyer* (C-582/14, 2016). In 2022 a Munich court ordered a website to pay damages for loading Google Fonts from Google's servers without consent, because that sent visitors' IP addresses to Google (LG München I, 3 O 17493/20).
- **Host fonts yourself** instead of loading them from Google, and avoid third-party embeds that load before consent.
- **Analytics and marketing cookies need consent** in the EU and EEA. Load GA4 only after the visitor agrees in a cookie banner.

## Email outreach

- The Outbound agent only drafts one-to-one messages for a person to send. Rules on unsolicited marketing email differ by country.
- **Germany** generally requires prior consent for advertising email, even to businesses.
- **Switzerland** requires consent for automated mass advertising email.
- **Norway** has its own rules in the Marketing Control Act (markedsføringsloven) section 15.
- Check the rules for each country before writing to someone you haven't met, and always include a clear way to opt out.

## AI-made content

The EU AI Act's transparency rules (Article 50) apply from 2 August 2026. Label AI-generated images, video and audio where the law or the platform asks you to.
