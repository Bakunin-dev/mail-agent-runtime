# Scope of this public edition

Read README.md, docs/ARCHITECTURE.md and docs/FEATURES.md before editing.
This repository is the synthetic showcase, not the private production Mail Agent.
Never add credentials, live mail, IMAP/SMTP transports, Bitrix tokens or a live mode.
Keep original/adapted/demo provenance explicit. No mail deletion capability.
Mail/CRM effects require an explicit reviewer decision and remain in memory.
Run `python -m pytest` and `python tools/release.py --check` after relevant changes.
Keep public-files.json current; release builds are strictly allowlisted.
