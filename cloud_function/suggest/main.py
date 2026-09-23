"""suggest用Cloud Run function。

ローカル側がアップロードした候補一覧(candidates.json)を読み、
スコアリング(scoring.py)と文脈付きバンディット(bandit_gcs.py)で1件選ぶ。
"""
import os

import functions_framework
import numpy as np
from flask import jsonify

from bandit_gcs import FEATURE_NAMES, GCSJsonStore, LinearThompsonSamplingBandit
from scoring import score_candidates

BUCKET_NAME = os.environ["GCS_BUCKET_NAME"]
CANDIDATES_BLOB = "candidates.json"


def _param(request, name: str, default=None):
    value = request.args.get(name)
    if value is not None:
        return value
    body = request.get_json(silent=True) or {}
    return body.get(name, default)

def _cors_json(payload, status=200):
    response = jsonify(payload)
    response.headers["Access-Control-Allow-Origin"] = "*"
    return response, status


@functions_framework.http
def suggest(request):

    # プリフライト(OPTIONS)への応答
    if request.method == "OPTIONS":
        headers = {
            "Access-Control-Allow-Origin": "*",
            "Access-Control-Allow-Methods": "GET, POST",
            "Access-Control-Allow-Headers": "Content-Type",
            "Access-Control-Max-Age": "3600",
        }
        return ("", 204, headers)
    """スコアリング済みでない候補一覧を読み、フィルタ→スコアリング→Thompson Samplingで1件選ぶ。

    クエリパラメータ(任意): min_watch_count(デフォルト2), category
    """
    store = GCSJsonStore(BUCKET_NAME)
    candidates = store.read(CANDIDATES_BLOB)
    if not candidates:
        return (
            _cors_json({"error": f"{CANDIDATES_BLOB}が見つかりません。ローカルでrun_pipeline.pyを実行してアップロードしてください。"}, 404)
            
        )

    min_watch_count = int(_param(request, "min_watch_count", 2))
    filtered = [c for c in candidates if c["watch_count"] >= min_watch_count] or candidates

    category = _param(request, "category")
    if category:
        by_category = [
            c for c in filtered if (c.get("dominant_category_name") or "").casefold() == category.casefold()
        ]
        if not by_category:
            available = sorted({c["dominant_category_name"] for c in filtered if c.get("dominant_category_name")})
            return (
                _cors_json({"error": f"「{category}」に一致する候補がありません。候補にあるジャンル: {', '.join(available)}"}, 404)
            )
        filtered = by_category

    scored = score_candidates(filtered)

    bandit = LinearThompsonSamplingBandit(store)
    already_judged = bandit.already_judged_channels()
    remaining = [c for c in scored if c["channel_name"] not in already_judged]
    if not remaining:
        return _cors_json({"error": "条件に合う候補はすべて評価済みです。条件を変えて試してください。"}, 404)

    context_matrix = np.array([[c[name] for name in FEATURE_NAMES] for c in remaining], dtype=float)
    sampled_scores = bandit.sample_scores(context_matrix)
    best_idx = int(np.argmax(sampled_scores))
    chosen = remaining[best_idx]
    chosen_context = context_matrix[best_idx]

    suggestion_id = bandit.save_pending(
        chosen["channel_name"], chosen_context, extra={"last_video_title": chosen.get("last_video_title")}
    )

    return _cors_json(
        {
            "suggestion_id": suggestion_id,
            "channel_name": chosen["channel_name"],
            "last_video_title": chosen.get("last_video_title"),
            "watch_count": chosen["watch_count"],
            "dominant_category_name": chosen.get("dominant_category_name"),
            "context": dict(zip(FEATURE_NAMES, chosen_context.tolist())),
            "sampled_score": float(sampled_scores[best_idx]),
            "reference_top5": [
                {
                    "channel_name": c["channel_name"],
                    "last_video_title": c.get("last_video_title"),
                    "watch_count": c["watch_count"],
                    "score": c["score"],
                }
                for c in scored[:5]
            ],
        }
    )
