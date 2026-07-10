import pytest
from pydantic import ValidationError

from app.api.schemas.chat import ChatRequest


def test_defaults():
    req = ChatRequest(question="what is the refund policy?")
    assert req.top_k == 5
    assert req.document_ids is None


def test_top_k_bounds():
    assert ChatRequest(question="q", top_k=20).top_k == 20
    with pytest.raises(ValidationError):
        ChatRequest(question="q", top_k=0)
    with pytest.raises(ValidationError):
        ChatRequest(question="q", top_k=21)


def test_empty_question_rejected():
    with pytest.raises(ValidationError):
        ChatRequest(question="")


def test_empty_document_ids_rejected():
    # [] would silently mean "search nothing" — force omit-or-name-one
    with pytest.raises(ValidationError):
        ChatRequest(question="q", document_ids=[])
    assert ChatRequest(question="q", document_ids=[1, 2]).document_ids == [1, 2]
