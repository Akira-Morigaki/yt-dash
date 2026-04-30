# YouTube ダッシュボード データ取得手段 調査メモ

調査日: 2026-04-30
対象チャンネル: AKIRA.M (`UCXDnQrp8Sao7ZmpL9Ws-SLA`, 現在 1,653 subs)
ダッシュボード更新間隔: 10 分

---

## TL;DR (推奨構成)

| 用途 | 推奨ソース | 状態 |
|---|---|---|
| 登録者数 (正確な値) | **Analytics API の `subscribersGained - subscribersLost` を日次で累積** + 既知の基準値 (1653) からのデルタ | ○ |
| 登録者数 (準リアルタイム表示) | **YouTube Studio 内部 API (Innertube / `studio.youtube.com`)** で SAPISID ハッシュ認証 | △ (非公式・ToS グレー) |
| 動画ごとの views / watch time / averageViewPercentage / impressions / CTR | **YouTube Analytics API (`yt-analytics.readonly`)** with `dimensions=video` | ○ (2-3日の遅延あり) |
| 動画ごとの「直近24h/48h 再生数」 | **YouTube Analytics API** で `startDate=今日-2`, `endDate=今日` を毎回投げて差分計算 | △ (遅延 48-72h) |
| リアルタイム動画パフォーマンス | **YouTube Studio 内部 API** (Realtime レポート相当) のみ | △ (非公式) |

**結論: 「登録者数」は Analytics API のデルタ累積で 1人単位の精度を確保。「動画ごとの統計」も Analytics API に寄せ、Data API は基本情報 (タイトル/サムネ/公開日) 取得のみに留める。DOM 解析は廃止可能。**

ただし現環境特有の重大な前提がある — 後述「6. 重要な前提」を参照。

---

## 1. YouTube Data API v3 — `subscriberCount` の丸め仕様

### 仕様
- **2019年9月10日 (公式 revision history 記載日)** 付けで、`channel.statistics.subscriberCount` は **1,000 人超のチャンネルでは 3 桁有効数字で切り捨て** されるようになった。
- 公式アナウンス: 2019年5月21日 (告知) → 2019年9月17日 (公開 UI ロールアウト) / 同 9月10日 (API 仕様変更)。
- 表示例: 1,653 → **1,650** / 7,492 → 7,490 / 14,304,323 → 14,300,000

### `mine=true` と `id=CHANNEL_ID` の挙動差
- **差は無い**。公式ドキュメントに「This change affects the property value even in cases where a user sends an authorized request for data about their own channel.」と明記。
- **実機検証 (2026-04-30)**: `id=UCXDnQrp8Sao7ZmpL9Ws-SLA` で叩いて `"subscriberCount": "1650"` を確認。実値 1,653 → 3桁丸め (1650) で返却された。

### 丸め回避の公式手段
- **存在しない。** Data API では誰がどう叩いても丸められる。
- 唯一の公式回避策は **YouTube Analytics API** (差分メトリクス経由) または YouTube Studio (UI / 内部 API) のみ。

### 判定: × (細かい数字は取れない)

---

## 2. YouTube Analytics API (`yt-analytics.readonly`)

### 2-1. 登録者数の精度確保

**`subscribersGained` / `subscribersLost` は日次で 1人単位の正確な値が返る。** 検証済み (2026-04-30 にダミーチャンネルで dimensions=day を叩き整数で返却を確認)。

運用方針:
1. 既知の基準値 (例: 2026-04-30 時点 1,653) を保存
2. 毎回 `startDate = 基準日, endDate = today, dimensions=day` で差分を取得
3. `current = base + sum(gained - lost)` で算出

メリット:
- 完全に公式 API、ToS 遵守
- 1 人単位の精度

デメリット:
- **データレイテンシが 24-72 時間**。今日と昨日の差分は遅れて反映 → 「現在の正確な値」ではなく「~2 日前までの確定値」になる
- 確定値が後から微修正されることがある (再集計)

