import { CommonModule } from '@angular/common';
import { Component, OnInit } from '@angular/core';
import { FormsModule } from '@angular/forms';
import { Router } from '@angular/router';
import {
  ApiService,
  UserSummary,
  Agent,
  ChatPromptResponse,
  UserDailyMetric,
  PromptLogItem,
  AgentMetricItem,
  MetricsSummary,
  UserQuota
} from './api.service';
import { HttpErrorResponse } from '@angular/common/http';

interface DailyTrend {
  date: string;
  label: string;
  prompts: number;
  totalTokens: number;
}

@Component({
  standalone: true,
  selector: 'app-home',
  template: `
    <section class="card dashboard">
      <div class="header-row">
        <div class="header-copy">
          <div class="eyebrow">OPERATIONS <span>/</span> INSIGHTS</div>
          <h1>Metrics Dashboard</h1>
          <p class="muted">
            A live view of prompt activity, token consumption, and agent performance.
          </p>
        </div>
        <div *ngIf="user" class="header-tools">
          <div class="live-status"><span class="status-dot"></span> Connected</div>
          <div class="user-badge">
            <span class="avatar">{{ (user.username || user.name || 'U').charAt(0).toUpperCase() }}</span>
            <span class="user-badge-copy">
              <strong>{{ user.username || user.name }}</strong>
              <span class="provider">{{ user.provider || 'Microsoft Entra ID' }}</span>
            </span>
          </div>
        </div>
      </div>

      <p *ngIf="loading">Checking your sign-in status…</p>
      <p *ngIf="errorMessage" class="error">{{ errorMessage }}</p>

      <ng-container *ngIf="user as currentUser">
        <div class="user-meta">
          <div class="auth-title"><span class="auth-check">✓</span><strong>Secure session</strong><span>Authenticated through Azure App Service Easy Auth</span></div>
          <div class="auth-details">
            <p><strong>User ID</strong><code>{{ currentUser.user_id }}</code></p>
            <p><strong>Display name</strong><span>{{ currentUser.name || 'Not supplied' }}</span></p>
            <p><strong>Roles</strong><span>{{ currentUser.roles.length ? currentUser.roles.join(', ') : 'No application roles' }}</span></p>
          </div>
        </div>

        <!-- 1. KPI Summary Cards -->
        <div class="metrics-grid">
          <div
            class="metric-card"
            [ngClass]="isQuotaExhausted ? 'quota-exhausted-card' : 'highlight-card'"
            *ngIf="quota"
          >
            <span class="metric-icon">⌁</span>
            <span class="metric-val">{{ quota.remaining }} <small>/ {{ quota.daily_limit }}</small></span>
            <span class="metric-label">{{ isQuotaExhausted ? 'Daily Quota Exhausted' : 'Your Daily Quota Remaining' }}</span>
          </div>
          <div class="metric-card" *ngIf="summary">
            <span class="metric-icon">↗</span>
            <span class="metric-val">{{ summary.prompts_today }}</span>
            <span class="metric-label">Prompts today <small>All users</small></span>
          </div>
          <div class="metric-card" *ngIf="summary">
            <span class="metric-icon">▤</span>
            <span class="metric-val">{{ summary.total_prompts }}</span>
            <span class="metric-label">Total prompts <small>All time</small></span>
          </div>
          <div class="metric-card" *ngIf="summary">
            <span class="metric-icon">◈</span>
            <span class="metric-val">{{ summary.tokens_today | number }}</span>
            <span class="metric-label">Tokens consumed <small>Today</small></span>
          </div>
          <div class="metric-card" *ngIf="summary">
            <span class="metric-icon">◎</span>
            <span class="metric-val">{{ summary.unique_users_today }}</span>
            <span class="metric-label">Active users <small>Today</small></span>
          </div>
        </div>

        <div class="analytics-grid">
          <section class="chart-card" aria-labelledby="daily-trend-title">
            <div class="chart-heading">
              <div>
                <h2 id="daily-trend-title">Prompt volume</h2>
                <p>Daily prompts across all users</p>
              </div>
              <span class="chart-total">{{ trendPromptTotal | number }} <small>prompts</small></span>
            </div>
            <div class="trend-chart" role="img" aria-label="Daily prompt volume chart">
              <div class="trend-column" *ngFor="let day of dailyTrend">
                <span class="bar-value">{{ day.prompts }}</span>
                <div class="bar-track">
                  <div class="bar-fill" [style.height.%]="trendBarHeight(day.prompts)"></div>
                </div>
                <small [title]="day.date">{{ day.label }}</small>
              </div>
              <div class="chart-empty" *ngIf="!dailyTrend.length">No prompt activity for this period yet.</div>
            </div>
            <div class="chart-footer">
              <span>{{ dailyTrend.length }} day{{ dailyTrend.length === 1 ? '' : 's' }} shown</span>
              <label class="range-control">
                <span>Period</span>
                <select [(ngModel)]="selectedTrendRange" (change)="onTrendRangeChanged()" aria-label="Trend date range">
                  <option value="7">Last 7 days</option>
                  <option value="30">Last 30 days</option>
                  <option value="all">All time</option>
                </select>
              </label>
            </div>
          </section>

          <section class="chart-card" aria-labelledby="agent-usage-title">
            <div class="chart-heading">
              <div>
                <h2 id="agent-usage-title">Agent usage</h2>
                <p>Prompt distribution by agent</p>
              </div>
              <span class="chart-total">{{ (summary?.total_prompts || 0) | number }} <small>total</small></span>
            </div>
            <div class="agent-chart">
              <div class="agent-bar-row" *ngFor="let agent of agentUsage">
                <div class="agent-bar-label">
                  <span>{{ agent.agent_name }}</span>
                  <strong>{{ agent.total_prompts | number }}</strong>
                </div>
                <div class="agent-track">
                  <div class="agent-fill" [style.width.%]="agentBarWidth(agent.total_prompts)"></div>
                </div>
              </div>
              <div class="chart-empty" *ngIf="!agentMetrics.length">Agent usage will appear when metrics are available.</div>
            </div>
            <div class="chart-footer"><span>{{ agentMetrics.length }} configured agents</span><span>Ranked by prompts</span></div>
          </section>
        </div>

        <!-- 2. Fake OpenAI Chat Sandbox -->
        <div class="section-box">
          <div class="section-heading">
            <span class="section-icon">✳</span>
            <div><h2>Prompt playground</h2><p class="muted">Test an agent and inspect the execution telemetry.</p></div>
          </div>
          <p class="muted">
            Sends prompts to the simulated OpenAI model. Every call captures the authenticated Easy Auth principal, input, response, tokens, and latency.
          </p>

          <!-- ENRICHED QUOTA EXCEEDED BANNER -->
          <div *ngIf="isQuotaExhausted" class="quota-warning-banner">
            <div class="quota-banner-icon">🛑</div>
            <div class="quota-banner-body">
              <div class="quota-banner-header">
                <h3>Daily Prompt Quota Exceeded</h3>
                <span class="quota-pill">HTTP 429 Protected</span>
              </div>
              <p>
                You have reached your daily limit of <strong>{{ quota?.daily_limit || 50 }} prompts</strong> for today ({{ quota?.date || 'today' }}).
                To protect system resources and manage LLM costs, further prompt submissions are paused until your quota resets.
              </p>
              <div class="quota-progress-container">
                <div class="quota-progress-bar"></div>
              </div>
              <div class="quota-footer-info">
                <span>🕒 Automatic Reset: <strong>Tomorrow at 00:00 UTC</strong></span>
                <span>👤 User: <code>{{ currentUser.username || currentUser.user_id }}</code></span>
              </div>
              <div class="quota-banner-actions">
                <button class="secondary btn-sm" (click)="checkQuota()">🔄 Check Quota Status</button>
              </div>
            </div>
          </div>

          <div class="form-row">
            <label><strong>Select AI agent</strong></label>
            <select [(ngModel)]="selectedAgentId" (change)="onAgentChanged()">
              <option *ngFor="let agent of agents" [value]="agent.id">
                {{ agent.name }} ({{ agent.model }})
              </option>
            </select>
          </div>

          <p class="agent-desc" *ngIf="currentAgent">
            <em>{{ currentAgent.description }}</em> &mdash; System prompt: <code>{{ currentAgent.system_prompt }}</code>
          </p>

          <div class="form-row">
            <label><strong>Your prompt</strong></label>
            <textarea
              [(ngModel)]="promptInput"
              rows="3"
              [disabled]="submittingPrompt || isQuotaExhausted"
              [placeholder]="placeholderText"
            ></textarea>
          </div>

          <div class="actions">
            <button
              class="primary"
              [disabled]="submittingPrompt || !promptInput.trim() || isQuotaExhausted"
              (click)="sendPrompt()"
            >
              {{ isQuotaExhausted ? 'Daily quota reached' : (submittingPrompt ? 'Simulating agent…' : 'Run prompt') }}
            </button>
            <button class="secondary" (click)="refreshMetrics()">Refresh Metrics</button>
            <button class="secondary" (click)="signOut()">Sign out</button>
          </div>

          <!-- Latest Prompt Result -->
          <div *ngIf="latestResponse" class="response-box">
            <h3>Latest Prompt Execution & Telemetry</h3>
            <div class="telemetry-bar">
              <span><strong>Prompt ID:</strong> <code>{{ latestResponse.prompt_id.substring(0, 8) }}...</code></span>
              <span><strong>Agent:</strong> {{ latestResponse.agent_name }}</span>
              <span><strong>Model:</strong> {{ latestResponse.model }}</span>
              <span><strong>Tokens:</strong> {{ latestResponse.usage.total_tokens }} (In: {{ latestResponse.usage.prompt_tokens }}, Out: {{ latestResponse.usage.completion_tokens }})</span>
              <span><strong>Latency:</strong> {{ latestResponse.latency_ms }} ms</span>
            </div>
            <div class="prompt-text">
              <strong>User Input:</strong>
              <p>{{ latestResponse.input }}</p>
            </div>
            <div class="response-text">
              <strong>Fake OpenAI Response:</strong>
              <pre>{{ latestResponse.response }}</pre>
            </div>
          </div>
        </div>

        <!-- 3. Metrics: Number of Prompts Per User Per Day -->
        <div class="section-box">
          <div class="section-topline">
            <div class="section-heading">
              <span class="section-icon">▥</span>
              <div><h2>Daily usage by user</h2><p class="muted">Prompt and token activity grouped by authenticated identity.</p></div>
            </div>
            <button class="secondary btn-sm" (click)="exportDailyMetrics()" [disabled]="!dailyMetrics.length">Export CSV</button>
          </div>

          <div class="table-container" *ngIf="dailyMetrics.length; else noDaily">
            <table>
              <thead>
                <tr>
                  <th>User ID / Username</th>
                  <th>Date</th>
                  <th>Prompt Count</th>
                  <th>Input Tokens</th>
                  <th>Output Tokens</th>
                  <th>Total Tokens</th>
                  <th>Avg Latency (ms)</th>
                </tr>
              </thead>
              <tbody>
                <tr *ngFor="let row of dailyMetrics">
                  <td>
                    <strong>{{ row.user_name }}</strong>
                    <div class="sub-text">{{ row.user_id }}</div>
                  </td>
                  <td>{{ row.date }}</td>
                  <td><span class="count-pill">{{ row.prompt_count }}</span></td>
                  <td>{{ row.total_input_tokens | number }}</td>
                  <td>{{ row.total_output_tokens | number }}</td>
                  <td><strong>{{ row.total_tokens | number }}</strong></td>
                  <td>{{ row.avg_latency_ms }} ms</td>
                </tr>
              </tbody>
            </table>
          </div>
          <ng-template #noDaily>
            <p class="muted">No daily prompt metrics recorded yet.</p>
          </ng-template>
        </div>

        <!-- 4. Metrics: Prompt Input and Response Logs -->
        <div class="section-box">
          <div class="section-topline">
            <div class="section-heading">
              <span class="section-icon">≡</span>
              <div><h2>Recent prompt activity</h2><p class="muted">Search and filter the latest 50 prompts and their execution telemetry.</p></div>
            </div>
            <button class="secondary btn-sm" (click)="exportPromptLogs()" [disabled]="!filteredPromptLogs.length">Export CSV</button>
          </div>

          <div class="activity-toolbar">
            <label class="search-control">
              <span class="search-icon" aria-hidden="true">⌕</span>
              <input type="search" [(ngModel)]="promptSearch" placeholder="Search prompts, users, or responses" aria-label="Search prompt activity">
            </label>
            <select [(ngModel)]="promptAgentFilter" aria-label="Filter by agent">
              <option value="">All agents</option>
              <option *ngFor="let agent of agents" [value]="agent.id">{{ agent.name }}</option>
            </select>
            <span class="result-count">{{ filteredPromptLogs.length }} of {{ promptLogs.length }} records</span>
            <button class="text-button" *ngIf="promptSearch || promptAgentFilter" (click)="clearPromptFilters()">Clear filters</button>
          </div>

          <div class="table-container" *ngIf="filteredPromptLogs.length; else noLogs">
            <table>
              <thead>
                <tr>
                  <th>Timestamp</th>
                  <th>User</th>
                  <th>Agent & Model</th>
                  <th>Input Prompt</th>
                  <th>LLM Response</th>
                  <th>Tokens</th>
                  <th>Latency</th>
                </tr>
              </thead>
              <tbody>
                <tr *ngFor="let log of filteredPromptLogs">
                  <td class="small">{{ log.created_at | date:'short' }}</td>
                  <td><strong>{{ log.user_name }}</strong></td>
                  <td>
                    {{ log.agent_name }}
                    <div class="sub-text">{{ log.model }}</div>
                  </td>
                  <td class="cell-text">{{ log.prompt_input }}</td>
                  <td class="cell-text">
                    <details>
                      <summary>{{ log.prompt_response.substring(0, 70) }}...</summary>
                      <pre class="inner-pre">{{ log.prompt_response }}</pre>
                    </details>
                  </td>
                  <td>{{ log.total_tokens }}</td>
                  <td>{{ log.latency_ms }} ms</td>
                </tr>
              </tbody>
            </table>
          </div>
          <ng-template #noLogs>
            <div class="empty-state">
              <span class="empty-icon">⌕</span>
              <strong>{{ promptLogs.length ? 'No matching prompts' : 'No prompt activity yet' }}</strong>
              <span>{{ promptLogs.length ? 'Try another search or clear the current filters.' : 'Run a prompt in the playground to start building your activity history.' }}</span>
            </div>
          </ng-template>
        </div>

        <!-- 5. Metrics: Agent Details & Statistics -->
        <div class="section-box">
          <div class="section-heading">
            <span class="section-icon">◇</span>
            <div><h2>Agent performance</h2><p class="muted">Usage and latency breakdown across available agents.</p></div>
          </div>
          <div class="table-container" *ngIf="agentMetrics.length">
            <table>
              <thead>
                <tr>
                  <th>Agent Name</th>
                  <th>Model</th>
                  <th>Temperature</th>
                  <th>Total Prompts</th>
                  <th>Total Tokens</th>
                  <th>Unique Users</th>
                  <th>Avg Latency</th>
                </tr>
              </thead>
              <tbody>
                <tr *ngFor="let a of agentMetrics">
                  <td><strong>{{ a.agent_name }}</strong> (<code>{{ a.agent_id }}</code>)</td>
                  <td>{{ a.model }}</td>
                  <td>{{ a.temperature }}</td>
                  <td><span class="count-pill">{{ a.total_prompts }}</span></td>
                  <td>{{ a.total_tokens | number }}</td>
                  <td>{{ a.unique_users }}</td>
                  <td>{{ a.avg_latency_ms }} ms</td>
                </tr>
              </tbody>
            </table>
          </div>
        </div>
      </ng-container>

      <div class="actions" *ngIf="!loading && !user">
        <button class="primary" (click)="signIn()">Sign in with Microsoft</button>
      </div>
    </section>
  `,
  styles: [`
    :host { display: block; }
    .header-row { display: flex; justify-content: space-between; align-items: center; flex-wrap: wrap; gap: 22px; margin-bottom: 25px; }
    .header-copy { min-width: min(100%, 430px); }
    .eyebrow { color: #5272aa; font-size: 10px; font-weight: 800; letter-spacing: .17em; margin-bottom: 10px; }
    .eyebrow span { color: #b6c3d6; padding: 0 5px; }
    .header-row h1 { margin: 0; color: #172b4d; font-size: clamp(28px, 3.5vw, 38px); letter-spacing: -.045em; line-height: 1.1; }
    .header-row .muted { margin: 10px 0 0; max-width: 580px; font-size: 14px; }
    .header-tools { display: flex; align-items: center; gap: 15px; flex-wrap: wrap; }
    .live-status { display: flex; align-items: center; gap: 7px; color: #58708f; font-size: 12px; font-weight: 650; }
    .status-dot { width: 8px; height: 8px; border-radius: 50%; background: #22a06b; box-shadow: 0 0 0 4px #e4f6ed; }
    .user-badge { display: flex; align-items: center; gap: 10px; background: #f8faff; padding: 8px 12px 8px 8px; border-radius: 12px; border: 1px solid #e6ecf5; }
    .avatar { display: grid; place-items: center; width: 34px; height: 34px; border-radius: 10px; background: #e5edff; color: #2459d3; font-size: 14px; font-weight: 800; }
    .user-badge-copy strong, .user-badge .provider { display: block; }
    .user-badge-copy strong { color: #2b3d58; font-size: 12px; }
    .user-badge .provider { margin-top: 3px; font-size: 11px; color: #8190a5; }
    .user-meta { background: #f7fbf9; border: 1px solid #e1f0e8; border-radius: 12px; padding: 13px 16px; margin-bottom: 20px; }
    .auth-title { display: flex; align-items: center; gap: 9px; color: #315d49; font-size: 12px; }
    .auth-title > span:last-child { color: #718578; }
    .auth-check { display: grid; place-items: center; width: 20px; height: 20px; border-radius: 50%; background: #dff3e8; color: #178451; font-size: 12px; font-weight: 800; }
    .auth-details { display: flex; gap: 30px; flex-wrap: wrap; margin: 12px 0 0 29px; }
    .auth-details p { display: flex; flex-direction: column; gap: 4px; margin: 0; font-size: 12px; color: #66778a; }
    .auth-details p strong { color: #8997a8; font-size: 10px; font-weight: 700; text-transform: uppercase; letter-spacing: .07em; }
    .auth-details code { color: #415875; }
    .metrics-grid { display: grid; grid-template-columns: repeat(5, minmax(0, 1fr)); gap: 13px; margin-bottom: 30px; }
    .metric-card { position: relative; min-height: 139px; padding: 18px 17px 16px; overflow: hidden; background: linear-gradient(145deg, #fff, #fbfcff); border: 1px solid #e6ebf3; border-radius: 13px; box-shadow: 0 3px 12px rgba(32, 54, 87, .035); transition: transform .18s ease, box-shadow .18s ease; }
    .metric-card:hover { transform: translateY(-2px); box-shadow: 0 8px 20px rgba(32, 54, 87, .08); }
    .metric-icon { display: grid; place-items: center; width: 28px; height: 28px; margin-bottom: 11px; color: #3567cb; background: #edf3ff; border-radius: 8px; font-size: 16px; font-weight: 750; }
    .highlight-card { background: linear-gradient(145deg, #f3fbf6, #fff); border-color: #d9eee1; }
    .highlight-card .metric-icon { color: #178451; background: #e1f4e8; }
    .highlight-card .metric-val { color: #178451; }
    .highlight-card .metric-val small { color: #76917f; }
    .quota-exhausted-card { background: linear-gradient(145deg, #fff7ed, #fff); border-color: #f8ddc0; }
    .quota-exhausted-card .metric-icon, .quota-exhausted-card .metric-val { color: #d35e1c; }
    .quota-exhausted-card .metric-icon { background: #ffead9; }
    .quota-exhausted-card .metric-label { color: #a95a2e; }
    .metric-val { display: block; color: #1e3150; font-size: 26px; font-weight: 750; letter-spacing: -.035em; line-height: 1.15; }
    .metric-val small { color: #8492a7; font-size: 14px; font-weight: 550; letter-spacing: 0; }
    .metric-label { display: block; margin-top: 5px; color: #66768d; font-size: 11px; font-weight: 650; }
    .metric-label small { color: #98a4b4; font-size: 10px; font-weight: 550; }
    .section-box { margin-top: 30px; padding-top: 25px; border-top: 1px solid #edf1f6; }
    .section-heading { display: flex; align-items: flex-start; gap: 12px; margin-bottom: 17px; }
    .section-icon { display: grid; place-items: center; flex: 0 0 36px; width: 36px; height: 36px; color: #3567cb; background: #edf3ff; border: 1px solid #e4ecfc; border-radius: 10px; font-size: 18px; font-weight: 750; }
    .section-heading h2 { margin: 1px 0 4px; color: #213552; font-size: 17px; letter-spacing: -.02em; }
    .section-heading .muted { margin: 0; font-size: 12px; }
    .section-box > .muted { font-size: 12px; margin: -4px 0 15px; }
    .form-row { margin-bottom: 16px; display: flex; flex-direction: column; gap: 8px; }
    .form-row label { color: #40536f; font-size: 12px; }
    select, textarea { width: 100%; padding: 12px 14px; color: #263b59; background: #fbfcfe; border: 1px solid #dce4ef; border-radius: 9px; font: inherit; font-size: 13px; transition: border-color .16s ease, box-shadow .16s ease; }
    select:focus, textarea:focus { outline: none; border-color: #6d91e5; box-shadow: 0 0 0 3px rgba(70, 111, 209, .1); }
    textarea { min-height: 92px; resize: vertical; line-height: 1.6; }
    textarea:disabled { background: #f8fafc; color: #64748b; cursor: not-allowed; border-color: #e2e8f0; }
    button:disabled { opacity: 0.6; cursor: not-allowed; }
    .agent-desc { padding: 11px 13px; color: #66768d; background: #f7f9fc; border-radius: 8px; font-size: 12px; line-height: 1.6; margin: 0 0 16px; }
    .agent-desc code { color: #4b5e7a; overflow-wrap: anywhere; }
    .quota-warning-banner { background: #fff8f1; border: 1px solid #fed7aa; border-left: 5px solid #ea580c; border-radius: 10px; padding: 16px 20px; margin-bottom: 20px; display: flex; gap: 16px; align-items: flex-start; box-shadow: 0 4px 12px rgba(234, 88, 12, .08); }
    .quota-banner-icon { font-size: 28px; line-height: 1; padding-top: 2px; }
    .quota-banner-body { flex: 1; }
    .quota-banner-header { display: flex; justify-content: space-between; align-items: center; flex-wrap: wrap; gap: 8px; margin-bottom: 6px; }
    .quota-banner-header h3 { margin: 0; font-size: 16px; color: #9a3412; }
    .quota-pill { background: #ffedd5; color: #c2410c; font-size: 11px; font-weight: 700; padding: 2px 8px; border-radius: 12px; border: 1px solid #fed7aa; text-transform: uppercase; }
    .quota-banner-body p { margin: 4px 0 10px; font-size: 13px; color: #7c2d12; line-height: 1.5; }
    .quota-progress-container { background: #fed7aa; border-radius: 6px; height: 8px; margin: 8px 0; overflow: hidden; }
    .quota-progress-bar { background: #ea580c; width: 100%; height: 100%; }
    .quota-footer-info { display: flex; justify-content: space-between; flex-wrap: wrap; font-size: 11px; color: #9a3412; margin-top: 8px; gap: 8px; }
    .quota-banner-actions { margin-top: 12px; }
    .btn-sm { padding: 6px 12px; font-size: 12px; }
    .response-box { margin-top: 22px; background: #f8faff; border: 1px solid #e2e9f4; border-radius: 12px; padding: 18px; }
    .response-box h3 { margin: 0 0 13px; font-size: 14px; color: #243955; }
    .telemetry-bar { display: flex; flex-wrap: wrap; gap: 8px; padding: 10px; border-radius: 8px; margin-bottom: 14px; background: #edf2fa; color: #51647e; font-size: 11px; }
    .telemetry-bar span { padding: 5px 8px; background: rgba(255,255,255,.72); border-radius: 6px; }
    .prompt-text, .response-text { margin-top: 12px; font-size: 12px; color: #50627d; }
    .prompt-text p { margin: 6px 0; padding: 10px 12px; color: #344965; background: #fff; border: 1px solid #e6ebf3; border-radius: 7px; }
    .response-text pre { margin-top: 6px; font-size: 12px; line-height: 1.6; white-space: pre-wrap; }
    .table-container { overflow-x: auto; margin-top: 14px; border: 1px solid #e7ecf3; border-radius: 10px; }
    table { width: 100%; border-collapse: separate; border-spacing: 0; font-size: 12px; text-align: left; }
    th { position: sticky; top: 0; background: #f7f9fc; padding: 11px 12px; color: #64748b; font-size: 10px; font-weight: 750; letter-spacing: .055em; text-transform: uppercase; white-space: nowrap; border-bottom: 1px solid #e7ecf3; }
    td { padding: 12px; color: #455770; border-bottom: 1px solid #eef1f5; vertical-align: top; }
    tbody tr:last-child td { border-bottom: 0; }
    tbody tr:hover td { background: #fafcff; }
    td strong { color: #2c405e; }
    td code { color: #61728b; font-size: 10px; }
    .sub-text { margin-top: 4px; font-size: 10px; color: #92a0b2; }
    .count-pill { background: #eaf1ff; color: #315db3; font-weight: 700; padding: 4px 9px; border-radius: 20px; font-size: 11px; display: inline-block; }
    .small { font-size: 11px; color: #718198; white-space: nowrap; }
    .cell-text { min-width: 150px; max-width: 240px; line-height: 1.5; word-break: break-word; }
    details summary { color: #315db3; cursor: pointer; }
    .inner-pre { margin: 6px 0 0; font-size: 11px; max-height: 150px; overflow-y: auto; white-space: pre-wrap; }
    @media (max-width: 1050px) { .metrics-grid { grid-template-columns: repeat(3, minmax(0, 1fr)); } }
    @media (max-width: 650px) {
      .header-row { align-items: flex-start; }
      .header-tools { width: 100%; justify-content: space-between; }
      .metrics-grid { grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 9px; }
      .metric-card { min-height: 124px; padding: 14px 12px; }
      .metric-val { font-size: 23px; }
      .auth-details { gap: 13px 22px; margin-left: 0; }
      .auth-title { align-items: flex-start; flex-wrap: wrap; }
      .auth-title > span:last-child { flex-basis: calc(100% - 30px); margin-left: 29px; margin-top: -6px; }
      .section-box { margin-top: 24px; padding-top: 21px; }
      .telemetry-bar { gap: 5px; }
      .quota-warning-banner { padding: 14px; }
    }
  `],
  imports: [CommonModule, FormsModule]
})
export class HomeComponent implements OnInit {
  loading = true;
  user: UserSummary | null = null;
  errorMessage = '';

