# app/services/ai_generator.py

from __future__ import annotations
from typing import Optional, Dict, Any

class AIGenerator:
    """
    간단한 스텁(placeholder) 구현.
    실제 모델 호출(OpenAI 등)은 나중에 generate() 내부를 교체하면 됩니다.
    """

    def __init__(
        self,
        model: Optional[str] = None,
        api_key: Optional[str] = None,
        temperature: float = 0.2,
        max_tokens: int = 512,
    ) -> None:
        self.model = model
        self.api_key = api_key
        self.temperature = temperature
        self.max_tokens = max_tokens

    def generate(self, prompt: str, metadata: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """
        실제론 LLM 호출로 바꿔야 하는 자리.
        현재는 입력을 그대로 되돌려주는 더미 응답을 반환합니다.
        """
        return {
            "model": self.model,
            "temperature": self.temperature,
            "max_tokens": self.max_tokens,
            "prompt_echo": prompt,
            "metadata": metadata or {},
            "output": f"[stub] generated text for: {prompt[:50]}...",
        }
