export type Observation = {
  id: string;
  source: string;
  location: string;
  category: string;
  value: number;
  confidence: number | null;
  timestamp: string;
  metadata: Record<string, unknown>;
};

export type VisionResult = {
  needs_review: boolean;
  observations: Observation[];
};

export type MediaRecord = {
  id: string;
  household_id: string;
  content_type: string;
  size_bytes: number;
  created_at: string;
  processing?: "processed" | "needs_review" | "retry_required" | "unavailable" | "pending_provider";
  observations?: Observation[];
};

export type HouseholdNotification = {
  id: string;
  task_id: string;
  title: string;
  space: string;
  estimated_minutes: number;
  state: string;
  delivery: string;
  feasibility: "FEASIBLE" | "NOT_FEASIBLE" | "UNKNOWN";
  recommended_time: string | null;
  source_observation_id: string | null;
  verification_status: string | null;
};

export type HouseholdPresence = {
  state: "HOME" | "AWAY" | "UNKNOWN";
  consent: boolean;
  source: string | null;
  expires_at: string | null;
};

export type RankedTask = {
  task: {
    id: string;
    task_key: string;
    description: string;
    urgency: string;
    estimated_effort_minutes: number;
    confidence: number;
    status: string;
    metadata: Record<string, unknown>;
  };
  priority_score: number;
};

export type IntelligenceReport = {
  household_id: string;
  snapshots: unknown[];
  forecasts: unknown[];
  action_decisions: unknown[];
  tasks: unknown[];
  ranked_tasks: RankedTask[];
};

export type PlanResponse = {
  plan: {
    summary: string;
    planner: string;
    steps: Array<{
      task_id: string;
      order: number;
      reason: string;
      active_minutes: number;
      passive_minutes: number;
    }>;
    deferred: Array<{ task_id: string; reason: string }>;
  };
  feasibility: unknown[];
  research: unknown[];
};

export class HomHiveApi {
  constructor(
    private readonly baseUrl: string,
    private readonly householdId: string,
    private readonly token: string,
  ) {}

  private headers(contentType = true): HeadersInit {
    const headers: Record<string, string> = {
      Authorization: `Bearer ${this.token}`,
    };
    if (contentType) headers["Content-Type"] = "application/json";
    return headers;
  }

  private async parse<T>(response: Response): Promise<T> {
    if (!response.ok) {
      let message = `Request failed with HTTP ${response.status}`;
      try {
        const body = await response.json();
        if (typeof body.detail === "string") message = body.detail;
      } catch {}
      throw new Error(message);
    }
    return response.json() as Promise<T>;
  }

  async upload(file: File, location?: string): Promise<MediaRecord> {
    const form = new FormData();
    form.append("file", file);
    if (location) form.append("location", location);
    const response = await fetch(`${this.baseUrl}/households/${encodeURIComponent(this.householdId)}/media`, {
      method: "POST",
      headers: this.headers(false),
      body: form,
    });
    return this.parse<MediaRecord>(response);
  }

  async analyze(mediaId: string, location: string): Promise<VisionResult> {
    const response = await fetch(
      `${this.baseUrl}/households/${encodeURIComponent(this.householdId)}/media/${encodeURIComponent(mediaId)}/observations`,
      {
        method: "POST",
        headers: this.headers(),
        body: JSON.stringify({ location }),
      },
    );
    return this.parse(response);
  }

  async observationHistory(): Promise<Observation[]> {
    const response = await fetch(
      `${this.baseUrl}/households/${encodeURIComponent(this.householdId)}/observations`,
      { method: "GET", headers: this.headers(), cache: "no-store" },
    );
    return this.parse(response);
  }

  async confirmObservation(observationId: string, confirmedValue: number): Promise<Observation> {
    const response = await fetch(
      `${this.baseUrl}/households/${encodeURIComponent(this.householdId)}/observations/${encodeURIComponent(observationId)}/confirm`,
      {
        method: "POST",
        headers: this.headers(),
        body: JSON.stringify({ confirmed_value: confirmedValue }),
      },
    );
    return this.parse(response);
  }

