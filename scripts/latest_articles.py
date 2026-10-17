#!/usr/bin/env python3
"""
Qiita / Zenn のフィードから新着記事を集め、README の ARTICLES セクションを更新する。
  python3 scripts/latest_articles.py --qiita QIITA_ID --zenn ZENN_ID
"""

from __future__ import annotations

import argparse
import html
import urllib.error
import urllib.request
import xml.etree.ElementTree as ET
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from email.utils import parsedate_to_datetime

from readme_section import update_section

JST = timezone(timedelta(hours=9))
ATOM = {"a": "http://www.w3.org/2005/Atom"}  # Atom 形式の XML 名前空間

BADGES = {
    "Qiita": "https://img.shields.io/badge/Qiita-55C500?style=flat-square&logo=qiita&logoColor=white",
    "Zenn": "https://img.shields.io/badge/Zenn-3EA8FF?style=flat-square&logo=zenn&logoColor=white",
}


@dataclass
class Article:
    title: str
    published: datetime
    # 投稿先ごとの URL（同じ記事を複数サービスに投稿した場合は 1 つにまとめる）
    links: dict[str, str] = field(default_factory=dict)


def fetch_xml(url: str) -> ET.Element:
    req = urllib.request.Request(url, headers={"User-Agent": "latest-articles"})
    try:
        with urllib.request.urlopen(req, timeout=20) as r:
            return ET.fromstring(r.read())
    except (urllib.error.URLError, ET.ParseError) as e:
        raise SystemExit(f"フィード {url} の取得に失敗しました: {e}") from e


def parse_qiita(user: str) -> list[tuple[str, str, datetime]]:
    """Qiita の Atom フィードから (タイトル, URL, 公開日時) を取り出す。"""
    root = fetch_xml(f"https://qiita.com/{user}/feed")
    return [
        (
            e.findtext("a:title", "", ATOM),
            e.find("a:link[@rel='alternate']", ATOM).get("href"),
            datetime.fromisoformat(e.findtext("a:published", "", ATOM)),
        )
        for e in root.iterfind("a:entry", ATOM)
    ]


def parse_zenn(user: str) -> list[tuple[str, str, datetime]]:
    """Zenn の RSS 2.0 フィードから (タイトル, URL, 公開日時) を取り出す。"""
    root = fetch_xml(f"https://zenn.dev/{user}/feed")
    return [
        (
            item.findtext("title", ""),
            item.findtext("link", ""),
            parsedate_to_datetime(item.findtext("pubDate", "")),  # RFC 2822 形式の日時
        )
        for item in root.iterfind("channel/item")
    ]


def collect(qiita: str, zenn: str) -> list[Article]:
    articles: dict[str, Article] = {}
    for source, entries in (("Qiita", parse_qiita(qiita)), ("Zenn", parse_zenn(zenn))):
        for title, url, published in entries:
            a = articles.setdefault(title, Article(title, published))
            a.links[source] = url
            a.published = min(a.published, published)
    return sorted(articles.values(), key=lambda a: a.published, reverse=True)


def build_section(articles: list[Article], limit: int) -> str:
    lines = []
    for a in articles[:limit]:
        # Markdown のリンク記法と衝突する [ ] をエスケープする
        title = html.escape(a.title, quote=False).replace("[", r"\[").replace("]", r"\]")
        badges = " ".join(
            f'<a href="{url}"><img src="{BADGES[src]}" alt="{src}"></a>'
            for src, url in a.links.items()
        )
        date = a.published.astimezone(JST).strftime("%Y-%m-%d")
        lines.append(f"- [{title}]({next(iter(a.links.values()))}) {badges} <sub>{date}</sub>")

    return "\n".join(lines) or "- （まだ記事はありません）"


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--qiita", required=True)
    p.add_argument("--zenn", required=True)
    p.add_argument("--readme", default="README.md")
    p.add_argument("--limit", type=int, default=5)
    args = p.parse_args()

    articles = collect(args.qiita, args.zenn)
    update_section(args.readme, "ARTICLES", build_section(articles, args.limit))


if __name__ == "__main__":
    main()
