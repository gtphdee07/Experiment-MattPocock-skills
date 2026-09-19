# Transactional email providers — research notes

> This file lives in `docs/research/`, a new directory created for this write-up because the repo had no existing convention for research/vendor-comparison notes (only `docs/adr/`, `docs/agents/`, and `docs/design/` existed, none of which fit).

**Status:** research only — no decision has been made. This document exists so a human can decide, informed by primary-source facts as of **2026-09-18**.

---

## Summary / lean

For this project's specific situation — a synchronous FastAPI backend, Python 3.12, currently **zero real users**, sending exactly two kinds of low-volume one-to-one emails (a fastapi-users password-set link, and possibly a purchase receipt) — the two strongest candidates are **Postmark** and **Resend**:

- **Postmark** has the most mature, purpose-built reputation specifically for *transactional* (not marketing) email, a permanent (not time-limited) free tier of 100 emails/month, a low-cost paid tier with no monthly minimum once volume grows, and an official (if beta-labeled) Python SDK. Its restructured 2026 pricing (Basic/Pro/Platform, all starting at 10,000 emails) removed the old $10 flat "10,000 emails" starter tier that many small projects used to cite — worth flagging since older blog posts about Postmark pricing are now stale.
- **Resend** is the more modern, developer-ergonomics-first option (clean official Python SDK, sync+async, webhooks for bounce/complaint/delivery events out of the box) with a genuinely free tier (3,000 emails/month, 100/day cap, 3 domains, no time limit found on the free tier itself) and no monthly minimum on paid plans. It's a newer company than Postmark, so has a shorter deliverability track record.

Either is a reasonable choice for the fastapi-users password-set-link use case. **AWS SES** is the cheapest at volume and has no monthly minimum on its base (Essentials) tier, but recent (2026) pricing-plan restructuring introduced *paid* tiers (Pro/Enterprise) with real monthly minimums ($105–$500/region) for anyone who wants dedicated-IP or higher-throughput features — and SES requires more manual deliverability setup (sandbox mode, manual DKIM/SPF, no polished dashboard) than Postmark or Resend, which is a worse fit for a green-field integration with no existing email infrastructure. **SendGrid** is the weakest fit here: its free tier was discontinued in 2025 (now only a 60-day trial), its cheapest paid plan is the most expensive of the group at $19.95/mo, and it has a documented, recurring shared-IP-pool deliverability reputation problem.

**Confirmed from Stripe's own docs:** Stripe does **not** bundle a general-purpose transactional email capability that could be repurposed to deliver a "set your password" link. Its only customer-email feature is fixed-template payment receipts / paid invoices, generated from a `Charge` or `Invoice` object and sent to the address on that object — there is no API to send arbitrary custom email content through Stripe. See details below. A dedicated email vendor is not avoidable via Stripe.

---

## 1. Does Stripe (or another already-relevant provider) bundle transactional email that could be repurposed?

### Stripe

Stripe's own documentation confirms Stripe has exactly one customer-facing email capability, and it is narrowly scoped to payments:

