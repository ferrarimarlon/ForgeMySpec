"""Progress and spend of the v0.6 experiment: python3 experiments/v06/status.py"""

import json
import statistics as st
from pathlib import Path

HERE = Path(__file__).resolve().parent
TASKS = sorted(p.stem for p in (HERE / "tasks").glob("*.md"))
REPS, ARMS = (1, 2, 3), ("without", "with")

builds = {}
for f in (HERE / "runs").glob("*/*/logs/meta.json"):
    m = json.loads(f.read_text())
    if m["rep"]:
        builds[(m["task"], m["arm"], m["rep"])] = sum(c.get("cost_usd") or 0 for c in m["calls"])
judges = {}
for f in (HERE / "judging").glob("*/cli.json"):
    task, rep = f.parent.name.rsplit("-r", 1)
    if rep != "0":
        try:
            judges[(task, int(rep))] = json.loads(f.read_text()).get("total_cost_usd") or 0
        except json.JSONDecodeError:
            judges[(task, int(rep))] = 0

total_b = len(TASKS) * len(REPS) * len(ARMS)
total_j = len(TASKS) * len(REPS)
lines = [f"builds  {len(builds):3}/{total_b}  ${sum(builds.values()):7.2f}",
         f"judges  {len(judges):3}/{total_j}  ${sum(judges.values()):7.2f}"]
proj = 0.0
for arm in ARMS:
    done = [v for (t, a, r), v in builds.items() if a == arm]
    left = sum(1 for t in TASKS for r in REPS if (t, arm, r) not in builds)
    avg = st.mean(done) if done else 0
    proj += avg * left
    lines.append(f"  {arm:8} {len(done):3} done  avg ${avg:5.2f}  {left:3} left")
javg = st.mean(judges.values()) if judges else 0.43  # pilot judge cost until real ones exist
proj += javg * (total_j - len(judges))
spent = sum(builds.values()) + sum(judges.values())
lines.append(f"spent ${spent:.2f} · projected to finish ${spent + proj:.2f} (API list price)")
print("\n".join(lines))
