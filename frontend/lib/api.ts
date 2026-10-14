export type Observation = {
  id: string;
  source: string;
  location: string;
  category: string;
  value: number;
  confidence: number | null;
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

  async upload(file: File): Promise<MediaRecord> {
    const form = new FormData();
    form.append("file", file);
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
