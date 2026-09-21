"""文脈付きバンディット本体（線形回帰+Thompson Sampling）。状態はCloud Storageに保存する。

ローカル側(src/watch_recommender)はGPUでの埋め込み計算・スコアリングのみ担当し、
banditの学習・状態管理はこちら側だけで完結させる構成のため、ロジックをここに集約している。

suggest用・feedback用の各インスタンスがそれぞれ自己完結したソースフォルダである必要が
あるため、このファイルは cloud_function/suggest/bandit_gcs.py と同じ内容を2箇所に
置いている。直したときは両方に反映すること。
"""
import json
from datetime import datetime, timedelta, timezone
from typing import Optional

import numpy as np
from google.cloud import storage

# src/watch_recommender/config.pyのFEATURE_NAMESと順序・名前を一致させること。
FEATURE_NAMES = ["recency_score", "frequency_score", "genre_score", "semantic_score"]

# good評価はこの日数だけ除外し、以後は再び候補になり得る（badは永久に除外）
GOOD_COOLDOWN_DAYS = 30

BANDIT_STATE_BLOB = "bandit_state.json"
PENDING_SUGGESTION_BLOB = "pending_suggestion.json"
SUGGESTION_LOG_BLOB = "suggestion_log.json"


class GCSJsonStore:
    """Cloud Storage上のJSONオブジェクトを読み書きする薄いラッパー。"""

    def __init__(self, bucket_name: str):
        self._bucket = storage.Client().bucket(bucket_name)

    def read(self, blob_name: str):
        blob = self._bucket.blob(blob_name)
        if not blob.exists():
            return None
        return json.loads(blob.download_as_text())

    def write(self, blob_name: str, data) -> None:
        blob = self._bucket.blob(blob_name)
        blob.upload_from_string(json.dumps(data, ensure_ascii=False), content_type="application/json")

    def delete(self, blob_name: str) -> None:
        blob = self._bucket.blob(blob_name)
        if blob.exists():
            blob.delete()


class LinearThompsonSamplingBandit:
    """フィードバック1件ごとに重み(theta)の確信度をその場で更新する文脈付きバンディット。"""

    def __init__(
        self,
        store: GCSJsonStore,
        feature_names=FEATURE_NAMES,
        alpha: float = 1.0,
        lambda_: float = 1.0,
    ):
        self.store = store
        self.feature_names = feature_names
        self.alpha = alpha
        self.lambda_ = lambda_
        self.d = len(feature_names) + 1  # +1 はバイアス項
        self.A, self.b = self._load_state()

    def _load_state(self):
        data = self.store.read(BANDIT_STATE_BLOB)
        if data is not None:
            return np.array(data["A"]), np.array(data["b"])
        return self.lambda_ * np.eye(self.d), np.zeros(self.d)

    def _save_state(self) -> None:
        self.store.write(
            BANDIT_STATE_BLOB,
            {"A": self.A.tolist(), "b": self.b.tolist(), "feature_names": self.feature_names},
        )

    @staticmethod
    def _with_bias(context_matrix: np.ndarray) -> np.ndarray:
        bias = np.ones((context_matrix.shape[0], 1))
        return np.hstack([context_matrix, bias])

    @property
    def theta_mean(self) -> np.ndarray:
        return np.linalg.inv(self.A) @ self.b

    def sample_scores(self, context_matrix: np.ndarray) -> np.ndarray:
        """各候補について事後分布からthetaを1回サンプリングし、予測スコアを返す。"""
        X = self._with_bias(context_matrix)
        A_inv = np.linalg.inv(self.A)
        theta_hat = A_inv @ self.b
        theta_sample = np.random.multivariate_normal(theta_hat, (self.alpha**2) * A_inv)
        return X @ theta_sample

    def update(self, context: np.ndarray, reward: float) -> None:
        x = np.append(context, 1.0)
        self.A += np.outer(x, x)
        self.b += reward * x
        self._save_state()

    def save_pending(self, channel_name: str, context: np.ndarray, extra: Optional[dict] = None) -> None:
        payload = {"channel_name": channel_name, "context": context.tolist(), **(extra or {})}
        self.store.write(PENDING_SUGGESTION_BLOB, payload)

    def load_pending(self) -> Optional[dict]:
        return self.store.read(PENDING_SUGGESTION_BLOB)

    def clear_pending(self) -> None:
        self.store.delete(PENDING_SUGGESTION_BLOB)

    def log_feedback(self, channel_name: str, label: str, judged_at: Optional[datetime] = None) -> None:
        """評価済みのチャンネルを記録する（同じチャンネルを繰り返し提案しないようにするため）。"""
        judged_at = judged_at or datetime.now(timezone.utc)
        log = self._load_log()
        log.append({"channel_name": channel_name, "label": label, "judged_at": judged_at.isoformat()})
        self.store.write(SUGGESTION_LOG_BLOB, log)

    def _load_log(self) -> list:
        return self.store.read(SUGGESTION_LOG_BLOB) or []

    def already_judged_channels(self, now: Optional[datetime] = None) -> set:
        """今、除外すべきチャンネル名の集合。

        bad評価は永久に除外する。good評価はGOOD_COOLDOWN_DAYS日だけ除外し、それ以降は
        再び候補になり得る（同じチャンネルに複数回評価がある場合は最新の評価を優先する）。
        """
        now = now or datetime.now(timezone.utc)
        latest_by_channel: dict = {}
        for entry in self._load_log():
            latest_by_channel[entry["channel_name"]] = entry  # 後に追記された方で上書き

        excluded = set()
        for channel_name, entry in latest_by_channel.items():
            if entry["label"] == "bad":
                excluded.add(channel_name)
                continue
            judged_at_str = entry.get("judged_at")
            if judged_at_str is None:
                excluded.add(channel_name)  # 記録形式が古い場合は安全側に倒して除外を継続
                continue
            judged_at = datetime.fromisoformat(judged_at_str)
            if now - judged_at < timedelta(days=GOOD_COOLDOWN_DAYS):
                excluded.add(channel_name)
        return excluded
