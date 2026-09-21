# config.py の説明書

## ひとことでいうと
このプログラム全体で使う「共通の設定」を1か所にまとめておく、
**"住所録＆設定ノート"** です。

## なにをしているところ？

家を建てるとき、「郵便受けはここ」「電気のスイッチはここ」と最初に
決めておくと、あとの工事がやりやすくなりますよね。それと同じで、
このファイルには

- データ(視聴履歴やキャッシュ)を**どこに保存するか**というファイルの場所
- YouTubeに問い合わせるための**秘密の合言葉(APIキー)**
- 候補データのアップロード先である**Cloud Storageバケットの名前**

が書かれています。他のファイルはぜんぶ、ここで決めた場所やルールを
`from .config import ...` で借りにきます。

（「チャンネルに点数をつけるときの重要度のバランス(重み)」は、以前はここに
`ScoringWeights`としてありましたが、点数付け自体がCloud Run functions側に
引っ越したので、今は[cloud_function/suggest/scoring.py](../cloud_function/suggest/scoring.py)の
`RECENCY_WEIGHT`などの定数になっています。）

## 出てくる主な道具

### `BASE_DIR`, `DATA_RAW`, `DATA_PROCESSED`
プロジェクトの中の「どのフォルダに何を置くか」を決めている変数です。
`DATA_RAW` は「生の(手を加えていない)データを置く場所」、
`DATA_PROCESSED` は「加工したあとのデータを置く場所」のイメージです。

### `load_dotenv(BASE_DIR / ".env")`
`.env` という秘密のメモ帳ファイルを読みこんで、`YOUTUBE_API_KEY` のような
「他の人に見られたくない合言葉」を安全に読みこむための道具です。
`.env`ファイルはGitにアップロードしない(秘密を守る)のがお約束です。

### `GCS_BUCKET_NAME`
`run_pipeline.py`が作った`candidates.json`をアップロードする先の
Cloud Storageバケット名です。`.env`の`GCS_BUCKET_NAME`から読み込みます
（Cloud Run functions側もデプロイ時に同じ名前を`GCS_BUCKET_NAME`という
環境変数として渡され、`candidates.json`やバンディットの状態ファイルを
そこから読み書きします）。

## もっと知りたい人へ
- `Path`: ファイルやフォルダの「住所」をあつかう部品(OSがWindowsでもMacでも
  同じ書き方で使えるようにしてくれます)。
- `os.environ.get("YOUTUBE_API_KEY", "")`: パソコンの中に保存された
  「環境変数」という引き出しから、APIキーを取り出します。もし無ければ
  空文字 `""` を代わりに使う、という意味です。
