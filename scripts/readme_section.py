"""README 内の <!-- NAME:START --> 〜 <!-- NAME:END --> の間を書き換える共通処理。"""

from __future__ import annotations

import re


def replace_section(readme: str, name: str, body: str) -> str:
    start = f"<!-- {name}:START -->"
    end = f"<!-- {name}:END -->"
    if start not in readme or end not in readme:
        raise SystemExit(f"マーカー {start} / {end} が README に見つかりません")
    # 置換先を関数で渡すと、body 中の \ がエスケープとして解釈されない
    return re.sub(
        re.escape(start) + r".*?" + re.escape(end),
        lambda _: f"{start}\n{body}\n{end}",
        readme,
        flags=re.DOTALL,
    )


def update_section(path: str, name: str, body: str) -> None:
    with open(path, encoding="utf-8") as f:
        readme = f.read()

    new = replace_section(readme, name, body)
    if new == readme:
        print(f"{name}: 変更なし")
        return
    with open(path, "w", encoding="utf-8") as f:
        f.write(new)
    print(f"{name}: {path} を更新しました")
