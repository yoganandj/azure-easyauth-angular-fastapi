"""SQLite database management for Easy Auth metrics and AI agent management."""

from __future__ import annotations

import datetime
import os
import sqlite3
from pathlib import Path
from typing import Any

DB_PATH = Path(os.getenv("METRICS_DB_PATH", Path(__file__).resolve().parents[1] / "metrics.db"))


def get_connection() -> sqlite3.Connection:
    conn = sqlite3.connect(str(DB_PATH), check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL;")
    return conn


def init_db() -> None:
    """Initialize database tables and seed initial AI agents."""
    conn = get_connection()
    try:
        with conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS agents (
                    id TEXT PRIMARY KEY,
                    name TEXT NOT NULL,
                    description TEXT NOT NULL,
                    system_prompt TEXT NOT NULL,
                    model TEXT NOT NULL,
                    temperature REAL NOT NULL DEFAULT 0.7,
                    is_active INTEGER NOT NULL DEFAULT 1,
                    created_at TEXT NOT NULL
                );
                """
            )

            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS prompt_metrics (
                    id TEXT PRIMARY KEY,
                    user_id TEXT NOT NULL,
                    user_name TEXT NOT NULL,
                    agent_id TEXT NOT NULL,
                    agent_name TEXT NOT NULL,
                    model TEXT NOT NULL,
                    prompt_input TEXT NOT NULL,
                    prompt_response TEXT NOT NULL,
                    input_tokens INTEGER NOT NULL,
                    output_tokens INTEGER NOT NULL,
                    total_tokens INTEGER NOT NULL,
                    latency_ms REAL NOT NULL,
                    created_at TEXT NOT NULL,
                    date TEXT NOT NULL,
                    FOREIGN KEY (agent_id) REFERENCES agents (id)
                );
                """
            )

            conn.execute("CREATE INDEX IF NOT EXISTS idx_prompt_user_date ON prompt_metrics(user_id, date);")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_prompt_date ON prompt_metrics(date);")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_prompt_agent ON prompt_metrics(agent_id);")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_prompt_created ON prompt_metrics(created_at DESC);")

            # Seed default agents if none exist
            cursor = conn.execute("SELECT COUNT(*) as count FROM agents;")
            if cursor.fetchone()["count"] == 0:
                now = datetime.datetime.now(datetime.timezone.utc).isoformat()
                default_agents = [
                    (
                        "agent-support",
                        "Customer Support Specialist",
                        "Assists users with inquiries, account questions, and troubleshooting.",
                        "You are a friendly and helpful customer support specialist.",
                        "fake-gpt-4o-mini",
                        0.7,
                        1,
                        now,
                    ),
                    (
                        "agent-code",
                        "Python & Cloud Architect",
                        "Specialized in FastAPI, Azure App Service, and secure coding practices.",
                        "You are an expert Python and Azure cloud architecture assistant.",
                        "fake-gpt-4o",
                        0.2,
                        1,
                        now,
                    ),
                    (
                        "agent-analyst",
                        "Data & Metrics Analyst",
                        "Analyzes prompt velocity, daily active users, and system performance.",
                        "You are a concise data analysis specialist focusing on operational metrics.",
                        "fake-gpt-4-turbo",
                        0.4,
                        1,
                        now,
                    ),
                ]
                conn.executemany(
                    """
                    INSERT INTO agents (id, name, description, system_prompt, model, temperature, is_active, created_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?);
                    """,
                    default_agents,
                )
    finally:
        conn.close()


def log_prompt_metric(
    prompt_id: str,
    user_id: str,
    user_name: str,
    agent_id: str,
    agent_name: str,
    model: str,
    prompt_input: str,
    prompt_response: str,
    input_tokens: int,
    output_tokens: int,
    total_tokens: int,
    latency_ms: float,
    created_at: str | None = None,
) -> dict[str, Any]:
    """Insert a prompt execution record and return the logged item."""
    if not created_at:
        now_dt = datetime.datetime.now(datetime.timezone.utc)
        created_at = now_dt.isoformat()
        date_str = now_dt.strftime("%Y-%m-%d")
    else:
        date_str = created_at[:10]

    conn = get_connection()
    try:
        with conn:
            conn.execute(
                """
                INSERT INTO prompt_metrics (
                    id, user_id, user_name, agent_id, agent_name, model,
                    prompt_input, prompt_response, input_tokens, output_tokens,
                    total_tokens, latency_ms, created_at, date
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?);
                """,
                (
                    prompt_id,
                    user_id,
                    user_name,
                    agent_id,
                    agent_name,
                    model,
                    prompt_input,
                    prompt_response,
                    input_tokens,
                    output_tokens,
                    total_tokens,
                    latency_ms,
                    created_at,
                    date_str,
                ),
            )
    finally:
        conn.close()

    return {
        "id": prompt_id,
        "user_id": user_id,
        "user_name": user_name,
        "agent_id": agent_id,
        "agent_name": agent_name,
        "model": model,
        "prompt_input": prompt_input,
        "prompt_response": prompt_response,
        "input_tokens": input_tokens,
        "output_tokens": output_tokens,
        "total_tokens": total_tokens,
        "latency_ms": latency_ms,
        "created_at": created_at,
        "date": date_str,
    }


