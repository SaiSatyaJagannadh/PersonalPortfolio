"""Fetch DJ's LeetCode stats and write data/leetcode.json (run by .github/workflows/leetcode.yml)."""
import json, urllib.request, datetime, pathlib, sys

USER = "saijagannadh0625"
QUERY = """query u($u: String!) {
  matchedUser(username: $u) {
    submitStatsGlobal { acSubmissionNum { difficulty count } }
    userCalendar { totalActiveDays streak }
    profile { ranking }
    tagProblemCounts { advanced { tagSlug problemsSolved } intermediate { tagSlug problemsSolved } fundamental { tagSlug problemsSolved } }
  }
}"""

req = urllib.request.Request(
    "https://leetcode.com/graphql/",
    data=json.dumps({"query": QUERY, "variables": {"u": USER}}).encode(),
    headers={"Content-Type": "application/json", "Referer": f"https://leetcode.com/u/{USER}/",
             "User-Agent": "Mozilla/5.0 (portfolio-stats-bot; +https://github.com/SaiSatyaJagannadh/PersonalPortfolio)"},
)
with urllib.request.urlopen(req, timeout=30) as r:
    u = json.load(r)["data"]["matchedUser"]

ac = {x["difficulty"]: x["count"] for x in u["submitStatsGlobal"]["acSubmissionNum"]}
tags = [t for lvl in u["tagProblemCounts"].values() for t in lvl]
dp = next((t["problemsSolved"] for t in tags if t["tagSlug"] == "dynamic-programming"), None)
out = {
    "username": USER, "total": ac["All"], "easy": ac["Easy"], "medium": ac["Medium"], "hard": ac["Hard"],
    "activeDays": u["userCalendar"]["totalActiveDays"], "streak": u["userCalendar"]["streak"],
    "ranking": u["profile"]["ranking"], "dp": dp,
    "updated": datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
}
path = pathlib.Path("data/leetcode.json")
old = json.loads(path.read_text()) if path.exists() else {}
IGNORE = {"updated", "ranking"}  # ranking drifts every run; only commit when solved counts / streak change
if {k: v for k, v in old.items() if k not in IGNORE} == {k: v for k, v in out.items() if k not in IGNORE}:
    print("no change", out); sys.exit(0)
path.write_text(json.dumps(out) + "\n")
print("updated", out)
