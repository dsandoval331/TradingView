# PMPD V5 9J — VWAP Event Path V2

This patch adds event-contact-anchored VWAP path fields. V1 was valid for
decision-time VWAP snapshots, but its touch/cross counters began at RTH open.
V2 corrects that research limitation by starting the path at each event's DP1
FIRST_CONTACT timestamp.

Extract over:
C:\Users\DirtySouth\TradingResearch

Run:
python -c "from tr_platform.pmpd_v5.vwap_event_path_v2 import _event_path; print('9J VWAP V2 import self-check: PASS')"
python -m tr_platform.pmpd_v5.vwap_event_path_v2_cli

Expected output:
C:\Users\DirtySouth\TradingResearch\pmpd_v5_9j_vwap_event_path_v2.zip

Upload that ZIP. No other files are needed.
