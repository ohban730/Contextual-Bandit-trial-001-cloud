"""チャンネルに点数をつける処理（旧src/watch_recommender/score.py）。

ローカル側はcandidates.jsonにrecency/frequencyのもとになる生データ(watch_count,
last_watched)を入れるだけで、「今から何日前か」の計算はリクエストのたびにこちら側で
行う（アップロード時刻ではなく参照時刻を基準にするため）。DataFrameは使わずnumpy配列
だけで計算し、依存を増やさない。
"""
from datetime import datetime, timezone

import numpy as np

RECENCY_WEIGHT = 0.4
FREQUENCY_WEIGHT = 0.2
GENRE_WEIGHT = 0.2
SEMANTIC_WEIGHT = 0.2


def _normalize(values: np.ndarray) -> np.ndarray:
    lo, hi = values.min(), values.max()
    if hi == lo:
        return np.full_like(values, 0.5, dtype=float)
    return (values - lo) / (hi - lo)


def score_candidates(candidates: list, now: datetime = None) -> list:
    """久しぶり度・好きだった度・ジャンル一致度・意味の近さから総合点をつけ、降順で返す。"""
    now = now or datetime.now(timezone.utc)

    last_watched = [datetime.fromisoformat(c["last_watched"]) for c in candidates]
    days_since_last_watch = np.array([(now - lw).total_seconds() / 86400 for lw in last_watched])
    watch_count = np.array([c["watch_count"] for c in candidates], dtype=float)

    recency_score = _normalize(days_since_last_watch)
    frequency_score = _normalize(watch_count)

    weighted_sum = RECENCY_WEIGHT * recency_score + FREQUENCY_WEIGHT * frequency_score
    active_weight = RECENCY_WEIGHT + FREQUENCY_WEIGHT

    has_genre = all("genre_score" in c for c in candidates)
    genre_score = np.array([c.get("genre_score", 0.0) for c in candidates], dtype=float)
    if has_genre:
        weighted_sum = weighted_sum + GENRE_WEIGHT * genre_score
        active_weight += GENRE_WEIGHT

    has_semantic = all("semantic_score" in c for c in candidates)
    semantic_score = np.array([c.get("semantic_score", 0.0) for c in candidates], dtype=float)
    if has_semantic:
        weighted_sum = weighted_sum + SEMANTIC_WEIGHT * semantic_score
        active_weight += SEMANTIC_WEIGHT

    scored = [
        {
            **c,
            "recency_score": float(recency_score[i]),
            "frequency_score": float(frequency_score[i]),
            "genre_score": float(genre_score[i]),
            "semantic_score": float(semantic_score[i]),
            "score": float(weighted_sum[i] / active_weight),
        }
        for i, c in enumerate(candidates)
    ]
    return sorted(scored, key=lambda c: c["score"], reverse=True)
