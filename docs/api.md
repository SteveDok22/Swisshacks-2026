# API Reference

Base URL: `http://localhost:8000/api/v1`  
Interactive docs: `http://localhost:8000/docs`  
Total endpoints: 27

## Endpoint Map

```mermaid
flowchart TB
    subgraph Drift["Drift Engine  — /drift"]
        D1["GET /customers\nScan full customer book\nReturns risk-ranked list"]
        D2["GET /customers/{customer_id}\nFull per-customer analysis\nAll 7 layers + causal evidence"]
        D3["GET /customers/{customer_id}/timeline\nDrift velocity over time"]
        D4["POST /scan\nRun cost cascade scan\nReturns CascadeCostReport"]
        D5["GET /contagion\nOwnership graph + PageRank scores"]
        D6["GET /replay/{customer_id}\nTime-travel as-of replay"]
        D7["POST /inject\nInject public signal\nBody: scenario, name"]
        D8["POST /rfi/{customer_id}\nGenerate RFI\nValue-of-Information ordering"]
    end

    subgraph Cases["Cases  — /cases"]
        C1["GET /\nFilterable case queue\n?case_type=&status=&jurisdiction=&page="]
        C2["GET /{case_id}\nCase detail + full context"]
        C3["POST /\nCreate case\nBody: client_id, case_type, jurisdiction, context"]
        C4["PATCH /{case_id}/status\nUpdate workflow status"]
        C5["GET /{case_id}/history\nFull audit trail for this case"]
    end

    subgraph Analysis["Analysis"]
        A1["POST /scoring/{case_id}\nScore a case — returns risk_score + risk_level"]
        A2["GET /scoring/models\nList available ML models"]
        A3["POST /explanations/{case_id}\nGenerate full explanation (JSON)"]
        A4["GET /explanations/{case_id}/stream\nSSE streaming explanation — chunked tokens"]
        A5["GET /explanations/{case_id}/anonymization\nPreview what data is sent to LLM vs stays local"]
        A6["POST /counterfactuals/{case_id}\nDiCE counterfactual scenarios"]
    end

    subgraph Governance["Governance"]
        G1["POST /decisions\nLog officer decision\nBody: case_id, action, rationale, overrode_ai"]
        G2["GET /decisions/case/{case_id}\nList all decisions for a case"]
        G3["GET /audit\nAudit log — paginated"]
        G4["GET /jurisdictions\nList all loaded rule packs"]
        G5["GET /jurisdictions/{code}\nGet rules for CH / EU / HK / AE"]
        G6["POST /jurisdictions/compare/{case_id}\nScore case under all jurisdictions simultaneously"]
    end

    subgraph Clients["Clients  — /clients"]
        CL1["GET /\nList all clients"]
        CL2["GET /{client_id}\nClient detail + KYC profile"]
    end
```

---

## Response Shape Reference

```mermaid
flowchart LR
    subgraph DriftSchemas["Drift Schemas"]
        DS1["DriftCustomerSummary\ncustomer_id · name · score · velocity\naction · risk_level"]
        DS2["DriftCustomerDetail\n+ LayerContribution[]\n+ CausalVerdictOut\n+ StabilityOut\n+ contagion_score"]
        DS3["ReplayResult\nas_of_score · current_score\nlead_time_months"]
        DS4["CascadeCostReport\ntier_counts · cost_saved · total_customers"]
    end

    subgraph CaseSchemas["Case Schemas"]
        CS1["CaseRead\nid · client_id · case_type · jurisdiction\nstatus · summary · context_data\nrisk_score · risk_level · confidence"]
        CS2["ScoringResponse\nrisk_score · risk_level · confidence\nshap_values · rule_overrides"]
    end

    subgraph ExplainSchemas["Explanation Schemas"]
        ES1["CaseExplanation\nnarrative · key_factors · recommendation"]
        ES2["SSE stream\nevent: message — data: token chunk\nevent: done — data: empty"]
        ES3["AnonymizationPreview\noriginal_fields · anonymized_fields\nfields_sent_to_llm"]
    end
```

---

## Authentication & Privacy

```mermaid
flowchart LR
    Request["Incoming request\n/explanations/{case_id}/stream"]
    Anon["anonymizer.py\nPseudonymize client data:\nCLIENT_AAF7 · bucketed amounts\nno PII in LLM context"]
    Claude["Claude AI\nReceives only anonymized context"]
    Response["SSE token stream\nNo PII in explanation"]

    Request --> Anon --> Claude --> Response
```

No auth tokens required in dev mode. All LLM calls pass through `anonymizer.py` — raw names and exact amounts never leave the backend.
