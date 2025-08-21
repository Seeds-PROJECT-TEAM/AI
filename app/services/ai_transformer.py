import os, re, json, time
from pathlib import Path
from typing import Optional
from dotenv import load_dotenv
from openai import OpenAI

# ==================== 경로/환경 ====================
THIS = Path(__file__).resolve()     # .../app/services/ai_transformer.py
ROOT = THIS.parents[2]              # 프로젝트 루트
APP  = THIS.parents[1]              # .../app

# .env: 루트 우선, 없으면 app/.env
if (ROOT / ".env").exists():
    load_dotenv(ROOT / ".env")
elif (APP / ".env").exists():
    load_dotenv(APP / ".env")
else:
    print("[warn] .env를 루트나 app/에 두면 자동 로드됩니다.")

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
if not OPENAI_API_KEY:
    raise RuntimeError("❌ OPENAI_API_KEY가 설정되어 있지 않습니다(.env 확인).")

client      = OpenAI(api_key=OPENAI_API_KEY)
MODEL       = "gpt-4o"      # 필요 시 gpt-4o-mini 등으로 교체
TEMPERATURE = 0.2
MAX_RETRY   = 2

# 디버그 모드: 원문(raw) 백업 파일 생성 여부 (기본 OFF)
DEBUG_RAW = os.getenv("AI_TRANSFORMER_DEBUG_RAW", "0") == "1"

# ==================== 커리큘럼/스키마 ====================
CURRICULUM_TEXT = r"""(여기에 한국 중학교 수학 교육과정 리스트를 붙여넣으세요)"""
SCHEMA_TEXT = r"""
[출력 JSON 스키마]
{
  "problem_id": "string",
  "korean_problem": "string",
  "english_problem": "string",
  "korean_solution": "string",
  "english_solution": "string",
  "choices": {"A":"string","B":"string","C":"string","D":"string"},
  "answer": "A|B|C|D",
  "curriculum": {"대단원":"string","소단원":"string","학년":"string"},
  "difficulty": "string"
}
"""

# ==================== 유틸 ====================
def clean_text(s: str) -> str:
    if not isinstance(s, str):
        return ""
    s = s.replace("\\\\", " ").replace("\n\n", "\n")
    s = re.sub(r"\s{2,}", " ", s).strip()
    return s

def build_prompt(item: dict) -> tuple[str, str]:
    problem_id    = clean_text(item.get("problem_id", ""))
    question_text = clean_text(item.get("question_text", ""))
    choices       = {k: clean_text(v) for k, v in (item.get("choices") or {}).items()}
    answer_src    = clean_text(item.get("answer", ""))
    rationale_src = clean_text(item.get("rationale", ""))
    difficulty_src= clean_text(item.get("difficulty", ""))

    system_msg = (
        "당신은 한국 중학교 수학 교사이며, SAT/ACT 문제를 중학생 수준에 맞게 변형하고 해설을 작성하는 전문가입니다. "
        "항상 JSON만 출력하세요."
    )

    user_msg = f"""
아래 SAT 문제를 한국 중학교 3학년 수준으로 변형해 주세요.
- 한국어/영어 문제와 풀이를 각각 작성
- 실생활 상황이나 예시를 반드시 포함 (예: 버스 요금 계산, 마트 할인, 운동 경기, 요리 재료 측정 등)
- 문제 배경이 학생들이 일상에서 접할 수 있는 상황이어야 함
- 실생활 예시가 없으면 변형이 완료되지 않은 것으로 간주
- 보기 4개 유지(A~D), 숫자 표기 일관
- 아래 제공된 '한국 전체 교육과정'에서만 대단원/소단원/학년을 선택
- 출력은 반드시 JSON만

[문항 ID] {problem_id}

[SAT 원문 문제]
{question_text}

[보기]
A. {choices.get('A','')}
B. {choices.get('B','')}
C. {choices.get('C','')}
D. {choices.get('D','')}

[정답(있으면 고정)]: {answer_src}
[해설(있으면)]: {rationale_src}
[난이도 힌트(있으면)]: {difficulty_src}

{CURRICULUM_TEXT}

{SCHEMA_TEXT}
"""
    return system_msg, user_msg

