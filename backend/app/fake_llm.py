"""Fake OpenAI LLM service.

Simulates OpenAI's Chat Completion API with realistic dummy responses,
token usage calculation, and latency tracking without incurring OpenAI API costs.
"""

from __future__ import annotations

import random
import time
import uuid
from typing import Any


class FakeOpenAIService:
    """Simulates OpenAI LLM chat completions with deterministic dummy responses and realistic token usage."""

    SUPPORTED_MODELS = [
        "fake-gpt-4o",
        "fake-gpt-4-turbo",
        "fake-gpt-3.5-turbo",
        "fake-gpt-4o-mini",
    ]

    @staticmethod
    def _estimate_tokens(text: str) -> int:
        """Rough token estimation (approx 1 token per 4 characters / 0.75 words, minimum 1)."""
        if not text:
            return 0
        words = len(text.strip().split())
        chars = len(text)
        return max(1, int((words * 1.3 + chars / 4) / 2))

    def generate_chat_completion(
        self,
        messages: list[dict[str, str]],
        model: str = "fake-gpt-4o",
        temperature: float = 0.7,
        agent_role: str | None = None,
        simulate_delay: bool = True,
    ) -> dict[str, Any]:
        """
        Generate a simulated ChatCompletion response.

        Args:
            messages: List of chat messages [{"role": "system"|"user", "content": "..."}]
            model: Name of the fake model
            temperature: Sampling temperature
            agent_role: Optional role or name of agent to flavor the response
            simulate_delay: Whether to sleep slightly to mimic real LLM API latency

        Returns:
            Dictionary matching standard OpenAI chat completion response + token & latency metrics
        """
        start_time = time.perf_counter()

        # Extract system prompt and latest user prompt
        system_prompt = ""
        user_prompt = ""
        for msg in messages:
            role = msg.get("role")
            content = msg.get("content", "")
            if role == "system":
                system_prompt = content
            elif role == "user":
                user_prompt = content

        # Simulate network & inference latency (50ms - 200ms)
        if simulate_delay:
            time.sleep(random.uniform(0.05, 0.20))

        # Generate realistic dummy response tailored to user input & agent role
        response_text = self._build_dummy_response(user_prompt, system_prompt, agent_role)

        end_time = time.perf_counter()
        latency_ms = round((end_time - start_time) * 1000, 2)

        # Estimate tokens
        prompt_text = " ".join([m.get("content", "") for m in messages])
        prompt_tokens = self._estimate_tokens(prompt_text)
        completion_tokens = self._estimate_tokens(response_text)
        total_tokens = prompt_tokens + completion_tokens

        completion_id = f"chatcmpl-{uuid.uuid4().hex[:16]}"

        return {
            "id": completion_id,
            "object": "chat.completion",
            "created": int(time.time()),
            "model": model if model in self.SUPPORTED_MODELS else "fake-gpt-4o",
            "choices": [
                {
                    "index": 0,
                    "message": {
                        "role": "assistant",
                        "content": response_text,
                    },
                    "finish_reason": "stop",
                }
            ],
            "usage": {
                "prompt_tokens": prompt_tokens,
                "completion_tokens": completion_tokens,
                "total_tokens": total_tokens,
            },
            "latency_ms": latency_ms,
        }

    def _build_dummy_response(
        self,
        user_prompt: str,
        system_prompt: str,
        agent_role: str | None,
    ) -> str:
        prompt_lower = user_prompt.lower()
        role_lower = (agent_role or "").lower()

        # 1. Code-oriented agent or code request
        if "code" in role_lower or "python" in prompt_lower or "fastapi" in prompt_lower or "sql" in prompt_lower:
            return (
                f"[Fake OpenAI Assistant - Code Specialist]\n\n"
                f"Here is a recommended implementation addressing your inquiry: \"{user_prompt}\":\n\n"
                f"```python\n"
                f"# Demonstration snippet generated for prompt context\n"
                f"def process_request(data: dict) -> dict:\n"
                f"    # Validating and handling input\n"
                f"    result = {{'status': 'success', 'input_length': len(str(data))}}\n"
                f"    return result\n"
                f"```\n\n"
                f"Key considerations:\n"
                f"1. Ensure input sanitization and authorization verification.\n"
                f"2. Use structured error handling and logging.\n"
                f"3. All requests are authenticated via Azure Easy Auth."
            )

        # 2. Analytics / Metrics agent
        if "analyst" in role_lower or "metric" in prompt_lower or "kpi" in prompt_lower or "report" in prompt_lower:
            return (
                f"[Fake OpenAI Assistant - Data & Analytics]\n\n"
                f"Analytics summary based on your prompt: \"{user_prompt}\":\n\n"
                f"• Metric Category: User Engagement & Prompt Volume\n"
                f"• Daily Prompt Velocity: Within normal operational thresholds (99.4% SLA)\n"
                f"• Token Efficiency: Optimal prompt-to-response token ratio\n"
                f"• Recommendation: Track active user trends per day to identify peak usage hours."
            )

        # 3. Customer Support agent
        if "support" in role_lower or "help" in prompt_lower or "problem" in prompt_lower or "issue" in prompt_lower:
            return (
                f"[Fake OpenAI Assistant - Customer Support]\n\n"
                f"Thank you for contacting support regarding: \"{user_prompt}\".\n\n"
                f"We have acknowledged your request. Your session is authenticated via Azure Easy Auth, "
                f"and all telemetry has been registered. If you need further assistance with your account "
                f"or services, our team is available 24/7."
            )

        # 4. Default intelligent dummy response
        return (
            f"[Fake OpenAI Assistant Response]\n\n"
            f"You asked: \"{user_prompt}\"\n\n"
            f"This is a simulated response generated by the Fake OpenAI LLM engine. "
            f"The prompt has been evaluated against system guidelines (Agent: {agent_role or 'General Assistant'}). "
            f"Execution telemetry including prompt tokens, completion tokens, latency, and user identity "
            f"has been recorded to the metrics database."
        )


fake_openai = FakeOpenAIService()
