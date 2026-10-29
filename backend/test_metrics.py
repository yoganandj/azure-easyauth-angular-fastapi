"""End-to-end integration test verifying metrics tracking with Easy Auth and Fake OpenAI LLM."""

import json
from starlette.testclient import TestClient
from app.main import app
from app.auth import build_mock_easy_auth_header
from app.db import init_db

def test_easy_auth_metrics_flow():
    init_db()
    client = TestClient(app)

    # 1. Unauthenticated request to /api/chat should fail with 401
    unauth_resp = client.post("/api/chat", json={"prompt": "Hello"})
    assert unauth_resp.status_code == 401, f"Expected 401, got {unauth_resp.status_code}"
    print("✓ Unauthenticated request rejected with 401 as expected")

    # 2. Simulate User 1: Alice
    alice_header = {
        "x-ms-client-principal": build_mock_easy_auth_header(
            user_id="user-alice-001",
            name="Alice Smith",
            username="alice@contoso.com",
            roles=["Reader"]
        )
    }

    # Verify Alice's Easy Auth profile via /api/me
    me_resp = client.get("/api/me", headers=alice_header)
    assert me_resp.status_code == 200
    user_info = me_resp.json()
    assert user_info["user_id"] == "user-alice-001"
    assert user_info["username"] == "alice@contoso.com"
    print(f"✓ Alice authenticated via Easy Auth: {user_info['name']} ({user_info['username']})")

    # 3. Simulate User 2: Bob
    bob_header = {
        "x-ms-client-principal": build_mock_easy_auth_header(
            user_id="user-bob-002",
            name="Bob Jones",
            username="bob@contoso.com",
            roles=["Admin"]
        )
    }

    # 4. Check available AI agents
    agents_resp = client.get("/api/agents")
    assert agents_resp.status_code == 200
    agents = agents_resp.json()
    assert len(agents) >= 3
    print(f"✓ Found {len(agents)} agents: {[a['id'] for a in agents]}")

    # 5. Alice sends 2 prompts to Customer Support agent
    alice_prompts = [
        "How do I reset my account password?",
        "What are your business hours?",
    ]
    for p in alice_prompts:
        resp = client.post(
            "/api/chat",
            headers=alice_header,
            json={"agent_id": "agent-support", "prompt": p}
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["user_id"] == "user-alice-001"
        assert data["agent_id"] == "agent-support"
        assert len(data["response"]) > 0
        assert data["usage"]["total_tokens"] > 0
        assert data["latency_ms"] > 0
        print(f"  → Alice prompt executed: '{p}' | Tokens: {data['usage']['total_tokens']} | Latency: {data['latency_ms']}ms")

    # 6. Bob sends 3 prompts to Python & Cloud Architect agent
    bob_prompts = [
        "How do I deploy FastAPI with Azure Easy Auth?",
        "Can you write a Python function to validate JWT tokens?",
        "What is the best way to optimize SQLite for daily metric aggregations?",
    ]
    for p in bob_prompts:
        resp = client.post(
            "/api/chat",
            headers=bob_header,
            json={"agent_id": "agent-code", "prompt": p}
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["user_id"] == "user-bob-002"
        assert data["agent_id"] == "agent-code"
        print(f"  → Bob prompt executed: '{p[:35]}...' | Tokens: {data['usage']['total_tokens']} | Latency: {data['latency_ms']}ms")

    # 7. Verify Metric: Prompts per user per day
    daily_resp = client.get("/api/metrics/prompts-per-user-per-day", headers=alice_header)
    assert daily_resp.status_code == 200
    daily_metrics = daily_resp.json()
    print("\n--- Prompts Per User Per Day ---")
    for row in daily_metrics:
        print(f"User: {row['user_name']} ({row['user_id']}) | Date: {row['date']} | Prompts: {row['prompt_count']} | Tokens: {row['total_tokens']} | Avg Latency: {row['avg_latency_ms']}ms")

    bob_stat = next(m for m in daily_metrics if m["user_id"] == "user-bob-002")
    alice_stat = next(m for m in daily_metrics if m["user_id"] == "user-alice-001")
    assert bob_stat["prompt_count"] >= 3
    assert alice_stat["prompt_count"] >= 2

    # 8. Verify Metric: Detailed Prompt Log (Input and Response)
    logs_resp = client.get("/api/metrics/prompts?limit=5", headers=alice_header)
    assert logs_resp.status_code == 200
    logs = logs_resp.json()
    print("\n--- Recent Prompt Logs (Input and Response) ---")
    for item in logs[:2]:
        print(f"ID: {item['id']}")
        print(f"User: {item['user_name']} | Agent: {item['agent_name']} ({item['agent_id']}) | Model: {item['model']}")
        print(f"Input: {item['prompt_input']}")
        print(f"Response: {item['prompt_response'][:80]}...")
        print(f"Tokens: {item['total_tokens']} (in: {item['input_tokens']}, out: {item['output_tokens']}) | Latency: {item['latency_ms']}ms")
        print("-" * 50)

    # 9. Verify Metric: Agent Usage
    agent_metrics_resp = client.get("/api/metrics/agents", headers=alice_header)
    assert agent_metrics_resp.status_code == 200
    agent_stats = agent_metrics_resp.json()
    print("\n--- Agent Usage Metrics ---")
    for a in agent_stats:
        print(f"Agent: {a['agent_name']} | Prompts: {a['total_prompts']} | Tokens: {a['total_tokens']} | Unique Users: {a['unique_users']}")

    # 10. Verify Metric: Overall Summary
    summary_resp = client.get("/api/metrics/summary", headers=alice_header)
    assert summary_resp.status_code == 200
    summary = summary_resp.json()
    print("\n--- System Metrics Summary ---")
    print(json.dumps(summary, indent=2))
    assert summary["total_prompts"] >= 5
    assert summary["unique_users_today"] >= 2

    # 11. Verify User Quota endpoint
    quota_resp = client.get("/api/me/quota", headers=alice_header)
    assert quota_resp.status_code == 200
    q_data = quota_resp.json()
    assert q_data["user_id"] == "user-alice-001"
    assert q_data["used_today"] >= 2
    print(f"\n✓ User Quota Endpoint OK: Used {q_data['used_today']}/{q_data['daily_limit']} (Remaining: {q_data['remaining']})")

    # 12. Verify Rate Limiting / Quota Enforcement (HTTP 429)
    import app.main as main_module
    original_limit = main_module.MAX_DAILY_PROMPTS_PER_USER
    try:
        # Set limit for testing rate limit rejection
        main_module.MAX_DAILY_PROMPTS_PER_USER = 2
        rate_limited_resp = client.post(
            "/api/chat",
            headers=alice_header,
            json={"agent_id": "agent-support", "prompt": "This should be blocked by rate limiting"}
        )
        assert rate_limited_resp.status_code == 429, f"Expected 429, got {rate_limited_resp.status_code}"
        assert "Daily prompt limit" in rate_limited_resp.json()["detail"]
        assert rate_limited_resp.headers.get("X-RateLimit-Remaining") == "0"
        print(f"✓ Rate Limiting Quota Enforcement OK: Blocked with HTTP 429 (Headers: {rate_limited_resp.headers.get('X-RateLimit-Limit')})")
    finally:
        main_module.MAX_DAILY_PROMPTS_PER_USER = original_limit

    print("\n ALL TESTS PASSED SUCCESSFULLY! ")

if __name__ == "__main__":
    test_easy_auth_metrics_flow()
