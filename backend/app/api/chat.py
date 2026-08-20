from fastapi import APIRouter

from app.agent.agent import run_agent
from app.models.chat import ChatRequest, ChatResponse

router = APIRouter(prefix="/api/chat", tags=["chat"])


@router.post("")
def chat(request: ChatRequest) -> ChatResponse:
    return run_agent(request.message, request.history)
