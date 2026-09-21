# Watch Recommender

YouTube視聴履歴から「最近見てないけど昔よく見た」動画を1件、文脈付きバンディットが提案するツール。「良い/イマイチ」を返すたびにその場で好みを学習していく。

[Contextual-Bandit-trial-001](https://github.com/ohban730/Contextual-Bandit-trial-001)の派生（クラウド構成を試すための派生テーマ）。ロジック本体（bandit・スコアリング）は同じで、こちらではその一部をCloud Run functionsに切り出している。

## セットアップ

### 1. Python環境

既存のconda環境 `llm-sandbox`（`pandas`/`requests`/`python-dotenv`/`sentence-transformers`/`torch`が導入済み）を使う。

```bash
conda activate llm-sandbox
pip install -r requirements.txt  # 念のため（大半は導入済みのはず）
```

### 2. Google Takeoutから視聴履歴を取得

1. https://takeout.google.com/ にアクセス
2. 「すべて選択を解除」→ **YouTube と YouTube Music** のみチェック
3. 「複数の形式」→ **履歴** を **JSON** 形式に変更（デフォルトはHTMLなので注意）
4. エクスポートを作成しダウンロード
5. 展開後、`Takeout/YouTube and YouTube Music/history/watch-history.json` を、このプロジェクトの `data/raw/watch-history.json` にコピー

### 3. YouTube Data APIキー（任意、ジャンル関連度を使う場合）

1. [Google Cloud Console](https://console.cloud.google.com/) でプロジェクト作成 → 「APIとサービス」→「ライブラリ」から **YouTube Data API v3** を有効化 → 「認証情報」→「APIキーを作成」
2. `.env.example` を `.env` にコピーし、取得したキーを `YOUTUBE_API_KEY` に設定（1日あたり無料枠1万クォータ、動画情報取得は1リクエストあたり1クォータ程度なので個人利用では十分足りる）
3. キーが無い場合はジャンル関連度の計算だけが自動でスキップされ、他の機能はそのまま動く

### 4. ローカルで候補データを作ってアップロード

```bash
python scripts/run_pipeline.py
```

これで行われるのはここまで（提案の選択やフィードバックの記録はしない）:

1. 視聴履歴を読み込み、チャンネルごとに集計
2. (`--no-enrich`を付けていなければ)YouTube Data APIでメタデータ補完・`genre_score`を計算
3. (`--no-semantic`を付けていなければ)タイトルを埋め込みベクトル化(GPU)し`semantic_score`を計算
4. 各チャンネルの`channel_name`/`last_video_title`/`watch_count`/`last_watched`/`genre_score`/`semantic_score`を`data/processed/candidates.json`に書き出す
5. `GCS_BUCKET_NAME`に設定したCloud Storageバケットへ`candidates.json`としてアップロード

出力例:
```
=== 視聴履歴サマリー: 27358件 / 7985チャンネル ===
候補7985件をdata/processed/candidates.jsonに書き出しました。
Cloud Storage(gs://watch-recommender-xxxx/candidates.json)にアップロードしました。
提案を見るには、デプロイ済みのCloud Run functions(suggest)のURLをブラウザ/curlで開いてください。
```

オプション:
- `--no-enrich`: YouTube Data APIでのメタデータ補完・ジャンル関連度をスキップ
- `--no-semantic`: タイトル埋め込みによる意味検索スコアをスキップ
- `--title-regex <正規表現>`: 動画タイトルがこの正規表現にマッチする視聴だけを対象にする。チャンネル単位ではなく「動画の種類」で絞りたいとき用（例: `--title-regex "\bMV\b|\bMAD\b"` でMV・MAD動画だけに絞る。単純に`"MV|MAD"`にすると英単語の"made"などに部分一致して誤検出が増えるので`\b`で単語境界を付けるのがコツ）
- `--no-upload`: Cloud Storageへのアップロードをスキップし、`data/processed/candidates.json`への書き出しだけ行う

初回実行時はYouTube Data APIの呼び出しとタイトルの埋め込みベクトル化が走るため数分かかることがある。結果は `data/processed/video_metadata.json`（メタデータ）と `data/processed/video_embeddings.npz`（埋め込みベクトル）にキャッシュされ、2回目以降は未取得分のみ処理するので数秒で終わる。

### 5. 提案を見る／評価する（Cloud Run functionsを直接呼ぶ）

`candidates.json`のアップロードが終わったら、あとはデプロイ済みのCloud Run functionsの
URLを直接叩く（ローカルのスクリプトはここに関与しない）。`suggest`用・`feedback`用で
別々のURLになる。

```bash
# 提案を1件もらう（min_watch_count, categoryは省略可）
curl "https://<suggestのURL>?min_watch_count=2"

# 気に入ったら
curl "https://<feedbackのURL>?label=good"
# イマイチなら
curl "https://<feedbackのURL>?label=bad"
```

`/suggest`のクエリパラメータ:
- `min_watch_count`: 候補にする最小累計視聴回数（デフォルト2、いいね的な一見動画を除外）
- `category`: 候補をそのジャンルだけに絞る（例: `category=Music`。`dominant_category_name`と一致させる。ジャンル補完が必要）

`good`か`bad`を返したチャンネルは`suggestion_log.json`（Cloud Storage上）に評価日時とともに記録され、以後の`/suggest`で除外される。`good`と答えても実際にそのチャンネルを視聴したわけではなく（＝視聴履歴上の`recency_score`は現実には下がらない）、1回のフィードバックだけでもbanditの重みはその候補の文脈に強く引っ張られるため、この除外が無いと同じような候補ばかりが繰り返し提案され続けてしまう。

- **bad評価は永久に除外**（[bandit_gcs.py](cloud_function/suggest/bandit_gcs.py) の `already_judged_channels`）。興味が無いという明確な意思表示なので、時間が経っても復活しない
- **good評価は`GOOD_COOLDOWN_DAYS`(デフォルト30日)だけ除外**し、それ以降は再び候補になり得る。このツールの趣旨は「たまに思い出させてくれる」ことなので、一度goodと言ったチャンネルを永久に除外する理由は薄いため
- 同じチャンネルに複数回評価がある場合は最新の評価が優先される
- 候補が尽きたとき、`suggestion_log.json`を丸ごと空にする必要は基本的にない。クールダウンにより時間経過で自然にgood評価の除外が切れていくため

## 提案ロジック — 文脈付きバンディット

各チャンネルは4つの0〜1スコアで表現される「文脈」を持つ。

```
recency_score   … 経過日数の正規化スコア（久しぶり度）
frequency_score … 過去の視聴頻度（好きだった度）
genre_score     … カテゴリIDの一致度（YouTube Data APIキーがある場合のみ、無ければ0固定）
semantic_score  … タイトル埋め込みの意味的な近さ
```

[bandit_gcs.py](cloud_function/suggest/bandit_gcs.py)（Cloud Run functionsにデプロイ、`feedback/`側にも同じ内容をコピー）が線形回帰+Thompson Samplingでこの4つの重み(theta)を管理し、フィードバックのたびに更新する。データが無いうちはthetaの確信度が低く候補選びはほぼ探索的（ランダムに近い）になり、フィードバックが貯まるほど学習した好みに沿った選択に寄っていく。固定の重み(`w1〜w4`, [scoring.py](cloud_function/suggest/scoring.py))による従来ロジックのスコアは`suggest`用URLのレスポンスに`reference_top5`として一緒に返る。

### ジャンル関連度 — [genre.py](src/watch_recommender/genre.py)

直近14日間に見た動画のカテゴリID分布（「最近見ているジャンル」）を作り、各チャンネルの主要カテゴリがそこにどれだけ含まれるかをスコア化。カテゴリIDは`videos.list`のsnippetから取得。

### 意味検索 — [embeddings.py](src/watch_recommender/embeddings.py) / [semantic.py](src/watch_recommender/semantic.py)

多言語対応の埋め込みモデル `paraphrase-multilingual-MiniLM-L12-v2`（Hugging Face / sentence-transformers、GPU使用）で動画タイトルをベクトル化。直近14日間の視聴タイトルの平均ベクトル（＝いまの興味の方向）と、各チャンネルの視聴タイトル平均ベクトルとのコサイン類似度をスコアにする。カテゴリIDが同じでも実際のタイトルが似ていない場合や、逆にカテゴリは違っても内容が近い場合を拾えるのが狙い。

### 既知の制限: 「今ハマってないジャンル」は出にくい

`genre_score`も`semantic_score`も、直近14日間によく見ているジャンル・話題を基準に計算している。そのため、直近の視聴が特定ジャンル（例: アニメ反応系）に偏っていると、それ以外のジャンル（例: 音楽）は「久しぶりだから見たい」という動機があっても両スコアが低く出てしまい、構造的に上位に出にくい。数回のフィードバックだけでこの偏りをbanditが学習しきるのは難しいため、`suggest`用URLの`category`クエリパラメータで候補を明示的にそのジャンルへ絞り込むのが実用的な回避策になる。

## クラウド構成 — score.py + bandit.pyをCloud Run functionsで動かす

`torch`/`sentence-transformers`を使う埋め込み計算・YouTube Data APIでのメタデータ補完は
GPUとAPIキーが要るためローカルのまま実行する。スコアリングと文脈付きバンディットは
`suggest`・`feedback`の2つのCloud Run functionsとして別々にデプロイする。状態
(`bandit_state.json`/`pending_suggestion.json`/`suggestion_log.json`)はCloud Storageに保存する。
ローカルとクラウドの間はHTTPで直接やり取りせず、Cloud Storage上の`candidates.json`を介した
受け渡しだけで完結する。

```
ローカル(GPU): load_history → aggregate → enrich/genre → embeddings/semantic
                                                                   │
                                                                   ▼
                                               candidates.json をGCSへアップロード
                                                                   │
                                                                   ▼
Cloud Run functions: suggest (scoring.py + bandit_gcs.py) ─ feedback (bandit_gcs.py)
                      ブラウザ/curlで直接叩く（それぞれ別URL）
```

`cloud_function/`は`suggest/`と`feedback/`の2フォルダに分かれていて、**それぞれが
そのままデプロイ対象の自己完結したソース一式**になっている(Cloud Functionsはデプロイ元
フォルダの外を参照できないため)。

```
cloud_function/
  suggest/
    main.py            # suggest(request) の実装
    bandit_gcs.py       # 文脈付きバンディット本体
    scoring.py          # スコアリング
    requirements.txt
  feedback/
    main.py            # feedback(request) の実装
    bandit_gcs.py       # suggest/と同じ内容（コピー）
    requirements.txt
```

`bandit_gcs.py`は両方で必要なため2箇所にコピーしてある。**ロジックを直すときは両方
反映すること**（各ファイル冒頭のdocstringにも注記あり）。

### デプロイ

Cloud Consoleの「Cloud Run」→「関数を作成」から、Console上で直接設定・構築した
（`gcloud` CLIは使っていない）。1つ目は`cloud_function/suggest`の中身（`main.py`/
`bandit_gcs.py`/`scoring.py`/`requirements.txt`）をアップロードしエントリポイントを
`suggest`に、2つ目は`cloud_function/feedback`の中身（`main.py`/`bandit_gcs.py`/
`requirements.txt`）をアップロードしエントリポイントを`feedback`にして、それぞれ
デプロイする（`GCS_BUCKET_NAME`環境変数も両方に設定。無料枠が効くのはus-east1/
us-west1/us-central1のバケット・リージョンのみ）。デプロイ後はConsoleの「ソースを編集」
からインラインでコードを直接いじって再デプロイでき、それぞれのフォルダには対応する
関数のファイルしか入っていないので、編集対象が混ざらない。

バケットへの読み書き権限は、各関数のデフォルトのランタイムサービスアカウントに対して
Cloud Consoleの権限設定から付与した。

`.env`にバケット名を設定する（ローカルはADC = `gcloud auth application-default login`
でこのバケットに書き込める権限があればよい）。

```
GCS_BUCKET_NAME=<上で作ったバケット名>
```

`--allow-unauthenticated`にしているためURLを知っていれば誰でも叩ける。個人利用の
簡易構成として割り切っているが、気になる場合はID トークン認証を追加する。

無料枠の目安: `flask`・`numpy`・`google-cloud-storage`だけの軽量なサービス（メモリ256MiB、
実行時間は数百ms程度）なので、個人利用（1日数回）であればCloud Runの無料枠（月200万リクエスト・
360,000GB秒）には十分収まる。

## 今後の拡張（まだ未着手）

- フィードバックが数百件貯まったら、埋め込みモデル自体を対照学習でファインチューニングし、「あなた固有の近さの感覚」をより深く反映させる

## License

[MIT](LICENSE)
