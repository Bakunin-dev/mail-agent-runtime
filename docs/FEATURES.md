# Capability and evidence map

REAL = selected code copied from the original Mail Agent. ADAPTED = original
code with explicitly listed changes. SIMULATED = new executable substitute.
DOCUMENTED = no implementation in this edition. NEW DEMO = proposed extension,
not a claim about the original working product.

| Capability | Status in public edition | Evidence / omission |
|---|---|---|
| Provider-independent mail DTOs | REAL | `mail_connector/models/*`; no provider transport |
| Search/read request validation | ADAPTED | `server/mail_query/models.py`; internal storage DTOs removed |
| Metadata-first search | SIMULATED | `QueryService.search`; zero body fetch until read |
| People / organizations / From-To-Cc / dates | SIMULATED | exact equality only; production matcher absent |
| Saved sender groups | SIMULATED | one in-memory `banks` group; no original registry |
| Ranking | SIMULATED | newest-first only; score/identity diversification omitted |
| Immutable search snapshot / pagination | SIMULATED | in-memory list; injected arrivals do not change existing set |
| Opaque refs / ownership / expiration | SIMULATED | named demo sessions and ten-minute memory lifetime |
| Mailbox generation changes | SIMULATED | explicit fault invalidates old ResultSets |
| Preview / full prepared text | REAL projection | `projection.py`; service supplies synthetic FetchedMail |
| Bounded recipients / text / truncation | REAL projection | counts and warnings preserved |
| MIME pre-fetch size gate | SIMULATED | illustrative local budgets; no MIME download |
| Attachment-only / empty body / metadata | REAL projection | empty-body fixture with attachment names; no attachment bytes |
| MIME parsing / nested RFC822 / HTML / encoding | DOCUMENTED | original parser and transport decoding excluded |
| Match evidence | ADAPTED contracts + SIMULATED values | records exact fixture match, no production inference |
| Attention annotations | ADAPTED DTOs + SIMULATED label | fixture-only; no filtering, original rules withheld |
| Partial candidates / size / provider / context | REAL DTOs + SIMULATED causes | fault controls and dedicated fixtures |
| Compact model text / handles m1..mN | REAL | `portal_projection.py` and original regression tests |
| Progress HTML / escaped data | REAL | `mail_progress.py`; static fixture metrics |
| OpenWebUI tool calls and progress events | SIMULATED bridge | loopback-only Tool; no original credentials or model prompt |
| First-use connection / reconnect / cancel / rejection | SIMULATED | outcome selector; no password field or IMAP validation |
| Multi-user account and mailbox binding | DOCUMENTED + session illustration | alice/bob are not authentication; production provisioning excluded |
| Encrypted credentials / ResultSets | DOCUMENTED | encryption and SQLite are not shipped; memory is plaintext |
| Busy admission / request correlation | SIMULATED | single lock + server-generated request ID |
| Durable jobs / leases / retries | DOCUMENTED | action state demo is not durable job runtime |
| Backup / restore / maintenance / OS deployment | DOCUMENTED | operational scripts excluded; demo only has launcher and packaging |
| Incoming email event | NEW DEMO | fixture injected via explicit event endpoint |
| Proactive proposal without a new chat message | NEW DEMO | deterministic event policy; no LLM or background scheduler |
| Draft / send / reply / forward | NEW DEMO | in-memory drafts/outbox after reviewer decision |
| Mark read / move | NEW DEMO | fixture flags and two non-trash folders |
| Mail deletion | ABSENT BY DESIGN | no enum value, connector method or API route |
| Bitrix24 contact lookup / task creation | NEW DEMO | synthetic CrmPort, not a real Bitrix client |
| Human review / rejection / expiry | NEW DEMO | proposal then separate boolean decision |
| Duplicate event / duplicate approval | NEW DEMO | process-local idempotency; not exactly-once delivery |
| CRM failure / explicit retry | NEW DEMO | failure injected before write; no network retries |

All rows describe this public edition. Security and deployment claims about the
closed product require separate evidence; the table does not assert production
readiness, load capacity or formal security certification.
