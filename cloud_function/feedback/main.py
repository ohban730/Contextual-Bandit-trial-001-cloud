"""feedback用Cloud Run function。

直前にsuggestしたpendingへの評価(good/bad)を受け取り、
文脈付きバンディット(bandit_gcs.py)を更新する。
"""
import os

import numpy as np
import functions_framework
from flask import jsonify

from bandit_gcs import FEATURE_NAMES, GCSJsonStore, LinearThompsonSamplingBandit

BUCKET_NAME = os.environ["GCS_BUCKET_NAME"]


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
def feedback(request):
    
    # プリフライト(OPTIONS)への応答
    if request.method == "OPTIONS":
        headers = {
            "Access-Control-Allow-Origin": "*",
            "Access-Control-Allow-Methods": "GET, POST",
            "Access-Control-Allow-Headers": "Content-Type",
            "Access-Control-Max-Age": "3600",
        }
        return ("", 204, headers)
    """直前にsuggestしたpendingへの評価(good/bad)を受け取り、banditを更新する。

    パラメータ: label=good または label=bad（クエリ文字列でもJSONボディでも可）
    """
    label = _param(request, "label")
    if label not in ("good", "bad"):
        return _cors_json({"error": "labelはgoodかbadを指定してください"}, 400)

    store = GCSJsonStore(BUCKET_NAME)
    bandit = LinearThompsonSamplingBandit(store)
    pending = bandit.load_pending()
    if pending is None:
        return _cors_json({"error": "評価対象の提案がありません。先にsuggestを呼んでください。"}, 404)

    reward = 1.0 if label == "good" else 0.0
    bandit.update(np.array(pending["context"]), reward)
    bandit.log_feedback(pending["channel_name"], label)
    bandit.clear_pending()

    theta = bandit.theta_mean
    return _cors_json(
        {
            "channel_name": pending["channel_name"],
            "label": label,
            "theta": dict(zip(FEATURE_NAMES + ["bias"], theta.tolist())),
        }
    )
