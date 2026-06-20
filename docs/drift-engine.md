# Drift Engine — Technical Specification

Bayesian KYC drift detection for FINMA-regulated banks. Diagrams, mathematics, and validation results for each layer.

For the product overview see the main [README](../README.md).

---

## The Reframe

A KYC profile is not a document — it is a snapshot of the parameters of a stochastic process, taken at onboarding. The customer is the process; the profile is a frozen estimate. **Drift is the divergence between the frozen declared model and the evolving observed trajectory.**

The question shifts from *"did something bad happen?"* to *"has the generative process behind this customer's behavior changed?"* — a well-posed statistical question with decades of theory behind it. Sanctions are the lagging consequence; drift is the leading precursor.

The bank's structural advantage: it holds both the declared model (original KYC) and the full observed trajectory (every transaction). No drifting customer can fake consistency between the two over time.

---

## 7-Layer Pipeline

```mermaid
flowchart TD
    Input["Customer Input\nKYC profile · Transactions · AML flags\nPublic signals · Ownership graph"]

    subgraph LayerB["Layer B — Internal Bank Data"]
        L1["1 · Behavioral Drift\nbocpd.py\nBayesian Online Changepoint Detection\n(Adams & MacKay 2007)"]
        L2["2 · Drift Velocity\nvelocity.py\nKL divergence time-derivative\nbits/month"]
        L6["6 · Suspicious Stability\nstability.py\nSlow-walker: anomalously smooth\nwhile environment moves"]
    end

    subgraph LayerA["Layer A — Public Intelligence"]
        L4["4 · Public Intelligence\npublic_intel.py\nNews · Sanctions · Adverse media\nOwnership changes · Funding events"]
    end

    subgraph Topo["Ownership Topology"]
        L3["3 · Ownership Contagion\ncontagion.py\nPersonalized PageRank\n(Page et al. 1999)"]
    end

    Fusion["Confirmation Lift\nTemporal co-occurrence fusion\n(Layer A × Layer B)"]

    L5["5 · Causal Drift\ncausal.py\nLikelihood ratio test\nRisk hypothesis vs benign growth\n(Neyman-Pearson)"]

    L7["7 · Cost-Aware Cascade\ncascade.py\nValue-of-Information routing\n(Howard 1966)"]

    Output["Fused Drift Score  0 – 100\n+ Recommended action\n+ Per-layer contribution\n+ Causal evidence cards\n+ Lead-time estimate"]

    Input --> L1 & L2 & L6
    Input --> L4
    Input --> L3
    L1 & L2 & L6 & L4 --> Fusion
    Fusion --> L5
    L3 --> L5
    L5 --> L7
    L7 --> Output
```

---

## Layer 1 — Behavioral Drift (BOCPD)

Bayesian Online Changepoint Detection (Adams & MacKay, 2007) maintains a posterior over the **run length** r_t — observations since the last regime change:

```
P(r_t | x_1:t)
```

with a Normal-Inverse-Gamma conjugate model giving a Student-t posterior predictive. A constant hazard H = 1/500 expresses a prior of roughly one regime change per business year.

**Detection.** In practice a changepoint manifests as a sharp **drop in the MAP run length** (posterior mass jumping to short runs), not as P(r=0) crossing a threshold — the mass spreads over r = 0..k. This distinction matters: it is why the detector catches gradual drift that threshold rules structurally miss. A customer who raised average volume from 5K to 9K over six months never crosses a 10K threshold, but the distribution shift is plainly visible to the run-length posterior.

**Surfacing.** BOCPD runs over the concatenated *daily* volume series, so its detected changepoint is a **day index** (`bocpd_changepoint_day`). The Drift Timeline is indexed by **month**, so `DriftEngine.get_customer` maps the day to its month window (`SyntheticCustomer.day_to_month`, i.e. `day // days_per_month`) and flags that month's timeline point with `bocpd_changepoint=True`. The UI renders it as a violet dashed **"Regime change"** marker, distinct from the (solid) alert and sanctions markers. A changepoint landing inside the baseline window — before the first timeline point — is intentionally not drawn.

