"use client";

import { useMemo, useState } from "react";
import demoCatalog from "../public/demo-library/catalog.json";
import { HomHiveApi, HouseholdNotification, HouseholdPresence, IntelligenceReport, MediaRecord, Observation, PlanResponse, VisionResult, AutonomousTask } from "../lib/api";

const defaultApi = process.env.NEXT_PUBLIC_HOMHIVE_API_URL ?? "http://127.0.0.1:8000";

export default function Home() {
  const [apiUrl, setApiUrl] = useState(defaultApi);
  const [householdId, setHouseholdId] = useState("homhive_test_home");
  const [token, setToken] = useState("");
  const [authEmail, setAuthEmail] = useState("");
  const [authPassword, setAuthPassword] = useState("");
  const [authMode, setAuthMode] = useState<"login" | "register">("login");
  const [authError, setAuthError] = useState("");
  const [confirmPassword, setConfirmPassword] = useState("");
  const [location, setLocation] = useState("");
  const [file, setFile] = useState<File | null>(null);
  const [media, setMedia] = useState<MediaRecord | null>(null);
  const [autonomousTasks, setAutonomousTasks] = useState<AutonomousTask[]>([]);
  const [roomReference, setRoomReference] = useState("");
  const [autonomousNote, setAutonomousNote] = useState("");
  const [observations, setObservations] = useState<Observation[]>([]);
  const [history, setHistory] = useState<Observation[]>([]);
  const [historyLoaded, setHistoryLoaded] = useState(false);
  const [selectedRoom, setSelectedRoom] = useState<string | null>(null);
  const [report, setReport] = useState<IntelligenceReport | null>(null);
  const [notifications, setNotifications] = useState<HouseholdNotification[]>([]);
  const [presence, setPresence] = useState<HouseholdPresence | null>(null);
  const [plan, setPlan] = useState<PlanResponse | null>(null);
  const [availableMinutes, setAvailableMinutes] = useState(30);
  const [atHome, setAtHome] = useState(true);
  const [quietHours, setQuietHours] = useState(false);
  const [researchQuery, setResearchQuery] = useState("");
  const [status, setStatus] = useState("Ready");
  const [view, setView] = useState<"home" | "spaces" | "tasks" | "activity">("home");
  const [settingsOpen, setSettingsOpen] = useState(false);
  const [scanOpen, setScanOpen] = useState(false);
  const [demoOpen, setDemoOpen] = useState(false);
  const [demoQuery, setDemoQuery] = useState("");
  const [demoCategory, setDemoCategory] = useState("All");
  const [demoSelectionError, setDemoSelectionError] = useState("");
  const [demoSelecting, setDemoSelecting] = useState(false);
  const [busy, setBusy] = useState(false);
  const [scanProgress, setScanProgress] = useState<{ phase: "uploading" | "analyzing" | "done" | "error"; percent: number | null; mediaId: string | null; detail: string } | null>(null);


  const api = useMemo(
    () => new HomHiveApi(apiUrl.replace(/\/$/, ""), householdId, token),
    [apiUrl, householdId, token],
  );

  async function run<T>(label: string, action: () => Promise<T>): Promise<T | null> {
    setBusy(true);
    setStatus(label);
    try {
      const result = await action();
      setStatus("Ready");
      return result;
    } catch (error) {
      setStatus(error instanceof Error ? error.message : "Request failed");
      return null;
    } finally {
      setBusy(false);
    }
  }

  const emailValid = /^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(authEmail.trim());
  const authDisabledReason = busy ? "Please wait for the current request to finish."
    : !authEmail.trim() ? "Enter your email address to continue."
    : !emailValid ? "Enter a valid email address."
    : !authPassword ? "Enter your password to continue."
    : authPassword.length < 12 ? "Use a password of at least 12 characters."
    : authMode === "register" && !confirmPassword ? "Confirm your password to create an account."
    : authMode === "register" && confirmPassword !== authPassword ? "Passwords do not match."
    : "";
  const householdDisabledReason = busy ? "A request is in progress."
    : !token ? "Sign in or create an account before loading your household."
    : !householdId.trim() ? "No household is assigned to this account."
    : historyLoaded ? "Your household is already connected." : "";

  async function authenticate() {
    if (authDisabledReason) { setAuthError(authDisabledReason); return; }
    setAuthError("");
    setBusy(true);
    try {
      const response = await fetch(`${apiUrl.replace(/\/$/, "")}/auth/${authMode}`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ email: authEmail.trim(), password: authPassword }),
      });
      const result = await response.json() as { detail?: string; access_token?: string; households?: string[] };
      if (!response.ok || !result.access_token || !result.households?.length) {
        throw new Error(result.detail ?? "Could not sign in. Check your credentials.");
      }
      setHouseholdId(result.households[0]);
      setHistoryLoaded(false);
      setReport(null);
      setHistory([]);
      setToken(result.access_token);
      setAuthPassword("");
      setConfirmPassword("");
      setSettingsOpen(false);
      setStatus("Signed in. Select Load household to connect your household data.");
    } catch (err) {
      const message = err instanceof Error ? err.message : "Authentication failed";
      setAuthError(authMode === "login" && /invalid credentials/i.test(message)
        ? "We couldn't sign you in with those details. Check your password or use another account."
        : authMode === "register" && /account already exists/i.test(message)
        ? "An account may already use this email. Try signing in with your existing password."
        : message);
    } finally {
      setBusy(false);
    }
  }

  async function signOut() {
    try {
      await fetch(`${apiUrl.replace(/\/$/, "")}/auth/logout`, {
        method: "POST", headers: { Authorization: `Bearer ${token}` },
      });
    } finally {
      setToken(""); setHistoryLoaded(false); setHistory([]); setReport(null);
      setNotifications([]); setObservations([]); setPlan(null);
      setSettingsOpen(false);
    }
  }


  async function loadHousehold(): Promise<boolean> {
    if (!token || !householdId.trim()) return false;
    const result = await run<Observation[]>("Loading persisted household observations...", () => api.observationHistory());
    if (result !== null) {
      setHistory(result);
      setHistoryLoaded(true);
      // Load persisted work alongside room history; no new vision request.
      const discovered = await run<IntelligenceReport>("Loading room tasks...", () => api.refresh());
      if (discovered) setReport(discovered);
      try {
        setNotifications(await api.notifications());
        setPresence(await api.presence());
      } catch {
        // Legacy backend compatibility: saved history and tasks remain visible.
        setNotifications([]);
      }
      return true;
    }
    return false;
  }

  // User confirmation is stored as a separate observation linked to its
  // original AI evidence. Preserve the original record but do not offer
  // a second confirmation or count it as pending.
  const confirmedSourceIds = useMemo(() => new Set(
    history.filter(item => item.source === "user_input")
      .map(item => item.metadata?.confirmed_observation_id)
      .filter((id): id is string => typeof id === "string" && id.length > 0),
  ), [history]);
  const isAiCorroborated = (item: Observation) => item.metadata?.ai_verification === "multi_model_corroborated" || item.metadata?.ai_verification === "independently_corroborated";
  const needsReview = (item: Observation) => item.confidence === null && !isAiCorroborated(item) && !confirmedSourceIds.has(item.id);
  const evidenceStatus = (item: Observation) => isAiCorroborated(item) ? "AI corroborated" : needsReview(item) ? "Unverified evidence" : item.source === "user_input" ? "Human confirmed" : "Confidence recorded";

  const roomSummaries = useMemo(() => {
    const grouped = new Map<string, Observation[]>();
    for (const observation of history) {
      const room = observation.location.trim() || "unspecified";
      grouped.set(room, [...(grouped.get(room) ?? []), observation]);
    }
    return Array.from(grouped.entries()).map(([room, items]) => {
      const ordered = [...items].sort((a, b) => b.timestamp.localeCompare(a.timestamp));
      const confirmed = ordered.filter((item) => item.confidence !== null);
      return {
        room,
        count: items.length,
        pending: items.filter(needsReview).length,
        latestConfirmed: confirmed[0] ?? null,
        latestPending: ordered.find(needsReview) ?? null,
        observations: ordered,
      };
    }).sort((a, b) => a.room.localeCompare(b.room));
  }, [history]);

  const activeRoom = roomSummaries.find((item) => item.room === selectedRoom) ?? roomSummaries[0] ?? null;

  // Only bind a task to a room when its structured identity or metadata establishes it.
  // Unlocated tasks remain in the global intelligence view instead of being guessed from prose.
  const roomTasks = useMemo(() => {
    if (!activeRoom || !report) return [];
    const room = activeRoom.room.toLowerCase();
    return report.ranked_tasks.filter(({ task }) => {
      const storedLocation = task.metadata?.location;
      if (typeof storedLocation === "string" && storedLocation.toLowerCase() === room) return true;
      return task.task_key.toLowerCase().split(":").includes(room);
    });
  }, [activeRoom, report]);

  const demoCategories = useMemo(() => ["All", ...Array.from(new Set(demoCatalog.map(item => item.category))).sort()], []);
  const visibleDemoImages = useMemo(() => demoCatalog.filter(item =>
    (demoCategory === "All" || item.category === demoCategory) &&
    `${item.title} ${item.category} ${item.group}`.toLowerCase().includes(demoQuery.trim().toLowerCase()),
  ), [demoCategory, demoQuery]);

  async function chooseDemoImage(image: (typeof demoCatalog)[number]) {
    if (!token || !historyLoaded) { setDemoSelectionError("Load your household before choosing a sample photo."); return; }
    setDemoSelecting(true);
    setDemoSelectionError("");
    try {
      const response = await fetch(image.image, { cache: "force-cache" });
      if (!response.ok) throw new Error("Could not load this sample photograph");
      const bytes = await response.blob();
      const selected = new File([bytes], `${image.id}.jpg`, { type: "image/jpeg" });
      setFile(selected);
      setMedia(null);
      setObservations([]);
      setDemoOpen(false);
      setStatus(`Selected ${image.title}. Ready for the same live analysis as a personal photo.`);
    } catch (error) {
      setDemoSelectionError(error instanceof Error ? error.message : "Sample unavailable");
    } finally { setDemoSelecting(false); }
  }

  async function upload() {
    if (!file || !token || !historyLoaded || busy) return;
    setBusy(true);
    setStatus("Uploading your photo…");
    setScanProgress({ phase: "uploading", percent: 0, mediaId: null, detail: "Securely saving your photo" });
    try {
      const stored = await api.upload(file, location, (percent) => {
        setScanProgress(current => current?.phase === "uploading" ? { ...current, percent } : current);
      });
      setMedia(stored);
      setScanOpen(false);
      setView("home");
      await analyzeSaved(stored.id, location || "unknown");
    } catch (error) {
      const message = error instanceof Error ? error.message : "Upload failed";
      setStatus(message);
      setScanProgress(current => ({ phase: "error", percent: null, mediaId: current?.mediaId ?? null, detail: message }));
    } finally {
      setBusy(false);
    }
  }

  async function analyzeSaved(mediaId: string, submittedLocation: string) {
    setScanProgress({ phase: "analyzing", percent: null, mediaId, detail: "Examining your photo and corroborating visible conditions with independent AI reviewers" });
    setStatus("Analyzing saved photo…");
    try {
      const result = await api.analyze(mediaId, submittedLocation);
      setObservations(result.observations);
      setScanProgress({ phase: "done", percent: 100, mediaId, detail: result.observations.length ? `${result.observations.length} verified observation(s) saved` : "Analysis completed; no supported observations were saved" });
      setStatus("Analysis complete");
      try { await loadHousehold(); }
      catch { setStatus("Analysis complete. Refresh household to view updates."); }
    } catch (error) {
      const message = error instanceof Error ? error.message : "Analysis could not be completed";
      setScanProgress({ phase: "error", percent: null, mediaId, detail: message });
      setStatus("Photo saved, but analysis needs another attempt");
    }
  }

  async function analyze() {
    const mediaId = scanProgress?.mediaId ?? media?.id;
    if (!mediaId || busy) return;
    setBusy(true);
    try { await analyzeSaved(mediaId, location || "unknown"); }
    finally { setBusy(false); }
  }

  async function confirm(observation: Observation) {
    const result = await run<Observation>("Saving your confirmation...", () => api.confirmObservation(observation.id, observation.value));
    if (result) {
      setObservations((items) => [...items.filter((item) => item.id !== observation.id), result]);
      await loadHousehold();
      // Refresh invokes the existing discovery and persistence pipeline.
      const discovered = await run<IntelligenceReport>("Discovering household work...", () => api.refresh());
      if (discovered) setReport(discovered);
    }
  }

  async function refreshAutonomousTasks() {
    const tasks = await run("Loading autonomous tasks...", () => api.autonomousTasks());
    if (tasks) setAutonomousTasks(tasks);
  }

  async function autonomousScan() {
    if (!media?.id || !roomReference.trim()) {
      setAutonomousNote("Upload a photograph and enter a reference media ID. Use this photograph's ID to enroll a new physical room.");
      return;
    }
    const result = await run("Independently reviewing and tracking household work...", () =>
      api.autonomousScan(media.id, roomReference.trim()));
    if (result) {
      setAutonomousNote(result.status === "held_unverified_room"
        ? "Room continuity could not be verified. No changes saved."
        : `Saved: ${result.created.length} created, ${result.existing.length} existing, ${Object.values(result.completed).filter(v => v === "completed").length} completed.`);
      await refreshAutonomousTasks();
    }
  }

  async function refresh() {
    const result = await run<IntelligenceReport>("Rebuilding household intelligence...", () => api.refresh());
    if (result) { setReport(result); await loadHousehold(); }
  }

  async function acceptTask(taskId: string) {
    const accepted = await run("Accepting discovered work...", () => api.acceptTask(taskId));
    if (accepted) {
      setReport((current) => current ? {
        ...current,
        ranked_tasks: current.ranked_tasks.map((entry) =>
          entry.task.id === taskId ? { ...entry, task: accepted } : entry,
        ),
      } : null);
      await loadHousehold();
    }
  }

  async function deferTask(taskId: string) {
    const result = await run("Deferring suggestion for an hour...", () => api.deferTask(taskId, 60));
    if (result) await refresh();
  }

  async function dismissTask(taskId: string) {
    const result = await run("Dismissing suggestion...", () => api.dismissTask(taskId));
    if (result) await refresh();
  }

  async function markDone(taskId: string) {
    const result = await run("Recording completion and scheduling verification...", () => api.reportDone(taskId));
    if (result) await loadHousehold();
  }

  async function changePresence(state: HouseholdPresence["state"]) {
    const result = await run("Updating presence...", () =>
      state === "UNKNOWN" ? api.revokePresence() : api.updatePresence(state, true));
    if (result) setPresence(result);
  }

  async function createPlan() {
    const result = await run<PlanResponse>("Finding tasks that fit your time...", () =>
      api.plan({
        availableMinutes,
        atHome,
        quietHours,
        researchQuery: researchQuery.trim() || undefined,
      }),
    );
    if (result) setPlan(result);
  }


  const taskEntries = report?.ranked_tasks ?? [];
  const nextSuggestion = notifications.find(item => item.state === "suggested") ?? null;
  const isConnected = Boolean(token && historyLoaded);
  const pendingCount = history.filter(needsReview).length;
  const displayCategory = (category: string) => {
    const labels: Record<string, string> = {
      dish_load: "Dishes", laundry_load: "Laundry", plant_condition: "Plants",
      lawn_condition: "Lawn", fridge_expiry: "Food storage",
    };
    return labels[category] ?? category.replaceAll("_", " ");
  };
  const conditionSummary = (item: Observation) => {
    if (item.category === "dish_load") return item.value >= 0.65 ? "Dishes need attention" : item.value >= 0.25 ? "Some dishes to wash" : "Sink looks clear";
    if (item.category === "laundry_load") return item.value >= 0.65 ? "Laundry is piling up" : item.value >= 0.25 ? "Some laundry to sort" : "Laundry looks clear";
    if (item.category === "plant_condition") return item.value >= 0.5 ? "Plants may need care" : "Plants look healthy";
    if (item.category === "lawn_condition") return item.value >= 0.5 ? "Lawn may need attention" : "Lawn looks maintained";
    return displayCategory(item.category);
  };
  const capitalizeFirst = (value: string) => value.length ? value[0].toLocaleUpperCase() + value.slice(1) : value;

  const acceptedTasks = taskEntries.filter(({task}) => Boolean(task.metadata?.accepted_at));
  const suggestedTasks = taskEntries.filter(({task}) => !task.metadata?.accepted_at && task.status === "pending");
  const availableRoom = activeRoom?.room ?? location;
  const plannedTasks = plan?.plan.steps ?? [];
  const taskById = new Map(taskEntries.map(({task}) => [task.id, task]));
  const display = (value: string) => value.replaceAll("_", " ");
  const observationEvidence = (item: Observation) => {
    const evidence = item.metadata?.visible_evidence;
    return typeof evidence === "string" && evidence.trim() ? evidence : "No description recorded";
  };
  const taskState = (task: IntelligenceReport["ranked_tasks"][number]["task"]) =>
    task.status === "completed" ? "Completed" : task.metadata?.accepted_at ? "Accepted" : "Suggested";
  const navItems = [
    { id: "home", label: "Home", icon: "⌂" },
    { id: "spaces", label: "Spaces", icon: "▦" },
    { id: "tasks", label: "Tasks", icon: "✓" },
    { id: "activity", label: "Activity", icon: "◷" },
  ] as const;

  return (
    <main className="hh-app" id="main-content">
      <a className="hh-skip-link" href="#household-content">Skip to household content</a>
      <header className="hh-header">
        <div className="hh-brand"><span className="hh-mark" aria-hidden="true">⌂</span><span>HomHive<small>Household intelligence</small></span></div>
        <nav className="hh-nav" aria-label="Main navigation">
          {navItems.map((item) => <button key={item.id} className={view === item.id ? "hh-nav-active" : "hh-nav-button"} aria-current={view === item.id ? "page" : undefined} onClick={() => setView(item.id)}><span aria-hidden="true">{item.icon}</span>{item.label}</button>)}
        </nav>
        <div className="hh-toolbar">{isConnected && <span className="hh-muted" aria-label="Connected household">Connected · My household</span>}<button className="hh-scan" onClick={() => setScanOpen(true)}>＋ Scan</button><button className="hh-icon-button" aria-label="Open settings" onClick={() => setSettingsOpen(true)}>⚙</button></div>
      </header>
      <div id="household-content" className="hh-live" role="status" aria-live="polite"><span className={busy ? "pulse" : "dot"}/>{status}</div>

      {scanProgress && <section className={`hh-analysis-card hh-analysis-${scanProgress.phase}`} role="status" aria-live="polite" aria-label="Photo analysis progress">
        <div className="hh-panel-head"><div><p className="hh-kicker">Household scan</p><h2>{scanProgress.phase === "uploading" ? "Saving your photo" : scanProgress.phase === "analyzing" ? "Analyzing your space" : scanProgress.phase === "done" ? "Analysis complete" : "Analysis needs attention"}</h2></div>{scanProgress.phase === "done" && <button className="hh-icon-button" aria-label="Dismiss completed scan" onClick={() => setScanProgress(null)}>✕</button>}</div>
        <p>{scanProgress.detail}</p>
        <div className={`hh-analysis-track ${scanProgress.percent === null ? "hh-analysis-indeterminate" : ""}`} role="progressbar" aria-label={scanProgress.phase === "uploading" ? "Photo upload" : "Photo analysis"} aria-valuemin={0} aria-valuemax={100} aria-valuenow={scanProgress.percent === null ? undefined : scanProgress.percent}>
          <div className="hh-analysis-fill" style={scanProgress.percent === null ? undefined : { width: `${scanProgress.percent}%` }}/>
        </div>
        <div className="hh-analysis-footer"><small>{scanProgress.phase === "uploading" ? `${scanProgress.percent ?? 0}% uploaded` : scanProgress.phase === "analyzing" ? "Analysis in progress · completion time varies" : scanProgress.phase === "done" ? "100% complete" : "Your original photo is retained"}</small>{scanProgress.phase === "error" && scanProgress.mediaId && <button disabled={busy} onClick={analyze}>Retry analysis</button>}</div>
      </section>}

      {!isConnected && <section className="hh-notice" role="status"><strong>Connect your household</strong><span>Sign in, then select Load household to connect your data.</span><button onClick={() => setSettingsOpen(true)}>Open Settings</button></section>}

      {view === "home" && <section className="hh-view">
        <div className="hh-view-title"><div><p className="hh-kicker">HomHive / Home intelligence</p><h1>Good to be home.</h1><p>Your home, understood. The right actions, at the right time.</p></div><button className="secondary" disabled={busy || !token} onClick={loadHousehold}>↻ Refresh</button></div>
        {isConnected && <div className="hh-stats">
          <button onClick={() => setView("spaces")}><span>Spaces</span><strong>{roomSummaries.length}</strong><small>Rooms with saved observations</small></button>
          <button onClick={() => setView("tasks")}><span>Accepted work</span><strong>{acceptedTasks.length}</strong><small>Ready for planning</small></button>
          <button onClick={() => setView("activity")}><span>Needs review</span><strong>{pendingCount}</strong><small>Evidence awaiting verification</small></button>
        </div>}
        {isConnected && nextSuggestion && <section className="hh-panel" aria-label="Household recommendation">
          <p className="hh-kicker">Suggested for you</p>
          <h2>{capitalizeFirst(nextSuggestion.title.replace(/ in unknown$/i, ""))}</h2>
          <p className="hh-muted">{nextSuggestion.space === "unknown" ? "Room not identified" : capitalizeFirst(display(nextSuggestion.space))} · About {nextSuggestion.estimated_minutes} minutes</p>
          <p className="hh-muted">Based on a saved household observation. {nextSuggestion.feasibility === "UNKNOWN" ? "Can you take care of it?" : nextSuggestion.feasibility === "NOT_FEASIBLE" ? "You may not be at home right now." : "This looks feasible."}</p>
          <div className="hh-task-actions"><button disabled={busy} onClick={() => acceptTask(nextSuggestion.task_id)}>I'll do it</button><button className="secondary" disabled={busy} onClick={() => deferTask(nextSuggestion.task_id)}>Later</button><button className="hh-text-danger" disabled={busy} onClick={() => dismissTask(nextSuggestion.task_id)}>Dismiss</button></div>
          <details><summary>Why this suggestion?</summary><p>Based on observation {nextSuggestion.source_observation_id ?? "not linked to a specific photo"}. Timing is not confirmed without your availability.</p></details>
        </section>}
        <div className="hh-home-grid">
          <section className="hh-panel"><div className="hh-panel-head"><h2>Spaces</h2><button className="hh-link" onClick={() => setView("spaces")}>View spaces →</button></div>
            {!historyLoaded ? <p className="hh-empty">Connect your household to see your spaces.</p> : roomSummaries.length === 0 ? <p className="hh-empty">Your spaces will appear after your first scan.</p> :
            <div className="hh-compact-list">{roomSummaries.slice(0,4).map(room => <button className="hh-room-row" key={room.room} onClick={() => {setSelectedRoom(room.room);setView("spaces");}}><span className="hh-room-symbol" aria-hidden="true">⌂</span><span><strong>{capitalizeFirst(display(room.room))}</strong><small>{room.latestConfirmed ? conditionSummary(room.latestConfirmed) : "No confirmed observation"}</small></span><span className="hh-count">{room.pending ? `${room.pending} to review` : "Up to date"}</span></button>)}</div>}
          </section>
          <section className="hh-panel"><div className="hh-panel-head"><h2>Accepted work</h2><button className="hh-link" onClick={() => setView("tasks")}>All tasks →</button></div>
            {!report ? <p className="hh-empty">Your accepted tasks will appear here.</p> : acceptedTasks.length === 0 ? <p className="hh-empty">No accepted work right now.</p> : <><p className="hh-muted">{acceptedTasks.length} accepted task{acceptedTasks.length === 1 ? "" : "s"} on your list.</p><button className="hh-inline-action" onClick={() => setView("tasks")}>View tasks →</button></>}
          </section>
        </div>
        {isConnected && <section className="hh-panel hh-planning"><div className="hh-panel-head"><div><p className="hh-kicker">Planning</p><h2>Make time for what matters</h2><p className="hh-muted">Build a realistic schedule from your accepted household tasks.</p></div></div>
          <div className="hh-plan-layout"><div className="hh-plan-controls"><div className="hh-time-picks" aria-label="Suggested planning windows">{[15,30,45,60].map(minutes => <button type="button" className={availableMinutes === minutes ? "hh-time-active" : "secondary"} key={minutes} onClick={() => setAvailableMinutes(minutes)}>{minutes} min</button>)}</div><label>Time available <input type="number" min={1} max={720} value={availableMinutes} onChange={e => setAvailableMinutes(Number(e.target.value))}/></label><label className="check"><input type="checkbox" checked={atHome} onChange={e => setAtHome(e.target.checked)}/> I'm at home</label><label className="check"><input type="checkbox" checked={quietHours} onChange={e => setQuietHours(e.target.checked)}/> Quiet hours</label><details><summary>More context</summary><label>Research question (optional)<input value={researchQuery} onChange={e => setResearchQuery(e.target.value)}/></label></details><button disabled={busy || !token} onClick={createPlan}>Build plan</button></div>
          <div className="hh-plan-output">{!plan ? <div className="hh-plan-preview"><span className="hh-plan-eyebrow">Your planning snapshot</span><strong>{acceptedTasks.length === 0 ? "Nothing accepted yet" : `${acceptedTasks.length} accepted task${acceptedTasks.length === 1 ? "" : "s"} ready`}</strong><p>{acceptedTasks.length ? `You have ${availableMinutes} minutes available. Build a plan to see which accepted chores fit your time and home context.` : "Accept a task from your suggestions to make it available for planning."}</p><div className="hh-plan-preview-meta"><span>{availableMinutes} minutes available</span><span>{quietHours ? "Quiet-hour friendly" : "Regular activity"}</span><span>{atHome ? "At home" : "Away from home"}</span></div></div> : plannedTasks.length === 0 ? <p className="hh-empty">No accepted tasks fit these constraints right now.</p> : <ol className="hh-plan-steps">{plannedTasks.map(step => <li key={step.task_id}><div><strong>{taskById.get(step.task_id)?.description ?? "Household task"}</strong><small>{step.active_minutes} min active{step.passive_minutes ? ` · ${step.passive_minutes} min passive` : ""}</small></div><details><summary>Why It Fits</summary><p>{capitalizeFirst(step.reason)}</p></details></li>)}</ol>}{plan && <details className="hh-plan-detail"><summary>Plan Details</summary><p>{plan.plan.summary}</p>{plan.plan.deferred.map(item => <p key={item.task_id}>{item.reason}</p>)}</details>}</div></div>
        </section>}
      </section>}

      {view === "spaces" && <section className="hh-view"><div className="hh-view-title"><div><p className="hh-kicker">Your household</p><h1>Spaces</h1><p>Confirmed conditions and the evidence behind them.</p></div><button className="secondary" disabled={busy || !token} onClick={loadHousehold}>↻ Refresh</button></div>
        {!roomSummaries.length ? <div className="hh-panel hh-empty">No spaces yet. Scan a room to get started.</div> : <><div className="hh-room-tabs" aria-label="Choose a room">{roomSummaries.map(room => <button key={room.room} aria-pressed={activeRoom?.room === room.room} className={activeRoom?.room === room.room ? "hh-selected" : ""} onClick={() => setSelectedRoom(room.room)}>{capitalizeFirst(display(room.room))}{room.pending > 0 && <span>{room.pending}</span>}</button>)}</div>
        {activeRoom && <div className="hh-home-grid"><section className="hh-panel"><p className="hh-kicker">Current condition</p><h2>{capitalizeFirst(display(activeRoom.room))}</h2>{activeRoom.latestConfirmed ? <><strong className="hh-state-value">{conditionSummary(activeRoom.latestConfirmed)}</strong><p className="hh-muted">Confirmed · {new Date(activeRoom.latestConfirmed.timestamp).toLocaleString()}</p><details><summary>Condition Details</summary><p className="hh-muted">{displayCategory(activeRoom.latestConfirmed.category)} · Estimated level {Math.round(activeRoom.latestConfirmed.value * 100)}%</p><p>{observationEvidence(activeRoom.latestConfirmed)}</p></details></> : <p className="hh-empty">No confirmed reading yet.</p>}{activeRoom.latestPending && <div className="hh-pending"><strong>Needs review</strong><p>{conditionSummary(activeRoom.latestPending)} · Unconfirmed</p><p className="hh-muted">{observationEvidence(activeRoom.latestPending)}</p><button disabled={busy || !token} onClick={() => confirm(activeRoom.latestPending!)}>Confirm observation</button></div>}<details><summary>Recent observations ({activeRoom.observations.length})</summary><div className="hh-compact-list">{activeRoom.observations.map(item => <div className="hh-history-entry" key={item.id}><strong>{conditionSummary(item)}</strong><small>{new Date(item.timestamp).toLocaleString()} · {needsReview(item) ? "Pending" : "Confirmed"}</small><details><summary>Evidence</summary><p>{observationEvidence(item)}</p><small>{displayCategory(item.category)} · Estimated level {Math.round(item.value * 100)}%</small></details></div>)}</div></details></section>
          <section className="hh-panel"><div className="hh-panel-head"><h2>Room tasks</h2><button className="hh-link" onClick={() => setView("tasks")}>All tasks →</button></div>{!report ? <p className="hh-empty">Load household tasks to view room work.</p> : roomTasks.length === 0 ? <p className="hh-empty">No active work for this space.</p> : <div className="hh-compact-list">{roomTasks.map(({task}) => <div className="hh-history-entry" key={task.id}><strong>{capitalizeFirst(task.description.replace(/ in unknown$/i, ""))}</strong><small>{taskState(task)} · {task.estimated_effort_minutes} min</small><button className="hh-inline-action" onClick={() => setView("tasks")}>View in Tasks →</button></div>)}</div>}</section></div>}</>}
      </section>}

      {view === "tasks" && <section className="hh-panel" aria-label="Autonomous household tasks">
        <div className="hh-panel-head"><h2>Autonomous tasks</h2><button className="secondary" disabled={busy || !token} onClick={refreshAutonomousTasks}>Refresh autonomous tasks</button></div>
        <p className="hh-muted">Opt-in live review. A reference photograph anchors a physical space; later photos require independent same-room verification.</p>
        <p className="hh-muted">Current photo ID: {media?.id ?? "Upload a photo first"}</p>
        <label htmlFor="hh-room-reference">Reference photo media ID</label>
        <input id="hh-room-reference" value={roomReference} onChange={e => setRoomReference(e.target.value)} placeholder="Use current photo ID for first registration" />
        {media?.id && <button className="secondary" onClick={() => setRoomReference(media.id)}>Use current photo as new room reference</button>}
        <button disabled={busy || !token || !media?.id || !roomReference.trim()} onClick={autonomousScan}>Verify scan and update tasks</button>
        {autonomousNote && <p role="status">{autonomousNote}</p>}
        {autonomousTasks.length === 0 ? <p className="hh-muted">No autonomous tasks loaded. Enable the backend feature flag and refresh to inspect stored tasks.</p> :
          <div className="hh-compact-list">{autonomousTasks.map(task => <div className="hh-task-row" key={task.id}>
            <div><strong>{task.title}</strong><p>{task.status} · {task.effort_min === null ? "Duration unknown" : `${task.effort_min}–${task.effort_max} min`}</p>
            <details><summary>Verification criteria</summary><p>{task.criteria}</p><small>Room reference: {task.room_id}</small></details></div>
          </div>)}</div>}
      </section>}

      {view === "tasks" && <section className="hh-view"><div className="hh-view-title"><div><p className="hh-kicker">Your work</p><h1>Tasks</h1><p>Review suggestions and manage accepted chores.</p></div><button className="secondary" disabled={busy || !token} onClick={refresh}>↻ Refresh</button></div>
        <div className="hh-panel"><div className="hh-panel-head"><h2>Suggestions <span className="hh-mini-count">{suggestedTasks.length}</span></h2></div>{!report ? <p className="hh-empty">Connect your household to view suggestions.</p> : suggestedTasks.length === 0 ? <p className="hh-empty">All caught up. New suggestions will appear here.</p> : <div className="hh-compact-list">{suggestedTasks.map(({task}) => <div className="hh-task-row" key={task.id}><div><strong>{capitalizeFirst(task.description.replace(/ in unknown$/i, ""))}</strong><p>{display(task.urgency)} priority · {task.estimated_effort_minutes} min</p><details><summary>Details</summary><p>{typeof task.metadata?.location === "string" ? `Space: ${display(task.metadata.location)}` : "Room not specified"}</p></details></div><div className="hh-task-actions"><button disabled={busy || !token} onClick={() => acceptTask(task.id)}>Accept</button><button className="secondary" disabled={busy || !token} onClick={() => deferTask(task.id)}>Later</button><button className="hh-text-danger" disabled={busy || !token} onClick={() => dismissTask(task.id)}>Dismiss</button></div></div>)}</div>}</div>
        <div className="hh-panel"><h2>Accepted <span className="hh-mini-count">{acceptedTasks.length}</span></h2>{!report ? <p className="hh-empty">Accepted work appears here.</p> : acceptedTasks.length === 0 ? <p className="hh-empty">Accepted tasks will appear here.</p> : <div className="hh-compact-list">{acceptedTasks.map(({task}) => <div className="hh-task-row" key={task.id}><div><strong>{capitalizeFirst(task.description.replace(/ in unknown$/i, ""))}</strong><p>{task.estimated_effort_minutes} min · {task.metadata?.verification_status === "verified_resolved" ? "Verified" : task.metadata?.user_reported_complete_at ? "Awaiting verification" : "Accepted"}</p></div>{task.metadata?.user_reported_complete_at ? <span className="hh-status-pill">Verification pending</span> : <button disabled={busy || !token} onClick={() => markDone(task.id)}>Done</button>}</div>)}</div>}</div>
      </section>}

      {view === "activity" && <section className="hh-view"><div className="hh-view-title"><div><p className="hh-kicker">Timeline</p><h1>Activity</h1><p>A transparent record of household evidence, decisions, and uncertainty.</p></div><button className="secondary" disabled={busy || !token} onClick={loadHousehold}>↻ Refresh</button></div>
        <section className="hh-panel">{!historyLoaded ? <p className="hh-empty">Load household history to see activity.</p> : history.length === 0 ? <p className="hh-empty">Your household activity will appear after your first scan.</p> : <div className="hh-compact-list">{[...history].sort((a,b)=>b.timestamp.localeCompare(a.timestamp)).map(item => <div key={item.id} className="hh-history-entry"><strong>{capitalizeFirst(display(item.location))} · {conditionSummary(item)}</strong><p>{needsReview(item) ? "Unverified" : evidenceStatus(item)} · {new Date(item.timestamp).toLocaleString()}</p><details><summary>Evidence</summary><p>{observationEvidence(item)}</p><small>{displayCategory(item.category)} · Estimated level {Math.round(item.value * 100)}%</small></details></div>)}</div>}</section>
      </section>}

      {scanOpen && <div className="hh-modal-backdrop" onClick={() => setScanOpen(false)}>
        <section role="dialog" aria-modal="true" aria-labelledby="hh-scan-title" className="hh-modal" onClick={e => e.stopPropagation()}>
          <div className="hh-panel-head"><h2 id="hh-scan-title">Scan a space</h2><button type="button" className="hh-icon-button" aria-label="Close scan" onClick={() => setScanOpen(false)}>✕</button></div>
          {!isConnected ? <div className="hh-pending" role="status" style={{display:"grid",gap:".75rem",padding:"1.2rem",marginTop:"1.2rem"}}>
            <strong style={{fontSize:"1.05rem"}}>Connect household to upload files</strong>
            <p style={{margin:0}}>{token ? "You're signed in, but your household isn't loaded yet. Open Settings and select Load household to access your private photo uploads and demo library." : "Sign in or create an account, then select Load household in Settings. Photo upload and demo scenes will become available after a successful connection."}</p>
            <button type="button" onClick={() => {setScanOpen(false);setSettingsOpen(true);}} style={{width:"100%"}}>{token ? "Open Settings · Load household" : "Open Settings · Sign in"}</button>
          </div> : <>
            <details><summary>Room (optional)</summary><label>Room label<input value={location} placeholder="Add a room name if known" onChange={e => setLocation(e.target.value)}/></label><p className="hh-muted">HomHive can suggest a room category but will not invent a physical room identity.</p></details>
            <div className="hh-photo-options" style={{alignItems:"stretch"}}>
              <div><strong>Choose a photo</strong><p className="hh-muted">Upload your own photo or choose from {demoCatalog.length} demo scenes. Both use live analysis.</p></div>
              <button type="button" className="secondary" onClick={() => setDemoOpen(true)}>Browse demo library</button>
            </div>
            <label style={{display:"block",padding:"1rem",border:"1px dashed #96b4a0",borderRadius:"14px",background:"#f7faf7",cursor:"pointer",textAlign:"center"}}>
              <strong>Upload a photo from your device</strong>
              <span style={{display:"block",fontSize:".8rem",color:"#5a6c60",marginTop:".3rem"}}>JPG, PNG, or WebP · Choose an image</span>
              <input type="file" accept="image/jpeg,image/png,image/webp" capture="environment" aria-label="Upload a household photo" style={{position:"absolute",width:"1px",height:"1px",opacity:0,overflow:"hidden"}} onChange={e => {setFile(e.target.files?.[0] ?? null);setMedia(null);setObservations([]);}} />
            </label>
            {file && <p className="hh-selected-photo" role="status">Selected: {file.name} · {(file.size / 1024 / 1024).toFixed(1)} MB</p>}
            {file && <p className="hh-muted">Ready for live AI analysis.</p>}
            <div className="hh-task-actions"><button disabled={busy || !file || !isConnected} onClick={upload}>{busy ? "Working…" : "Upload and analyze"}</button>{media?.processing === "retry_required" && <button className="secondary" disabled={busy || !isConnected} onClick={analyze}>Retry analysis</button>}</div>
            {!file && <p className="hh-muted" role="status">Select a photo from your device or browse the demo library to enable analysis.</p>}
            {observations.length > 0 && <div className="hh-compact-list"><h3>Observations</h3>{observations.map(item => <div className="hh-history-entry" key={item.id}><strong>{conditionSummary(item)}</strong><p>{observationEvidence(item)}</p><small>{needsReview(item) ? "Unverified" : evidenceStatus(item)}</small>{needsReview(item) && <button disabled={busy} onClick={() => confirm(item)}>Confirm observation</button>}</div>)}</div>}
            <p className="hh-muted">AI-corroborated observations do not require routine confirmation. Accepting a task is a separate decision.</p>
          </>}
        </section>
      </div>}
      {demoOpen && <div className="hh-modal-backdrop hh-demo-backdrop" onClick={() => setDemoOpen(false)}><section role="dialog" aria-modal="true" aria-labelledby="hh-demo-title" className="hh-modal hh-demo-dialog" onClick={e => e.stopPropagation()}><div className="hh-panel-head"><div><p className="hh-kicker">HomHive demo library</p><h2 id="hh-demo-title">Choose a household scene</h2><p className="hh-muted">{demoCatalog.length} sample photographs. Selecting one uses real AI analysis when you submit it.</p></div><button className="hh-icon-button" aria-label="Close image library" onClick={() => setDemoOpen(false)}>✕</button></div><div className="hh-demo-filters"><label>Find a scene<input value={demoQuery} onChange={e => setDemoQuery(e.target.value)} placeholder="Search rooms, conditions, and scenes"/></label><label>Room category<select value={demoCategory} onChange={e => setDemoCategory(e.target.value)}>{demoCategories.map(category => <option key={category} value={category}>{category}</option>)}</select></label></div><p className="hh-muted" aria-live="polite">Showing {visibleDemoImages.length} photographs</p>{demoSelectionError && <p role="alert" className="hh-demo-error">{demoSelectionError}</p>}<div className="hh-demo-grid">{visibleDemoImages.map(image => <button className="hh-demo-item" disabled={demoSelecting} key={image.id} onClick={() => chooseDemoImage(image)} aria-label={`Select ${image.title}`}><img src={image.thumbnail} alt={image.title} loading="lazy"/><span><strong>{image.title}</strong><small>{image.category} · {image.group === "original" ? "Original scene" : image.group === "base" ? "Base scene" : "Controlled variant"}</small></span></button>)}</div></section></div>}
      {settingsOpen && <div className="hh-modal-backdrop" onClick={() => setSettingsOpen(false)}>
        <section role="dialog" aria-modal="true" aria-labelledby="hh-settings-title" className="hh-modal hh-settings-dialog" onClick={e => e.stopPropagation()}>
          <div className="hh-panel-head"><h2 id="hh-settings-title">Settings</h2><button type="button" className="hh-icon-button" aria-label="Close settings" onClick={() => setSettingsOpen(false)}>✕</button></div>
          {!token ? <div className="hh-auth-form">
            <div className="hh-auth-switch" role="group" aria-label="Account access">
              <button type="button" aria-pressed={authMode === "login"} className={authMode === "login" ? "hh-time-active" : "secondary"} onClick={() => { setAuthMode("login"); setAuthError(""); setConfirmPassword(""); }}>Sign in</button>
              <button type="button" aria-pressed={authMode === "register"} className={authMode === "register" ? "hh-time-active" : "secondary"} onClick={() => { setAuthMode("register"); setAuthError(""); setConfirmPassword(""); }}>Create account</button>
            </div>
            <div className="hh-auth-heading"><h3>{authMode === "login" ? "Welcome back" : "Create your private household"}</h3><p>{authMode === "login" ? "Sign in to access your saved household and tasks." : "Create an account to securely save scans, rooms, and household tasks."}</p></div>
            <form className="hh-auth-fields" onSubmit={e => {e.preventDefault();void authenticate();}} noValidate>
              <label>Email address<input type="email" autoComplete="email" placeholder="you@example.com" value={authEmail} onChange={e => {setAuthEmail(e.target.value);setAuthError("");}} /></label>
              <label>Password<input type="password" autoComplete={authMode === "register" ? "new-password" : "current-password"} placeholder={authMode === "register" ? "At least 12 characters" : "Your password"} value={authPassword} onChange={e => {setAuthPassword(e.target.value);setAuthError("");}} /></label>
              {authMode === "register" && <label>Confirm password<input type="password" autoComplete="new-password" placeholder="Re-enter your password" value={confirmPassword} onChange={e => {setConfirmPassword(e.target.value);setAuthError("");}} /></label>}
              {authError && <div className="hh-auth-feedback" role="alert"><p>{authError}</p>{authMode === "register" && /already|existing/i.test(authError) && <button type="button" className="hh-inline-action" onClick={() => {setAuthMode("login");setAuthError("");setAuthPassword("");setConfirmPassword("");}}>Switch to sign in →</button>}</div>}
              <button className="hh-auth-submit" type="submit" disabled={Boolean(authDisabledReason)}>{busy ? "Please wait…" : authMode === "login" ? "Sign in" : "Create account"}</button>
              {authDisabledReason && <p className="hh-auth-reason" role="status">{authDisabledReason}</p>}
            </form>
            <p className="hh-auth-footnote">{authMode === "register" ? "Your account creates a private household. Sessions expire after seven days." : "Use the password you created with this email. Account recovery is not yet available."}</p>
          </div> : <div className="hh-auth-connected"><strong>Signed in</strong><p>Your account has a private household. Select <strong>Load household</strong> to access scans and saved work.</p><button type="button" className="secondary" disabled={busy} onClick={signOut}>Sign out</button></div>}
          <section className="hh-settings-section" aria-label="Household connection"><h3>Household connection</h3><p className="hh-muted">{isConnected ? "Your household is loaded. Scans and saved work are available." : token ? "You are signed in. Select Load household to connect your saved data." : "Sign in or create an account to connect your private household."}</p><button type="button" disabled={Boolean(householdDisabledReason)} onClick={async () => {if (await loadHousehold()) setSettingsOpen(false);}}>{busy ? "Connecting…" : isConnected ? "Household connected" : "Load household"}</button>{householdDisabledReason && <p role="status" className="hh-auth-reason">{householdDisabledReason}</p>}</section>
          <details className="hh-settings-details"><summary>Presence (optional)</summary><p className="hh-muted">Share whether you are home. This is manual and expires after one hour.</p><p className="hh-muted">Current: {presence?.state ?? "UNKNOWN"}</p><div className="hh-task-actions"><button className="secondary" disabled={!isConnected || busy} onClick={() => changePresence("HOME")}>I'm home</button><button className="secondary" disabled={!isConnected || busy} onClick={() => changePresence("AWAY")}>I'm away</button><button className="secondary" disabled={!isConnected || busy} onClick={() => changePresence("UNKNOWN")}>Stop sharing</button></div>{(!isConnected || busy) && <p className="hh-auth-reason">{!isConnected ? "Load your household before sharing presence." : "Please wait for the current request."}</p>}</details>
          <details className="hh-settings-details"><summary>Connection diagnostics</summary><label>API URL<input value={apiUrl} onChange={e => setApiUrl(e.target.value)}/></label><p className="hh-muted">Account sessions are held in this browser tab and revoked on sign out.</p>{token && <p className="hh-muted">Technical household ID (for troubleshooting): <code style={{overflowWrap:"anywhere"}}>{householdId}</code></p>}</details>
        </section></div>}
    </main>
  );
}
