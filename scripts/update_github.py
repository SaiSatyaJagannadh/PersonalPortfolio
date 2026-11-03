"""Fetch DJ's GitHub contribution calendar + latest pushes and write data/github.json.

Run daily by .github/workflows/github-activity.yml. Uses only the standard library.
"""
import datetime as dt
import html
import json
import os
import pathlib
import re
import sys
import urllib.request

USER = "SaiSatyaJagannadh"
UA = "Mozilla/5.0 (portfolio-stats-bot; +https://github.com/SaiSatyaJagannadh/PersonalPortfolio)"
TOKEN = os.environ.get("GITHUB_TOKEN", "")
MAX_PUSHES = 8


def get(url, api=False):
    h = {"User-Agent": UA}
    if api:
        h["Accept"] = "application/vnd.github+json"
        if TOKEN:
            h["Authorization"] = f"Bearer {TOKEN}"
    with urllib.request.urlopen(urllib.request.Request(url, headers=h), timeout=30) as r:
        return r.read().decode("utf-8")


def attrs(tag):
    return {k: v for k, v in re.findall(r'([\w:-]+)="([^"]*)"', tag)}


def calendar():
    page = get(f"https://github.com/users/{USER}/contributions")
    tips = {}
    for tag, text in re.findall(r"<tool-tip\b([^>]*)>(.*?)</tool-tip>", page, re.S):
        a = attrs(tag)
        if "for" in a:
            t = html.unescape(re.sub(r"<[^>]+>", "", text)).strip()
            m = re.match(r"([\d,]+) contributions?", t)
            tips[a["for"]] = int(m.group(1).replace(",", "")) if m else 0
    days = []
    for tag in re.findall(r"<td\b[^>]*ContributionCalendar-day[^>]*>", page):
        a = attrs(tag)
        if "data-date" not in a:
            continue
        lvl = int(a.get("data-level", 0))
        days.append([a["data-date"], tips.get(a.get("id"), lvl), lvl])
    days.sort()
    if len(days) < 300:
        raise SystemExit(f"calendar parse failed: only {len(days)} days")
    return days


def streaks(days):
    cur = longest = run = 0
    for _, c, _ in days:
        run = run + 1 if c > 0 else 0
        longest = max(longest, run)
    # current streak: count back from the last day; today may still be empty
    i = len(days) - 1
    if days[i][1] == 0:
        i -= 1
    while i >= 0 and days[i][1] > 0:
        cur += 1
        i -= 1
    return cur, longest


def pushes():
    events = json.loads(get(f"https://api.github.com/users/{USER}/events/public?per_page=100", api=True))
    push_events = sorted((e for e in events if e.get("type") == "PushEvent"), key=lambda e: e["created_at"], reverse=True)
    out, seen = [], set()
    for e in push_events:
        repo, p = e["repo"]["name"], e.get("payload", {})
        sha = p.get("head")
        if not sha or (repo, sha) in seen:
            continue
        seen.add((repo, sha))
        msg = ""
        commits = p.get("commits") or []
        if commits:
            msg = commits[-1].get("message", "")
        else:
            try:
                msg = json.loads(get(f"https://api.github.com/repos/{repo}/commits/{sha}", api=True))["commit"]["message"]
            except Exception as ex:  # private/deleted commit — keep the push, skip the message
                print("commit lookup failed", repo, sha, ex, file=sys.stderr)
        out.append({
            "repo": repo.split("/", 1)[1],
            "branch": (p.get("ref") or "").replace("refs/heads/", ""),
            "sha": sha[:7],
            "msg": msg.strip().splitlines()[0][:110] if msg.strip() else "",
            "at": e["created_at"],
        })
        if len(out) >= MAX_PUSHES:
            break
    return out, len(push_events), len({e["repo"]["name"] for e in push_events})


days = calendar()
cur, longest = streaks(days)
best = max(days, key=lambda d: d[1])
recent, n_push, n_repos = pushes()
out = {
    "user": USER,
    "total": sum(d[1] for d in days),
    "activeDays": sum(1 for d in days if d[1] > 0),
    "streak": cur,
    "longest": longest,
    "best": {"date": best[0], "count": best[1]},
    "last30": sum(d[1] for d in days[-30:]),
    "recentPushes": n_push,
    "recentRepos": n_repos,
    "days": days,
    "pushes": recent,
    "updated": dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
}

path = pathlib.Path("data/github.json")
old = json.loads(path.read_text()) if path.exists() else {}
if {k: v for k, v in old.items() if k != "updated"} == {k: v for k, v in out.items() if k != "updated"}:
    print("no change"); sys.exit(0)
path.write_text(json.dumps(out, separators=(",", ":")) + "\n")
print("updated", {k: v for k, v in out.items() if k not in ("days", "pushes")}, len(recent), "pushes")