---

## Layer 2 — Drift Velocity

Let P_0 be the onboarding profile distribution and P_t the current estimate:

```
Drift(t) = KL( P_0 || P_t )      accumulated divergence, in bits
DV(t)    = d/dt Drift(t)         drift velocity, bits per month
```

Each monitored metric is modeled as a Gaussian per window; the closed-form Gaussian KL is summed across metrics. A key robustness choice: the KL is evaluated with the **baseline variance on both sides** (mean-shift KL), because window-level variance estimates over ~21 daily observations are noisy and would otherwise drown the mean-shift signal. The drift trajectory is smoothed before differentiation, since differentiation amplifies noise.

Velocity is a **leading** indicator; accumulated drift is **lagging**. A customer can show meaningful velocity months before absolute divergence crosses any sane alert threshold.

---

## Layer 3 — Ownership Contagion

Ownership relations form a directed graph. When entities S become flagged, propagated risk for customer i is personalized PageRank with the teleport vector concentrated on S:

```
risk_prop(i) = PPR(i | personalization = S, alpha = 0.85)
```

computed over an undirected, stake-weighted view so risk flows both ways (an owner contaminates what it owns, and owning a flagged entity contaminates the owner). Customers two ownership hops from a newly sanctioned entity receive elevated risk **before** any list contains their name.

---

## Layer 4 — Public Intelligence + Confirmation Lift

Five public-signal categories (news, sanctions, adverse media, ownership changes, funding events) are classified by severity and aggregated into a public-risk score, severity- and recency-weighted.

**Confirmation Lift** is the differentiator. Two weak, independent signals that co-occur in time provide more evidence together than the product of their parts:

```
Lift = P(risk | public AND internal) / [ P(risk | public) · P(risk | internal) ]
```

A temporal-coincidence factor amplifies the joint when the peak public signal and peak internal drift fall within a few months — because the external story and the internal behavior are plausibly the same event seen from two sides. The lift is gated: it is only meaningful when **both** signals clear a floor; two near-zero risks coinciding is the absence of evidence, not its presence.

The current hand-tuned fusion parameters are centralized in
`app/core/config.py`:

| Constant | Value | Role |
|---|---:|---|
| `DRIFT_INTERNAL_VELOCITY_WEIGHT` | 0.60 | Leading drift contribution |
| `DRIFT_INTERNAL_ACCUMULATED_WEIGHT` | 0.25 | Accumulated divergence contribution |
| `DRIFT_INTERNAL_CONTAGION_WEIGHT` | 0.40 | Ownership-propagated risk contribution |
| `DRIFT_PUBLIC_RISK_WEIGHT` | 0.85 | Public-risk scaling before fusion |
| `DRIFT_CONFIRMATION_LIFT_RANGE` | 3.0 | Lift excess mapped to the amplification range |
| `DRIFT_CONFIRMATION_MAX_AMPLIFICATION` | 0.35 | Maximum confirmation-lift score increase |

---

## Layer 5 — Causal Drift

Pure drift detection fires on any structural change. But selling a business and becoming a laundering conduit move the same metrics. The insight: benign and risky change have different **correlation signatures**, not different magnitudes.

- **Benign growth:** volume up, margin preserved, counterparties stay clean.
- **Risk transit:** volume up, margin collapses (money flows straight through), counterparties concentrate on risky, corridors shift high.

Two generative hypotheses compete via a likelihood ratio:

```
causal_LLR = log P(signature | RISK) / P(signature | BENIGN)
```

Margin is the discriminator (kept orthogonal to velocity). A forensic asymmetry applies: a metric sitting in its neutral zone does not argue *against* risk just because the risk profile expected movement there — absence of evidence is not evidence of absence. The verdict modulates the final score: clearly-benign drift is demoted out of the alert queue; risk-shaped drift is confirmed.

