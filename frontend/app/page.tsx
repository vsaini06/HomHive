"use client";

import { useMemo, useState } from "react";
import { HomHiveApi, IntelligenceReport, MediaRecord, Observation, PlanResponse, VisionResult } from "../lib/api";

const defaultApi = process.env.NEXT_PUBLIC_HOMHIVE_API_URL ?? "http://127.0.0.1:8000";

export default function Home() {
  const [apiUrl, setApiUrl] = useState(defaultApi);
  const [householdId, setHouseholdId] = useState("homhive_test_home");
  const [token, setToken] = useState("");
  const [location, setLocation] = useState("kitchen");
  const [file, setFile] = useState<File | null>(null);
  const [media, setMedia] = useState<MediaRecord | null>(null);
  const [observations, setObservations] = useState<Observation[]>([]);
  const [report, setReport] = useState<IntelligenceReport | null>(null);
  const [plan, setPlan] = useState<PlanResponse | null>(null);
  const [availableMinutes, setAvailableMinutes] = useState(30);
  const [atHome, setAtHome] = useState(true);
  const [quietHours, setQuietHours] = useState(false);
  const [researchQuery, setResearchQuery] = useState("");
  const [status, setStatus] = useState("Ready");
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

  async function upload() {
    if (!file || !token) return;
    const result = await run<MediaRecord>("Uploading private household media...", () => api.upload(file));
    if (result) {
      setMedia(result);
      setObservations([]);
      setReport(null);
      setPlan(null);
    }
  }

  async function analyze() {
    if (!media) return;
    const result = await run<VisionResult>("Analyzing visible household conditions...", () => api.analyze(media.id, location));
    if (result) setObservations(result.observations);
  }

  async function confirm(observation: Observation) {
    const result = await run<Observation>("Saving your confirmation...", () => api.confirmObservation(observation.id, observation.value));
    if (result) setObservations((items) => items.map((item) => (item.id === observation.id ? result : item)));
  }

  async function refresh() {
    const result = await run<IntelligenceReport>("Rebuilding household intelligence...", () => api.refresh());
    if (result) setReport(result);
  }

  async function createPlan() {
    const result = await run<PlanResponse>("Planning around your current constraints...", () =>
      api.plan({
        availableMinutes,
        atHome,
        quietHours,
        researchQuery: researchQuery.trim() || undefined,
      }),
    );
    if (result) setPlan(result);
  }

  return (
    <main>
      <section className="hero">
        <div>
          <p className="eyebrow">HomHive</p>
          <h1>The intelligence layer for the autonomous home.</h1>
          <p className="lede">Turn household evidence into remembered state, discovered work, forecasts, research, and a plan that changes with your constraints.</p>
        </div>
        <div className="status"><span className={busy ? "pulse" : "dot"} />{status}</div>
      </section>

      <section className="grid two">
        <article className="card">
          <h2>Connect</h2>
          <label>API URL<input value={apiUrl} onChange={(e) => setApiUrl(e.target.value)} /></label>
          <label>Household<input value={householdId} onChange={(e) => setHouseholdId(e.target.value)} /></label>
          <label>Household token<input type="password" value={token} onChange={(e) => setToken(e.target.value)} placeholder="Bearer token" /></label>
          <p className="hint">The token stays in this browser session and is sent only to your configured HomHive API.</p>
        </article>

        <article className="card">
          <h2>Scan a space</h2>
          <label>Location<input value={location} onChange={(e) => setLocation(e.target.value)} /></label>
          <label>Photo<input type="file" accept="image/jpeg,image/png,image/webp" capture="environment" onChange={(e) => setFile(e.target.files?.[0] ?? null)} /></label>
          <div className="actions">
            <button disabled={busy || !file || !token} onClick={upload}>Upload</button>
            <button className="secondary" disabled={busy || !media} onClick={analyze}>Analyze</button>
          </div>
          {media && <p className="hint">Stored privately as {media.id}</p>}
        </article>
      </section>

      <section className="card">
        <div className="sectionHead"><div><p className="eyebrow">Evidence</p><h2>What HomHive observed</h2></div></div>
        {!observations.length && <p className="empty">No extracted observations yet.</p>}
        <div className="items">
          {observations.map((observation) => (
            <div className="item" key={observation.id}>
              <div>
                <strong>{observation.category.replaceAll("_", " ")}</strong>
                <p>{String(observation.metadata.visible_evidence ?? "Visible household evidence")}</p>
              </div>
              <div className="metric">{Math.round(observation.value * 100)}%</div>
              <div className="badge">{observation.confidence === null ? "Needs confirmation" : "Confirmed"}</div>
              {observation.confidence === null && <button disabled={busy} onClick={() => confirm(observation)}>Confirm</button>}
            </div>
          ))}
        </div>
      </section>

      <section className="card">
        <div className="sectionHead">
          <div><p className="eyebrow">Household state</p><h2>Current intelligence</h2></div>
          <button disabled={busy || !token} onClick={refresh}>Refresh intelligence</button>
        </div>
        {!report && <p className="empty">Refresh after confirming evidence to discover and rank household work.</p>}
        {report && (
          <div className="taskList">
            {report.ranked_tasks.map((entry) => (
              <div className="task" key={entry.task.id}>
                <div><strong>{entry.task.description}</strong><p>{entry.task.urgency} urgency · {entry.task.estimated_effort_minutes} min total effort</p></div>
                <span>{entry.priority_score.toFixed(3)}</span>
              </div>
            ))}
            {!report.ranked_tasks.length && <p className="empty">No active tasks from confirmed evidence.</p>}
          </div>
        )}
      </section>

      <section className="grid two">
        <article className="card">
          <p className="eyebrow">Context</p>
          <h2>What fits now?</h2>
          <label>Available active minutes<input type="number" min={1} max={720} value={availableMinutes} onChange={(e) => setAvailableMinutes(Number(e.target.value))} /></label>
          <label className="check"><input type="checkbox" checked={atHome} onChange={(e) => setAtHome(e.target.checked)} /> I am at home</label>
          <label className="check"><input type="checkbox" checked={quietHours} onChange={(e) => setQuietHours(e.target.checked)} /> Quiet hours are active</label>
          <label>Optional research question<input value={researchQuery} onChange={(e) => setResearchQuery(e.target.value)} placeholder="e.g. Monstera watering guidance" /></label>
          <button disabled={busy || !token} onClick={createPlan}>Create plan</button>
        </article>

        <article className="card planCard">
          <p className="eyebrow">Plan</p>
          <h2>{plan?.plan.summary ?? "Your household plan will appear here."}</h2>
          {plan && <p className="hint">Planner: {plan.plan.planner.replaceAll("_", " ")}</p>}
          <ol>
            {plan?.plan.steps.map((step) => (
              <li key={step.task_id}><strong>{step.active_minutes} active min</strong><span>{step.reason}</span></li>
            ))}
          </ol>
          {!!plan?.plan.deferred.length && <details><summary>Deferred work</summary>{plan.plan.deferred.map((item) => <p key={item.task_id}>{item.reason}</p>)}</details>}
        </article>
      </section>
    </main>
  );
}