  agents: Agent[] = [];
  selectedAgentId = 'agent-support';
  promptInput = 'Can you help me analyze user prompt metrics today?';
  submittingPrompt = false;
  latestResponse: ChatPromptResponse | null = null;

  dailyMetrics: UserDailyMetric[] = [];
  dailyTrend: DailyTrend[] = [];
  promptLogs: PromptLogItem[] = [];
  agentMetrics: AgentMetricItem[] = [];
  summary: MetricsSummary | null = null;
  quota: UserQuota | null = null;
  quotaExceeded = false;
  selectedTrendRange = '7';
  promptSearch = '';
  promptAgentFilter = '';

  constructor(private readonly api: ApiService, private readonly router: Router) {}

  get currentAgent(): Agent | undefined {
    return this.agents.find(a => a.id === this.selectedAgentId);
  }

  get isQuotaExhausted(): boolean {
    return (this.quota !== null && this.quota.daily_limit > 0 && this.quota.remaining <= 0) || this.quotaExceeded;
  }

  get placeholderText(): string {
    if (this.isQuotaExhausted) {
      const limit = this.quota?.daily_limit || 50;
      return `Daily prompt limit reached (${limit}/${limit}). Quota resets at 00:00 UTC.`;
    }
    return 'Ask a question or enter a prompt (e.g. How do I optimize metrics in Azure?)';
  }

