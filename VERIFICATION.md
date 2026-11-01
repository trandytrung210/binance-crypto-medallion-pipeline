# Recorded verification

Executed on 2026-11-01. See evidence/environment.json for actual interpreter and package versions. The recorded execution used Python 3.12.14; the Dockerfile targets Python 3.11 and was not built in this environment.

- Downloaded 34 real successful API responses, totaling 5,033,994 raw response bytes.
- Published 30,240 typed Silver facts and 21 daily Gold groups.
- 6 unit/dashboard tests passed, including Streamlit AppTest opening the app and changing the entity selector.
- Offline integration replay preserved natural-key row counts and Gold values (floating values compared after rounding to nine decimal places).
- Bronze response checksums remained unchanged across replay.
- An injected failure before publication left data/current.json byte-for-byte unchanged.
- Source-unit, completeness and range gates passed for the shipped data.

The crypto builder additionally reconciles exact decimal base/quote volumes and trade counts between Silver and both aggregate levels. The weather integration check independently validates the 24-hour rainfall sum across the January/February boundary for three cities. Unit tests use small controlled fixtures; production input and all supplied results come from the real API download.

Streamlit was exercised using its application test harness, not a browser screenshot. evidence/overview.png is a real Matplotlib rendering of the measured Gold output. Docker image builds and another user's machine have not been verified.