def get_user_prompt_count_today(user_id: str, date_str: str | None = None) -> int:
    """Return total number of prompts executed by this user for the specified date."""
    if not date_str:
        date_str = datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%d")
    conn = get_connection()
    try:
        row = conn.execute(
            "SELECT COUNT(*) AS count FROM prompt_metrics WHERE user_id = ? AND date = ?;",
            (user_id, date_str),
        ).fetchone()
        return int(row["count"]) if row else 0
    finally:
        conn.close()


def get_prompts_per_user_per_day(
    user_id: str | None = None,
    start_date: str | None = None,
    end_date: str | None = None,
) -> list[dict[str, Any]]:
    """Retrieve daily prompt aggregation per user."""
    conn = get_connection()
    try:
        query = """
            SELECT
                user_id,
                user_name,
                date,
                COUNT(*) AS prompt_count,
                SUM(input_tokens) AS total_input_tokens,
                SUM(output_tokens) AS total_output_tokens,
                SUM(total_tokens) AS total_tokens,
                ROUND(AVG(latency_ms), 2) AS avg_latency_ms
            FROM prompt_metrics
            WHERE 1=1
        """
        params: list[Any] = []
        if user_id:
            query += " AND user_id = ?"
            params.append(user_id)
        if start_date:
            query += " AND date >= ?"
            params.append(start_date)
        if end_date:
            query += " AND date <= ?"
            params.append(end_date)

        query += " GROUP BY user_id, user_name, date ORDER BY date DESC, prompt_count DESC;"

        rows = conn.execute(query, params).fetchall()
        return [dict(row) for row in rows]
    finally:
        conn.close()


def get_prompt_history(
    user_id: str | None = None,
    agent_id: str | None = None,
    date: str | None = None,
    limit: int = 50,
    offset: int = 0,
) -> list[dict[str, Any]]:
    """Retrieve full history of prompt inputs and responses."""
    conn = get_connection()
    try:
        query = """
            SELECT
                id, user_id, user_name, agent_id, agent_name, model,
                prompt_input, prompt_response, input_tokens, output_tokens,
                total_tokens, latency_ms, created_at, date
            FROM prompt_metrics
            WHERE 1=1
        """
        params: list[Any] = []
        if user_id:
            query += " AND user_id = ?"
            params.append(user_id)
        if agent_id:
            query += " AND agent_id = ?"
            params.append(agent_id)
        if date:
            query += " AND date = ?"
            params.append(date)

        query += " ORDER BY created_at DESC LIMIT ? OFFSET ?;"
        params.extend([limit, offset])

        rows = conn.execute(query, params).fetchall()
        return [dict(row) for row in rows]
    finally:
        conn.close()


def get_agent_metrics() -> list[dict[str, Any]]:
    """Retrieve prompt and token metrics aggregated by agent."""
    conn = get_connection()
    try:
        query = """
            SELECT
                a.id AS agent_id,
                a.name AS agent_name,
                a.model AS model,
                a.temperature AS temperature,
                a.is_active AS is_active,
                COUNT(p.id) AS total_prompts,
                COALESCE(SUM(p.total_tokens), 0) AS total_tokens,
                COUNT(DISTINCT p.user_id) AS unique_users,
                ROUND(COALESCE(AVG(p.latency_ms), 0.0), 2) AS avg_latency_ms
            FROM agents a
            LEFT JOIN prompt_metrics p ON a.id = p.agent_id
            GROUP BY a.id, a.name, a.model, a.temperature, a.is_active
            ORDER BY total_prompts DESC;
        """
        rows = conn.execute(query).fetchall()
        return [dict(row) for row in rows]
    finally:
        conn.close()


def get_summary_metrics() -> dict[str, Any]:
    """Retrieve high-level summary overview."""
    conn = get_connection()
    try:
        today_str = datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%d")

        total_row = conn.execute(
            """
            SELECT
                COUNT(*) AS total_prompts,
                COALESCE(SUM(total_tokens), 0) AS total_tokens,
                COUNT(DISTINCT user_id) AS unique_users_all_time
            FROM prompt_metrics;
            """
        ).fetchone()

        today_row = conn.execute(
            """
            SELECT
                COUNT(*) AS prompts_today,
                COALESCE(SUM(total_tokens), 0) AS tokens_today,
                COUNT(DISTINCT user_id) AS unique_users_today
            FROM prompt_metrics
            WHERE date = ?;
            """,
            (today_str,),
        ).fetchone()

        return {
            "date": today_str,
            "total_prompts": total_row["total_prompts"],
            "total_tokens": total_row["total_tokens"],
            "unique_users_all_time": total_row["unique_users_all_time"],
            "prompts_today": today_row["prompts_today"],
            "tokens_today": today_row["tokens_today"],
            "unique_users_today": today_row["unique_users_today"],
        }
    finally:
        conn.close()


def list_agents() -> list[dict[str, Any]]:
    conn = get_connection()
    try:
        rows = conn.execute("SELECT * FROM agents ORDER BY id ASC;").fetchall()
        return [dict(row) for row in rows]
    finally:
        conn.close()


def get_agent(agent_id: str) -> dict[str, Any] | None:
    conn = get_connection()
    try:
        row = conn.execute("SELECT * FROM agents WHERE id = ?;", (agent_id,)).fetchone()
        return dict(row) if row else None
    finally:
        conn.close()
