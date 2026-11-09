# Privacy and GDPR guide

The Lead Loop handles personal data: names, email addresses, job titles and whatever people write in your contact form. GDPR applies in the EU and the EEA, which includes Norway. Switzerland has its own law (the revised FADP). This guide lists what to set up before you use the engine with real leads.

> This is general information, checked against the sources below in November 2026. It is not legal advice. Laws and vendor terms change, so check the current versions, and ask a lawyer before a real decision such as an outreach campaign.

## Where the data goes

Contact form → n8n (runs the workflow) → Claude API (scores the lead and drafts a reply) → HubSpot (stores the contact) → Gmail (sends you the alert)

Each service is a **processor** that handles data for you. Under GDPR Article 28 you need a data processing agreement (DPA) with each one [1].

| Service | DPA | Notes |
| --- | --- | --- |
| Anthropic (Claude API) | Built into the Commercial Terms, with Standard Contractual Clauses [2][3] | Under the Commercial Terms, Anthropic may not train models on your content. API inputs and outputs are deleted within 30 days, unless they're flagged for a policy check or you store them yourself [2][4]. Keep lead data out of the consumer Claude app. |
| HubSpot | Part of HubSpot's terms, using the EU-US Data Privacy Framework plus SCCs [5] | Use a contacts-only key |
| n8n Cloud | Pre-signed by n8n. **You have to countersign it and send it back** [6] | |
| Gmail | **No DPA was found for free Gmail.** Google offers one for Google Workspace used for work [7] | Use Workspace for lead email, or set `ALERT_DETAILS=minimal` so the alert says only "hot lead, score 90" and the details stay in HubSpot |

## Checklist before going live

1. **Privacy notice at the form** (GDPR Article 13) [1]. Cover:
   - who you are, and why you collect the details (to answer the enquiry)
   - your legal basis
   - who processes the data (n8n, Anthropic, HubSpot, Google), and that some of them are in the US
   - how long you keep it, and how people can ask for access or deletion

   Put a short line under the form with a link to the full notice.
2. **Say that AI helps.** Mention that an AI tool helps sort enquiries and draft replies, and that a person reads and sends every reply.
3. **A person decides.** Article 22 limits decisions made *solely* by automated means with legal or similarly significant effects [1]. The EU Court's SCHUFA ruling (C-634/21) shows that a score can count as a decision when it's decisive [8]. So the score here only orders your replies, and never auto-rejects anyone.
4. **Lawful basis.** Answering someone who contacted you usually rests on steps before a contract or on legitimate interest (Article 6(1)(b) or (f)) [1]. Marketing emails are different, see below.
5. **Collect only what you need.** Name, email and message are enough. Never ask for sensitive data.
6. **Transfers to the US.** The EU-US Data Privacy Framework is still in force and covers the EEA, including Norway [9]. It came under new pressure in 2026: after the US Supreme Court's Trump v. Slaughter ruling, noyb asked the Commission to withdraw it, and the EDPB wrote to the Commission [10][11]. Prefer vendors that also offer Standard Contractual Clauses.
7. **Retention.** Write down a deletion rule, for example deleting leads that never replied after 12 months. Delete test leads when you're done testing.
8. **Keep a simple record** of what you process, why, where and for how long.
9. **In Switzerland,** the revised FADP has a duty to inform. Its fines of up to CHF 250,000 are aimed at the responsible person, which for a sole trader is you [12].

## Your website

- **IP addresses are personal data.** In *Breyer* (C-582/14, 2016) the EU Court said a dynamic IP address can be personal data [13]. In 2022 a Munich court awarded damages because a website loaded Google Fonts from Google's servers, which sent visitors' IP addresses to Google without consent (LG München I, 3 O 17493/20) [14].
- **Host fonts and scripts yourself,** and load YouTube, maps and other embeds only after a click.
- **Ask before analytics cookies.** Norway has required GDPR-level consent for cookies since 1 January 2025 [15]. Load GA4 only after the visitor agrees, make Decline as easy as Accept, and let people change their mind later. Accept Google's data processing terms in the Analytics admin, and switch off ads features and Google signals if you don't need them.
- **Only note a lead's channel with consent.** The source a form sends to the Lead Loop (a UTM tag or the referring site) comes from the visit, so collect it only after the visitor accepted analytics, and say so in your privacy notice.
- **The weekly overview holds no personal data.** It reads counts from Google Analytics, Search Console and HubSpot and writes counts to Notion and the email. No names or messages leave HubSpot.
- **Protect your public form** with a honeypot or bot check and length limits, and keep a spend limit on the API key behind it.