---

## Layer 6 — Suspicious Stability

Every other layer hunts for movement. A launderer who knows drift is monitored does the opposite: stays smooth. But real customers jitter; an unnaturally smooth trajectory **while the environment moves** is itself anomalous.

```
suspicion = stability_anomaly × environmental_movement
```

A product, not a sum — both factors must be present. Stability is measured by coefficient of variation versus the cohort median (scale-free). A flagged slow-walker has its score elevated so it cannot hide below the radar.

---

## Layer 6b — Dormancy Break (Suspicious Activation)

The mirror image of suspicious stability. Every drift/velocity layer assumes a customer who is *doing something* the whole time; a dormant shell is the opposite — near-zero activity for a long stretch, then a sudden burst. Because the baseline is so quiet, even a large absolute jump reads as "starting from nothing" rather than a regime change, so the magnitude layers under-react. `drift/dormancy.py` detects it explicitly (pure numpy, no external API):

```
dormancy_break = dormancy_depth × activation_strength
```

- **dormancy_depth** — how quiet the baseline window was, relative to the customer's own overall level.
- **activation_strength** — how large the later burst is versus the dormant baseline (a small floor on the baseline keeps a near-zero baseline from exploding the ratio).

A product, not a sum: a company that stays dormant scores ~0, and one that was always active and merely grew scores ~0 (ordinary drift, handled elsewhere). Only the dormant → active transition scores high. A confirmed break floors the drift score upward — deliberately overriding the causal demotion — so a reactivated sleeper surfaces for review. This realises the AMINA brief's *"previously dormant company begins high transaction volume → Dormancy Break – Suspicious Activation"* use case.

---

## Cost-Aware Cascade (Tier Router)

Escalation is framed as information economics:

```
escalate from tier k to k+1  iff  E[information gain] · case_value > cost(k+1)
```

```mermaid
flowchart TD
    Start([Customer])

    T0{"Tier 0\nRule Engine\nFree — ~95% of customers"}
    T1{"Tier 1\nStatistical · LLR layer scoring\n~$0.0002 per customer"}
    T2{"Tier 2\nLLM · Claude adjudication\n~$0.05 per customer"}

    Clear["Clear\nLow-risk — no action"]
    Review["Review\nScheduled re-KYC"]
    EDD["Escalate\nEnhanced Due Diligence\n+ AI explanation + RFI"]

    Start --> T0
    T0 -->|"Deterministic rules pass\n~95% volume"| Clear
    T0 -->|Borderline| T1
    T1 -->|Effective risk < 55| Review
    T1 -->|Effective risk ≥ 55\nand case value clears floor| T2
    T2 -->|Verdict: risk| EDD
    T2 -->|Verdict: benign or ambiguous| Review

    style Clear fill:#16a34a,color:#fff
    style Review fill:#d97706,color:#fff
    style EDD fill:#dc2626,color:#fff
```

T2 adjudication is an actual execution path in `drift/service.py`: every customer routed to `T2_LLM` is sent through the shared `AnthropicClient`. The adjudicator compares risk-shaped drift, benign business change, and ambiguous/insufficient-evidence hypotheses, and returns parsed JSON with verdict, confidence, rationale, key evidence, and a human compliance action. In development, the same client runs in mock mode when no Anthropic API key is configured.

The scan response keeps `llm_on_everything_cost` as a counterfactual baseline and separately reports `actual_t2_llm_calls`, `real_t2_llm_calls`, `mock_t2_llm_calls`, and `llm_adjudications[]`.

**Result:** 96% cost reduction vs LLM-on-everything at equal high-risk recall (H4, validated on the synthetic book).

---

## Two-Layer Fusion

