---
marp: true
theme: default
paginate: true
backgroundColor: "#fafafa"
color: "#0a0a0b"
style: |
  section {
    font-family: "Geist", "Inter", system-ui, sans-serif;
    padding: 60px;
  }
  h1 {
    font-size: 56px;
    font-weight: 600;
    letter-spacing: -0.02em;
    margin-bottom: 24px;
  }
  h2 {
    font-size: 36px;
    font-weight: 600;
    color: #1e3a5f;
    margin-bottom: 24px;
  }
  h3 {
    font-size: 22px;
    font-weight: 500;
    color: #3f3f46;
  }
  p, li {
    font-size: 22px;
    line-height: 1.5;
    color: #3f3f46;
  }
  strong {
    color: #0a0a0b;
    font-weight: 600;
  }
  code {
    font-family: "IBM Plex Mono", ui-monospace, monospace;
    background: #f4f4f5;
    padding: 2px 6px;
    border-radius: 4px;
    font-size: 0.9em;
  }
  .accent { color: #1e3a5f; }
  .risk-critical { color: #b91c1c; font-weight: 600; }
  .risk-low { color: #15803d; font-weight: 600; }
  .small { font-size: 18px; color: #71717a; }
  table {
    font-size: 18px;
    border-collapse: collapse;
    width: 100%;
  }
  th, td {
    text-align: left;
    padding: 8px 12px;
    border-bottom: 1px solid #e4e4e7;
  }
  th { font-weight: 600; color: #0a0a0b; }
  section.title h1 { font-size: 76px; margin-top: 80px; }
  section.title p { font-size: 26px; color: #71717a; }
---

<!-- _class: title -->

# Sentinel

## Risk Intelligence for FINMA-regulated banks

<br>

Explainable AI for cross-jurisdictional compliance review.

<br>

<span class="small">SwissHacks 2026 · Team Sentinel</span>

---

## The problem

Compliance officers at AMINA, Julius Baer, and similar banks review **hundreds of flagged cases per day** — voice transfers, suspicious trades, on-chain transactions.

Each case needs:

- A **risk score** they can defend in writing
- An explanation that survives a **regulator audit**
- Reasoning that works across **4 jurisdictions** (FINMA, MiCA, SFC, FSRA)
- A **decision trail** that holds up in court

Current tools give them a black-box score. Officers either rubber-stamp or override blindly. **Liability falls on them.**

---

## What we built

A single dashboard where the compliance officer sees:

- **The score** — XGBoost, 0-100
- **Why** — SHAP feature contributions, ranked
- **What would change it** — DiCE counterfactual scenarios
- **Under whose rules** — live toggle between FINMA / MiCA / SFC / FSRA
- **What goes to AI** — privacy split-view (FINMA Circular 2024/3)
- **Their decision** — immutably logged with rationale if overriding AI

End-to-end. Streaming. Auditable.

---

## Live demo: Marc Weber case

<br>

<span class="risk-critical">CRITICAL · 100/100</span>

> **Voice call** requesting CHF 8.7M to unknown wallet
> Sunday 3:14am · Destination: RU
> Transcript: *"urgent, my partner is waiting, don't tell anyone..."*

<br>

In the next 90 seconds:

1. AI assessment streams in word-by-word
2. Top 5 risk factors light up
3. Counterfactual: *"if destination weren't Russia..."*
4. Toggle to **FSRA** — score adjusted
5. Decision: **BLOCK** — logged with rationale

→ Switching to demo

---

## Four things we did differently

| | Most teams | Sentinel |
|---|---|---|
| **Explainability** | SHAP only | SHAP **+ DiCE counterfactuals** |
| **LLM data** | Raw client info | **Anonymized pseudonyms** + bucketed amounts |
| **Jurisdictions** | Hardcoded | **YAML rule packs**, live toggle |
| **UX** | Request → wait → response | **Server-Sent Events** streaming |

These aren't features bolted on. They're architectural decisions because AMINA actually operates under four regulators.

---

## Architecture

```
Frontend (Next.js 15)                    Backend (FastAPI)
─────────────────────                    ─────────────────
Case Queue              ──REST──▶        Risk Engine
                                              │
Detail Panel            ◀──SSE──          XGBoost + SHAP
  ├ Streaming AI                              │
  ├ SHAP viewer                          DiCE Counterfactuals
  ├ Counterfactuals                           │
  ├ Privacy split                        Jurisdiction Engine
  ├ Jurisdiction toggle                     (4 YAML packs)
  └ Decision bar                              │
                                          Anonymizer
                                              │
                                       Claude API · SSE stream
                                              │
                                       Audit Log (immutable)
```

**~30 API endpoints** · **4 jurisdiction rule packs** · **persistent DB** · **mock-mode fallback**

---

## Privacy by design — what FINMA cares about

**Before any AI call**, the anonymizer transforms case data:

<br>

| What stays local | What goes to AI |
|---|---|
| `client_name: "Marc Weber"` | `client_pseudonym: "CLIENT_AAF7"` |
| `amount_chf: 8,700,000` | `amount_band: "CHF 5M-10M"` |
| `destination_wallet: 0x3a1b...` | `destination_wallet: "0xUN****9012"` |
| `voice_sample_id: vs_001_...` | <span style="color:#a1a1aa">redacted</span> |
| `transcript_excerpt: ...` | <span style="color:#a1a1aa">redacted</span> |

The model reasons about **patterns**, not personal data.

Compliance officer audits this **before** signing off.

---

## Cross-jurisdictional reasoning

Same case. Different rules.

<br>

| Jurisdiction | Adjusted score | Recommended action |
|---|---|---|
| 🇨🇭 **CH** · FINMA | 100 | <span class="risk-critical">BLOCK</span> |
| 🇪🇺 **EU** · MiCA | 100 | <span class="risk-critical">BLOCK</span> |
| 🇭🇰 **HK** · SFC | 92 | ESCALATE |
| 🇦🇪 **AE** · FSRA | 100 | <span class="risk-critical">BLOCK</span> |

<br>

Each rule pack is **YAML**. Compliance team edits without writing code.

This is the AMINA cross-border challenge — directly addressed.

---

## What's next

**On the hackathon weekend** — features the team will add:

- **Voice biometric layer** for AMINA challenge (deepfake detection)
- **Julius Baer skin** — investment recommendation walkthrough
- **Ripple skin** — XRPL transaction with RLUSD escrow flow
- **Real-time alerts** — WebSocket notifications

**Already built and waiting** — backend supports all three case types via the same engine. Adding skins is hours, not days.

---

<!-- _class: title -->

# Thank you

<br>

<span class="small">Repo: github.com/SteveDok22/swisshacks-2026</span>
<span class="small">Live demo: localhost:3000</span>

<br>

Questions?
