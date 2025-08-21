# app/db/mongo.py
import os
from pathlib import Path
from dotenv import load_dotenv
from pymongo import MongoClient, ASCENDING

# 프로젝트 루트(AI/.env) 로드
ROOT = Path(__file__).resolve().parents[2]
load_dotenv(ROOT / ".env")

MONGODB_URI = os.getenv("MONGODB_URI")
if not MONGODB_URI:
    raise RuntimeError("MONGODB_URI not set in .env")

_client = MongoClient(MONGODB_URI)
db = _client.get_default_database()  # URI에 DB명이 들어있으면 자동 선택

# 컬렉션 핸들
problems = db["problems"]
generated = db["generated_problems"]

# 인덱스(없으면 생성)
problems.create_index([("problem_id", ASCENDING)], unique=True, name="u_problem_id")
generated.create_index([("origin_problem_id", ASCENDING), ("problem_id", ASCENDING)],
                       unique=True, name="u_origin_problem")

def ping() -> bool:
    # 1이면 OK
    return _client.admin.command("ping").get("ok") == 1
