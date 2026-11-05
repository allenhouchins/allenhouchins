#!/usr/bin/env python3
"""Rewrite the LIVE block in README.md with fresh numbers from Allen's tracker repos.

Sources (all public, no secrets needed beyond the Action's GITHUB_TOKEN):
  - fleet-maintained-apps-growth-tracker/data/apps_growth.csv
  - fleet-maintained-apps-growth-tracker/data/patches_per_day.csv
  - new-casks-tracker/data/new_casks_log.json
  - fleetdm/fleet latest release
"""
import csv
import io
import json
import os
import re
import sys
import urllib.request
from datetime import datetime, timedelta, timezone

RAW = "https://raw.githubusercontent.com/allenhouchins"
README = os.path.join(os.path.dirname(__file__), "..", "README.md")
SPARK = "▁▂▃▄▅▆▇█"


def get(url, accept=None):
    req = urllib.request.Request(url, headers={"User-Agent": "profile-readme-updater"})
    token = os.environ.get("GITHUB_TOKEN")
    if token and "api.github.com" in url:
        req.add_header("Authorization", f"Bearer {token}")
    if accept:
        req.add_header("Accept", accept)
    with urllib.request.urlopen(req, timeout=30) as r:
        return r.read().decode("utf-8")


def sparkline(values):
    lo, hi = min(values), max(values)
    span = (hi - lo) or 1
    return "".join(SPARK[int((v - lo) / span * (len(SPARK) - 1))] for v in values)


def main():
    now = datetime.now(timezone.utc)

    # Fleet-maintained apps growth
    growth = list(csv.DictReader(io.StringIO(get(f"{RAW}/fleet-maintained-apps-growth-tracker/main/data/apps_growth.csv"))))
    latest = growth[-1]
    total = int(latest["app_count"])
    mac, win = int(latest["mac_count"]), int(latest["windows_count"])
    last30 = growth[-30:]
    added_30d = total - int(last30[0]["app_count"])
    # weekly samples over ~16 weeks for the trend
    weekly = [int(r["app_count"]) for r in growth[-112::7]]

    # Patches shipped in the last 7 days
    patches = list(csv.DictReader(io.StringIO(get(f"{RAW}/fleet-maintained-apps-growth-tracker/main/data/patches_per_day.csv"))))
    patches_7d = sum(int(r["patch_count"]) for r in patches[-7:])

    # New Homebrew casks in the last 7 days
    log = json.loads(get(f"{RAW}/new-casks-tracker/main/data/new_casks_log.json"))
    cutoff = now - timedelta(days=7)
    recent = [c for c in log if datetime.fromisoformat(c["detected_at"][:19]).replace(tzinfo=timezone.utc) >= cutoff]
    newest = recent[-1]["name"] if recent else "—"

    # Latest Fleet release
    try:
        release = json.loads(get("https://api.github.com/repos/fleetdm/fleet/releases/latest"))["tag_name"]
    except Exception:
        release = "—"

    rows = [
        ("fleet_maintained_apps", f"{total:,}", sparkline(weekly) + "  (16 wk)"),
        ("  macos / windows", f"{mac:,} / {win:,}", ""),
        ("apps_added_last_30d", f"+{added_30d}", ""),
        ("fma_patches_last_7d", f"{patches_7d:,}", ""),
        ("new_homebrew_casks_7d", f"{len(recent)}", f"newest: {newest}"[:28]),
        ("latest_fleet_release", release, ""),
    ]
    w = [max(len(r[i]) for r in rows + [("metric", "value", "trend")]) for i in range(3)]
    line = "+" + "+".join("-" * (x + 2) for x in w) + "+"
    fmt = lambda r: "| " + " | ".join(c.ljust(w[i]) for i, c in enumerate(r)) + " |"
    table = "\n".join([
        "```sql",
        "osquery> SELECT * FROM fleet_live_stats;",
        line, fmt(("metric", "value", "trend")), line,
        *[fmt(r) for r in rows],
        line,
        f"{len(rows)} rows in set. Last refreshed {now:%Y-%m-%d %H:%M} UTC",
        "```",
    ])

    path = os.path.abspath(README)
    text = open(path, encoding="utf-8").read()
    new = re.sub(r"(<!-- LIVE:START -->).*?(<!-- LIVE:END -->)", lambda m: f"{m.group(1)}\n{table}\n{m.group(2)}", text, flags=re.S)
    if new != text:
        open(path, "w", encoding="utf-8").write(new)
        print("README updated")
    else:
        print("No change")


if __name__ == "__main__":
    sys.exit(main())