  private buildDailyTrend(metrics: UserDailyMetric[]): DailyTrend[] {
    const byDate = new Map<string, DailyTrend>();
    for (const metric of metrics) {
      const current = byDate.get(metric.date) ?? {
        date: metric.date,
        label: new Date(`${metric.date}T00:00:00`).toLocaleDateString(undefined, { month: 'short', day: 'numeric' }),
        prompts: 0,
        totalTokens: 0
      };
      current.prompts += metric.prompt_count;
      current.totalTokens += metric.total_tokens;
      byDate.set(metric.date, current);
    }
    return Array.from(byDate.values()).sort((a, b) => a.date.localeCompare(b.date)).slice(-30);
  }

  get trendPromptTotal(): number {
    return this.dailyTrend.reduce((total, day) => total + day.prompts, 0);
  }

  get agentUsage(): AgentMetricItem[] {
    return [...this.agentMetrics].sort((a, b) => b.total_prompts - a.total_prompts);
  }

  get filteredPromptLogs(): PromptLogItem[] {
    const query = this.promptSearch.trim().toLocaleLowerCase();
    return this.promptLogs.filter(log => {
      const matchesAgent = !this.promptAgentFilter || log.agent_id === this.promptAgentFilter;
      const searchableText = `${log.user_name} ${log.agent_name} ${log.model} ${log.prompt_input} ${log.prompt_response}`.toLocaleLowerCase();
      return matchesAgent && (!query || searchableText.includes(query));
    });
  }