  async acceptTask(taskId: string): Promise<RankedTask["task"]> {
    const response = await fetch(
      `${this.baseUrl}/households/${encodeURIComponent(this.householdId)}/tasks/${encodeURIComponent(taskId)}/accept`,
      { method: "POST", headers: this.headers() },
    );
    return this.parse(response);
  }

  async deferTask(taskId: string, minutes: number): Promise<RankedTask["task"]> {
    const response = await fetch(
      `${this.baseUrl}/households/${encodeURIComponent(this.householdId)}/tasks/${encodeURIComponent(taskId)}/defer`,
      { method: "POST", headers: this.headers(), body: JSON.stringify({ minutes }) },
    );
    return this.parse(response);
  }

  async dismissTask(taskId: string): Promise<RankedTask["task"]> {
    const response = await fetch(
      `${this.baseUrl}/households/${encodeURIComponent(this.householdId)}/tasks/${encodeURIComponent(taskId)}/dismiss`,
      { method: "POST", headers: this.headers() },
    );
    return this.parse(response);
  }

  async notifications(): Promise<HouseholdNotification[]> {
    const response = await fetch(
      `${this.baseUrl}/households/${encodeURIComponent(this.householdId)}/notifications`,
      { headers: this.headers(), cache: "no-store" },
    );
    return this.parse(response);
  }

  async reportDone(taskId: string): Promise<RankedTask["task"]> {
    const response = await fetch(
      `${this.baseUrl}/households/${encodeURIComponent(this.householdId)}/tasks/${encodeURIComponent(taskId)}/done`,
      { method: "POST", headers: this.headers(), body: JSON.stringify({}) },
    );
    return this.parse(response);
  }

  async presence(): Promise<HouseholdPresence> {
    const response = await fetch(
      `${this.baseUrl}/households/${encodeURIComponent(this.householdId)}/presence`,
      { headers: this.headers(), cache: "no-store" },
    );
    return this.parse(response);
  }

  async updatePresence(state: HouseholdPresence["state"], consent: boolean): Promise<HouseholdPresence> {
    const response = await fetch(
      `${this.baseUrl}/households/${encodeURIComponent(this.householdId)}/presence`,
      { method: "POST", headers: this.headers(), body: JSON.stringify({ state, consent, ttl_minutes: 60 }) },
    );
    return this.parse(response);
  }

  async revokePresence(): Promise<HouseholdPresence> {
    const response = await fetch(
      `${this.baseUrl}/households/${encodeURIComponent(this.householdId)}/presence/revoke`,
      { method: "POST", headers: this.headers() },
    );
    return this.parse(response);
  }

  async refresh(): Promise<IntelligenceReport> {
    const response = await fetch(
      `${this.baseUrl}/households/${encodeURIComponent(this.householdId)}/intelligence/refresh`,
      { method: "POST", headers: this.headers() },
    );
    return this.parse(response);
  }

  async plan(options: {
    availableMinutes: number;
    atHome: boolean;
    quietHours: boolean;
    researchQuery?: string;
    researchPurpose?: string;
  }): Promise<PlanResponse> {
    const research = options.researchQuery
      ? [
          {
            query: options.researchQuery,
            purpose: options.researchPurpose ?? "household_context",
            max_results: 5,
          },
        ]
      : [];

    const response = await fetch(
      `${this.baseUrl}/households/${encodeURIComponent(this.householdId)}/plan`,
      {
        method: "POST",
        headers: this.headers(),
        body: JSON.stringify({
          context: {
            available_minutes: options.availableMinutes,
            at_home: options.atHome,
            quiet_hours_active: options.quietHours,
            max_tasks: 5,
          },
          research,
        }),
      },
    );
    return this.parse(response);
  }
}
