# boardgame-news-bot

海外ボードゲームニュースを取得し、Claude APIで日本語要約に翻訳して
Xに自動投稿するボットです。GitHub Actionsで1日3回、自動実行されます。

## セットアップ手順

### 1. リポジトリ作成
GitHubで新規リポジトリ `boardgame-news-bot` を作成し、このフォルダ内の
ファイルをすべてアップロードしてください。

### 2. Secretsの登録
リポジトリの `Settings > Secrets and variables > Actions > New repository secret`
から、以下5つを登録します(値はこのファイルには書きません。各自のキーを登録してください)。

- `ANTHROPIC_API_KEY`
- `X_API_KEY`
- `X_API_KEY_SECRET`
- `X_ACCESS_TOKEN`
- `X_ACCESS_TOKEN_SECRET`

### 3. 動作確認
`Actions` タブ → `Post Board Game News` → `Run workflow` で手動実行できます。
ログを見て、投稿が成功しているか確認してください。

### 4. 自動実行
`.github/workflows/post-news.yml` の cron 設定により、
UTC 0:00 / 4:00 / 9:00(日本時間 朝9時・13時・18時ごろ)に自動実行されます。
1回の実行につき最大4件まで投稿します(`post_news.py` 内の `MAX_POSTS_PER_RUN` で調整可能)。

## ファイル構成

- `post_news.py` — メインスクリプト
- `requirements.txt` — 依存パッケージ
- `seen_ids.json` — 投稿済み記事の記録(自動更新される)
- `.github/workflows/post-news.yml` — 定期実行設定

## ニュースソースの追加・変更

`post_news.py` 内の `FEEDS` リストに `{"name": ..., "url": ...}` を追加/削除するだけです。

## 注意事項

- 元記事の文章をそのまま転載せず、必ず要約・翻訳した上で出典リンクを付けています(著作権対応)
- コスト管理のため `MAX_POSTS_PER_RUN` で1回あたりの投稿数に上限を設けています
- X APIの利用量はX Developer Consoleの「使用状況」ページで定期的に確認してください
