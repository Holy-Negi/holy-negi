#!/usr/bin/env python3
"""
PubChem からランダムに化合物を 1 つ選び、構造式 SVG と README の MOLECULE セクションを更新する。
  python3 scripts/molecule_of_the_day.py
"""

from __future__ import annotations

import argparse
import html
import json
import random
import re
import urllib.error
import urllib.request
from datetime import datetime, timedelta, timezone
from pathlib import Path

from rdkit import Chem
from rdkit.Chem import rdDepictor
from rdkit.Chem.Draw import rdMolDraw2D

from readme_section import update_section

JST = timezone(timedelta(hours=9))
PUG = "https://pubchem.ncbi.nlm.nih.gov/rest/pug/compound/cid"
PROPS = "Title,MolecularFormula,MolecularWeight,SMILES,HeavyAtomCount"

MAX_CID = 175_000_000  # PubChem の CID 上限付近（欠番は候補から除外される）
BATCH = 50  # 1 リクエストで問い合わせる CID 数
MAX_TRIES = 5
HEAVY_ATOMS = range(10, 41)  # 構造式として見栄えのする水素以外の原子数
MAX_NAME_LEN = 100

# ヘッダー分子と同じ配色。キーは原子番号
PALETTE = {
    "light": {6: "#1B2430", 1: "#1B2430", 7: "#3057A8", 8: "#C1361F"},
    "dark": {6: "#E6EDF3", 1: "#E6EDF3", 7: "#7EA6FF", 8: "#FF8A75"},
}


def fetch_properties(cids: list[int]) -> list[dict]:
    url = f"{PUG}/{','.join(map(str, cids))}/property/{PROPS}/JSON"
    req = urllib.request.Request(url, headers={"User-Agent": "molecule-of-the-day"})
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            return json.load(r)["PropertyTable"]["Properties"]
    except (urllib.error.URLError, json.JSONDecodeError, KeyError) as e:
        raise SystemExit(f"PubChem API からの取得に失敗しました: {e}") from e


def is_presentable(p: dict) -> bool:
    smiles, title = p.get("SMILES", ""), p.get("Title", "")
    return (
        p.get("HeavyAtomCount", 0) in HEAVY_ATOMS
        and "." not in smiles  # 塩・混合物（複数成分）を除外
        and 0 < len(title) <= MAX_NAME_LEN
    )


def pick_compound() -> tuple[dict, Chem.Mol]:
    for _ in range(MAX_TRIES):
        cids = random.sample(range(1, MAX_CID), BATCH)
        for p in filter(is_presentable, fetch_properties(cids)):
            mol = Chem.MolFromSmiles(p["SMILES"])
            if mol is not None:
                return p, mol
    raise SystemExit(f"{MAX_TRIES * BATCH} 件の候補から条件を満たす化合物が見つかりませんでした")


def hex_to_rgb(code: str) -> tuple[float, float, float]:
    """'#RRGGBB' を RDKit が受け取る 0–1 の RGB タプルに変換する。"""
    return tuple(int(code[i : i + 2], 16) / 255 for i in (1, 3, 5))


def render_svg(mol: Chem.Mol, theme: str) -> str:
    drawer = rdMolDraw2D.MolDraw2DSVG(480, 320)
    opts = drawer.drawOptions()
    if theme == "dark":
        rdMolDraw2D.SetDarkMode(opts)  # 暗い背景向けの原子色に切り替える
    opts.clearBackground = False  # 背景を透明にする
    opts.bondLineWidth = 2
    opts.updateAtomPalette({z: hex_to_rgb(c) for z, c in PALETTE[theme].items()})
    rdMolDraw2D.PrepareAndDrawMolecule(drawer, mol)
    drawer.FinishDrawing()
    return drawer.GetDrawingText()


def build_section(p: dict, light: str, dark: str) -> str:
    cid = p["CID"]
    name = html.escape(p["Title"])
    # 分子式の数字を下付きにする（例: C9H8O4 → C<sub>9</sub>H<sub>8</sub>O<sub>4</sub>）
    formula = re.sub(r"(\d+)", r"<sub>\1</sub>", p["MolecularFormula"])
    date = datetime.now(JST).strftime("%Y-%m-%d")
    return f"""<div align="center">
<picture>
  <source media="(prefers-color-scheme: dark)" srcset="{dark}">
  <img src="{light}" alt="{name}" width="360">
</picture>
<br>
<b><a href="https://pubchem.ncbi.nlm.nih.gov/compound/{cid}">{name}</a></b><br>
{formula} · {p["MolecularWeight"]} g/mol · CID {cid}<br>
<sub>Randomly picked from PubChem on {date}</sub>
</div>"""


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--readme", default="README.md")
    p.add_argument("--outdir", type=Path, default=Path("assets/molecule"))
    args = p.parse_args()

    rdDepictor.SetPreferCoordGen(True)  # 環構造などをより自然な 2D 配置で描く
    compound, mol = pick_compound()
    print(f"CID {compound['CID']}: {compound['Title']}")

    # ファイル名に CID を含めて毎日 URL を変え、ブラウザに古い画像を使い回させない
    args.outdir.mkdir(parents=True, exist_ok=True)
    for old in args.outdir.glob("*.svg"):
        old.unlink()
    paths = {}
    for theme in ("light", "dark"):
        path = args.outdir / f"{compound['CID']}-{theme}.svg"
        path.write_text(render_svg(mol, theme), encoding="utf-8")
        paths[theme] = path.as_posix()  # README 用に区切り文字を / に統一する

    update_section(args.readme, "MOLECULE", build_section(compound, paths["light"], paths["dark"]))


if __name__ == "__main__":
    main()
