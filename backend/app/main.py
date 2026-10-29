from __future__ import annotations

import datetime
import os
import uuid
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any

from fastapi import Depends, FastAPI, HTTPException, Query, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from .auth import get_current_user, get_principal, require_role, safe_user_summary
from .db import (
    get_agent,
    get_agent_metrics,
    get_prompt_history,
    get_prompts_per_user_per_day,
    get_summary_metrics,
    get_user_prompt_count_today,
    init_db,
    list_agents,
    log_prompt_metric,
)
from .fake_llm import fake_openai
from .models import (
    AgentMetricItem,
    AgentResponse,
    ChatPromptRequest,
    ChatPromptResponse,
    MetricsSummaryResponse,
    PromptLogItem,
    TokenUsage,
    UserDailyMetric,
    UserQuotaResponse,
)

# Daily prompt rate limiting / quota per user (0 or negative means unlimited)
MAX_DAILY_PROMPTS_PER_USER = int(os.getenv("MAX_DAILY_PROMPTS_PER_USER", "50"))


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Initialize SQLite database and seed initial AI agents
    init_db()
    yield


app = FastAPI(
    title="Azure App Service Easy Auth + Fake OpenAI Metrics API",
    description="LLM metrics tracking (prompts per user per day, prompt inputs & responses, agent details, rate limiting) using Easy Auth only.",
    version="1.0.0",
    lifespan=lifespan,
)

# Allow CORS for development convenience (e.g. Angular running on port 4200)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

BASE_DIR = Path(__file__).resolve().parents[1]
STATIC_DIR = BASE_DIR / "static"


# ---------------------------------------------------------------------------
# Basic & Identity Endpoints
# ---------------------------------------------------------------------------


@app.get("/api/health", tags=["Health"])
def health():
    """Health check endpoint (unauthenticated)."""
    return {"status": "ok"}


@app.get("/api/me", tags=["Identity"])
def me(principal: dict[str, Any] = Depends(get_principal)):
    """Return user identity extracted solely from Easy Auth header."""
    return safe_user_summary(principal)


@app.get("/api/me/quota", response_model=UserQuotaResponse, tags=["Identity"])
def get_user_quota(current_user: dict[str, Any] = Depends(get_current_user)):
    """Retrieve daily prompt quota, prompts used today, and remaining prompts for the authenticated user."""
    today_str = datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%d")
    used_today = get_user_prompt_count_today(current_user["user_id"], today_str)
    remaining = max(0, MAX_DAILY_PROMPTS_PER_USER - used_today) if MAX_DAILY_PROMPTS_PER_USER > 0 else 9999
    return UserQuotaResponse(
        user_id=current_user["user_id"],
        username=current_user["username"],
        date=today_str,
        daily_limit=MAX_DAILY_PROMPTS_PER_USER,
        used_today=used_today,
        remaining=remaining,
    )


@app.get("/api/documents", tags=["Documents"])
def list_documents(principal: dict[str, Any] = Depends(get_principal)):
    return {
        "items": [
            {"id": "doc-001", "title": "Example document", "access": "authenticated users"}
        ]
    }


@app.get("/api/admin", tags=["Roles"])
def admin_area(principal: dict[str, Any] = Depends(require_role("Admin"))):
    return {"message": "Admin access granted"}


@app.get("/api/reader", tags=["Roles"])
def reader_area(principal: dict[str, Any] = Depends(require_role("Reader"))):
    return {"message": "Reader access granted"}


# ---------------------------------------------------------------------------
# AI Agents & Fake OpenAI LLM Execution
# ---------------------------------------------------------------------------


@app.get("/api/agents", response_model=list[AgentResponse], tags=["Agents"])
def get_agents():
    """List all available AI agents with details like name, model, system prompt, and temperature."""
    return list_agents()


@app.get("/api/agents/{agent_id}", response_model=AgentResponse, tags=["Agents"])
def get_agent_detail(agent_id: str):
    """Retrieve details for a specific AI agent."""
    agent = get_agent(agent_id)
    if not agent:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Agent '{agent_id}' not found")
    return agent