- **Receipts**: Stripe can automatically email a receipt when a payment or refund succeeds (toggle in Dashboard → Settings → Business → Customer emails). The receipt is generated from the `Charge` object and its content/branding is limited to logo, brand colors, and required legal/support fields — there is no way to inject arbitrary custom body content like a password-set link. ([docs.stripe.com/payments/checkout/receipts](https://docs.stripe.com/payments/checkout/receipts))
- **Paid invoices**: For Checkout Sessions, setting `invoice_creation[enabled]=true` makes Stripe generate and email a paid-invoice summary (with PDF links) after a successful payment. This is also a fixed Stripe-owned template driven by the `Invoice`/`Checkout Session` object, and Stripe notes this is a *separately priced* Invoicing feature for one-time payments, not a generic email API. ("Invoice creation for one-time payments through the Checkout Sessions API is not an Invoicing feature, and is priced separately.") ([docs.stripe.com/payments/checkout/receipts](https://docs.stripe.com/payments/checkout/receipts))
- Related Stripe pages ("Send customer emails" for Invoicing, "Automate customer emails" for Billing/revenue-recovery) are similarly scoped to dunning/invoice-lifecycle emails Stripe itself owns and templates — not a mechanism for a business to send its own custom transactional content (e.g., a fastapi-users password-reset token URL) through Stripe's sending infrastructure.

**Conclusion**: Stripe cannot be repurposed for the "email a new Account a password-set link" use case. Its email sending is a closed system tied to Stripe's own receipt/invoice objects and templates, with no arbitrary-content API. A separate email vendor is necessary.

### Other backend/auth providers (Supabase, Firebase Auth, Auth0, Clerk, AWS Cognito)

These *do* bundle transactional email as part of their managed auth service (e.g., Supabase Auth and Firebase Auth both send password-reset/magic-link emails out of the box; Auth0 and Clerk likewise). However, none of them are relevant to this project's actual architecture: the backend already uses **fastapi-users** (a self-hosted, session-cookie-based auth library) for account/session management, and the password-reset-token generation is explicitly being reused from fastapi-users per the spec. Adopting one of these providers to get "free" bundled email would mean replacing the entire auth system, not just adding an email step — wildly disproportionate to the actual gap (email *delivery* only). This option is noted for completeness per the research question, but is not a realistic alternative to picking a dedicated email vendor.

---

## 2–3. Comparison of dedicated transactional email providers

**Providers compared:** SendGrid, Postmark, AWS SES, Resend. **Mailgun** was investigated but is not carried forward as a top recommendation (see note at the end) — its current pricing/positioning is very similar to Postmark's but without Postmark's specific transactional-only reputation, so it's included in the table for completeness rather than as a leading candidate.

### SendGrid (Twilio)

- **Pricing (primary source: [twilio.com/en-us/products/email-api/pricing](https://www.twilio.com/en-us/products/email-api/pricing), confirmed via [www.twilio.com/en-us/changelog/sendgrid-free-plan](https://www.twilio.com/en-us/changelog/sendgrid-free-plan)):**
  - No permanent free tier. As of March 25, 2025, new accounts get a **60-day trial capped at 100 emails/day**, after which sending stops until upgrade. The old permanent free plan was fully retired for existing accounts by ~July 2025 (60 days after the May 28, 2025 changelog announcement).
  - Cheapest paid plan: **Essentials, starting at $19.95/month**, covering roughly 50,000–100,000 emails/month depending on tier.
  - Next: **Pro, starting at $89.95/month**, 100,000–2,500,000 emails/month, includes 1 dedicated IP.
  - **Premier**: custom pricing, 5M+ emails/month.
  - No explicit monthly minimum stated beyond the plan's own base price (i.e., you pay the plan price regardless of whether you use the volume).
- **SDK**: Official, actively maintained Python SDK — `pip install sendgrid` ([github.com/sendgrid/sendgrid-python](https://github.com/sendgrid/sendgrid-python)), full v3 Web API coverage.
- **Deliverability / features**: 2 event webhooks on Essentials, 5 on Pro/Premier (covers bounce/complaint events). Dedicated IP only included from Pro ($89.95/mo) up. Notable downside: SendGrid's shared-IP pools have a documented, recurring reputation problem — e.g. Spamhaus blocklisting incidents affecting Outlook/Hotmail delivery for senders on shared IPs in early 2025 due to other tenants' abuse, independent of the affected sender's own practices (SendGrid's own support docs recommend a dedicated IP as "the only practical solution" for senders who need to avoid this). Sources: [SendGrid support: "Email Deliverability: Shared IP Pools 101"](https://support.sendgrid.com/hc/en-us/articles/17326626295579-Email-Deliverability-Shared-IP-Pools-101), [Spamhaus blocklist analysis](https://www.suped.com/learn/blocklists/why-was-sendgrids-ip-blocked-by-spamhaus).
- **Notable downside**: the 2025 free-tier discontinuation is a real, recent, primary-source-confirmed change (not rumor) — this project should not assume a free SendGrid tier is available at all going forward.
- **Startup/free-forever fit**: Poor. No ongoing free tier; cheapest real option is $19.95/mo flat regardless of the near-zero volume this project currently needs.

### Postmark (ActiveCampaign)

- **Pricing (primary source: [postmarkapp.com/pricing](https://postmarkapp.com/pricing)):**
  - **Free Developer tier: 100 emails/month, no overages allowed, does not expire** — a genuine permanent free tier, not a trial.
  - Paid plans restructured in 2026 into three tiers, all starting at 10,000 emails/month included: **Basic $15/mo** (overage $1.80/1,000), **Pro $16.50/mo** (overage $1.30/1,000, "Most Popular"), **Platform $18/mo** (overage $1.20/1,000, adds more features e.g. SSO/higher retention).
  - No monthly minimum beyond the flat plan price; no tier exists between the 100/month free plan and the 10,000/month paid plans ("We do not offer a tier between 100 emails/month … and 10,000 emails/month" — Postmark's own pricing page copy).
  - High-volume (10M+/month): custom/sales pricing.
- **SDK**: Official Python SDK, `pip install postmark-python` ([github.com/ActiveCampaign/postmark-python](https://github.com/ActiveCampaign/postmark-python)) — async-first with a sync wrapper added in v0.3.0, Python 3.10+. Labeled Beta as of the versions found. (Older third-party/community libraries `postmarker` and `python-postmark` also exist on PyPI but are not the official SDK.)
- **Deliverability / features**: Postmark automatically generates DKIM keys per domain during domain setup; SPF/DMARC guidance is documented, including specific troubleshooting docs for DMARC-policy bounces. Dedicated bounce webhook (JSON POST) and a general webhooks API cover bounce/complaint/delivery events. Postmark's brand positioning and product design (separate "transactional" vs. "broadcast" message streams, fast delivery-speed focus) is specifically built around transactional email, which is the exact use case here (a single password-set-link email, not bulk marketing). Sources: [Bounce webhook docs](https://postmarkapp.com/developer/webhooks/bounce-webhook), [Webhooks overview](https://postmarkapp.com/developer/webhooks/webhooks-overview), [DMARC bounce troubleshooting](https://postmarkapp.com/support/article/how-to-fix-dmarc-policy-bounces).
- **Notable downside**: the 2026 pricing restructure changed the historical "$15 flat = 10,000 emails/mo" story that a lot of older comparison content still repeats — the *entry* price is still $15, but there's now a 3-way Basic/Pro/Platform split gating features like SSO behind higher tiers. Worth confirming against the live pricing page before committing, since this changed recently.
- **Startup/free-forever fit**: Good. The 100/month free tier is small but is exactly proportional to a pre-launch product's real volume (password-set emails + receipts, likely single digits/month at first), and it does not expire.

### AWS SES

- **Pricing (primary source: [aws.amazon.com/ses/pricing](https://aws.amazon.com/ses/pricing/)):**
  - No SES-specific "N free emails/month forever" tier anymore in the form it used to have. For accounts created before July 15, 2025: 3,000 message-charges/month free for the first 12 months. For accounts created after that date, the "free tier" is a general **$200 AWS Free Tier credit** (not SES-specific, shared across AWS services), valid for 6 months post-signup and usable within 12 months.
  - Base **Essentials plan** (the default new-account tier as of July 21, 2026): **$0.16 per 1,000 emails** (0–10M/month), dropping to $0.14/1,000 (10–100M) and $0.11/1,000 (100M+). **No monthly minimum on Essentials.**
  - **Pro plan**: $0.22/$0.17/$0.12 per 1,000 at the same volume breakpoints, but carries a **$105/month minimum per account per region**.
  - **Enterprise plan**: $0.23/$0.18/$0.13 per 1,000, **$500/month minimum per account per region**.
  - Dedicated IP (managed): $15/month/account plus a lower per-email add-on rate; included free (1 IP) on Pro, 5 on Enterprise.
- **SDK**: Not a bespoke SES-branded SDK — sent via the general-purpose official **boto3** AWS SDK (`ses` or `sesv2` client, `send_email` method). ([boto3 SES send_email docs](https://docs.aws.amazon.com/boto3/latest/reference/services/ses/client/send_email.html)) This is a mature, official, `pip install boto3` library, but it is a full general AWS SDK rather than an email-purpose-built client — more setup/boilerplate (IAM credentials/roles, verified identities, sandbox-mode exit request) than a dedicated email vendor's SDK.
- **Deliverability / features**: New accounts start in a **sandbox mode** that only allows sending to verified addresses until AWS approves a production-access request — an extra manual step not present with SendGrid/Postmark/Resend/Mailgun. DKIM/SPF setup is manual DNS configuration through the SES console; no built-in polished dashboard/analytics comparable to the dedicated providers. Bounce/complaint notifications are delivered via SNS topics (more plumbing to wire up vs. the dedicated providers' simple webhook endpoints).
- **Notable downside**: the Essentials/Pro/Enterprise plan restructuring is very recent (Pro/Enterprise monthly minimums, the July 21 2026 Essentials-by-default cutover) — this is a primary-source-confirmed, currently-in-flux area of AWS's pricing that could change again; the historical "SES is $0.10/1,000 with basically no free tier" reputation is already stale relative to the live pricing page.
- **Startup/free-forever fit**: Fine on raw cost (Essentials has no minimum and is the cheapest per-email rate of the group at real volume) but weaker on "zero-friction to get started" — sandbox mode, manual DNS/DKIM, and IAM setup add real integration overhead for a green-field email integration with no existing AWS email usage.

### Resend

- **Pricing (primary source: [resend.com/pricing](https://resend.com/pricing)):**
  - **Free tier: 3,000 emails/month, capped at 100/day, 3 domains.** (One secondary source noted a 2026 change to 30-day data retention and only 1 domain on some historical version of the free plan — the live page as fetched today shows 3 domains; treat the exact domain count as needing a final double-check against the live page at implementation time since aggregator sources disagreed slightly.)
  - **Pro**: $20/mo (50,000 emails) up to $35/mo (100,000 emails), $0.90/1,000 overage.
  - **Scale**: $90/mo (100,000 emails) up to $1,150/mo (2,500,000 emails), overage rate improving with tier ($0.90 → $0.46 per 1,000).
  - **Enterprise**: custom.
  - **No monthly minimum stated on any paid plan** — "the overage rate applies only to emails sent beyond the included volume," i.e., pay for the plan's base allotment, nothing extra unless you exceed it.
- **SDK**: Official Python SDK, `pip install resend` ([github.com/resend/resend-python](https://github.com/resend/resend-python)), simple API (`resend.Emails.send(params)`), with both sync and async (`send_async`, via httpx) support out of the box — the cleanest, most modern-feeling SDK of the group for a small FastAPI app.
- **Deliverability / features**: Supports DKIM/SPF/DMARC domain authentication via DNS records from the dashboard, with dedicated docs on DMARC implementation. Webhooks cover `sent`, `delivered`, `delivery_delayed`, `bounced`, `complained`, `opened`, `clicked`, and `suppressed` events with signed payloads — comparable webhook coverage to Postmark. Source: [resend.com/docs/dashboard/domains/dmarc](https://resend.com/docs/dashboard/domains/dmarc).
- **Notable downside**: Resend is the youngest company of the four (founded circa 2023), so it has a shorter public deliverability/reliability track record than Postmark or SendGrid; it also changed its billing model recently (pay-as-you-go overage billing turned on December 2025, retention bumped to 30 days in March 2026 per secondary sources) — i.e., it is a fast-moving product, which cuts both ways (rapid improvement, but pricing/policy has moved more than once in the last year).
- **Startup/free-forever fit**: Good. 3,000/month free (well above this project's near-zero current volume) with no stated expiration on the free tier itself, and no paid-plan minimum.

### Mailgun (for completeness, not a top recommendation)

- **Pricing (primary source: [mailgun.com/pricing](https://www.mailgun.com/pricing/)):** Free tier ~100 emails/day (~3,000/month), $0/mo, 1 custom domain. Paid: **Basic $15/mo** (10,000 emails, $1.80/1,000 overage), **Foundation** (50,000 emails, $1.30/1,000 overage, first month free), **Scale** (100,000 emails, $1.10/1,000 overage, first month free, adds dedicated IPs/SSO/phone support). No stated monthly minimum beyond plan price.
- **SDK**: Official `mailgun-python` package (`pip install mailgun-python`), Python 3.11+, actively maintained ([github.com/mailgun/mailgun-python](https://github.com/mailgun/mailgun-python)).
- Not elevated to a top recommendation because its pricing/positioning essentially mirrors Postmark's at the entry tier without Postmark's specific reputation as a transactional-email specialist — Mailgun markets itself more broadly across transactional and marketing/bulk use cases. It remains a reasonable fallback if either Postmark or Resend turns out to have an integration blocker.

---

## Free-forever / pay-as-you-go vs. monthly-minimum tiers — quick reference

| Provider | Free tier | Expires? | Cheapest paid entry | Monthly minimum (any tier)? |
|---|---|---|---|---|
| SendGrid | None (60-day, 100/day trial only) | Yes — trial | $19.95/mo | No explicit minimum beyond flat plan price |
| Postmark | 100 emails/mo | No — permanent | $15/mo (10,000 incl.) | No |
| AWS SES | $200 general AWS credit (not SES-specific) / legacy 3,000-msg tier for pre-7/15/2025 accounts | Credit: 6-12 mo | $0.16/1,000, no minimum (Essentials) | **Yes, on Pro ($105/mo) and Enterprise ($500/mo) only** — Essentials has none |
| Resend | 3,000 emails/mo, 100/day cap | Not stated as expiring | $20/mo (50,000 incl.) | No |
| Mailgun | ~3,000 emails/mo (100/day) | Not stated as expiring | $15/mo (10,000 incl.) | No |

Only AWS SES has a monthly-minimum trap — and only on its Pro/Enterprise tiers, which this project would have no reason to choose at current scale (its no-minimum Essentials tier is the relevant comparison point).

---

## Sources

- Stripe: [Receipts and paid invoices](https://docs.stripe.com/payments/checkout/receipts) (fetched 2026-09-18)
- SendGrid: [Email API pricing](https://www.twilio.com/en-us/products/email-api/pricing), [Free plan changelog](https://www.twilio.com/en-us/changelog/sendgrid-free-plan), [Shared IP Pools 101](https://support.sendgrid.com/hc/en-us/articles/17326626295579-Email-Deliverability-Shared-IP-Pools-101), [sendgrid-python](https://github.com/sendgrid/sendgrid-python) (fetched 2026-09-18)
- Postmark: [Pricing](https://postmarkapp.com/pricing), [Bounce webhook](https://postmarkapp.com/developer/webhooks/bounce-webhook), [postmark-python](https://github.com/ActiveCampaign/postmark-python) (fetched 2026-09-18)
- AWS SES: [Pricing](https://aws.amazon.com/ses/pricing/), [boto3 send_email](https://docs.aws.amazon.com/boto3/latest/reference/services/ses/client/send_email.html) (fetched 2026-09-18)
- Resend: [Pricing](https://resend.com/pricing), [resend-python](https://github.com/resend/resend-python), [DMARC docs](https://resend.com/docs/dashboard/domains/dmarc) (fetched 2026-09-18)
- Mailgun: [Pricing](https://www.mailgun.com/pricing/), [mailgun-python](https://github.com/mailgun/mailgun-python) (fetched 2026-09-18)

Where a claim above relies on a secondary source (a few noted exceptions, e.g. the exact current domain count on Resend's free tier, or historical Mailgun free-trial-month wording), that is called out explicitly in the relevant section rather than presented as primary-confirmed.
