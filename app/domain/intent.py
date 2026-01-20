from enum import Enum


class ChatIntent(str, Enum):
    KNOWLEDGE = "knowledge"
    CHITCHAT = "chitchat"
    UNSUPPORTED = "unsupported"
