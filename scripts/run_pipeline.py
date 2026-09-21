#!/usr/bin/env python
"""視聴履歴からチャンネルごとの候補データを作り、Cloud Storageにアップロードするローカル用CLI。

GPUが要る処理（YouTube Data APIでのメタデータ補完・タイトルの埋め込みベクトル化）は
ここでだけ行う。スコアリング(recency/frequency)と文脈付きバンディットによる選択・学習は
Cloud Run functions側（cloud_function/）が担当するので、このスクリプトはcandidates.jsonを
作ってアップロードするところまでで完了する。提案の閲覧・good/bad評価はCloud Run functions
のURL(suggest用・feedback用の2つ)をブラウザやcurlで直接叩く。
"""
import argparse
import json
import re
import sys
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")
sys.stderr.reconfigure(encoding="utf-8")

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from watch_recommender.aggregate import aggregate_by_channel  # noqa: E402
from watch_recommender.config import CANDIDATES_PATH, GCS_BUCKET_NAME, YOUTUBE_API_KEY  # noqa: E402
from watch_recommender.embeddings import embed_video_titles  # noqa: E402
from watch_recommender.enrich import fetch_video_metadata  # noqa: E402
from watch_recommender.genre import add_genre_scores  # noqa: E402
from watch_recommender.load_history import load_watch_history  # noqa: E402
from watch_recommender.semantic import add_semantic_scores  # noqa: E402


def upload_candidates(candidates: list) -> None:
    if not GCS_BUCKET_NAME:
        print(
            "GCS_BUCKET_NAMEが未設定です。.envにCloud Storageのバケット名を設定してください。",
            file=sys.stderr,
        )
        sys.exit(1)

    from google.cloud import storage

    bucket = storage.Client().bucket(GCS_BUCKET_NAME)
    bucket.blob("candidates.json").upload_from_string(
        json.dumps(candidates, ensure_ascii=False), content_type="application/json"
    )


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--no-enrich", action="store_true", help="YouTube Data APIでのメタデータ補完・ジャンル関連度の計算をスキップ"
    )
    parser.add_argument("--no-semantic", action="store_true", help="タイトル埋め込みによる意味検索スコアの計算をスキップ")
    parser.add_argument(
        "--title-regex",
        help="動画タイトルがこの正規表現にマッチする視聴だけを対象にする（例: 'MV|MAD'）。チャンネルではなく動画の種類で絞りたいときに使う",
    )
    parser.add_argument("--no-upload", action="store_true", help="Cloud Storageへのアップロードをスキップし、ローカル保存だけ行う")
    args = parser.parse_args()

    history_df = load_watch_history()
    if history_df.empty:
        print("視聴履歴が読み込めませんでした。data/raw/watch-history.json を確認してください。", file=sys.stderr)
        sys.exit(1)

    if args.title_regex:
        try:
            pattern = re.compile(args.title_regex, re.IGNORECASE)
        except re.error as e:
            print(f"--title-regexの正規表現が不正です: {e}", file=sys.stderr)
            sys.exit(1)
        history_df = history_df[history_df["video_title"].str.contains(pattern, na=False)]
        if history_df.empty:
            print(f"「{args.title_regex}」に一致する視聴履歴が見つかりませんでした。", file=sys.stderr)
            sys.exit(1)

    channel_df = aggregate_by_channel(history_df)

    if args.no_enrich:
        pass
    elif not YOUTUBE_API_KEY:
        print("YOUTUBE_API_KEY未設定のため、ジャンル関連度はスキップします（.envを確認してください）。\n", file=sys.stderr)
    else:
        print("YouTube Data APIでメタデータを取得中（初回は数分かかる場合があります）...\n", file=sys.stderr)
        metadata_df = fetch_video_metadata(history_df["video_id"].dropna().unique())
        channel_df = add_genre_scores(channel_df, history_df, metadata_df)
    if "genre_score" not in channel_df.columns:
        channel_df["genre_score"] = 0.0

    if not args.no_semantic:
        print("動画タイトルを埋め込みベクトル化中（初回は数分かかる場合があります）...\n", file=sys.stderr)
        video_id_to_title = (
            history_df.dropna(subset=["video_id"])
            .drop_duplicates("video_id")
            .set_index("video_id")["video_title"]
            .to_dict()
        )
        embedding_df = embed_video_titles(video_id_to_title)
        channel_df = add_semantic_scores(channel_df, history_df, embedding_df)
    if "semantic_score" not in channel_df.columns:
        channel_df["semantic_score"] = 0.0

    columns = ["channel_name", "last_video_title", "watch_count", "last_watched", "genre_score", "semantic_score"]
    if "dominant_category_name" in channel_df.columns:
        columns.append("dominant_category_name")

    candidates_df = channel_df[columns].copy()
    candidates_df["last_watched"] = candidates_df["last_watched"].apply(lambda ts: ts.isoformat())
    candidates = candidates_df.to_dict(orient="records")

    CANDIDATES_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(CANDIDATES_PATH, "w", encoding="utf-8") as f:
        json.dump(candidates, f, ensure_ascii=False)

    print(f"=== 視聴履歴サマリー: {len(history_df)}件 / {len(channel_df)}チャンネル ===")
    print(f"候補{len(candidates)}件を{CANDIDATES_PATH}に書き出しました。")

    if args.no_upload:
        return

    upload_candidates(candidates)
    print(f"Cloud Storage(gs://{GCS_BUCKET_NAME}/candidates.json)にアップロードしました。")
    print("提案を見るには、デプロイ済みのCloud Run functions(suggest)のURLをブラウザ/curlで開いてください。")


if __name__ == "__main__":
    main()