def call_chat_json(
    system_msg: str,
    user_msg: str,
    model: str = MODEL,
    temperature: float = TEMPERATURE,
    max_retry: int = MAX_RETRY,
    raw_dump_path: Optional[Path] = None,  # 성공 시에도 raw 남기고 싶을 때만 전달
) -> dict:
    last_err: Optional[Exception] = None
    for attempt in range(max_retry + 1):
        try:
            resp = client.chat.completions.create(
                model=model,
                temperature=temperature,
                messages=[
                    {"role": "system", "content": system_msg},
                    {"role": "user", "content": user_msg},
                ],
                response_format={"type": "json_object"},  # JSON 모드
            )
            content = resp.choices[0].message.content
            if raw_dump_path and DEBUG_RAW:
                raw_dump_path.write_text(content, encoding="utf-8")  # 원문 백업(디버그 ON일 때만)
            return json.loads(content)
        except Exception as e:
            last_err = e
            time.sleep(0.8)
    raise last_err or RuntimeError("OpenAI 호출 실패")

def transform_problem(item: dict) -> dict:
    sys_msg, usr_msg = build_prompt(item)
    data = call_chat_json(sys_msg, usr_msg)
    # 필수 키 검증
    for k in ["problem_id","korean_problem","english_problem","korean_solution",
              "english_solution","choices","answer","curriculum","difficulty"]:
        if k not in data:
            raise ValueError(f"필수 키 누락: {k}")
    for k in ["A","B","C","D"]:
        if k not in data["choices"]:
            raise ValueError("보기 키(A,B,C,D) 누락")
    for k in ["대단원","소단원","학년"]:
        if k not in data["curriculum"]:
            raise ValueError("curriculum 키 누락")
    return data

# ==================== 입력/출력 자동 결정 ====================
def pick_input_json() -> Path:
    """out/problem.json → out/problems.json → out/**/problem(s).json 최신 파일 순으로 선택"""
    OUT_ROOT = (ROOT / "out").resolve()
    cand = [OUT_ROOT / "problem.json", OUT_ROOT / "problems.json"]
    for c in cand:
        if c.exists():
            return c
    candidates = list(OUT_ROOT.rglob("problem.json")) + list(OUT_ROOT.rglob("problems.json"))
    if not candidates:
        raise FileNotFoundError(
            f"입력 파일을 찾을 수 없습니다. 다음 중 하나가 필요합니다:\n"
            f"- {OUT_ROOT/'problem.json'}\n- {OUT_ROOT/'problems.json'}\n- {OUT_ROOT}/**/problem(s).json"
        )
    return max(candidates, key=lambda p: p.stat().st_mtime)

def decide_out_path(in_path: Path) -> Path:
    """규칙:
       - in == out/problem.json → out/converted_with_schema.json
       - in ∈ out/<폴더>/...   → out/<폴더>/converted_with_schema.json
       - 그 외                  → out/<in.stem>/converted_with_schema.json
    """
    OUT_ROOT = (ROOT / "out").resolve()
    if in_path.parent == OUT_ROOT:
        return OUT_ROOT / "converted_with_schema.json"
    try:
        rel = in_path.resolve().relative_to(OUT_ROOT)
        if len(rel.parts) >= 2:
            return in_path.parent / "converted_with_schema.json"
    except Exception:
        pass
    return OUT_ROOT / in_path.stem / "converted_with_schema.json"

# ==================== 엔트리포인트 ====================
def main():
    OUT_ROOT = (ROOT / "out").resolve()
    OUT_ROOT.mkdir(parents=True, exist_ok=True)

    in_path = pick_input_json()
    out_path = decide_out_path(in_path)
    out_dir  = out_path.parent
    out_dir.mkdir(parents=True, exist_ok=True)

    # 디버그 로그(원하면 주석 처리)
    print(f"[paths] ROOT={ROOT}")
    print(f"[paths] IN={in_path}")
    print(f"[paths] OUT={out_path}")
    print(f"[env] OPENAI_KEY_SET={bool(os.getenv('OPENAI_API_KEY'))}")
    if DEBUG_RAW:
        print("[debug] AI_TRANSFORMER_DEBUG_RAW=1 → 성공 시 원문을 _last_raw.json에 저장합니다.")

    # 입력 로드
    src = json.loads(in_path.read_text(encoding="utf-8"))
    items = src if isinstance(src, list) else [src]

    err_log  = out_dir / "_error.txt"
    raw_dump = out_dir / "_last_raw.json" if DEBUG_RAW else None

    results = []
    try:
        for it in items:
            data = call_chat_json(*build_prompt(it), raw_dump_path=raw_dump)  # 디버그 ON일 때만 raw 저장
            results.append(data)

        out_path.write_text(
            json.dumps(results if len(results) > 1 else results[0], ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        print(f"[OK] 저장 완료: {out_path}")
        print("ok")  # 성공 신호
    except Exception as e:
        err_log.write_text(repr(e), encoding="utf-8")
        print(f"[ERROR] 변환 실패: {e}\n-> 디버그: {err_log}")
        raise

if __name__ == "__main__":
    main()
