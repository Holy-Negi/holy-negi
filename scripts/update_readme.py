#!/usr/bin/env python3
"""
  python3 scripts/update_readme.py --user USERNAME
"""

from __future__ import annotations

import argparse
import json
import os
import re
import urllib.error
import urllib.request
from datetime import datetime, timedelta, timezone

JST = timezone(timedelta(hours=9))
START = "<!-- ACTIVITY:START -->"
END = "<!-- ACTIVITY:END -->"


def fetch_events(user: str) -> list[dict]:
    req = urllib.request.Request(
        f"https://api.github.com/users/{user}/events/public?per_page=100",
        headers={
            "Accept": "application/vnd.github+json",
            "User-Agent": f"{user}-profile-updater",
        },
    )
    token = os.environ.get("GH_TOKEN")
    if token:
        req.add_header("Authorization", f"Bearer {token}")
    try:
        with urllib.request.urlopen(req, timeout=20) as r:
            return json.load(r)
    except (urllib.error.URLError, json.JSONDecodeError) as e:
        print(f"warning: events API failed: {e}")
        return []


def humanize(ts: str) -> str:
    t = datetime.strptime(ts, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc)
    d = datetime.now(timezone.utc) - t
    if d.days >= 1:
        return f"{d.days}日前"
    if d.seconds >= 3600:
        return f"{d.seconds // 3600}時間前"
    return f"{max(d.seconds // 60, 1)}分前"


def build_section(user: str, events: list[dict], limit: int) -> str:
    lines: list[str] = []
    seen: set[str] = set()

    for ev in events:
        repo = ev.get("repo", {}).get("name", "")
        if not repo or repo in seen:
            continue

        kind = ev.get("type")
        if kind == "PushEvent":
            commits = ev.get("payload", {}).get("commits", [])
            if not commits:
                continue
            msg = commits[-1].get("message", "").splitlines()[0][:72]
            what = f"`{msg}`"
        elif kind == "CreateEvent" and ev["payload"].get("ref_type") == "repository":
            what = "リポジトリを作成"
        elif kind == "ReleaseEvent":
            what = f"リリース {ev['payload']['release'].get('tag_name', '')}"
        elif kind == "PullRequestEvent" and ev["payload"].get("action") == "opened":
            what = f"PR #{ev['payload']['number']} を作成"
        else:
            continue

        seen.add(repo)
        name = repo.split("/", 1)[-1]
        lines.append(
            f"- [`{name}`](https://github.com/{repo}) — {what} <sub>({humanize(ev['created_at'])})</sub>"
        )
        if len(lines) >= limit:
            break

    if not lines:
        lines = ["- （直近の公開アクティビティはありません）"]

    stamp = datetime.now(JST).strftime("%Y-%m-%d %H:%M JST")
    return "\n".join(lines) + f"\n\n<sub>最終更新: {stamp}</sub>"


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--user", required=True)
    p.add_argument("--readme", default="README.md")
    p.add_argument("--limit", type=int, default=5)
    args = p.parse_args()

    with open(args.readme, encoding="utf-8") as f:
        readme = f.read()

    if START not in readme or END not in readme:
        raise SystemExit(f"マーカー {START} / {END} が {args.readme} に見つかりません")

    section = build_section(args.user, fetch_events(args.user), args.limit)
    new = re.sub(
        re.escape(START) + r".*?" + re.escape(END),
        START + "\n" + section + "\n" + END,
        readme,
        flags=re.DOTALL,
    )

    if new == readme:
        print("変更なし")
        return
    with open(args.readme, "w", encoding="utf-8") as f:
        f.write(new)
    print("README.md を更新しました")


if __name__ == "__main__":
    main()