```mermaid
flowchart LR
    subgraph A["Layer A — Public Intelligence"]
        News[News & adverse media]
        Sanctions[Sanctions hits]
        Ownership[Ownership changes]
        Funding[Funding events]
    end

    subgraph B["Layer B — Internal Bank Data"]
        BOCPD2[Behavioral drift\nBOCPD score]
        Vel2[Drift velocity\nbits/month]
        TxVol[Transaction volume\npattern shift]
        AML[AML flag history]
    end

    CL["Confirmation Lift\nMultiplied when signals\nco-occur within 3 months"]

    FusedScore["Fused Drift Score\nWeighted combination\nof all 7 layers"]

    A --> CL
    B --> CL
    CL --> FusedScore
```

---

## Time-Travel Audit

A regulatory-grade property: replay any customer **as-of** month T using only data available then. BOCPD is online by construction (it processes the stream left-to-right and cannot use future data), which makes truncation honest rather than a hack. All future sources are cut: metrics to [:T], public signals by date, contagion only after the listing month. This proves the system would have flagged a customer early, with no look-ahead bias.

```mermaid
sequenceDiagram
    participant O as Officer
    participant TT as timetravel.py
    participant DE as Drift Engine

    O->>DE: replay(customer_id)
    DE->>TT: replay_trajectory(customer snapshot)
    TT->>TT: Truncate metrics and public signals at month T
    TT->>TT: Activate contagion only after sanctions listing

    note over TT: Strictly truncates future data —<br/>no look-ahead bias

    TT->>TT: Apply shared internal/public weights<br/>and replay-specific causal factor
    note over TT: Replay does not apply confirmation lift<br/>or stability/dormancy anomaly floors
    TT-->>DE: Historical score points + lead time
    DE-->>O: ReplayResult<br/>(score, lead_time, what_was_known)

    note over O: Proves the system would<br/>have flagged this customer<br/>without hindsight
```

---

## Runtime State and Worker Model

The MVP keeps its synthetic customer book and injected scenarios in the
process-local `DriftEngine` singleton. Run the API with exactly one worker so
all requests see the same demo state. The current Docker and Compose commands
already use one Uvicorn worker.

Before scaling to multiple workers, move mutable engine state to a shared
database or cache. `get_drift_engine()` emits a warning when it creates the
singleton to make this deployment constraint visible in application logs.

---

## Validation Results

| Hypothesis | Scenario | Result |
|---|---|---|
| H1 — Lead time | Changepoint on step data, none on stationary | 2–7 months lead (median 5.5), 0 false positives |
| H2 — Velocity leads level | Velocity vs absolute-threshold alerting | Velocity fires earlier at equal FP rate |
| H3 — Contagion propagates | Personalized PageRank from sanctioned seed | 2-hop customers elevated; distant unaffected |
| H4 — Cascade cost reduction | Cascade vs LLM-on-everything, 1,000 customers | 96% cost reduction at equal recall |
| Causal classification | 11 scenarios with ground truth | 11/11 correct, 8/8 seed robustness |
| Stability classification | 13 scenarios with ground truth | 13/13 correct, 8/8 seed robustness |
| Time-Travel honesty | 3 leak-detection tests | No future data reaches the score |

---

## References

- Adams, R. P. & MacKay, D. J. C. (2007). *Bayesian Online Changepoint Detection.* arXiv:0710.3742.
- Page, E. S. (1954). *Continuous Inspection Schemes.* Biometrika 41.
- Kullback, S. & Leibler, R. A. (1951). *On Information and Sufficiency.* Annals of Mathematical Statistics 22.
- Page, L., Brin, S., Motwani, R. & Winograd, T. (1999). *The PageRank Citation Ranking.* Stanford InfoLab.
- Howard, R. A. (1966). *Information Value Theory.* IEEE Trans. Systems Science and Cybernetics 2.
- Shafer, G. & Vovk, V. (2008). *A Tutorial on Conformal Prediction.* JMLR 9.
- FATF (2023). *Guidance on Beneficial Ownership of Legal Persons.*
- FINMA Circular 2024/3. *Operational risks and resilience — banks.*