### 判定: ○ (1人単位の精度で取得可、ただし 1-3 日遅延)

### 2-2. 動画ごとに取れるメトリクス一覧

`dimensions=video` + `filters=video==VIDEO_ID,VIDEO_ID,...` (上限 ~200) で以下が取得可能:

| メトリクス | 内容 | 備考 |
|---|---|---|
| `views` | 再生数 | core metric |
| `estimatedMinutesWatched` | 視聴時間 (分) | core |
| `averageViewDuration` | 平均視聴秒数 | core |
| **`averageViewPercentage`** | **視聴維持率 (%)** | これが「視聴維持率」 |
| `subscribersGained` / `subscribersLost` | 該当動画経由の登録/解除 | core |
| `likes` / `dislikes` / `comments` / `shares` | エンゲージメント | |
| `annotationClickThroughRate` | アノテーション CTR | レガシー |
| **`cardImpressions` / `cardClickRate`** | カード CTR | |
| **`impressions`** | サムネのインプレッション数 | サムネ表示時間 1秒 & 50% 可視で計上 |
| **`impressionsClickThroughRate` (= CTR)** | サムネ CTR | |
| `audienceWatchRatio` | 視聴維持グラフ用 | dimensions=elapsedVideoTimeRatio が必要 |

**注: `impressions` と `impressionsClickThroughRate` は `dimensions=video` と組み合わせて取得可能だが、`startDate`/`endDate` 範囲のデータのみ。リアルタイムではない。**

### 2-3. レイテンシ

- 公式: **「up to 72 hours」** の遅延
- 実態: 多くのメトリクスで **2-3 日**、`impressions/CTR` は特に集計が遅く 24-72h 後に確定
- 当日のデータも返るが値が暫定 → 後日確定値に修正される
- YouTube Studio UI の「リアルタイム」(48時間表示) は別系統 (Realtime レポート) で、Analytics API には公開されていない

### 2-4. クォータ

- Data API と **別枠** (Analytics API は通常 50,000 queries/day がデフォルト, 1 リクエスト = 1 query)
- 10 分ごと (= 144回/日) 1チャンネルなら全く問題なし
- 動画ごとの個別取得でも `filters=video==id1,id2,...` で複数まとめて 1 クエリにできる

### 判定: ○ (ダッシュボードのほぼ全メトリクスをカバー、ただし 1-3 日遅延)

---

## 3. YouTube Studio 内部 API (Innertube / `studio.youtube.com`)

### 3-1. 実体
- 本番ドメイン: `studio.youtube.com/youtubei/v1/...`
  - 例: `/youtubei/v1/creator/get_creator_videos`, `/youtubei/v1/creator/list_creator_videos`, `/youtubei/v1/analytics2/get_screen` 等
- 一般 YouTube 用と同じ Innertube プロトコル (POST + JSON body + `INNERTUBE_API_KEY`)
- 認証: **SAPISID cookie + Origin ヘッダ + 現在時刻** から HMAC-SHA1 ハッシュを作って `Authorization: SAPISIDHASH <timestamp>_<hash>` を付与
  ```
  HASH = SHA1(timestamp + " " + SAPISID + " " + origin)
  ```
- 必要 cookie: `SID`, `HSID`, `SSID`, `APISID`, `SAPISID`, `LOGIN_INFO` (場合により `SESSION_TOKEN` / `__Secure-1PSID` 等)

### 3-2. 公式ドキュメントの有無
- **存在しない。** YouTube Data API / Analytics API の公開仕様には含まれていない
- YouTube API Services Terms of Service の "scraping/automated access" 制限の対象になり得るグレーゾーン
- BAN リスク: 個人チャンネルかつ低頻度なら実害は稀だが **ToS 違反扱いになる可能性は明確に存在する**

