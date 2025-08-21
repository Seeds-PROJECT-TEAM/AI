# app/services/learning_path.py

from __future__ import annotations
from typing import List, Dict, Any

class LearningPathService:
    """
    선수 개념 그래프(Neo4j)나 규칙을 이용해 학습 경로를 산출하는 서비스의 스텁.
    실제 로직은 나중에 메서드 내부를 구현하세요.
    """

    def __init__(self) -> None:
        # 필요시 드라이버/설정 주입
        pass

    def recommend(self, target_concept: str) -> List[Dict[str, Any]]:
        """
        예시: target_concept까지 도달하기 위한 선행 개념 경로.
        현재는 더미 결과 반환.
        """
        return [
            {"concept": "기본 연산", "distance": 2},
            {"concept": "약수/배수", "distance": 1},
            {"concept": target_concept, "distance": 0},
        ]
