"""Pydantic schemas for AI agent prompts and metrics tracking."""

from __future__ import annotations

from pydantic import BaseModel, Field


class ChatPromptRequest(BaseModel):
    agent_id: str = Field(default="agent-support", description="ID of the AI agent to converse with")
    prompt: str = Field(..., min_length=1, max_length=10000, description="User's input prompt")
    model: str | None = Field(default=None, description="Optional override for fake model name")
    temperature: float | None = Field(default=None, ge=0.0, le=2.0, description="Optional temperature override")


class TokenUsage(BaseModel):
    prompt_tokens: int
    completion_tokens: int
    total_tokens: int


class ChatPromptResponse(BaseModel):
    prompt_id: str
    agent_id: str
    agent_name: str
    model: str
    user_id: str
    user_name: str
    input: str
    response: str
    usage: TokenUsage
    latency_ms: float
    timestamp: str
    daily_quota_limit: int
    daily_quota_remaining: int


class UserDailyMetric(BaseModel):
    user_id: str
    user_name: str
    date: str
    prompt_count: int
    total_input_tokens: int
    total_output_tokens: int
    total_tokens: int
    avg_latency_ms: float


class PromptLogItem(BaseModel):
    id: str
    user_id: str
    user_name: str
    agent_id: str
    agent_name: str
    model: str
    prompt_input: str
    prompt_response: str
    input_tokens: int
    output_tokens: int
    total_tokens: int
    latency_ms: float
    created_at: str
    date: str


class AgentResponse(BaseModel):
    id: str
    name: str
    description: str
    system_prompt: str
    model: str
    temperature: float
    is_active: bool
    created_at: str


class AgentMetricItem(BaseModel):
    agent_id: str
    agent_name: str
    model: str
    temperature: float
    is_active: bool
    total_prompts: int
    total_tokens: int
    unique_users: int
    avg_latency_ms: float


class MetricsSummaryResponse(BaseModel):
    date: str
    total_prompts: int
    total_tokens: int
    unique_users_all_time: int
    prompts_today: int
    tokens_today: int
    unique_users_today: int


class UserQuotaResponse(BaseModel):
    user_id: str
    username: str
    date: str
    daily_limit: int
    used_today: int
    remaining: int
