import { Injectable } from '@angular/core';
import { HttpClient, HttpErrorResponse } from '@angular/common/http';
import { Observable, catchError, throwError } from 'rxjs';

export interface UserSummary {
  authenticated: boolean;
  user_id?: string | null;
  provider?: string | null;
  name?: string | null;
  username?: string | null;
  roles: string[];
}

export interface Agent {
  id: string;
  name: string;
  description: string;
  system_prompt: string;
  model: string;
  temperature: number;
  is_active: boolean;
  created_at: string;
}

export interface TokenUsage {
  prompt_tokens: number;
  completion_tokens: number;
  total_tokens: number;
}

export interface ChatPromptResponse {
  prompt_id: string;
  agent_id: string;
  agent_name: string;
  model: string;
  user_id: string;
  user_name: string;
  input: string;
  response: string;
  usage: TokenUsage;
  latency_ms: number;
  timestamp: string;
  daily_quota_limit?: number;
  daily_quota_remaining?: number;
}

export interface UserQuota {
  user_id: string;
  username: string;
  date: string;
  daily_limit: number;
  used_today: number;
  remaining: number;
}

export interface UserDailyMetric {
  user_id: string;
  user_name: string;
  date: string;
  prompt_count: number;
  total_input_tokens: number;
  total_output_tokens: number;
  total_tokens: number;
  avg_latency_ms: number;
}

export interface PromptLogItem {
  id: string;
  user_id: string;
  user_name: string;
  agent_id: string;
  agent_name: string;
  model: string;
  prompt_input: string;
  prompt_response: string;
  input_tokens: number;
  output_tokens: number;
  total_tokens: number;
  latency_ms: number;
  created_at: string;
  date: string;
}

export interface AgentMetricItem {
  agent_id: string;
  agent_name: string;
  model: string;
  temperature: number;
  is_active: boolean;
  total_prompts: number;
  total_tokens: number;
  unique_users: number;
  avg_latency_ms: number;
}

export interface MetricsSummary {
  date: string;
  total_prompts: number;
  total_tokens: number;
  unique_users_all_time: number;
  prompts_today: number;
  tokens_today: number;
  unique_users_today: number;
}

@Injectable({ providedIn: 'root' })
export class ApiService {
  private readonly apiBase = '/api';

  constructor(private readonly http: HttpClient) {}

  me(): Observable<UserSummary> {
    return this.http.get<UserSummary>(`${this.apiBase}/me`).pipe(
      catchError((error: HttpErrorResponse) => throwError(() => error))
    );
  }

  documents(): Observable<unknown> {
    return this.http.get(`${this.apiBase}/documents`);
  }

  admin(): Observable<unknown> {
    return this.http.get(`${this.apiBase}/admin`);
  }

  getQuota(): Observable<UserQuota> {
    return this.http.get<UserQuota>(`${this.apiBase}/me/quota`);
  }

  getAgents(): Observable<Agent[]> {
    return this.http.get<Agent[]>(`${this.apiBase}/agents`);
  }

  sendPrompt(agentId: string, prompt: string): Observable<ChatPromptResponse> {
    return this.http.post<ChatPromptResponse>(`${this.apiBase}/chat`, {
      agent_id: agentId,
      prompt: prompt
    });
  }

  getUserDailyMetrics(startDate?: string): Observable<UserDailyMetric[]> {
    const params = startDate ? `?start_date=${encodeURIComponent(startDate)}` : '';
    return this.http.get<UserDailyMetric[]>(`${this.apiBase}/metrics/prompts-per-user-per-day${params}`);
  }

  getPromptHistory(limit: number = 20): Observable<PromptLogItem[]> {
    return this.http.get<PromptLogItem[]>(`${this.apiBase}/metrics/prompts?limit=${limit}`);
  }

  getAgentMetrics(): Observable<AgentMetricItem[]> {
    return this.http.get<AgentMetricItem[]>(`${this.apiBase}/metrics/agents`);
  }

  getMetricsSummary(): Observable<MetricsSummary> {
    return this.http.get<MetricsSummary>(`${this.apiBase}/metrics/summary`);
  }
}
