<!-- .github/pull_request_template.md -->
## 📝 What and Why
<!-- Briefly describe the feature, architectural change, or bug fix. Link the related ticket/issue. -->
- **Closes:** #

## 🧪 How It Was Tested
<!-- Explain how you validated this change. What unit/integration tests were added? -->
- [ ] Unit tests added / updated
- [ ] Integration tests executed locally
- [ ] Manual test verification performed (details/steps below):

```text
<!-- Paste sample CLI output, test report, or screenshot here -->
```

## ⚠️ Risks, Rollout & Rollback
<!-- Does this require database migrations? Environment variable additions? How do we rollback if errors spike? -->
- **Breaking Changes:** None / Yes (explain)
- **Database Migrations:** None / Backward compatible (expand-and-contract)
- **Rollback Strategy:** Revert commit / feature flag toggle (`flag_name`)

## ✅ Quality Checklist
- [ ] Code follows [01. Clean Code](file:///c:/Users/likhi/OneDrive/Pictures/Desktop/CollabProj/PaperMind/code_quality_guide/01_clean_code_fundamentals.md) (guard clauses, descriptive names, no bare catches)
- [ ] All new outbound network calls have explicit timeouts ([02. Backend Reliability](file:///c:/Users/likhi/OneDrive/Pictures/Desktop/CollabProj/PaperMind/code_quality_guide/02_backend_reliability_patterns.md))
- [ ] If fixing a bug, a regression test is included that fails without this fix
- [ ] No secrets, tokens, or personal data committed in code or logs
- [ ] PR size is under ~300 lines changed (or split into reviewable increments)

## 🤖 For AI & LLM Changes (Skip if not applicable)
- [ ] Prompt stored in versioned file (`prompts/`) and version identifier bumped
- [ ] Rationale recorded in `prompts/CHANGELOG.md`
- [ ] Model outputs validated through strict schema with bounded repair loop
- [ ] Smoke evaluation run against golden dataset; score delta attached below:

```text
Baseline Eval Accuracy: ___%
New Eval Accuracy:      ___% (Delta: +___%)
```
