# Source provenance

The original Mail Agent implementation was inspected locally. Only the following
files were selected for direct publication. Relative paths below refer to both
the source tree and this public tree; no local filesystem paths are distributed.

## Unmodified original source

- `mail_connector/models/folder.py`
- `mail_connector/models/metadata.py`
- `mail_connector/models/result.py`
- `mail_connector/models/query.py`
- `server/mail_query/projection.py`
- `server/mail_query/portal_projection.py`
- `server/integrations/mail_progress.py`
- `tests/server/test_projection.py`

SHA-256 evidence is in `provenance.json`; `tools/release.py --check` verifies it.
The original projection tests run alongside the new API scenario tests.

## Adapted original contracts

`server/mail_query/models.py`: retained public query/search/read DTOs and their
validation; removed the two internal StoredQueryItem classes and their metadata
import. Public contracts retain original field names and validation limits.

`server/mail_query/attention.py`: selected assessment DTOs from the original file,
with formatting/import cleanup. Registry, configuration, rules, matching and
scoring implementation are excluded.

## Newly written demonstration code

The synthetic mail and Bitrix adapters, QueryService, in-memory snapshots, API
wiring, approval service, proactive event policy, CLI, local portal Tool, release
checks and API tests were written for this edition. They demonstrate the original
layering and new extension seams; they are not labelled as production algorithms.

In particular, the original `server/api/app.py`, `matching.py`, `ranking.py`,
mail-query service, user repository, IMAP transport, MIME parser, executor,
worker, live diagnostics, deployment bundle and model prompt were not copied.

## What the code demonstrates

Follow a request through `server/app.py` → `server/mail_query/service.py` →
`mail_connector/synthetic.py` → the original projection. Follow a delivery event
through `server/proactive.py` → `server/actions.py` → the two synthetic connectors.
This exposes application boundaries and failure behavior while keeping the
commercial implementations outside the published tree.
