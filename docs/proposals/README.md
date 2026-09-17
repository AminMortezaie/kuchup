# Proposals

Open design docs — not current runtime behavior. Do not implement from these without an explicit decision.

Living architecture: [architecture.md](../reference/architecture.md) · backlog: [backlog.md](../backlog.md)

| Proposal | Status on `main` |
|----------|------------------|
| [board-read-model-proposal.md](board-read-model-proposal.md) | Not approved. Board still flattens catalog per request. |
| [multi-user-scaling-proposal.md](multi-user-scaling-proposal.md) | Phase 0 (DB pool + gunicorn workers=2) shipped. SQS for fetch/PDF and board projection not on `main`. |
| [kafka-fetch-pipeline-proposal.md](kafka-fetch-pipeline-proposal.md) | Not approved. Fetch stays in-process on the Playwright worker. SQS in this repo is the **opportunity refresh** queue, not fetch/PDF. |
| [full-spa-ui-modernization-proposal.md](full-spa-ui-modernization-proposal.md) | Not approved. Panel is still Flask + static JS + a React board widget. |
| [apple-liquid-glass-warm-horizon-proposal.md](apple-liquid-glass-warm-horizon-proposal.md) | Not approved. Marketing UI discipline only; Warm Horizon tokens stay. No production CSS. |
