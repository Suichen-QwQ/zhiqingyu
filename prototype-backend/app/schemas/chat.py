"""
聊天相关的Pydantic模型
"""
from pydantic import BaseModel, Field, field_validator
from typing import Literal, Optional
from datetime import datetime


class PromptMessage(BaseModel):
    """Internal prompt message; system prompts never enter the public chat schema."""
    role: Literal["system", "user", "assistant"]
    content: str


class ChatMessage(BaseModel):
    """聊天消息"""
    role: Literal["user", "assistant"]
    content: str
    card_data: Optional[dict] = None  # 卡片数据（可选，用于卡片展示）


class ChatRequest(BaseModel):
    """聊天请求"""
    session_id: Optional[str] = None
    messages: list[ChatMessage] = Field(min_length=1, max_length=200)

    @field_validator("messages")
    @classmethod
    def require_user_turn(cls, messages):
        if messages[-1].role != "user" or not messages[-1].content.strip():
            raise ValueError("The latest message must be a nonempty user message")
        return messages

    experience_mode: Optional[Literal["A", "B", "C", "D"]] = None  # 体验模式：A:只想被听 B:想搞懂 C:想要建议 D:系统深聊
    ai_style: Optional[str] = None  # AI风格：comfort, analyst, coach, mentor, friend, listener, growth, crisis_safe
    chat_mode: Optional[Literal["deep", "quick"]] = None  # 聊天模式：deep(深聊模式) 或 quick(快速模式)


class ChatResponse(BaseModel):
    """聊天响应"""
    session_id: str
    reply: str
    emotion: str
    intensity: int
    topics: list[str]
    risk_level: Literal["normal", "high"]
    # 结构化卡片数据（可选，用于卡片展示）
    card_data: Optional[dict] = None  # 包含 theme, emotion_echo, clarification, suggestion
    # 多阶段对话流程控制
    should_show_card_button: bool = False  # 是否显示"开始关心吧！"按钮
    should_show_satisfaction_buttons: bool = False  # 是否显示"满意/不满意"按钮（阶段3完成后）


class SessionItem(BaseModel):
    """会话项"""
    id: str
    title: Optional[str] = None
    created_at: datetime
    latest_message_at: Optional[datetime] = None
    preview: Optional[str] = None  # 第一条用户消息的预览


class SessionListResponse(BaseModel):
    """会话列表响应"""
    sessions: list[SessionItem]


class SessionMessagesResponse(BaseModel):
    """会话消息响应"""
    session_id: str
    messages: list[ChatMessage]
