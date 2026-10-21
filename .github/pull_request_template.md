<!-- .github/pull_request_template.md -->
## 📝 What and Why
<!-- Briefly describe the feature, architectural change, or bug fix. Link the related ticket/issue. -->
- **Closes:** #

## 🧪 How It Was Tested
<!-- Explain how you validated this change. What unit/integration tests were added? -->
- [ ] Pipeline unit tests executed locally (`pytest pipeline/tests/`)
- [ ] Backend syntax & startup verified
- [ ] Manual test verification performed (details/steps below):

```text
<!-- Paste sample CLI output, test report, or screenshot here -->
```

## ⚠️ Risks, Rollout & Rollback
<!-- Does this require environment variable additions? How do we rollback if errors spike? -->
- **Breaking Changes:** None / Yes (explain)
- **Rollback Strategy:** Revert commit

## ✅ Quality Checklist
- [ ] Code adheres to [code_quality_guide/01_clean_code_fundamentals.md](file:///c:/Users/likhi/OneDrive/Pictures/Desktop/CollabProj/PaperMind/code_quality_guide/01_clean_code_fundamentals.md)
- [ ] All new outbound network calls have explicit timeouts
- [ ] If fixing a bug, a regression test is included that fails without this fix
- [ ] No secrets, tokens, or personal data committed in code or logs
- [ ] PR size is under ~300 lines changed (or split into reviewable increments)

## 🤖 For AI & LLM Changes (Skip if not applicable)
- [ ] Prompt stored in versioned file (`pipeline/prompts/`) and version identifier bumped
- [ ] Rationale recorded in `pipeline/prompts/CHANGELOG.md`
- [ ] Model outputs validated through strict schema with bounded repair loop
- [ ] Smoke evaluation run against golden dataset; score delta attached below:

```text
Baseline Eval Accuracy: ___%
New Eval Accuracy:      ___% (Delta: +___%)
```
