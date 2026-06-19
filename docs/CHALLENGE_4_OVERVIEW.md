# CHALLENGE 4: AMINA — Dynamic Risk Profiling System

## Overview

**Challenge 4** asks teams to build an AI system that spots financial risk early by combining real-time public signals (news, sanctions lists, adverse media, ownership changes, funding events) with internal KYC and AML data.

The core innovation is **KYC drift detection**: catching the slow structural changes that quietly invalidate a customer's original risk profile — often **months before a sanctions listing** and years before a regulator notices.

---

## The Problem Statement

### Why This Matters

Banks onboard customers with a KYC profile: employment, ultimate beneficial owners (UBOs), residence, business type, expected transaction patterns. This snapshot represents the bank's understanding of who the customer is and what "normal" looks like.

In reality, customers change:
- **Legitimate drift**: a salesperson opens a manufacturing side business, turnover spikes, ownership shifts to a family trust.
- **Dangerous drift**: a compliant customer's beneficial owner is sanctioned; funding shifts to high-risk jurisdictions; the UBO's connections surface in adverse media.

The challenge: **distinguish between the two**, and catch risk drift **before** regulatory action makes it obvious.

### The Twist: KYC Drift

Traditional AML systems ask: *"Is this customer currently high-risk?"* They rely on:
- Static thresholds (volume > $X, jurisdictions in a blocklist)
- Periodic re-screening against sanctions lists
- Manual officer review, triggered by rule breaks

All of these are **lagging indicators**. A sanctioned customer's connection to your UBO might take weeks to surface in public lists.

**KYC drift reframes the question**: *"Has the underlying stochastic process changed?"*

If a customer's UBO was in London, self-employed in tech, and sent €2K/month to friends in Switzerland, and six months later the UBO has moved to Moscow, the business is now import-export, and the cash flow pattern shows €50K/month to Russian oligarchs' supply chains — the *process changed*. That's the signal. It doesn't require a sanctions hit.

---

## Key Terminology

### KYC (Know Your Customer)

The foundational compliance control: at onboarding, a bank collects and verifies:

- **Identity**: legal name, date of birth, passport/ID
- **Residence**: address, tax residency
- **Economic activity**: employment, business, source of funds
- **Ultimate Beneficial Owner (UBO)**: the natural person(s) who ultimately own / control the customer entity
- **Politically Exposed Person (PEP) status**: public office, family ties to public office
- **Adverse media**: news, sanctions, criminal records
- **Expected activity**: anticipated transaction volumes, corridors, counterparty types

This is the **baseline profile**. Once created, it is rarely updated unless the customer requests a change or a routine periodic review triggers a refresh.

### AML (Anti-Money Laundering)

The ongoing monitoring system that looks for signs of illicit activity:

- **Transaction monitoring**: ongoing surveillance of customer activity against their KYC profile and risk tier
- **Sanctions screening**: matching customers and counterparties against OFAC, EU, UN, and local blocklists
- **Suspicious activity reporting (SAR)**: filing with regulators when activity is suspicious
- **Due diligence (DD)**: deeper investigation before onboarding high-risk customers
- **Enhanced due diligence (EDD)**: ongoing review of high-risk customers with special scrutiny

AML traditionally runs in **alert mode**: trigger rules (large payment, PEP match, known bad actor), then escalate to an officer for review.

### KYC Drift

The divergence between the frozen KYC profile and the actual evolving customer behavior.

**Examples:**

| Profile | Reality | Drift Signal |
|---------|---------|--------------|
| "Self-employed consultant, London, €5–10K/month to EU clients" | Now Moscow-based, €50K/month to Russian entities, UBO sanctioned | High risk |
| "Import-export SME, stable 2 years, €20K/month turnover" | Volume doubled, now receiving from 10 new counterparties in Türkiye, corporate ownership changed | Medium risk (could be legitimate growth) |
| "Charity, fundraising 2–5K/month, UK-based" | Still 2–3K/month, donors unchanged, UBO unchanged, steady 10 years | Low risk (no drift) |

**Key insight**: Drift is *relative to the original profile*, not absolute thresholds. A consultant doing €50K/month is normal; the *same customer* doing €50K/month when the profile said €5–10K is a drift event.

### Bayesian Online Changepoint Detection (BOCPD)

A statistical method that continuously updates the probability that a customer's behavior has shifted into a new regime.

- **Run length**: the number of observations (e.g., transaction months) since the last regime change
- **Posterior over run length**: at each timepoint, the system maintains a belief distribution over "how long have we been in the current regime?"
- **Changepoint detected**: when the posterior mass **shifts to short run lengths**, indicating the old regime has likely ended

**Why it works**: It catches *gradual drift* that simple threshold rules miss. A customer who drifts from €5K to €9K over six months never crosses a €10K alert threshold, but the distribution shift is visible to the run-length posterior.

### Drift Velocity

The rate of change of KYC divergence over time.

