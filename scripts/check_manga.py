#!/usr/bin/env python3
"""
アウト 最新話チェッカー
新しい話が更新されたらntfyに通知を送る
"""
import json
import re
import sys
import time
import urllib.request
import urllib.error
from datetime import datetime, timezone, timedelta
from pathlib import Path

MANGA_URL = "https://syosetu.sale/manga/%E3%82%A2%E3%82%A6%E3%83%88-raw-free/"
NTFY_URL = "https://ntfy.sh/manga-out"
STATUS_FILE = Path(__file__).parent.parent / "data" / "status.json"

JST = timezone(timedelta(hours=9))

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "ja,en-US;q=0.9,en;q=0.8",
    "Connection": "keep-alive",
}


def fetch_page(url: str) -> str:
    req = urllib.request.Request(url, headers=HEADERS)
    with urllib.request.urlopen(req, timeout=30) as resp:
        content_type = resp.headers.get("Content-Type", "")
        raw = resp.read()
        charset = "utf-8"
        if "charset=" in content_type:
            charset = content_type.split("charset=")[-1].strip()
        return raw.decode(charset, errors="replace")


def find_latest_chapter(html: str) -> int | None:
    """
    HTMLからチャプター番号を抽出して最大値を返す。
    複数のパターンを試みる。
    """
    candidates = []

    # パターン1: href に chapter-数字 が含まれるリンク
    for m in re.finditer(r'href=["\'][^"\']*chapter[-/](\d+)', html, re.IGNORECASE):
        candidates.append(int(m.group(1)))

    # パターン2: 「第N話」テキスト
    for m in re.finditer(r'第\s*(\d+)\s*話', html):
        candidates.append(int(m.group(1)))

    # パターン3: #N または /N/ のURL断片（3桁以上）
    for m in re.finditer(r'href=["\'][^"\']*[/#](\d{3,})[/"\'?]', html):
        n = int(m.group(1))
        if 200 <= n <= 9999:   # 妥当な話数の範囲
            candidates.append(n)

    # パターン4: テキスト中の "270" のような数字（li/td内）
    for m in re.finditer(r'<(?:li|td|span|div)[^>]*>\s*(?:第\s*)?(\d+)\s*(?:話|章|回)?\s*</(?:li|td|span|div)>', html):
        n = int(m.group(1))
        if 200 <= n <= 9999:
            candidates.append(n)

    if not candidates:
        return None
    return max(candidates)


def load_status() -> dict:
    with open(STATUS_FILE, encoding="utf-8") as f:
        return json.load(f)


def save_status(status: dict) -> None:
    with open(STATUS_FILE, "w", encoding="utf-8") as f:
        json.dump(status, f, ensure_ascii=False, indent=2)


def send_ntfy(chapter: int) -> None:
    message = f"アウト 第{chapter}話が更新されました！\n{MANGA_URL}"
    data = message.encode("utf-8")
    req = urllib.request.Request(
        NTFY_URL,
        data=data,
        method="POST",
        headers={
            "Content-Type": "text/plain; charset=utf-8",
            "Title": f"アウト 第{chapter}話 更新",
            "Priority": "default",
            "Tags": "manga,アウト",
        },
    )
    with urllib.request.urlopen(req, timeout=15) as resp:
        print(f"ntfy送信完了: {resp.status}")


def main() -> None:
    status = load_status()
    current_latest = status["latest_chapter"]

    print(f"現在の最新話: {current_latest}")
    print(f"チェック中: {MANGA_URL}")

    html = fetch_page(MANGA_URL)
    found = find_latest_chapter(html)

    now_jst = datetime.now(JST).isoformat()
    status["last_checked"] = now_jst

    if found is None:
        print("チャプター番号を検出できませんでした（パース失敗）")
        # デバッグ用に一部のHTMLを出力
        print("--- HTML先頭500文字 ---")
        print(html[:500])
        save_status(status)
        sys.exit(1)

    print(f"サイト上の最新話: {found}")

    if found > current_latest:
        print(f"新しい話を検出: 第{found}話")
        send_ntfy(found)
        status["latest_chapter"] = found
        print(f"status.json を {found} に更新")
    else:
        print("新しい話はありません")

    save_status(status)


if __name__ == "__main__":
    main()