  trendBarHeight(value: number): number {
    const maximum = Math.max(1, ...this.dailyTrend.map(day => day.prompts));
    return value === 0 ? 0 : Math.max(5, value / maximum * 100);
  }

  agentBarWidth(value: number): number {
    const maximum = Math.max(1, ...this.agentMetrics.map(agent => agent.total_prompts));
    return value === 0 ? 0 : Math.max(3, value / maximum * 100);
  }

  onTrendRangeChanged(): void {
    const startDate = this.selectedTrendRange === 'all' ? undefined : this.getRangeStartDate(Number(this.selectedTrendRange));
    this.api.getUserDailyMetrics(startDate).subscribe({
      next: data => {
        this.dailyMetrics = data;
        this.dailyTrend = this.buildDailyTrend(data);
      },
      error: err => console.error('Daily metrics error', err)
    });
  }

  clearPromptFilters(): void {
    this.promptSearch = '';
    this.promptAgentFilter = '';
  }

  exportDailyMetrics(): void {
    const headers = ['User', 'User ID', 'Date', 'Prompts', 'Input Tokens', 'Output Tokens', 'Total Tokens', 'Average Latency (ms)'];
    const rows = this.dailyMetrics.map(row => [
      row.user_name, row.user_id, row.date, row.prompt_count,
      row.total_input_tokens, row.total_output_tokens, row.total_tokens, row.avg_latency_ms
    ]);
    this.downloadCsv('daily-usage', headers, rows);
  }

