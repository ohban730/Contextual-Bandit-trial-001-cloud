import os
from pathlib import Path

from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent.parent.parent
load_dotenv(BASE_DIR / ".env")

DATA_RAW = BASE_DIR / "data" / "raw"
DATA_PROCESSED = BASE_DIR / "data" / "processed"

WATCH_HISTORY_PATH = DATA_RAW / "watch-history.json"
CANDIDATES_PATH = DATA_PROCESSED / "candidates.json"

YOUTUBE_API_KEY = os.environ.get("YOUTUBE_API_KEY", "")

# 文脈付きバンディット・スコアリング本体はCloud Runで動く（cloud_function/）。
# ローカルはスコアリング済みでない候補一覧(candidates.json)をこのバケットにアップロードするだけ。
GCS_BUCKET_NAME = os.environ.get("GCS_BUCKET_NAME", "")
