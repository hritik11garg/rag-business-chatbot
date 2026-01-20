from app.domain.intent import ChatIntent


class IntentClassifier:
    def classify(self, text: str) -> ChatIntent:
        normalized = text.lower().strip()

        if normalized in {"hi", "hello", "hey", "thanks", "thank you"}:
            return ChatIntent.CHITCHAT

        if len(normalized.split()) <= 2:
            # short ambiguous queries like "about", "refund"
            return ChatIntent.KNOWLEDGE

        return ChatIntent.KNOWLEDGE
