# scripts/load_to_mongo.py
from __future__ import annotations
import os, json, glob, datetime
from pathlib import Path
from dotenv import load_dotenv
from pymongo import MongoClient, ASCENDING, errors

# ── 경로 & .env 로드 (AI/.env) ─────────────────────────────
ROOT = Path(__file__).resolve().parents[1]
load_dotenv(ROOT / ".env")

MONGODB_URI = os.getenv("MONGODB_URI")
if not MONGODB_URI:
    raise RuntimeError("MONGODB_URI가 .env에 없습니다")

client = MongoClient(MONGODB_URI)
db = client.get_default_database()  # URI에 DB명이 들어있으면 그걸로 선택됨

problems = db["problems"]
generated = db["generated_problems"]

# ── 인덱스 ────────────────────────────────────────────────
# 문제 ID 기준 중복 방지
problems.create_index([("problem_id", ASCENDING)], unique=True, name="u_problem_id")
# 생성문항은 (origin_problem_id, problem_id) 조합으로 유니크 추천
generated.create_index([("origin_problem_id", ASCENDING), ("problem_id", ASCENDING)],
                       unique=True, name="u_origin_problem")

def load_json(p: Path):
    with open(p, "r", encoding="utf-8") as f:
        return json.load(f)

def now_iso():
    return datetime.datetime.utcnow().isoformat() + "Z"

def upsert_problem(doc: dict, source_file: str, is_generated: bool):
    # 필수 키 정리
    problem_id = doc.get("problem_id") or doc.get("id") or doc.get("uid")
    if not problem_id:
        # 파일명 기반 fallback 키(권장하지 않지만 임시)
        problem_id = source_file.replace(".json","")

    base = {
        "problem_id": problem_id,
        "source_file": source_file,
        "created_at": now_iso(),
    }
    if is_generated:
        # 원본 참조 키 추출(없으면 problem_id를 그대로 origin으로)
        origin_pid = doc.get("origin_problem_id") or doc.get("origin") or doc.get("base_problem_id") or problem_id
        payload = {
            **doc,
            **base,
            "type": "generated",
            "origin_problem_id": origin_pid
        }
        # upsert
        generated.update_one(
            {"origin_problem_id": origin_pid, "problem_id": problem_id},
            {"$set": payload},
            upsert=True
        )
    else:
        payload = {**doc, **base, "type": "original"}
        problems.update_one(
            {"problem_id": problem_id},
            {"$set": payload},
            upsert=True
        )

def main():
    out_dir = ROOT / "out"
    files = sorted(glob.glob(str(out_dir / "*.json")))
    if not files:
        print(f"out 폴더에 JSON이 없습니다: {out_dir}")
        return

    inserted, updated = 0, 0
    for fp in files:
        p = Path(fp)
        data = load_json(p)

        # 파일 형식이 배열/단일 객체 모두 가능
        docs = data if isinstance(data, list) else [data]

        # 파일명으로 원본/생성 추정 규칙(원하면 바꾸세요)
        is_generated = p.name.startswith("problem_") or "generated" in p.name.lower()
        for d in docs:
            try:
                # upsert 수행 전 기존 여부 확인
                if is_generated:
                    key = {
                        "origin_problem_id": d.get("origin_problem_id") or d.get("origin") or d.get("base_problem_id") or d.get("problem_id"),
                        "problem_id": d.get("problem_id") or p.stem
                    }
                    before = generated.find_one(key)
                    upsert_problem(d, p.name, is_generated=True)
                    updated += 1 if before else 0
                    inserted += 0 if before else 1
                else:
                    key = {"problem_id": d.get("problem_id") or p.stem}
                    before = problems.find_one(key)
                    upsert_problem(d, p.name, is_generated=False)
                    updated += 1 if before else 0
                    inserted += 0 if before else 1
            except errors.DuplicateKeyError:
                # 유니크 충돌 시 덮어쓰기
                upsert_problem(d, p.name, is_generated=is_generated)
                updated += 1

    print(f"✅ 완료: inserted={inserted}, updated={updated}")

if __name__ == "__main__":
    main()
