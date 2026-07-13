"""
boardgame-news-bot
海外ボードゲームニュースを取得し、Claude APIで日本語に要約翻訳して
Xに自動投稿するスクリプト。
"""

import os
import json
import time
import feedparser
import requests
from requests_oauthlib import OAuth1

FEEDS = [
    {"name": "BoardGameGeek News", "url": "https://boardgamegeek.com/rss/blog/1"},
    {"name": "Meeple Mountain", "url": "https://www.meeplemountain.com/feed/"},
    {"name": "The Board Game Family", "url": "https://theboardgamefamily.com/feed/"},
    {"name": "Casual Game Revolution", "url": "https://casualgamerevolution.com/rss.xml"},
    {"name": "EverythingBoardGames", "url": "https://www.everythingboardgames.com/feeds/posts/default?alt=rss"},
]

MAX_POSTS_PER_RUN = 4
SEEN_FILE = "seen_ids.json"

ANTHROPIC_API_KEY = os.environ["ANTHROPIC_API_KEY"]
X_API_KEY = os.environ["X_API_KEY"]
X_API_KEY_SECRET = os.environ["X_API_KEY_SECRET"]
X_ACCESS_TOKEN = os.environ["X_ACCESS_TOKEN"]
X_ACCESS_TOKEN_SECRET = os.environ["X_ACCESS_TOKEN_SECRET"]


def load_seen():
    if os.path.exists(SEEN_FILE):
        with open(SEEN_FILE, "r", encoding="utf-8") as f:
            return set(json.load(f))
    return set()


def save_seen(seen):
    with open(SEEN_FILE, "w", encoding="utf-8") as f:
        json.dump(sorted(seen), f, ensure_ascii=False, indent=2)


def fetch_new_entries(seen):
    candidates = []
    for feed in FEEDS:
        try:
            parsed = feedparser.parse(feed["url"])
        except Exception as e:
            print(f"[WARN] {feed['name']} の取得に失敗: {e}")
            continue

        for entry in parsed.entries:
            entry_id = entry.get("id") or entry.get("link")
            if not entry_id or entry_id in seen:
                continue
            candidates.append(
                {
                    "id": entry_id,
                    "source": feed["name"],
                    "title": entry.get("title", ""),
                    "summary": entry.get("summary", ""),
                    "link": entry.get("link", ""),
                }
            )
    return candidates


def summarize_ja(entry):
    system_prompt = (
        "あなたはボードゲームニュースを紹介するXアカウントの編集者です。"
        "与えられた英語記事のタイトルと概要をもとに、日本語のツイート文を作成してください。"
        "ルール:\n"
        "- 原文の一部を逐語的に引用せず、必ず自分の言葉で要約すること\n"
        "- 100文字以内(URLは含めない)\n"
        "- 絵文字は最大1つまで\n"
        "- 事実を誇張しない\n"
        "- 出力はツイート本文のみ。前置きや説明文は不要\n"
    )
    user_prompt = (
        f"タイトル: {entry['title']}\n"
        f"概要: {entry['summary']}\n"
        f"出典: {entry['source']}"
    )

    resp = requests.post(
        "https://api.anthropic.com/v1/messages",
        headers={
            "x-api-key": ANTHROPIC_API_KEY,
            "anthropic-version": "2023-06-01",
            "content-type": "application/json",
        },
        json={
            "model": "claude-sonnet-5",
            "max_tokens": 300,
            "system": system_prompt,
            "messages": [{"role": "user", "content": user_prompt}],
        },
        timeout=30,
    )
        if resp.status_code >= 300:
        print(f"[DEBUG] Anthropic APIエラー詳細: {resp.status_code} {resp.text}")
        resp.raise_for_status()
        data = resp.json()

    text = "".join(b["text"] for b in data["content"] if b["type"] == "text").strip()
    return text


def post_tweet(text, link):
    tweet_text = f"{text}\n{link}"
    auth = OAuth1(
        X_API_KEY,
        X_API_KEY_SECRET,
        X_ACCESS_TOKEN,
        X_ACCESS_TOKEN_SECRET,
    )
    resp = requests.post(
        "https://api.twitter.com/2/tweets",
        auth=auth,
        json={"text": tweet_text},
        timeout=30,
    )
    if resp.status_code >= 300:
        print(f"[ERROR] 投稿失敗: {resp.status_code} {resp.text}")
        return False
    print(f"[OK] 投稿成功: {tweet_text}")
    return True


def main():
    seen = load_seen()
    candidates = fetch_new_entries(seen)
    print(f"新着候補: {len(candidates)}件")

    posted_count = 0
    for entry in candidates:
        if posted_count >= MAX_POSTS_PER_RUN:
            break
        try:
            tweet_text = summarize_ja(entry)
            success = post_tweet(tweet_text, entry["link"])
            if success:
                seen.add(entry["id"])
                posted_count += 1
                time.sleep(5)
        except Exception as e:
            print(f"[ERROR] {entry['title']} の処理中にエラー: {e}")

    save_seen(seen)
    print(f"今回の投稿件数: {posted_count}")


if __name__ == "__main__":
    main()
