# app/services/chat_service.py
class ChatService:
    def __init__(self, model: str, api_key: str, temperature: float = 0.2):
        self.model = model
        self.api_key = api_key
        self.temperature = temperature

    def reply(self, messages):
        ...