  exportPromptLogs(): void {
    const headers = ['Timestamp', 'User', 'Agent', 'Model', 'Input Prompt', 'Response', 'Input Tokens', 'Output Tokens', 'Total Tokens', 'Latency (ms)'];
    const rows = this.filteredPromptLogs.map(log => [
      log.created_at, log.user_name, log.agent_name, log.model,
      log.prompt_input, log.prompt_response, log.input_tokens,
      log.output_tokens, log.total_tokens, log.latency_ms
    ]);
    this.downloadCsv('prompt-activity', headers, rows);
  }

  ngOnInit(): void {
    this.api.me().subscribe({
      next: user => {
        this.user = user;
        this.loading = false;
        this.loadAgents();
        this.refreshMetrics();
      },
      error: (error: HttpErrorResponse) => {
        this.loading = false;
        if (error.status === 401) {
          void this.router.navigate(['/unauthorized']);
        } else {
          this.errorMessage = `Unable to check sign-in status (HTTP ${error.status || 'network error'}).`;
        }
      }
    });
  }

  loadAgents(): void {
    this.api.getAgents().subscribe({
      next: list => {
        this.agents = list;
        if (list.length > 0 && !this.selectedAgentId) {
          this.selectedAgentId = list[0].id;
        }
      },
      error: err => console.error('Failed to load agents', err)
    });
  }