- **Accumulated drift**: total KL divergence between the original profile and today's observed distribution
- **Drift velocity**: how fast that divergence is growing (bits per month)

A customer with high drift velocity is **accelerating away** from their profile. A customer with high drift but low velocity has settled into a new stable state (possibly due to legitimate business change).

**Use case**: Combine drift magnitude + velocity to prioritize investigation. High drift + high velocity = urgent. High drift + flat velocity = investigate, but less acute.

### Ultimate Beneficial Owner (UBO)

The natural person (or persons) who ultimately own or control a customer entity, directly or indirectly.

**Why it matters for drift detection**: A company's ownership structure can change — shares transferred to a family trust, new partners brought in, a parent company acquired. If a UBO is later sanctioned or surfaces in adverse media, the entire customer entity becomes higher risk retroactively.

**Example**: A consulting firm is 100% owned by Alice. Alice's profile is clean. One year later, Alice transfers her shares to a trust for her benefit; the trust is also controlled by her brother Bob. Later, Bob is sanctioned. Now the company is at risk through its UBO chain, even if the company itself never did anything wrong.

### Ownership Contagion (PageRank)

A graph-based method to propagate risk through ownership structures.

- **Nodes**: individuals, companies, trusts
- **Edges**: ownership (Alice owns 60% of Co A), control (Alice controls Trust T), beneficial interest
- **Risk score for a node**: weighted combination of its direct risk + risk propagated from connected nodes

**Use case**: If a sanctioned oligarch is discovered to own 5% of a company, that company's risk score increases. If that company owns another company, that company's risk also increases. The system can trace the propagation path and explain why customer X became higher-risk due to an indirect connection.

### Confirmation Lift

When public signals (news, sanctions, adverse media) **confirm** an internal drift signal.

**Example**:
1. Internal data: customer's UBO moved from London to Moscow, funding from Russian sources rose 5x.
2. Public signal: news article reveals the UBO is under investigation for sanctions evasion.
3. **Confirmation lift**: the internal drift signal is elevated because external data independently flagged the same entity.

This multiplies the signal strength and increases confidence that the drift is genuinely risk-related (not a data artifact or normal business variation).

### Causal Drift vs. Benign Drift

**Causal drift**: changes in customer behavior that are caused by or correlate with risk events (sanctioning, adverse media, FX conversion changes, illicit funding).

**Benign drift**: changes in customer behavior that are explained by normal business growth, legitimate jurisdiction changes, or market conditions.

**The challenge**: Both look like statistical drift. The Drift Engine uses causal analysis to separate them:

- **Causal hypothesis**: "The drift is due to a sanctioning event" — testable by cross-referencing public data and ownership records.
- **Benign hypothesis**: "The drift is due to the customer winning new legitimate contracts" — testable by transaction analysis, counterparty reputation, corridor risk.

Each hypothesis accumulates evidence (SHAP-style per-variable breakdown). The system recommends the hypothesis with the highest posterior probability and explains why.

### Suspicious Stability

The inverse problem: a customer in a high-risk environment who *never drifts* — their behavior is unnaturally smooth.

**Example**: A customer living in a jurisdiction known for financial crime, with a business model that historically shows 20% monthly volatility, but their transactions are exactly ±2% month-on-month for 2 years.

This could indicate:
- Deliberate smoothing to avoid detection (layering in AML terms)
- Outsourced operations (funding flows are routed through intermediaries)
- Or, it could be legitimate (boring business, small customer, high discipline)

The detector flags it for investigation; context determines if it's a red flag.

### Time-Travel Audit

A retrospective analysis that proves when the system *would have* flagged a customer, given only data available at that time.

**Use case**: A customer is sanctioned on June 1. The compliance officer needs to demonstrate to the regulator that:
- "Our Drift Engine would have flagged this customer on March 15 — two and a half months before the sanctions hit."
- "Here's the drift score, velocity, and evidence on March 15, using only data we had by March 15 (no hindsight)."

This proves the system is a **leading indicator**, not a trailing one. It's essential for regulatory defense.

---

## The Two-Layer Architecture

### Layer 1: Public Intelligence

**Inputs:**
- Sanctions lists (OFAC, EU, UN, local blocklists)
- News and adverse media (PEP connections, criminal investigations, regime changes)
- Funding events (capital raises, M&A, major contracts)
- Ownership changes (share transfers, board changes, corporate restructuring)

**Output:**
- Risk signals: customer or UBO has a sanctions hit, adverse media, risky funding source, sudden ownership change
- **Confirmation Lift**: when public signals align with internal drift

**Why it's separate**: Public data is slower, coarser, and requires human judgment to interpret. It's a **filter**, not a full picture. It catches the obvious cases and boosts confidence in internal drift signals.

### Layer 2: Internal Bank Data

