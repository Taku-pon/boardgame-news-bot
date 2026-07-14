"""
boardgame-news-bot
海外ボードゲームニュースを取得し、注目度の高い1件だけを選んで
Claude APIで日本語要約(リンク付き)にしてXに投稿するスクリプト。
注目度が高いと言える記事がない日は、何も投稿しない。
"""

import os
import json
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

SCORE_THRESHOLD = 4  # 5段階評価でこれ以上のスコアがあれば投稿する
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


def evaluate_entry(entry):
    """Claude APIで注目度スコア(1-5)と日本語ツイート文をまとめて生成する"""
    system_prompt = (
        "あなたはボードゲームニュースを紹介するXアカウントの編集者です。"
        "与えられた英語記事のタイトルと概要を読み、以下2つを判定してください。\n"
        "1. score: このニュースの注目度を1〜5の整数で評価する。"
        "5=大手メーカーの新作発表/大型受賞/業界を揺るがすニュース、"
        "3=通常の新作情報、"
        "1=個人ブログのレビューや小規模な話題。\n"
        "2. tweet: 日本語のツイート文(100文字以内、URLは含めない)。"
        "原文を逐語的に引用せず、必ず自分の言葉で要約すること。絵文字は最大1つまで。\n"
        "出力は以下のJSON形式のみ。前置きや説明文は一切不要:\n"
        '{"score": 数値, "tweet": "文章"}'
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

    try:
        parsed = json.loads(text)
        return int(parsed["score"]), parsed["tweet"]
    except Exception as e:
        print(f"[WARN] スコア判定のJSON解析に失敗: {e} / 出力: {text}")
        return 0, ""


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

    best_entry = None
    best_score = 0
    best_tweet = ""

    for entry in candidates:
        try:
            score, tweet = evaluate_entry(entry)
            print(f"[SCORE={score}] {entry['title']}")
            if score > best_score:
                best_score = score
                best_entry = entry
                best_tweet = tweet
        except Exception as e:
            print(f"[ERROR] {entry['title']} の評価中にエラー: {e}")
        finally:
            seen.add(entry["id"])  # 評価済みは二度と対象にしない

    if best_entry and best_score >= SCORE_THRESHOLD:
        success = post_tweet(best_tweet, best_entry["link"])
        if not success:
            print("[INFO] 投稿に失敗しました")
    else:
        print(f"[INFO] 注目度{SCORE_THRESHOLD}以上のニュースがなかったため、本日は投稿しません(最高スコア: {best_score})")

    save_seen(seen)


if __name__ == "__main__":
    main()
