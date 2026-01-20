class ChitChatUseCase:
    def execute(self, *, question: str) -> dict:
        return {
            "question": question,
            "answer": "Hi! How can I help you today?",
            "sources": [],
            "confidence": "high",
        }