  onAgentChanged(): void {
    if (this.selectedAgentId === 'agent-code') {
      this.promptInput = 'How do I optimize SQL queries for daily active user metrics?';
    } else if (this.selectedAgentId === 'agent-analyst') {
      this.promptInput = 'Summarize today\'s prompt token consumption and latency trends.';
    } else {
      this.promptInput = 'What are your support hours and how do I reset credentials?';
    }
  }

  sendPrompt(): void {
    if (!this.promptInput.trim() || this.isQuotaExhausted) return;
    this.submittingPrompt = true;

    this.api.sendPrompt(this.selectedAgentId, this.promptInput.trim()).subscribe({
      next: resp => {
        this.latestResponse = resp;
        this.submittingPrompt = false;
        this.refreshMetrics();
      },
      error: (err: HttpErrorResponse) => {
        this.submittingPrompt = false;
        this.handleApiError(err);
      }
    });
  }

  checkQuota(): void {
    this.api.getQuota().subscribe({
      next: data => {
        this.quota = data;
        this.quotaExceeded = data.daily_limit > 0 && data.remaining <= 0;
      },
      error: err => console.error('Quota check failed', err)
    });
  }

  refreshMetrics(): void {
    this.checkQuota();
    this.onTrendRangeChanged();

    this.api.getPromptHistory(50).subscribe({
      next: data => (this.promptLogs = data),
      error: err => console.error('Prompt history error', err)
    });

    this.api.getAgentMetrics().subscribe({
      next: data => (this.agentMetrics = data),
      error: err => console.error('Agent metrics error', err)
    });

    this.api.getMetricsSummary().subscribe({
      next: data => (this.summary = data),
      error: err => console.error('Summary error', err)
    });
  }

