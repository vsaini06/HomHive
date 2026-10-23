"use client";

import { useMemo, useState } from "react";
import { HomHiveApi, HouseholdNotification, HouseholdPresence, IntelligenceReport, MediaRecord, Observation, PlanResponse, VisionResult } from "../lib/api";

const defaultApi = process.env.NEXT_PUBLIC_HOMHIVE_API_URL ?? "http://127.0.0.1:8000";

export default function Home() {
  const [apiUrl, setApiUrl] = useState(defaultApi);
  const [householdId, setHouseholdId] = useState("homhive_test_home");
  const [token, setToken] = useState("");
  const [location, setLocation] = useState("");
  const [file, setFile] = useState<File | null>(null);
  const [media, setMedia] = useState<MediaRecord | null>(null);
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
  const [busy, setBusy] = useState(false);

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

  async function loadHousehold() {
    if (!token || !householdId.trim()) return;
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
    }
  }

  // User confirmation is stored as a separate observation linked to its
  // original AI evidence. Preserve the original record but do not offer
  // a second confirmation or count it as pending.
  const confirmedSourceIds = useMemo(() => new Set(
    history.filter(item => item.source === "user_input")
      .map(item => item.metadata?.confirmed_observation_id)
      .filter((id): id is string => typeof id === "string" && id.length > 0),
  ), [history]);
  const needsReview = (item: Observation) => item.confidence === null && !confirmedSourceIds.has(item.id);

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

  async function upload() {
    if (!file || !token) return;
    const result = await run<MediaRecord>("Uploading and inspecting household photo...", () => api.upload(file, location));
    if (result) {
      setMedia(result);
      setObservations(result.observations ?? []);
      setPlan(null);
      if (result.processing === "retry_required") {
        setStatus("Photo saved, but analysis could not finish. You can retry below.");
      } else if (result.processing === "needs_review") {
        setStatus("Photo saved. HomHive needs more information to interpret it.");
      } else if (result.processing === "processed") {
        setStatus(result.observations?.length ? "Photo analyzed. Review the observations below." : "Photo analyzed. No supported conditions were found.");
      } else {
        setStatus("Photo saved. Analysis is pending or unavailable.");
      }
      if (result.processing === "processed" && result.observations?.length) {
        await loadHousehold();
        const detectedRoom = result.observations[0]?.location;
        if (detectedRoom && detectedRoom !== "unknown") setSelectedRoom(detectedRoom);
        setScanOpen(false);
        setView("spaces");
        setStatus(detectedRoom && detectedRoom !== "unknown"
          ? `Photo analyzed · ${capitalizeFirst(display(detectedRoom))} detected. Review the observation.`
          : "Photo analyzed. Review the observation in Spaces.");
      } else if (result.observations?.length) await loadHousehold();
    }
  }

  async function analyze() {
    if (!media) return;
    const result = await run<VisionResult>("Analyzing visible household conditions...", () => api.analyze(media.id, location || "unknown"));
    if (result) { setObservations(result.observations); await loadHousehold(); }
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
    <main className="hh-app">
      <header className="hh-header">
        <div className="hh-brand"><span className="hh-mark" aria-hidden="true">⌂</span><span>HomHive<small>Household intelligence</small></span></div>
        <nav className="hh-nav" aria-label="Main navigation">
          {navItems.map((item) => <button key={item.id} className={view === item.id ? "hh-nav-active" : "hh-nav-button"} aria-current={view === item.id ? "page" : undefined} onClick={() => setView(item.id)}><span aria-hidden="true">{item.icon}</span>{item.label}</button>)}
        </nav>
        <div className="hh-toolbar">{isConnected && <span className="hh-muted" aria-label="Connected household">Connected · {householdId}</span>}<button className="hh-scan" onClick={() => setScanOpen(true)}>＋ Scan</button><button className="hh-icon-button" aria-label="Open settings" onClick={() => setSettingsOpen(true)}>⚙</button></div>
      </header>
      <div className="hh-live" role="status" aria-live="polite"><span className={busy ? "pulse" : "dot"}/>{status}</div>

      {!token && <section className="hh-notice" role="status"><strong>Connect your household</strong><span>Add your household token in Settings to load saved work.</span><button onClick={() => setSettingsOpen(true)}>Open Settings</button></section>}

      {view === "home" && <section className="hh-view">
        <div className="hh-view-title"><div><p className="hh-kicker">Your household</p><h1>Overview</h1><p>A clear view of what matters at home.</p></div><button className="secondary" disabled={busy || !token} onClick={loadHousehold}>↻ Refresh</button></div>
        {isConnected && <div className="hh-stats">
          <button onClick={() => setView("spaces")}><span>Spaces</span><strong>{roomSummaries.length}</strong><small>Rooms with saved observations</small></button>
          <button onClick={() => setView("tasks")}><span>Accepted work</span><strong>{acceptedTasks.length}</strong><small>Ready for planning</small></button>
          <button onClick={() => setView("activity")}><span>Needs review</span><strong>{pendingCount}</strong><small>Observations awaiting confirmation</small></button>
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
        {isConnected && <section className="hh-panel hh-planning"><div className="hh-panel-head"><div><p className="hh-kicker">Planning</p><h2>Your plan</h2></div></div>
          <div className="hh-plan-layout"><div className="hh-plan-controls"><label>Time available <input type="number" min={1} max={720} value={availableMinutes} onChange={e => setAvailableMinutes(Number(e.target.value))}/></label><label className="check"><input type="checkbox" checked={atHome} onChange={e => setAtHome(e.target.checked)}/> I'm at home</label><label className="check"><input type="checkbox" checked={quietHours} onChange={e => setQuietHours(e.target.checked)}/> Quiet hours</label><details><summary>More context</summary><label>Research question (optional)<input value={researchQuery} onChange={e => setResearchQuery(e.target.value)}/></label></details><button disabled={busy || !token} onClick={createPlan}>Build plan</button></div>
          <div className="hh-plan-output">{!plan ? <p className="hh-empty">Your plan will list accepted work that fits your availability.</p> : plannedTasks.length === 0 ? <p className="hh-empty">No accepted tasks fit these constraints right now.</p> : <ol className="hh-plan-steps">{plannedTasks.map(step => <li key={step.task_id}><div><strong>{taskById.get(step.task_id)?.description ?? "Household task"}</strong><small>{step.active_minutes} min active{step.passive_minutes ? ` · ${step.passive_minutes} min passive` : ""}</small></div><details><summary>Why It Fits</summary><p>{capitalizeFirst(step.reason)}</p></details></li>)}</ol>}{plan && <details className="hh-plan-detail"><summary>Plan Details</summary><p>{plan.plan.summary}</p>{plan.plan.deferred.map(item => <p key={item.task_id}>{item.reason}</p>)}</details>}</div></div>
        </section>}
      </section>}

      {view === "spaces" && <section className="hh-view"><div className="hh-view-title"><div><p className="hh-kicker">Your household</p><h1>Spaces</h1><p>Confirmed conditions and the evidence behind them.</p></div><button className="secondary" disabled={busy || !token} onClick={loadHousehold}>↻ Refresh</button></div>
        {!roomSummaries.length ? <div className="hh-panel hh-empty">No spaces yet. Scan a room to get started.</div> : <><div className="hh-room-tabs" aria-label="Choose a room">{roomSummaries.map(room => <button key={room.room} aria-pressed={activeRoom?.room === room.room} className={activeRoom?.room === room.room ? "hh-selected" : ""} onClick={() => setSelectedRoom(room.room)}>{capitalizeFirst(display(room.room))}{room.pending > 0 && <span>{room.pending}</span>}</button>)}</div>
        {activeRoom && <div className="hh-home-grid"><section className="hh-panel"><p className="hh-kicker">Current condition</p><h2>{capitalizeFirst(display(activeRoom.room))}</h2>{activeRoom.latestConfirmed ? <><strong className="hh-state-value">{conditionSummary(activeRoom.latestConfirmed)}</strong><p className="hh-muted">Confirmed · {new Date(activeRoom.latestConfirmed.timestamp).toLocaleString()}</p><details><summary>Condition Details</summary><p className="hh-muted">{displayCategory(activeRoom.latestConfirmed.category)} · Estimated level {Math.round(activeRoom.latestConfirmed.value * 100)}%</p><p>{observationEvidence(activeRoom.latestConfirmed)}</p></details></> : <p className="hh-empty">No confirmed reading yet.</p>}{activeRoom.latestPending && <div className="hh-pending"><strong>Needs review</strong><p>{conditionSummary(activeRoom.latestPending)} · Unconfirmed</p><p className="hh-muted">{observationEvidence(activeRoom.latestPending)}</p><button disabled={busy || !token} onClick={() => confirm(activeRoom.latestPending!)}>Confirm observation</button></div>}<details><summary>Recent observations ({activeRoom.observations.length})</summary><div className="hh-compact-list">{activeRoom.observations.map(item => <div className="hh-history-entry" key={item.id}><strong>{conditionSummary(item)}</strong><small>{new Date(item.timestamp).toLocaleString()} · {needsReview(item) ? "Pending" : "Confirmed"}</small><details><summary>Evidence</summary><p>{observationEvidence(item)}</p><small>{displayCategory(item.category)} · Estimated level {Math.round(item.value * 100)}%</small></details></div>)}</div></details></section>
          <section className="hh-panel"><div className="hh-panel-head"><h2>Room tasks</h2><button className="hh-link" onClick={() => setView("tasks")}>All tasks →</button></div>{!report ? <p className="hh-empty">Load household tasks to view room work.</p> : roomTasks.length === 0 ? <p className="hh-empty">No active work for this space.</p> : <div className="hh-compact-list">{roomTasks.map(({task}) => <div className="hh-history-entry" key={task.id}><strong>{capitalizeFirst(task.description.replace(/ in unknown$/i, ""))}</strong><small>{taskState(task)} · {task.estimated_effort_minutes} min</small><button className="hh-inline-action" onClick={() => setView("tasks")}>View in Tasks →</button></div>)}</div>}</section></div>}</>}
      </section>}

      {view === "tasks" && <section className="hh-view"><div className="hh-view-title"><div><p className="hh-kicker">Your work</p><h1>Tasks</h1><p>Review suggestions and manage accepted chores.</p></div><button className="secondary" disabled={busy || !token} onClick={refresh}>↻ Refresh</button></div>
        <div className="hh-panel"><div className="hh-panel-head"><h2>Suggestions <span className="hh-mini-count">{suggestedTasks.length}</span></h2></div>{!report ? <p className="hh-empty">Connect your household to view suggestions.</p> : suggestedTasks.length === 0 ? <p className="hh-empty">All caught up. New suggestions will appear here.</p> : <div className="hh-compact-list">{suggestedTasks.map(({task}) => <div className="hh-task-row" key={task.id}><div><strong>{capitalizeFirst(task.description.replace(/ in unknown$/i, ""))}</strong><p>{display(task.urgency)} priority · {task.estimated_effort_minutes} min</p><details><summary>Details</summary><p>{typeof task.metadata?.location === "string" ? `Space: ${display(task.metadata.location)}` : "Room not specified"}</p></details></div><div className="hh-task-actions"><button disabled={busy || !token} onClick={() => acceptTask(task.id)}>Accept</button><button className="secondary" disabled={busy || !token} onClick={() => deferTask(task.id)}>Later</button><button className="hh-text-danger" disabled={busy || !token} onClick={() => dismissTask(task.id)}>Dismiss</button></div></div>)}</div>}</div>
        <div className="hh-panel"><h2>Accepted <span className="hh-mini-count">{acceptedTasks.length}</span></h2>{!report ? <p className="hh-empty">Accepted work appears here.</p> : acceptedTasks.length === 0 ? <p className="hh-empty">Accepted tasks will appear here.</p> : <div className="hh-compact-list">{acceptedTasks.map(({task}) => <div className="hh-task-row" key={task.id}><div><strong>{capitalizeFirst(task.description.replace(/ in unknown$/i, ""))}</strong><p>{task.estimated_effort_minutes} min · {task.metadata?.verification_status === "verified_resolved" ? "Verified" : task.metadata?.user_reported_complete_at ? "Awaiting verification" : "Accepted"}</p></div>{task.metadata?.user_reported_complete_at ? <span className="hh-status-pill">Verification pending</span> : <button disabled={busy || !token} onClick={() => markDone(task.id)}>Done</button>}</div>)}</div>}</div>
      </section>}

      {view === "activity" && <section className="hh-view"><div className="hh-view-title"><div><p className="hh-kicker">Timeline</p><h1>Activity</h1><p>Past observations and decisions, with uncertainty preserved.</p></div><button className="secondary" disabled={busy || !token} onClick={loadHousehold}>↻ Refresh</button></div>
        <section className="hh-panel">{!historyLoaded ? <p className="hh-empty">Load household history to see activity.</p> : history.length === 0 ? <p className="hh-empty">Your household activity will appear after your first scan.</p> : <div className="hh-compact-list">{[...history].sort((a,b)=>b.timestamp.localeCompare(a.timestamp)).map(item => <div key={item.id} className="hh-history-entry"><strong>{capitalizeFirst(display(item.location))} · {conditionSummary(item)}</strong><p>{needsReview(item) ? "Needs review" : "Confirmed"} · {new Date(item.timestamp).toLocaleString()}</p><details><summary>Evidence</summary><p>{observationEvidence(item)}</p><small>{displayCategory(item.category)} · Estimated level {Math.round(item.value * 100)}%</small></details></div>)}</div>}</section>
      </section>}

      {scanOpen && <div className="hh-modal-backdrop" onClick={() => setScanOpen(false)}><section role="dialog" aria-modal="true" aria-labelledby="hh-scan-title" className="hh-modal" onClick={e=>e.stopPropagation()}><div className="hh-panel-head"><h2 id="hh-scan-title">Scan a space</h2><button className="hh-icon-button" aria-label="Close scan" onClick={() => setScanOpen(false)}>✕</button></div><details><summary>Room (optional)</summary><label>Room label<input value={location} placeholder="Add a room name if known" onChange={e => setLocation(e.target.value)}/></label><p className="hh-muted">HomHive may suggest a room category, but it will not guess which physical room it is.</p></details><label>Photo<input type="file" accept="image/jpeg,image/png,image/webp" capture="environment" onChange={e => {setFile(e.target.files?.[0] ?? null);setMedia(null);setObservations([]);}}/></label>{!token && <div className="hh-pending" role="status"><strong>Connect to upload</strong><p>Enter your household token in Settings to keep this scan private.</p><button type="button" className="secondary" onClick={() => {setScanOpen(false);setSettingsOpen(true);}}>Open Settings</button></div>}{file && token && <p className="hh-muted">Ready to upload. HomHive will analyze the photo automatically.</p>}<div className="hh-task-actions"><button disabled={busy || !file || !token} onClick={upload}>{busy ? "Working…" : "Upload and analyze"}</button>{media?.processing === "retry_required" && <button className="secondary" disabled={busy || !token} onClick={analyze}>Retry analysis</button>}</div>{observations.length > 0 && <div className="hh-compact-list"><h3>Observations</h3>{observations.map(item => <div className="hh-history-entry" key={item.id}><strong>{conditionSummary(item)}</strong><p>{observationEvidence(item)}</p><small>{needsReview(item) ? "Needs confirmation" : "Confirmed"}</small>{needsReview(item) && <button disabled={busy} onClick={() => confirm(item)}>Confirm observation</button>}</div>)}</div>}<p className="hh-muted">Confirming an observation is separate from accepting a suggested task.</p></section></div>}

      {settingsOpen && <div className="hh-modal-backdrop" onClick={() => setSettingsOpen(false)}><section role="dialog" aria-modal="true" aria-labelledby="hh-settings-title" className="hh-modal" onClick={e=>e.stopPropagation()}><div className="hh-panel-head"><h2 id="hh-settings-title">Settings</h2><button className="hh-icon-button" aria-label="Close settings" onClick={() => setSettingsOpen(false)}>✕</button></div><label>Household<input value={householdId} onChange={e => setHouseholdId(e.target.value)}/></label><label>Household token<input type="password" autoComplete="off" value={token} onChange={e => setToken(e.target.value)} placeholder="Enter household token"/></label><details><summary>Connection diagnostics</summary><label>API URL<input value={apiUrl} onChange={e=>setApiUrl(e.target.value)}/></label><p className="hh-muted">Your token stays in this browser session. Never share it in chat.</p></details><details><summary>Presence (optional)</summary><p className="hh-muted">Manually share whether you're home. This is not automatic location tracking and expires after one hour.</p><p className="hh-muted">Current: {presence?.state ?? "UNKNOWN"}</p><div className="hh-task-actions"><button className="secondary" disabled={!token || busy} onClick={() => changePresence("HOME")}>I'm home</button><button className="secondary" disabled={!token || busy} onClick={() => changePresence("AWAY")}>I'm away</button><button className="secondary" disabled={!token || busy} onClick={() => changePresence("UNKNOWN")}>Stop sharing</button></div></details><button disabled={busy || !token || !householdId.trim()} onClick={async()=>{await loadHousehold();setSettingsOpen(false);}}>Load household</button></section></div>}
    </main>
  );
}
