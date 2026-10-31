P1 start persists JSON (R3,R7) | P2 refuse start while active (R8) | P3 stop sets end (R4) | P4 stop w/o active graceful (R12)
P5 log shows HH:MM:SS (R5,R10) | P6 report totals per project (R6,R11) | P7 overlap detected in log (R9) | P8 adjacent not flagged (R9)
P9 corrupt JSON graceful (R13) | P10 >24h as 25:00:00 (R10) | P11 single file + stdlib (R1,R2; B fails file-count only if extra .py at root)
P12 invalid timestamp graceful (R13) | P13 naive timestamp no traceback (R13) | P14 persistence across invocations (R7) | P15 report runs on overlapping data (R6)
