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
  autonomous_enqueue?: "disabled" | "retry_required";
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

export type AutonomousTask = {
  id: string; room_id: string; title: string; action: string;
  status: string; effort_min: number | null; effort_max: number | null; criteria: string;
  room_category?: string | null; evidence_summary?: string | null;
  created_at: string; updated_at: string; remind_at?: string | null;
  confirmation_required?: boolean;
  recommended_at?: string | null;
  recommendation_basis?: string | null;
  estimate_rationale?: string | null;
  estimate_sources?: string[];
  progress?: {percent: number; media_id: string; explanation: string; next_step?: string | null; reviewed_at: string; estimated: boolean} | null;
};
export type AutonomousAlert = {
  id: string; task_id: string; kind: "suggestion" | "progress" | "completed";
  title: string; detail: string; created_at: string; read_at: string | null;
};
export type WorkWindow = {
  timezone: string; start_time: string; end_time: string; weekdays: number[];
};
export type AutonomousRoom = {
  room_id: string; reference_media_id: string; room_category: string | null;
  room_category_source?: "ai_reviewed" | "user_confirmed"; created_at: string;
};
export type AutonomousReviewSummary = {
  room_category?: string | null;
  verification?: string;
  evidence?: string[];
  proposed_count?: number;
  approved_count?: number;
  created_count?: number;
  existing_count?: number;
  proposal_reviews?: Array<{
    title: string;
    decision: "approved" | "rejected";
    reason?: string | null;
    reviewer_explanation?: string | null;
  }>;
};
export type AutonomousScanJob = {
  id: string; media_id: string; room_id: string | null;
  state: string; attempts: number; message: string;
  updated_at?: string; review_summary?: AutonomousReviewSummary | null;
};
export type AutonomousScanResult = {
  status: string; saved: boolean; created: string[]; existing: string[];
  completed: Record<string, string>; approved_actions: number; room_id?: string;
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

  private failureMessage(status: number, detail?: string): string {
    if (status === 401 || status === 403) return "Your session isn't authorized for this household. Sign in again.";
    if (status === 413) return "This photo is too large. Choose an image under 10 MB.";
    if (status === 415) return "Unsupported image. Choose a JPG, PNG, or WebP photo.";
    if (status === 429) return "Too many requests right now. Wait a moment before retrying.";
    if (status >= 500) return "HomHive couldn't complete the request because a service is unavailable. Please try again.";
    return detail?.trim() || `The request could not be completed (HTTP ${status}).`;
  }

  private async parse<T>(response: Response): Promise<T> {
    if (!response.ok) {
      let message = `Request failed with HTTP ${response.status}`;
      try {
        const body = await response.json();
        if (typeof body.detail === "string") message = body.detail;
      } catch {}
      throw new Error(this.failureMessage(response.status, message));
    }
    return response.json() as Promise<T>;
  }

  async autonomousRooms(): Promise<AutonomousRoom[]> {
    const response = await fetch(`${this.baseUrl}/households/${encodeURIComponent(this.householdId)}/autonomous-rooms`,
      { headers: this.headers(), cache: "no-store" });
    return (await this.parse<{rooms: AutonomousRoom[]}>(response)).rooms;
  }

  async correctAutonomousRoom(roomId: string, category: string): Promise<AutonomousRoom> {
    const response = await fetch(`${this.baseUrl}/households/${encodeURIComponent(this.householdId)}/autonomous-rooms/${encodeURIComponent(roomId)}/category`, {
      method: "PUT", headers: this.headers(), body: JSON.stringify({room_category: category}),
    });
    return this.parse(response);
  }

  async recheckAutonomousScan(mediaId: string): Promise<{job_id: string}> {
    const response = await fetch(`${this.baseUrl}/households/${encodeURIComponent(this.householdId)}/media/${encodeURIComponent(mediaId)}/autonomous-recheck`, {
      method: "POST", headers: this.headers(),
    });
    return this.parse(response);
  }

  async autonomousScanJobs(): Promise<AutonomousScanJob[]> {
    const response = await fetch(`${this.baseUrl}/households/${encodeURIComponent(this.householdId)}/autonomous-scan-jobs`,
      { headers: this.headers(), cache: "no-store" });
    return (await this.parse<{jobs: AutonomousScanJob[]}>(response)).jobs;
  }

  async enrollAutonomousRoom(mediaId: string): Promise<AutonomousRoom> {
    const response = await fetch(`${this.baseUrl}/households/${encodeURIComponent(this.householdId)}/autonomous-rooms/${encodeURIComponent(mediaId)}`,
      { method: "POST", headers: this.headers() });
    return this.parse(response);
  }

  async decideAutonomousTask(taskId: string, decision: "accept" | "decline" | "remind" | "done"): Promise<{id: string; status: string}> {
    const response = await fetch(`${this.baseUrl}/households/${encodeURIComponent(this.householdId)}/autonomous-tasks/${encodeURIComponent(taskId)}/decisions/${decision}`, {
      method: "POST", headers: this.headers(),
    });
    return this.parse(response);
  }

  async autonomousAlerts(): Promise<AutonomousAlert[]> {
    const response = await fetch(`${this.baseUrl}/households/${encodeURIComponent(this.householdId)}/autonomous-alerts`,
      {headers: this.headers(), cache: "no-store"});
    return (await this.parse<{alerts: AutonomousAlert[]}>(response)).alerts;
  }

  async acknowledgeAutonomousAlert(alertId: string): Promise<void> {
    const response = await fetch(`${this.baseUrl}/households/${encodeURIComponent(this.householdId)}/autonomous-alerts/${encodeURIComponent(alertId)}/read`,
      {method: "POST", headers: this.headers()});
    await this.parse(response);
  }

  async workWindow(): Promise<WorkWindow | null> {
    const response = await fetch(`${this.baseUrl}/households/${encodeURIComponent(this.householdId)}/autonomous-work-window`,
      {headers: this.headers(), cache: "no-store"});
    return (await this.parse<{window: WorkWindow | null}>(response)).window;
  }

  async setWorkWindow(window: WorkWindow): Promise<WorkWindow> {
    const response = await fetch(`${this.baseUrl}/households/${encodeURIComponent(this.householdId)}/autonomous-work-window`,
      {method: "PUT", headers: this.headers(), body: JSON.stringify(window)});
    return (await this.parse<{window: WorkWindow}>(response)).window;
  }

  async autonomousTasks(): Promise<AutonomousTask[]> {
    const response = await fetch(`${this.baseUrl}/households/${encodeURIComponent(this.householdId)}/autonomous-tasks`,
      { headers: this.headers(), cache: "no-store" });
    return (await this.parse<{tasks: AutonomousTask[]}>(response)).tasks;
  }

  async retryAutonomousScan(mediaId: string): Promise<{job_id: string}> {
    const response = await fetch(`${this.baseUrl}/households/${encodeURIComponent(this.householdId)}/media/${encodeURIComponent(mediaId)}/autonomous-queue`, {
      method: "POST", headers: this.headers(),
    });
    return this.parse(response);
  }

  async autonomousScan(mediaId: string, referenceMediaId: string): Promise<AutonomousScanResult> {
    const response = await fetch(`${this.baseUrl}/households/${encodeURIComponent(this.householdId)}/media/${encodeURIComponent(mediaId)}/autonomous-scan`, {
      method: "POST", headers: this.headers(), body: JSON.stringify({reference_media_id:referenceMediaId}),
    });
    return this.parse(response);
  }

  async upload(file: File, location?: string, onProgress?: (percent: number) => void): Promise<MediaRecord> {
    const form = new FormData();
    form.append("file", file);
    if (location) form.append("location", location);
    form.append("defer_analysis", "true");
    return new Promise<MediaRecord>((resolve, reject) => {
      const xhr = new XMLHttpRequest();
      xhr.open("POST", `${this.baseUrl}/households/${encodeURIComponent(this.householdId)}/media`);
      xhr.setRequestHeader("Authorization", `Bearer ${this.token}`);
      xhr.upload.onprogress = (event) => {
        if (event.lengthComputable && event.total > 0) {
          onProgress?.(Math.min(100, Math.round((event.loaded / event.total) * 100)));
        }
      };
      xhr.onerror = () => reject(new Error("Could not upload photo. Check your connection."));
      xhr.onabort = () => reject(new Error("Photo upload was cancelled."));
      xhr.onload = () => {
        let body: Record<string, unknown>;
        try { body = JSON.parse(xhr.responseText) as Record<string, unknown>; }
        catch { reject(new Error(`Unexpected upload response (HTTP ${xhr.status}).`)); return; }
        if (xhr.status < 200 || xhr.status >= 300) {
          reject(new Error(this.failureMessage(xhr.status, typeof body.detail === "string" ? body.detail : undefined)));
          return;
        }
        resolve(body as unknown as MediaRecord);
      };
      xhr.send(form);
    });
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