### 3-3. OSS 事例
- **`adasq/youtube-studio` (Node)**: 動画メタデータ・収益化設定・エンドカード等を編集できる。SAPISID hash 認証実装あり
- **`yusufusta/ytstudio` (Node)**: 同上, よりシンプル。ドキュメントあり (https://yusufusta.github.io/ytstudio/)
- **`Tyrrrz/YoutubeExplode`**: 視聴側の `youtubei/v1/player` を叩く実装。Studio 領域は対象外
- **`zerodytrash/YouTube-Internal-Clients`**: 隠し API クライアント ID の研究
- Social Blade / mixerno.space / livecounts.io は **公式 Data API + 高頻度ポーリング + 過去履歴推定** がベース。「丸められた値」をベースに増減トレンドから "exact" を推定しているだけで、**真の丸め回避はしていない** (Social Blade 自身が 2019 年に「もう正確な数字は取れない」と公式声明)

### 3-4. リアルタイム取得可能項目
- 登録者数: ほぼリアルタイム (UI 同等)
- 動画ごとの過去 48 時間視聴数 (Studio の "Realtime activity" カード相当): **取れる**
- ただしエンドポイントが頻繁に変わる、cookie が切れたら全停止、2FA との相性問題

### 判定: △ (取れるが非公式・保守コスト高・ToS リスク)

---

## 4. その他の手段

| 手段 | 結論 | 備考 |
|---|---|---|
| Social Blade API | × | 元データが Data API なので **同じく 3桁丸め**。彼らの "Estimated" は推定値 |
| mixerno.space / livecounts.io | × | 同上。Data API + 高頻度ポーリング + 増減推定。**真値ではない** |
| 古い Channel Statistics ガジェット (`gdata.youtube.com`) | × | 2015年に廃止 (v2 API 終了) |
| Subscribe Button widget | × | 表示のみ、値は丸められたものを表示 |
| YouTube Reporting API (バルクCSV) | △ | レイテンシ更に遅い (毎日 1 ファイル, 24h+遅延)。10分更新ダッシュには不向き |
| WebSub / PubSubHubbub | × | 動画公開のプッシュ通知のみ。統計は取れない |
| YouTube Studio の DOM スクレイピング (現行手法) | △ | 現行採用中。動くが壊れやすい・コスト高 |

---

## 5. 各論点の最終判定マトリクス

| 取りたいデータ | Data API | Analytics API | Studio内部 API | DOM解析 | Social Blade |
|---|---|---|---|---|---|
| 登録者数 (1人単位) | × (3桁丸め) | ○ (差分累積) | ○ (UI同等) | ○ | × (元が Data API) |
| 動画 views | △ (累計のみ, リアルタイムでない) | ○ (期間指定可) | ○ | △ | × |
| averageViewPercentage (視聴維持率) | × | ○ | ○ | ○ | × |
| impressions / CTR | × | ○ (1-3日遅延) | ○ (Studio UI同等) | ○ | × |
| 直近 24-48h views | × | △ (遅延あり) | ○ | ○ | × |
| 動画タイトル/サムネ/公開日 | ○ | × | ○ | ○ | △ |

---

## 6. 重要な前提 — OAuth トークンの紐付き先

**実機検証 (2026-04-30) で判明した重大な制約:**

現在の `youtube-oauth/token.json` の OAuth ユーザーは `mine=true` で
チャンネル ID `UCPlyd38TWD-2jiXQwsUa0bA` (動画 0 本, sub 0) を返す。
これは **AKIRA.M (`UCXDnQrp8Sao7ZmpL9Ws-SLA`) ではない別チャンネル** (恐らく Google アカウント直下の personal channel)。

→ **Analytics API を `ids=channel==MINE` で叩くと AKIRA.M のデータが取れない。**
→ **`ids=channel==UCXDnQrp8Sao7ZmpL9Ws-SLA` を直接指定すると 403 Forbidden。**

これにより現状 Analytics API は AKIRA.M に対して**事実上使えていない**。
そのため DOM 解析に依存している、というのが今のダッシュボードの実体と整合する。

### 解決策
1. **OAuth 取り直し**: `setup_oauth.py` を AKIRA.M (ブランドアカウント) の選択画面が出る状態で再実行し、AKIRA.M を選んで認可する
   - Google アカウントログイン後にブランドアカウント選択画面が出るので、そこで AKIRA.M を選ぶ
   - 取得後 `mine=true` で `UCXDnQrp8Sao7ZmpL9Ws-SLA` が返ることを確認
2. それが完了すれば本ドキュメントの推奨構成 (Analytics API 主体) がそのまま動く

---

## 7. 推奨ダッシュボード構成 (再掲・詳細版)

```
[10分ごと cron]
   │
   ├─ Data API (channels.list, id=UCXDn...)         ← 表示用 viewCount/videoCount/動画一覧
   │     cost: 1 unit, 丸めOK (登録者は使わない)
   │
   ├─ Analytics API
   │   ├─ dimensions=day, metrics=subscribersGained,subscribersLost
   │   │     → 累積デルタで現在の登録者数を算出 (基準値 1653 + Σdelta)
   │   │
   │   └─ dimensions=video, filters=video==id1,...,id_n,
   │         metrics=views,estimatedMinutesWatched,
   │                 averageViewPercentage,impressions,
   │                 impressionsClickThroughRate
   │     → 動画ごとの視聴維持率・CTR・views を一括取得
   │
   └─ (フォールバック) Studio 内部 API
         登録者数のリアルタイム値が必要な場合のみ。
         Cookie ローテーション運用必要、ToS リスクあり。
```

### 移行ステップ
1. OAuth 再認可で AKIRA.M ブランドアカウントへ切り替え (上記§6)
2. `update_dashboard.py` の動画統計取得部を Data API → Analytics API に置き換え
3. 登録者数算出: 基準値 1653 + `subscribersGained - subscribersLost` 累積
4. DOM 解析を撤去 (またはフォールバックとして残す)
5. レイテンシ表示: ダッシュボードに「動画統計は最大72時間遅延」と注記

### 「直近 24h 再生数」の取り方
- 真にリアルタイムなのは Studio 内部 API のみ
- Analytics API で代替するなら `startDate=today-1, endDate=today` を毎回投げる
  - ただし当日値は暫定 (後日修正される)
  - 現実的には「直近 24h (確定値ベースで 2-3 日前の値)」と妥協

---

## 8. 出典 / 参考リンク

- [YouTube Data API v3 Revision History (3桁丸め告知 2019-09-10)](https://developers.google.com/youtube/v3/revision_history)
- [Channels: list reference (subscriberCount 仕様)](https://developers.google.com/youtube/v3/docs/channels/list)
- [YouTube Analytics API - Metrics 一覧](https://developers.google.com/youtube/analytics/metrics)
- [YouTube Analytics API - Channel Reports](https://developers.google.com/youtube/analytics/channel_reports)
- [YouTube Analytics Sample Requests](https://developers.google.com/youtube/analytics/sample-requests)
- [Variety: YouTube Will Roll Out Abbreviated Subscriber Counts (2019-05-21 告知)](https://variety.com/2019/digital/news/youtube-change-subscriber-counts-rounding-1203223404/)
- [Engadget: YouTube to abbreviate subscriber counts](https://www.engadget.com/2019-08-30-youtube-abbreviated-subscriber-counts.html)
- [adasq/youtube-studio (Unofficial Studio API, Node)](https://github.com/adasq/youtube-studio)
- [yusufusta/ytstudio API documentation](https://yusufusta.github.io/ytstudio/)
- [Tyrrrz/YoutubeExplode (Innertube reverse engineering)](https://github.com/Tyrrrz/YoutubeExplode)
- [Reverse-Engineering YouTube: Revisited (Oleksii Holub)](https://tyrrrz.me/blog/reverse-engineering-youtube-revisited)
- [zerodytrash/YouTube-Internal-Clients](https://github.com/zerodytrash/YouTube-Internal-Clients)
- [Social Blade Developers Docs](https://socialblade.com/developers/docs)
- [Issue Tracker: YouTube Analytics 3 days slow](https://issuetracker.google.com/issues/247364351)