## Email outreach

The Outbound agent only drafts one-to-one messages for a person to send.
- **Norway** (markedsføringsloven § 15): marketing email to a person needs prior consent. Forbrukertilsynet says a named work address like ola.nordmann@firma.no counts, even for a business offer. Generic addresses like post@firma.no are allowed. Every email needs a free way to say no thanks [16][17].
- **Germany** (UWG § 7): email advertising needs prior express consent, with no business exception [18].
- **Switzerland** (UWG Art. 3(1)(o)): mass advertising needs prior consent, a correct sender and an easy free opt-out [19].
- GDPR also lets any named contact object to direct marketing at any time [1].
- **The safe default:** follow up by LinkedIn message or in person, and ask before you email.

## AI-made content

- The EU AI Act's transparency rules (Article 50) have applied in the EU since 2 August 2026 [20].
  - Chatbots must say they're AI.
  - Deepfakes must be disclosed.
  - AI text published to inform the public needs a label, unless a person reviewed it and takes editorial responsibility.
- Norway hasn't adopted the AI Act yet, and a bill is planned for spring 2027 [21].

## Sources

1. GDPR, Regulation (EU) 2016/679. https://eur-lex.europa.eu/eli/reg/2016/679/oj
2. Anthropic Commercial Terms of Service. https://www.anthropic.com/legal/commercial-terms
3. Anthropic Data Processing Addendum. https://www.anthropic.com/legal/data-processing-addendum
4. Anthropic Privacy Center, how long organisation data is stored. https://privacy.claude.com/en/articles/7996866-how-long-do-you-store-my-organization-s-data
5. HubSpot Data Processing Agreement. https://legal.hubspot.com/dpa
6. n8n Legal. https://n8n.io/legal
7. Google Workspace Individual Help, data processing terms. https://support.google.com/google-workspace-individual/answer/10757067
8. CJEU press release 186/23, SCHUFA, C-634/21. https://curia.europa.eu/jcms/jcms/p1_4213242/en
9. Wikborg Rein, transfers of personal data to the USA. https://www.wr.no/en/news/more-about-transfers-of-personal-data-to-the-usa
10. noyb, 29 June 2026. https://noyb.eu/en/us-supreme-court-just-blew-eu-us-data-transfers
11. EDPB letter on Trump v. Slaughter, 31 July 2026. https://www.edpb.europa.eu/documents/edpb-correspondence/edpb-letter-to-the-european-commission-on-us-supreme-court-judgment_en
12. FDPIC, the revised FADP. https://www.edoeb.admin.ch/en/new-fdpics-role
13. CJEU, C-582/14 Breyer. https://collab.dpa.gr/wp-content/uploads/2023/07/CJEU_C-582.14-Breyer_en.pdf
14. LG München I, 3 O 17493/20. https://www.gesetze-bayern.de/Content/Document/Y-300-Z-GRURRS-B-2022-N-612?view=Print
15. CMS Norway, new electronic communications act. https://cms.law/en/nor/publication/ny-ekomlovgivning
16. Marketing Control Act, English translation. https://faolex.fao.org/docs/pdf/nor220628eng.pdf
17. Forbrukertilsynet, marketing by email and SMS. https://www.forbrukertilsynet.no/?p=2165
18. UWG § 7 (Germany). https://www.gesetze-im-internet.de/uwg_2004/__7.html
19. OFCOM, when is mass sending allowed? https://www.bakom.admin.ch/en/when-is-mass-sending-allowed
20. European Commission, Article 50 AI Act FAQ. https://digital-strategy.ec.europa.eu/en/faqs/transparency-obligations-under-article-50-ai-act
21. KI-akademiet, the AI Act in Norway, status and timeline. https://kiakademiet.no/kunnskap/ki-forordningen/norge