**Inputs:**
- KYC profile (original onboarding data)
- Transaction history (cash flows, corridors, counterparties)
- AML alerts (past rule triggers, officer decisions)
- Periodic reviews (refreshed KYC data from compliance checks)

**Output:**
- Drift signals: BOCPD, velocity, causal/benign hypothesis competition
- Cost-aware scoring: cheap rules first, ML next, expensive reasoning (LLM causal analysis) only for borderline cases
- **Verdict**: recommended action (green, yellow, red) + explanation + override capability

**Why it's separate**: Bank data is rich, precise, and owned. It enables continuous, quantitative drift detection. Public data can't do this at scale.

---

## Cost Awareness

The system is built for regulatory compliance in a bank, where running expensive models on every customer is not practical.

**Cascade approach:**

1. **Tier 0 — Rules** (free): Velocity > threshold? Drift > threshold? Very high-risk jurisdiction? Flag it. ~95% of customers pass.
2. **Tier 1 — ML** (cheap): For borderline cases, run XGBoost risk model (trained on historical alerts + outcomes). ~5% of customers reach here.
3. **Tier 2 — LLM reasoning** (expensive): Only for high-stakes borderline cases, use Claude to debate causal vs. benign hypothesis, generate rationale for officer review. ~0.5% of customers reach here.

**Result**: 96% cheaper than running the LLM on everyone, with better decisions at each layer.

---

## Guardrails: Explainability, Human-in-the-Loop, Audit

### Explainability

Every score is broken down by component:
- **Per-layer breakdown**: how much does BOCPD contribute vs. public intel vs. velocity?
- **Per-variable SHAP values**: which KYC fields or transaction corridors most influenced the score?
- **Causal evidence cards**: what specific news articles, sanctions entries, or transaction anomalies were factored in?

### Human-in-the-Loop (HITL)

- **Verdict bar**: the system recommends an action (investigate, enhance DD, escalate) with confidence.
- **Officer override**: a compliance officer can accept, challenge, or override the verdict with a written rationale.
- **Time-bound review**: the system may suggest a re-scan in 30 days, or mark the case as "decision pending" until more data arrives.

### Audit Log

Every decision is logged immutably:
- Timestamp
- Input data version
- Model version
- Score, components, explanation
- Officer action + rationale
- Outcome (if later labeled as false positive / positive)

This supports:
- **Regulatory defense**: "Here's what we knew on March 15 and what we decided."
- **Model improvement**: feedback loop to retrain and validate future versions.
- **Liability protection**: clear record of due diligence.

---

## Success Criteria (from AMINA Challenge 4)

1. **Detect drift early**: Flag a customer before public sanctions/regulatory action.
2. **Separate causal from benign**: Don't waste officer time on legitimate growth; focus on risk.
3. **Explain decisions**: Per-layer, per-variable breakdown so an officer (and regulator) can understand why.
4. **Cost-efficient**: Cheap rules + ML tiering so the system scales to thousands of customers.
5. **Audit-ready**: Time-travel proof that the system would have caught it.

---

## How This System Works (High-Level Flow)

1. **Onboarding**: Customer's KYC profile is captured; profile distribution (P_0) is initialized.
2. **Monthly monitoring**:
   - Collect transaction data, refresh public signals
   - Run BOCPD on behavioral time series (volume, geography, counterparty risk)
   - Calculate accumulated drift (KL divergence) and velocity
   - Query contagion graph (any UBO in adverse media? ownership changed?)
3. **Scoring**:
   - Rules layer: velocity / drift high? → immediate escalation
   - ML layer: XGBoost risk model on borderline cases
   - LLM layer: causal vs. benign debate, explanation generation
4. **Verdict**:
   - Risk score (0–100) with recommended action
   - Per-component breakdown (BOCPD score, velocity score, public signal score, causal score)
   - SHAP explanation + optional officer notes
5. **Outcome**:
   - Officer reviews, decides action (investigate, enhanced DD, or accept risk)
   - Decision is logged with rationale
   - System re-scores after 30 days or upon request

---

## Next Steps for the Team

1. **Read** `DRIFT_ENGINE_README.md` for the full technical specification, math, and academic references.
2. **Run** the system locally per `QUICKSTART.md` — see it in action.
3. **Explore** the demo cases (Viktor, Maria, Pavel) to see how causal analysis separates risk from growth.
4. **Extend**: Real public-signal feeds, deeper ownership graphs, more drift scenarios.

---

## References & Regulations

- **FINMA (Swiss)**: AML enforcement, KYC drift expectations
- **EU AML Directive 5**: beneficial ownership, risk-based approach, drift detection
- **OFAC**: Sanctions list methodology and compliance requirements
- **Bayesian Online Changepoint Detection**: Adams & MacKay (2007)
- **KL Divergence & Drift Velocity**: Information theory foundations for drift measurement
- **SHAP & Counterfactual Fairness**: Explainability standards for regulatory use

For mathematical depth, see `DRIFT_ENGINE_README.md`.