  signIn(): void {
    window.location.assign('/.auth/login/aad?post_login_redirect_uri=%2F');
  }

  signOut(): void {
    window.location.assign('/.auth/logout?post_logout_redirect_uri=%2F');
  }

  private handleApiError(error: HttpErrorResponse): void {
    if (error.status === 401) {
      void this.router.navigate(['/unauthorized']);
    } else if (error.status === 403) {
      void this.router.navigate(['/access-denied']);
    } else if (error.status === 429) {
      // Graceful quota exhaustion handling - enrich UI and eliminate raw HTTP 429 error text
      this.quotaExceeded = true;
      if (this.quota) {
        this.quota.remaining = 0;
        this.quota.used_today = this.quota.daily_limit;
      }
      this.errorMessage = '';
    } else {
      this.errorMessage = `Request failed: ${error.error?.detail || error.message || 'HTTP ' + error.status}`;
    }
  }

  private getRangeStartDate(days: number): string {
    const start = new Date();
    start.setDate(start.getDate() - days + 1);
    const year = start.getFullYear();
    const month = String(start.getMonth() + 1).padStart(2, '0');
    const day = String(start.getDate()).padStart(2, '0');
    return `${year}-${month}-${day}`;
  }

  private downloadCsv(filename: string, headers: string[], rows: unknown[][]): void {
    const escapeCell = (value: unknown): string => `"${String(value ?? '').replace(/"/g, '""')}"`;
    const csv = [headers, ...rows].map(row => row.map(escapeCell).join(',')).join('\r\n');
    const blob = new Blob([`\uFEFF${csv}`], { type: 'text/csv;charset=utf-8' });
    const url = URL.createObjectURL(blob);
    const link = document.createElement('a');
    link.href = url;
    link.download = `${filename}-${new Date().toISOString().slice(0, 10)}.csv`;
    link.click();
    URL.revokeObjectURL(url);
  }
}