@app.post("/api/chat", response_model=ChatPromptResponse, tags=["AI Chat & Metrics"])
def execute_prompt(
    payload: ChatPromptRequest,
    current_user: dict[str, Any] = Depends(get_current_user),
):
    """
    Execute a prompt against the Fake OpenAI LLM service and track metrics.

    User identity is derived strictly from Azure Easy Auth (current_user).
    Rate Limiting:
      - Checks current user's prompt count for today.
      - Enforces MAX_DAILY_PROMPTS_PER_USER (returns 429 if exceeded).
    Metrics logged:
      - Prompt input & response
      - User ID & Username (Easy Auth)
      - Agent details & model
      - Token counts (prompt, completion, total)
      - Latency (ms)
      - Timestamp & Date (YYYY-MM-DD for daily aggregation)
    """
    today_str = datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%d")

    # 1. Check daily quota & rate limit for this user
    used_today = get_user_prompt_count_today(current_user["user_id"], today_str)
    if MAX_DAILY_PROMPTS_PER_USER > 0 and used_today >= MAX_DAILY_PROMPTS_PER_USER:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail=f"Daily prompt limit of {MAX_DAILY_PROMPTS_PER_USER} reached for user '{current_user['username']}'. Resets tomorrow at 00:00 UTC.",
            headers={
                "X-RateLimit-Limit": str(MAX_DAILY_PROMPTS_PER_USER),
                "X-RateLimit-Remaining": "0",
                "Retry-After": "3600",
            },
        )

    # 2. Lookup Agent details
    agent = get_agent(payload.agent_id)
    if not agent:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Agent '{payload.agent_id}' not found",
        )
    if not agent.get("is_active"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Agent '{payload.agent_id}' is currently inactive",
        )

    model_to_use = payload.model or agent["model"]
    temperature_to_use = payload.temperature if payload.temperature is not None else agent["temperature"]

    # 3. Invoke Fake OpenAI LLM service
    messages = [
        {"role": "system", "content": agent["system_prompt"]},
        {"role": "user", "content": payload.prompt},
    ]

    llm_result = fake_openai.generate_chat_completion(
        messages=messages,
        model=model_to_use,
        temperature=temperature_to_use,
        agent_role=agent["name"],
        simulate_delay=True,
    )

    response_text = llm_result["choices"][0]["message"]["content"]
    usage = llm_result["usage"]
    latency_ms = llm_result["latency_ms"]

    prompt_id = str(uuid.uuid4())

    # 4. Log metrics to SQLite database using Easy Auth user
    log_entry = log_prompt_metric(
        prompt_id=prompt_id,
        user_id=current_user["user_id"],
        user_name=current_user["username"],
        agent_id=agent["id"],
        agent_name=agent["name"],
        model=model_to_use,
        prompt_input=payload.prompt,
        prompt_response=response_text,
        input_tokens=usage["prompt_tokens"],
        output_tokens=usage["completion_tokens"],
        total_tokens=usage["total_tokens"],
        latency_ms=latency_ms,
    )

    remaining_after = (
        max(0, MAX_DAILY_PROMPTS_PER_USER - (used_today + 1))
        if MAX_DAILY_PROMPTS_PER_USER > 0
        else 9999
    )

    return ChatPromptResponse(
        prompt_id=prompt_id,
        agent_id=agent["id"],
        agent_name=agent["name"],
        model=model_to_use,
        user_id=current_user["user_id"],
        user_name=current_user["username"],
        input=payload.prompt,
        response=response_text,
        usage=TokenUsage(**usage),
        latency_ms=latency_ms,
        timestamp=log_entry["created_at"],
        daily_quota_limit=MAX_DAILY_PROMPTS_PER_USER,
        daily_quota_remaining=remaining_after,
    )


# ---------------------------------------------------------------------------
# Metrics & Analytics Endpoints
# ---------------------------------------------------------------------------


@app.get(
    "/api/metrics/prompts-per-user-per-day",
    response_model=list[UserDailyMetric],
    tags=["Metrics & Analytics"],
)
def get_user_daily_metrics(
    user_id: str | None = Query(None, description="Optional user ID filter"),
    start_date: str | None = Query(None, description="Filter from date (YYYY-MM-DD)"),
    end_date: str | None = Query(None, description="Filter up to date (YYYY-MM-DD)"),
    principal: dict[str, Any] = Depends(get_principal),
):
    """
    Returns metrics on number of prompts per user per day.
    Includes prompt count, input tokens, output tokens, total tokens, and average latency.
    """
    return get_prompts_per_user_per_day(user_id=user_id, start_date=start_date, end_date=end_date)


@app.get(
    "/api/metrics/prompts",
    response_model=list[PromptLogItem],
    tags=["Metrics & Analytics"],
)
def get_prompt_logs(
    user_id: str | None = Query(None, description="Filter by user ID"),
    agent_id: str | None = Query(None, description="Filter by agent ID"),
    date: str | None = Query(None, description="Filter by date (YYYY-MM-DD)"),
    limit: int = Query(50, ge=1, le=500, description="Max records to return"),
    offset: int = Query(0, ge=0, description="Offset for pagination"),
    principal: dict[str, Any] = Depends(get_principal),
):
    """
    Returns historical log of prompt inputs and LLM responses,
    including agent details, token usage, latency, and Easy Auth user details.
    """
    return get_prompt_history(
        user_id=user_id,
        agent_id=agent_id,
        date=date,
        limit=limit,
        offset=offset,
    )


@app.get(
    "/api/metrics/agents",
    response_model=list[AgentMetricItem],
    tags=["Metrics & Analytics"],
)
def get_agent_usage_metrics(
    principal: dict[str, Any] = Depends(get_principal),
):
    """
    Returns aggregated metrics by agent (total prompts, total tokens, unique users, avg latency).
    """
    return get_agent_metrics()


@app.get(
    "/api/metrics/summary",
    response_model=MetricsSummaryResponse,
    tags=["Metrics & Analytics"],
)
def get_metrics_summary(
    principal: dict[str, Any] = Depends(get_principal),
):
    """
    Returns high-level summary KPI metrics: total prompts, prompts today, active users, total tokens.
    """
    return get_summary_metrics()


# ---------------------------------------------------------------------------
# Optional Static Hosting for Angular SPA
# ---------------------------------------------------------------------------

if STATIC_DIR.exists():
    app.mount("/assets", StaticFiles(directory=STATIC_DIR / "assets", check_dir=False), name="assets")

    @app.get("/{full_path:path}", include_in_schema=False)
    def serve_spa(full_path: str):
        if full_path.startswith(".auth/"):
            raise HTTPException(status_code=404, detail="Not found")
        candidate = (STATIC_DIR / full_path).resolve()
        if candidate.is_file() and STATIC_DIR.resolve() in candidate.parents:
            return FileResponse(candidate)
        index_file = STATIC_DIR / "index.html"
        if index_file.exists():
            return FileResponse(index_file)
        raise HTTPException(status_code=404, detail="Frontend build not found")
