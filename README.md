
# Azure App Service Easy Auth + Angular + FastAPI (LLM Metrics Starter)

> 📖 **Production Architecture Guide**: See [docs/METRICS_AND_PRODUCTION_GUIDE.md](docs/METRICS_AND_PRODUCTION_GUIDE.md) for full instructions on migrating from SQLite to Azure Cosmos DB / PostgreSQL, integrating Azure OpenAI with Managed Identity, and enterprise monitoring with Application Insights.

Starter project demonstrating:
- Azure App Service Authentication (Easy Auth) with Microsoft Entra ID
- **AI Prompt Metrics Tracking**:
  - Number of prompts per user per day (`GET /api/metrics/prompts-per-user-per-day`)
  - Full audit log of input prompts and LLM responses (`GET /api/metrics/prompts`)
  - AI Agent configuration & usage telemetry (`GET /api/metrics/agents`)
  - Overall summary metrics & token consumption (`GET /api/metrics/summary`)
- **Fake OpenAI LLM Service**: Realistic simulated chat completions with token and latency tracking (zero OpenAI API charges)
- Angular UI with an interactive Prompt Sandbox, unauthorized page, and live metrics dashboard featuring selectable daily trends, agent usage charts, searchable/filterable prompt activity, and CSV exports
- FastAPI backend extracting user identity exclusively from Azure Easy Auth (`x-ms-client-principal`)
- Same-origin deployment, so Angular calls `/api/...` and login uses `/.auth/login/aad`

## Architecture

```text
Browser
  |  GET /
  v
Azure App Service (Easy Auth enabled, unauthenticated action = Allow anonymous)
  |-- Angular UI
  |     |-- /unauthorized page + Sign in button
  |     |-- Fake OpenAI Prompt Sandbox
  |     |-- Daily Prompts per User Table
  |     `-- Prompt Input & Response Audit Log
  |
  `-- FastAPI
        |-- reads x-ms-client-principal injected by Easy Auth
        |-- extracts user identity (userId, username, name, roles)
        |-- invokes FakeOpenAIService (simulates OpenAI chat completions)
        `-- logs prompt telemetry into SQLite metrics database:
              * Prompts per user per day
              * Input & response of prompts
              * Agent details & token metrics
```

## AI Metrics & Fake OpenAI Endpoints

| Method | Endpoint | Description | Auth Required |
|---|---|---|---|
| `POST` | `/api/chat` | Send prompt to Fake OpenAI LLM, logs prompt input/response & user metrics | Yes (Easy Auth) |
| `GET` | `/api/agents` | List AI agents (name, model, system prompt, temperature) | No |
| `GET` | `/api/agents/{agent_id}` | Retrieve details for a specific AI agent | No |
| `GET` | `/api/metrics/prompts-per-user-per-day` | Daily aggregated prompt counts, total tokens, avg latency per user | Yes (Easy Auth) |
| `GET` | `/api/metrics/prompts` | Audit log of prompt inputs, responses, agent details, tokens & latency | Yes (Easy Auth) |
| `GET` | `/api/metrics/agents` | Aggregated usage & token stats by agent | Yes (Easy Auth) |
| `GET` | `/api/metrics/summary` | Overall KPI summary (prompts today, total tokens, active users) | Yes (Easy Auth) |
| `GET` | `/api/me` | Current authenticated user identity derived from Easy Auth | Yes (Easy Auth) |

## 1. How Easy Auth Identifies Users

Azure App Service Easy Auth injects the `x-ms-client-principal` header into all incoming HTTP requests. The backend parses this base64 JSON payload:
- **User ID**: Stable object identifier (`userId` or `nameidentifier` claim)
- **Username**: Email or UPN (`preferred_username` or `upn` claim)
- **Roles**: App roles assigned in Microsoft Entra ID

No custom JWT parsing, secret keys, or separate user database are required. Every prompt execution in `/api/chat` automatically binds to the verified Easy Auth identity:

```python
@app.post("/api/chat")
def execute_prompt(
    payload: ChatPromptRequest,
    current_user: dict = Depends(get_current_user), # Populated from Easy Auth
):
    # Generates response using Fake OpenAI service
    llm_result = fake_openai.generate_chat_completion(...)

    # Records prompt input, response, tokens, latency, agent, and user
    log_prompt_metric(
        user_id=current_user["user_id"],
        user_name=current_user["username"],
        agent_id=payload.agent_id,
        prompt_input=payload.prompt,
        prompt_response=llm_result["choices"][0]["message"]["content"],
        ...
    )
```

## 2. Run Locally

### Backend

```bash
cd backend
python -m venv .venv
source .venv/bin/activate  # On Windows: .venv\Scripts\activate
pip install -r requirements.txt
uvicorn app.main:app --reload
```

Backend runs on `http://127.0.0.1:8000`. You can inspect interactive Swagger documentation at `http://127.0.0.1:8000/docs`.

#### Local Dev Auth Simulation:
To simulate authenticated requests locally without Azure App Service:
1. Set `ALLOW_DEV_AUTH=1` in your environment, or
2. Pass a mock `x-ms-client-principal` header in your requests. You can use the built-in helper `build_mock_easy_auth_header(...)` from `app.auth`.

To run the automated integration test verifying multi-user metrics:
```bash
python test_metrics.py
```

### Frontend

```bash
cd frontend
npm install
npm start
```

Frontend runs on `http://localhost:4200` with proxy configured to forward `/api` to `http://127.0.0.1:8000`.

## 3. Build & Deploy to Azure App Service

1. Build Angular:
```bash
cd frontend
npm run build
cp -r dist/azure-easyauth-angular-ui/browser/* ../backend/static/
```

2. Deploy the `backend` folder to your Azure Linux App Service (Python 3.11+).
3. In Azure Portal, enable **Authentication (Easy Auth)** with Microsoft Entra ID. Set unauthenticated request handling to **Allow unauthenticated requests** so Angular can display its custom unauthorized view.
