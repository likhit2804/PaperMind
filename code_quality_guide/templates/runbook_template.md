# Runbook: [Alert Name, e.g., High LLM Rate-Limit Errors (429)]

> **Audience:** On-call engineer responding to a production alert.  
> **Writing Rule:** Write clearly for an exhausted engineer at 3:00 AM who has never touched this service.

---

## 1. What the Alert Means
- **Trigger Condition:** [e.g., HTTP 429 response rate from Gemini/OpenAI exceeds 5% of all calls over a 5-minute window.]
- **Monitoring Link:** [Link to Grafana / Datadog / CloudWatch Dashboard]

---

## 2. Business & User Impact
- **Severity:** P1 (Critical) | P2 (Degraded) | P3 (Low)
- **What Users Experience:** [e.g., Users attempting to extract research papers experience timeouts or failure error cards. Read-only search remains operational.]

---

## 3. Triage & Diagnostic Steps
Follow these steps in order to diagnose the root cause:

1. **Check Provider Status:**  
   Visit the upstream API status page: `https://status.cloud.google.com/` (or equivalent).
2. **Inspect Error Spikes:**  
   Run this log query:
   ```bash
   # Filter logs for rate limits in the last 15 minutes
   grep "rate_limit_exceeded" /var/log/app/app.log | tail -n 50
   ```
3. **Check Tenant / User Traffic:**  
   Verify whether a single tenant or automated script is spamming requests (noisy neighbor).

---

## 4. Immediate Mitigation Options
Choose the quickest mitigation that restores customer service:

- [ ] **Option A (Toggle Fallback Model):**  
  Set the operational flag to route traffic to the secondary provider or fast model:
  ```bash
  # Command or flag update:
  curl -X POST https://api.internal/flags/llm.fallback_enabled -d '{"enabled": true}'
  ```
- [ ] **Option B (Throttle Ingestion):**  
  Temporarily reduce worker queue concurrency to 5 workers to stay under API quotas.
- [ ] **Option C (Rate-Limit Abuse):**  
  Block offending IP or tenant ID at the API gateway layer.

---

## 5. Escalation Path
If the incident is not mitigated within **20 minutes**:
1. Page Secondary On-Call: [Name / Phone / PagerDuty Rota Link]
2. Notify Incident Lead on Slack/Teams channel `#incident-room`.

---

## 6. Post-Incident Follow-Up
- [ ] File a blameless postmortem within 48 hours.
- [ ] Create ticket with `label:tech-debt` to adjust quota headroom or optimize prompt token usage.
