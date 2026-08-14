#!/usr/bin/env python3
"""
    python3 animate_svg.py in.svg -o out-light.svg
    python3 animate_svg.py in.svg -o out-dark.svg  --ink '#E6EDF3'
"""

from __future__ import annotations

import argparse
import re
import sys

# ---------------------------------------------------------------- CPK 配色
# id の末尾は文字コード。'N' → 78, 'O' → 79 など。
CPK = {
    78: "nitrogen",   # N
    79: "oxygen",     # O
    83: "sulfur",     # S
    80: "phosphorus", # P
}

STYLE_TEMPLATE = """
<style><![CDATA[
  .bond {{
    stroke: {ink};
    fill: none;
    stroke-linecap: round;
    stroke-dasharray: 1;
    stroke-dashoffset: 1;
    animation: draw {bond_dur:.2f}s ease-in-out forwards;
  }}
  .label {{
    fill: {ink};
    opacity: 0;
    animation: appear {label_dur:.2f}s ease-out forwards;
  }}
  .nitrogen   {{ fill: {nitrogen}; }}
  .oxygen     {{ fill: {oxygen}; }}
  .sulfur     {{ fill: {sulfur}; }}
  .phosphorus {{ fill: {phosphorus}; }}

  @keyframes draw   {{ to {{ stroke-dashoffset: 0; }} }}
  @keyframes appear {{ to {{ opacity: 1; }} }}

  /* 動きを減らす設定の環境では完成形を静止表示する */
  @media (prefers-reduced-motion: reduce) {{
    .bond  {{ stroke-dashoffset: 0; animation: none; }}
    .label {{ opacity: 1; animation: none; }}
  }}
]]></style>
"""


def build_style(args, n_bonds: int) -> str:
    return STYLE_TEMPLATE.format(
        ink=args.ink,
        nitrogen=args.nitrogen,
        oxygen=args.oxygen,
        sulfur=args.sulfur,
        phosphorus=args.phosphorus,
        bond_dur=args.bond_duration,
        label_dur=args.label_duration,
    )


def animate(svg: str, args) -> str:
    # --- 1) 結合パス（fill='none' を持つ <path>）--------------------------
    bond_index = [0]

    def bond_repl(m: re.Match) -> str:
        i = bond_index[0]
        bond_index[0] += 1
        delay = args.start_delay + i * args.bond_stagger
        return (
            f"{m.group(1)} class='bond' pathLength='1' "
            f"style='animation-delay:{delay:.2f}s'{m.group(2)}"
        )

    # <path ... fill='none' ... /> のうち defs の外にあるものだけを対象にする
    head, sep, body = svg.partition("</defs>")
    if not sep:  # defs が無い SVG でも壊れないように
        head, body = "", svg

    body = re.sub(r"(<path)((?=[^>]*fill='none')[^>]*?/>)", bond_repl, body)
    n_bonds = bond_index[0]

    # --- 2) 原子ラベル（<use>）------------------------------------------
    total_bond_time = args.start_delay + max(n_bonds - 1, 0) * args.bond_stagger + args.bond_duration
    label_index = [0]

    def use_repl(m: re.Match) -> str:
        attrs = m.group(0)
        code = None
        idm = re.search(r"xlink:href='#g\d+-(\d+)'", attrs)
        if idm:
            code = int(idm.group(1))
        cls = "label"
        if args.cpk and code in CPK:
            cls += " " + CPK[code]
        delay = total_bond_time + args.label_gap + label_index[0] * args.label_stagger
        label_index[0] += 1
        return attrs[:-2] + (
            f" class='{cls}' style='animation-delay:{delay:.2f}s'/>"
        )

    body = re.sub(r"<use[^>]*/>", use_repl, body)

    svg = head + sep + body if sep else body

    # --- 3) スタイル注入 & スケーラブル化 --------------------------------
    style = build_style(args, n_bonds)
    if "</defs>" in svg:
        svg = svg.replace("</defs>", "</defs>" + style, 1)
    else:
        svg = re.sub(r"(<svg[^>]*>)", r"\1" + style, svg, count=1)

    # width/height を外して viewBox だけにすると README 側で自由に伸縮できる
    if args.responsive:
        svg = re.sub(r"(<svg[^>]*?)\s+width='[^']*'", r"\1", svg, count=1)
        svg = re.sub(r"(<svg[^>]*?)\s+height='[^']*'", r"\1", svg, count=1)

    print(
        f"bonds: {n_bonds}, labels: {label_index[0]}, "
        f"total: {total_bond_time + args.label_gap + label_index[0] * args.label_stagger:.1f}s",
        file=sys.stderr,
    )
    return svg


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("input")
    p.add_argument("-o", "--output", required=True)
    p.add_argument("--ink", default="#1B2430", help="結合と炭素骨格ラベルの色")
    p.add_argument("--nitrogen", default="#3057A8")
    p.add_argument("--oxygen", default="#C1361F")
    p.add_argument("--sulfur", default="#B8860B")
    p.add_argument("--phosphorus", default="#C46A1F")
    p.add_argument("--no-cpk", dest="cpk", action="store_false", help="ヘテロ原子も ink 色にする")
    p.add_argument("--bond-duration", type=float, default=0.45, help="1 本の結合を引く時間 [s]")
    p.add_argument("--bond-stagger", type=float, default=0.10, help="結合どうしの時間差 [s]")
    p.add_argument("--start-delay", type=float, default=0.3)
    p.add_argument("--label-duration", type=float, default=0.5)
    p.add_argument("--label-stagger", type=float, default=0.06)
    p.add_argument("--label-gap", type=float, default=0.15, help="結合完成からラベル出現までの間 [s]")
    p.add_argument("--no-responsive", dest="responsive", action="store_false")
    args = p.parse_args()

    with open(args.input, encoding="utf-8") as f:
        svg = f.read()
    out = animate(svg, args)
    with open(args.output, "w", encoding="utf-8") as f:
        f.write(out)


if __name__ == "__main__":
    main()
