# scripts/load_prereq_graph.py
from __future__ import annotations
import os, sys, csv, io, glob
from pathlib import Path
from dotenv import load_dotenv
from neo4j import GraphDatabase, exceptions as neo4j_exc

# ── 0) 프로젝트 루트/경로 ─────────────────────────────────────────
ROOT_DIR = Path(__file__).resolve().parents[1]        # .../AI
ENV_PATH = ROOT_DIR / ".env"
DATA_DIR = ROOT_DIR / "data"

# ── 1) .env 로드 ──────────────────────────────────────────────────
if not ENV_PATH.exists():
    print(f"❌ .env not found: {ENV_PATH}")
    sys.exit(1)
load_dotenv(ENV_PATH)

AURA_URI  = (os.getenv("AURA_URI") or "").strip()
AURA_USER = (os.getenv("AURA_USER") or "").strip()
AURA_PASS = (os.getenv("AURA_PASS") or "").strip()

def _require_env(k, v):
    if not v:
        print(f"❌ Missing env: {k}")
        sys.exit(1)

_require_env("AURA_URI", AURA_URI)
_require_env("AURA_USER", AURA_USER)
_require_env("AURA_PASS", AURA_PASS)

# ── 2) Neo4j 드라이버 & 연결 확인 ────────────────────────────────
driver = GraphDatabase.driver(AURA_URI, auth=(AURA_USER, AURA_PASS))
try:
    driver.verify_connectivity()
    print("✅ Connected to Neo4j Aura")
except neo4j_exc.Neo4jError as e:
    print("❌ Neo4j connectivity error:", e)
    sys.exit(1)

# ── 유틸: CSV 인코딩 자동 판별 + DictReader 생성 ────────────────
def _open_csv_flex(path: Path):
    encodings = ["utf-8-sig", "utf-8", "cp949", "euc-kr", "latin1"]
    last_err = None
    for enc in encodings:
        try:
            f = open(path, "r", encoding=enc, newline="")
            reader = csv.DictReader(f)
            # fieldnames 평가(헤더 확인)
            if not reader.fieldnames:
                raise ValueError("No header found")
            # BOM 제거/정규화 재시작
            f.seek(0)
            return f, enc
        except Exception as e:
            last_err = e
            try:
                f.close()
            except:
                pass
    raise RuntimeError(f"CSV 인코딩 판별 실패: {path} ({last_err})")

def _norm_row_keys(d: dict):
    return { (k.lstrip("\ufeff").strip().lower() if isinstance(k, str) else k): v
             for k, v in d.items() }

# ── 3) 스키마 제약 ────────────────────────────────────────────────
def create_constraints():
    with driver.session() as s:
        s.run("""
        CREATE CONSTRAINT concept_name IF NOT EXISTS
        FOR (c:Concept) REQUIRE c.name IS UNIQUE
        """)
    print("🔧 Constraint ensured: Concept.name UNIQUE")

# ── 4) 적재 함수 ─────────────────────────────────────────────────
def load_nodes(csv_path: Path):
    if not csv_path.exists():
        print(f"❌ nodes CSV not found: {csv_path}")
        sys.exit(1)
    f, enc_used = _open_csv_flex(csv_path)
    print(f"📄 Nodes CSV encoding detected: {enc_used}")
    with driver.session() as s, f:
        reader = csv.DictReader(f)
        cnt = 0
        for raw in reader:
            row = _norm_row_keys(raw)
            name  = row.get("concept") or row.get("name")
            unit  = row.get("unit") or ""
            grade = row.get("grade") or ""
            if not name:
                continue
            s.run("""
            MERGE (c:Concept {name:$name})
            SET c.unit = CASE WHEN $unit<>'' THEN $unit ELSE c.unit END,
                c.grade = CASE WHEN $grade<>'' THEN $grade ELSE c.grade END
            """, name=name, unit=unit, grade=grade)
            cnt += 1
    print(f"⬆️  Nodes upserted: {cnt}")

def load_edges(csv_path: Path):
    if not csv_path.exists():
        # neo4j_edges (1).csv 같은 파일 자동 탐색
        candidates = sorted(DATA_DIR.glob("neo4j_edges*.csv"))
        if candidates:
            print(f"ℹ️ edges CSV not found at '{csv_path.name}', using '{candidates[0].name}'")
            csv_path = candidates[0]
        else:
            print(f"❌ edges CSV not found: {csv_path}")
            sys.exit(1)
    f, enc_used = _open_csv_flex(csv_path)
    print(f"📄 Edges CSV encoding detected: {enc_used} ({csv_path.name})")
    with driver.session() as s, f:
        reader = csv.DictReader(f)
        cnt = 0
        for raw in reader:
            row = _norm_row_keys(raw)
            src = row.get("source") or row.get("src")
            dst = row.get("target") or row.get("dst")
            if not src or not dst:
                continue
            s.run("""
            MERGE (src:Concept {name:$src})
            MERGE (dst:Concept {name:$dst})
            MERGE (src)-[:PRECEDES]->(dst)
            """, src=src, dst=dst)
            cnt += 1
    print(f"🔗 Edges upserted: {cnt}")

# ── 5) 실행 진입점 ────────────────────────────────────────────────
if __name__ == "__main__":
    nodes_csv = DATA_DIR / "neo4j_nodes.csv"
    edges_csv = DATA_DIR / "neo4j_edges.csv"  # 기본 이름. 없으면 glob로 대체됨

    create_constraints()
    load_nodes(nodes_csv)
    load_edges(edges_csv)
    driver.close()
    print("🏁 Done: Neo4j Aura 적재 완료")
