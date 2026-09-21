# run_pipeline.py の説明書

## ひとことでいうと
ここまで説明してきた「ローカル(GPU)側」の係(ファイル)を順番に呼び出して、
チャンネルごとの候補データを作り、Cloud Storageにアップロードするところまでを
行う**司令塔(しれいとう)となるプログラム**です。あなたが実際にターミナルで
実行するのは、このファイルです。

「おすすめを1件もらう」「good/badを評価する」はこのファイルの仕事ではなく、
Cloud Run functionsとしてデプロイした`suggest`用・`feedback`用の2つのURLを
ブラウザやcurlで直接呼んで行います(詳しくは[bandit.md](bandit.md)・[score.md](score.md)を参照)。

## なにをしているところ？

料理でいうなら、これまでのファイルが「野菜を切る係」「お肉を焼く係」
「味付けする係」だとすると、`run_pipeline.py`はそれらを正しい順番で呼び出して
「素材を仕込んで、あとは注文が来たら仕上げるだけの状態にして冷蔵庫(Cloud Storage)
にしまっておく」ところまでを担当します。「仕上げ」(総合点をつけて1つ選ぶ)は
別の場所(Cloud Run functions)で行われます。

## 実行すると起きること

```
python scripts/run_pipeline.py
```

1. `load_watch_history()` で視聴履歴を読みこむ
2. (オプションで)`--title-regex` により、特定のタイトルの動画だけに絞る
3. `aggregate_by_channel()` でチャンネルごとに集計する
4. (`--no-enrich`を付けていなければ)`fetch_video_metadata` と
   `add_genre_scores` でジャンルの一致度を計算する
5. (`--no-semantic`を付けていなければ)`embed_video_titles` と
   `add_semantic_scores` で意味の近さを計算する
6. `channel_name`/`last_video_title`/`watch_count`/`last_watched`/
   `genre_score`/`semantic_score`(などの列)だけを取り出し、
   `data/processed/candidates.json`に書き出す
7. (`--no-upload`を付けていなければ)`upload_candidates()`で、その
   `candidates.json`をCloud Storage(`GCS_BUCKET_NAME`で指定したバケット)に
   アップロードする

ここで終わりです。「総合点をつける」(旧`score_channels()`、今は
[cloud_function/suggest/scoring.py](../cloud_function/suggest/scoring.py))も「1件選ぶ」
(`bandit`)も、Cloud Run functionsの`suggest`用URLを呼んだときに初めて動きます。
`--min-watch-count`や`--category`による絞り込みも、今は`suggest`用URLを呼ぶときの
クエリパラメータ(`?min_watch_count=2&category=Music`)として指定します。

## 提案を見る・評価する

このスクリプトの仕事ではありませんが、流れとして知っておくと理解しやすいです。
`suggest`用と`feedback`用は、同じソースからentry-point違いでデプロイされた
別々のCloud Run functionsなので、URLも別々です。

```
curl "https://<suggestのURL>?min_watch_count=2"
curl "https://<feedbackのURL>?label=good"
```

- `suggest`: `candidates.json`を読み込み、[scoring.py](../cloud_function/suggest/scoring.py)で
  総合点(recency_score/frequency_score)を計算し、すでに評価済み・お休み中のチャンネルを
  除外したあと、`bandit.sample_scores()`でThompson Samplingにより1件選んで`pending`として
  保存し、結果を返す
- `feedback`: `pending`を読み込み、`good`なら`reward=1.0`、`bad`なら`reward=0.0`として
  `bandit.update()`で学習させ、`log_feedback()`で評価済みとして記録する

## 出てくる主な道具

### `argparse`
ターミナルで打ちこむオプション(`--no-semantic`のようなもの)を
読み取るための、Python標準の道具です。`--help`を付けて実行すると、
それぞれのオプションの説明が表示されます。

### `sys.path.insert(0, ...)`
このファイルは`scripts`フォルダにありますが、中身は`src`フォルダの
プログラム(`watch_recommender`パッケージ)を使いたいので、
「ここも探しにいってね」とPythonに教えているおまじないです。

### `re.compile(args.title_regex, re.IGNORECASE)`
`--title-regex`オプションで、たとえば`"MV|MAD"`のような
「動画タイトルの中に含まれていてほしい文字パターン」を指定できます。
`re.IGNORECASE`は「大文字・小文字を区別しない」という設定です。

## 具体的な流れの例

初めてこのプログラムを実行したとしましょう(まだ評価履歴がありません)。

```
python scripts/run_pipeline.py --no-enrich --no-semantic
```

これで`candidates.json`がアップロードされます。続けて`suggest`用URLを呼ぶと、

```
curl "https://<suggestのURL>"
```

`bandit`はまだ何も学習していないので、`sample_scores`はほぼランダムに近い
選び方でチャンネルを1つ選びます。表示された提案が気に入ったら

```
curl "https://<feedbackのURL>?label=good"
```

を呼ぶと、そのチャンネルの特徴(`recency_score`などの組み合わせ)が
「良い」として記憶され、次に`suggest`用URLを呼んだときには、似た特徴を持つ
チャンネルが選ばれやすくなっていきます。

## もっと知りたい人へ
- `sys.stdout.reconfigure(encoding="utf-8")`: 日本語などの文字が
  ターミナルで文字化けしないように、出力の文字コードを指定しています。
- `# noqa: E402`: 「本来はファイルの先頭にimportを書くべき」という
  Pythonの作法(スタイルチェッカーの警告)を、あえて無視する印です。
  ここでは`sys.path`を先に設定してからimportする必要があるための
  やむを得ない例外です。
