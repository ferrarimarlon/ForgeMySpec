# Acceptance Checklist — Cron Parser

- [ ] next computes correct times for * wildcard
- [ ] next handles ranges (A-B)
- [ ] next handles lists (A,B,C)
- [ ] next handles steps (*/N, A-B/N)
- [ ] validate reports invalid field values
- [ ] dow mapping: 0=Sun, 6=Sat
- [ ] invalid dates (Feb 30) are skipped
