"use client";

import { useEffect, useMemo, useRef, useState } from "react";
import { inspectHouseholdPhoto, type PhotoInspection } from "../lib/photo-check";
import { clearAccountSession, readAccountSession, saveAccountSession } from "../lib/account-session";
import { WORK_DAYS, WORK_TIME_OPTIONS, readableWorkDays, readableWorkTime, workWindowError } from "../lib/work-schedule";
import demoCatalog from "../public/demo-library/catalog.json";
import {
  HomHiveApi,
  HouseholdNotification,
  HouseholdPresence,
  IntelligenceReport,
  MediaRecord,
  Observation,
  PlanResponse,
  VisionResult,
  AutonomousTask,
  AutonomousScanJob,
  AutonomousRoom,
  AutonomousScanResult,
  AutonomousAlert,
  WorkWindow,
} from "../lib/api";

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
  const [photoInspection, setPhotoInspection] = useState<PhotoInspection | null>(null);
  const [photoPreviewUrl, setPhotoPreviewUrl] = useState<string | null>(null);
  const selectedPhotoRequestRef = useRef(0);
  const [notices, setNotices] = useState<Array<{id: number; title: string; detail: string; kind: "error" | "warning" | "success" | "info"}>>([]);
  const nextNoticeId = useRef(0);
  const [confirmation, setConfirmation] = useState<{title: string; detail: string; actionLabel: string; onConfirm: () => void} | null>(null);
  const [media, setMedia] = useState<MediaRecord | null>(null);
  const [autonomousTasks, setAutonomousTasks] = useState<AutonomousTask[]>([]);
  const [autonomousAlerts, setAutonomousAlerts] = useState<AutonomousAlert[]>([]);
  const seenAlertIds = useRef<Set<string> | null>(null);
  const [workWindow, setWorkWindow] = useState<WorkWindow | null>(null);
  const [windowStart, setWindowStart] = useState("18:00");
  const [windowEnd, setWindowEnd] = useState("21:00");
  const [windowWeekdays, setWindowWeekdays] = useState([0, 1, 2, 3, 4, 5, 6]);
  const [savingWindow, setSavingWindow] = useState(false);
  const [scanJobs, setScanJobs] = useState<AutonomousScanJob[]>([]);
  const [showScanStatus, setShowScanStatus] = useState(false);
  const [autonomousAvailable, setAutonomousAvailable] = useState(false);
  const [autonomousFetchError, setAutonomousFetchError] = useState("");
  const autonomousErrorReportedRef = useRef(false);
  const lastScanNoticeRef = useRef("");
  const [enrolledRooms, setEnrolledRooms] = useState<AutonomousRoom[]>([]);
  const [autonomousLoading, setAutonomousLoading] = useState(false);
  const loadedAccountRef = useRef("");
  const [roomReference, setRoomReference] = useState("");
  const [autonomousNote, setAutonomousNote] = useState("");
  const [editingRoomId, setEditingRoomId] = useState<string | null>(null);
  const [roomLabelDraft, setRoomLabelDraft] = useState("");
  const [recheckingMediaId, setRecheckingMediaId] = useState<string | null>(null);
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
  const [view, setView] = useState<"home" | "spaces" | "tasks" | "activity" | "schedule">("home");
  const [settingsOpen, setSettingsOpen] = useState(false);
  const [scanOpen, setScanOpen] = useState(false);
  const [demoOpen, setDemoOpen] = useState(false);
  const [demoQuery, setDemoQuery] = useState("");
  const [demoCategory, setDemoCategory] = useState("All");
  const [demoSelectionError, setDemoSelectionError] = useState("");
  const [demoSelecting, setDemoSelecting] = useState(false);
  const [busy, setBusy] = useState(false);
  const [scanProgress, setScanProgress] = useState<{ phase: "uploading" | "analyzing" | "held" | "done" | "error"; percent: number | null; mediaId: string | null; detail: string } | null>(null);


  const api = useMemo(
    () => new HomHiveApi(apiUrl.replace(/\/$/, ""), householdId, token),
    [apiUrl, householdId, token],
  );

  function friendlyError(error: unknown, fallback: string): string {
    const message = error instanceof Error ? error.message : fallback;
    if (/failed to fetch|networkerror|network request failed/i.test(message)) {
      return "Can't connect to HomHive. Check that the backend is running and your device is online.";
    }
    return message;
  }

  function notify(kind: "error" | "warning" | "success" | "info", title: string, detail = "") {
    const id = ++nextNoticeId.current;
    setNotices(items => [...items.slice(-2), {id, kind, title, detail}]);
    setTimeout(() => setNotices(items => items.filter(item => item.id !== id)), kind === "error" ? 11000 : 7500);
  }

  async function selectPhoto(selected: File | null): Promise<boolean> {
    const requestId = ++selectedPhotoRequestRef.current;
    setFile(null);
    setMedia(null);
    setObservations([]);
    setScanProgress(null);
    setPhotoInspection(null);
    if (!selected) return false;
    try {
      const inspected = await inspectHouseholdPhoto(selected);
      if (requestId !== selectedPhotoRequestRef.current) return false;
      setFile(selected);
      setPhotoInspection(inspected);
      if (inspected.warnings.length) notify("warning", "This photo may be difficult to analyze", inspected.warnings.join(" "));
      else notify("success", "Photo ready", "You can submit this image for AI review.");
      return true;
    } catch (error) {
      if (requestId !== selectedPhotoRequestRef.current) return false;
      notify("error", "Can't use this photo", error instanceof Error ? error.message : "Choose a different photo and try again.");
      return false;
    }
  }

  useEffect(() => {
    try {
      const saved = readAccountSession(window.sessionStorage, defaultApi);
      if (!saved) return;
      setHouseholdId(saved.householdId);
      setToken(saved.accessToken);
      setStatus("Restoring your household session…");
    } catch {
      notify("warning", "Your session won't survive a refresh", "This browser is blocking tab storage. Your current sign-in can still be used.");
    }
  }, []);

  useEffect(() => {
    if (!file) { setPhotoPreviewUrl(null); return; }
    const preview = URL.createObjectURL(file);
    setPhotoPreviewUrl(preview);
    return () => URL.revokeObjectURL(preview);
  }, [file]);

  useEffect(() => {
    if (!confirmation) return;
    const onEscape = (event: KeyboardEvent) => { if (event.key === "Escape") setConfirmation(null); };
    window.addEventListener("keydown", onEscape);
    return () => window.removeEventListener("keydown", onEscape);
  }, [confirmation]);

  async function run<T>(label: string, action: () => Promise<T>): Promise<T | null> {
    setBusy(true);
    setStatus(label);
    try {
      const result = await action();
      setStatus("Ready");
      return result;
    } catch (error) {
      const message = friendlyError(error, "Request failed");
      if (message === "Your session isn't authorized for this household. Sign in again.") {
        try { clearAccountSession(window.sessionStorage); } catch {}
        loadedAccountRef.current = "";
        setToken("");
        setHistoryLoaded(false);
        setHistory([]);
        setReport(null);
        setAutonomousTasks([]);
        setAutonomousAlerts([]); seenAlertIds.current = null;
        setScanJobs([]);
        setEnrolledRooms([]);
        setNotifications([]);
        setStatus("Session expired. Please sign in again.");
        notify("warning", "Sign in again", "Your session has expired or been revoked. Your saved household data is unchanged.");
      } else {
        setStatus(message);
        notify("error", label.replace(/\.{2,}$/, ""), message);
      }
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
    if (authDisabledReason) { setAuthError(authDisabledReason); notify("warning", "Check your sign-in details", authDisabledReason); return; }
    setAuthError("");
    setBusy(true);
    try {
      const response = await fetch(`${apiUrl.replace(/\/$/, "")}/auth/${authMode}`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ email: authEmail.trim(), password: authPassword }),
      });
      const result = await response.json() as { detail?: string; access_token?: string; households?: string[]; expires_at?: string };
      if (!response.ok || !result.access_token || !result.households?.length) {
        throw new Error(result.detail ?? "Could not sign in. Check your credentials.");
      }
      try {
        if (result.expires_at) {
          saveAccountSession(window.sessionStorage, {
            apiUrl: apiUrl.replace(/\/$/, ""),
            householdId: result.households[0],
            accessToken: result.access_token,
            expiresAt: result.expires_at,
          });
        }
      } catch {
        notify("warning", "Sign-in won't persist", "This browser blocked tab storage. You can use HomHive now, but refreshing may require signing in again.");
      }
      setHouseholdId(result.households[0]);
      setHistoryLoaded(false);
      setReport(null);
      setHistory([]);
      setToken(result.access_token);
      setAuthPassword("");
      setConfirmPassword("");
      setSettingsOpen(false);
      setStatus("Signed in. Connecting your household…");
      notify("success", "Signed in", "Connecting to your household.");
    } catch (err) {
      const message = err instanceof Error ? err.message : "Authentication failed";
      setAuthError(authMode === "login" && /invalid credentials/i.test(message)
        ? "We couldn't sign you in with those details. Check your password or use another account."
        : authMode === "register" && /account already exists/i.test(message)
        ? "An account may already use this email. Try signing in with your existing password."
        : message);
      notify("error", "Could not sign in", friendlyError(err, message));
    } finally {
      setBusy(false);
    }
  }

  async function signOut() {
    try {
      clearAccountSession(window.sessionStorage);
    } catch {
    }
    try {
      await fetch(`${apiUrl.replace(/\/$/, "")}/auth/logout`, {
        method: "POST", headers: { Authorization: `Bearer ${token}` },
      });
    } finally {
      setToken(""); setHistoryLoaded(false); setHistory([]); setReport(null);
      setNotifications([]); setObservations([]); setPlan(null);
      setSettingsOpen(false);
      setScanJobs([]); setEnrolledRooms([]); setAutonomousTasks([]); setAutonomousAlerts([]);
      setWorkWindow(null); seenAlertIds.current = null; loadedAccountRef.current = "";
      notify("info", "Signed out", "Your session has ended.");
    }
  }

  useEffect(() => {
    const key = token && householdId.trim() ? `${householdId}:${token}` : "";
    if (!key || loadedAccountRef.current === key) return;
    loadedAccountRef.current = key;
    void loadHousehold();
  }, [token, householdId]);

  async function loadHousehold(): Promise<boolean> {
    if (!token || !householdId.trim()) return false;
    const result = await run<Observation[]>("Loading persisted household observations...", () => api.observationHistory());
    if (result !== null) {
      setHistory(result);
      setHistoryLoaded(true);
      // Legacy task discovery is not part of the autonomous consumer workflow.
      try {
        setNotifications(await api.notifications());
        setPresence(await api.presence());
      } catch {
        setNotifications([]);
      }
      await loadAutonomousState();
      return true;
    }
    return false;
  }

  async function loadAutonomousState() {
    if (!token || !householdId.trim()) return;
    const results = await Promise.allSettled([
      api.autonomousTasks(), api.autonomousRooms(), api.autonomousScanJobs(),
      api.autonomousAlerts(), api.workWindow()
    ]);
    if (results[0].status === "fulfilled") setAutonomousTasks(results[0].value);
    if (results[1].status === "fulfilled") setEnrolledRooms(results[1].value);
    if (results[2].status === "fulfilled") {
      setScanJobs(results[2].value);
      setAutonomousAvailable(true);
    } else {
      setAutonomousAvailable(false);
    }
    if (results[3].status === "fulfilled") {
      const fresh = results[3].value;
      if (seenAlertIds.current !== null) {
        const newItems = fresh.filter(item => !item.read_at && !seenAlertIds.current?.has(item.id));
        if (newItems.length) notify("info", newItems[0].title,
          newItems[0].detail + (newItems.length > 1 ? ` (${newItems.length} new updates)` : ""));
      }
      seenAlertIds.current = new Set(fresh.map(item => item.id));
      setAutonomousAlerts(fresh);
    }
    if (results[4].status === "fulfilled") {
      const window = results[4].value;
      setWorkWindow(window);
      if (window) {
        setWindowStart(window.start_time); setWindowEnd(window.end_time);
        setWindowWeekdays(window.weekdays);
      }
    }
    if (results.some(result => result.status === "rejected")) {
      const message = "Some household information is temporarily unavailable. Your previous scans and tasks have not been deleted.";
      setAutonomousFetchError(message);
      if (!autonomousErrorReportedRef.current) notify("error", "Couldn't load all household data", message);
      autonomousErrorReportedRef.current = true;
    } else {
      setAutonomousFetchError("");
      autonomousErrorReportedRef.current = false;
    }
  }

  useEffect(() => {
    if (!token || !householdId) return;
    const interval = setInterval(() => { void loadAutonomousState(); }, 60000);
    return () => clearInterval(interval);
    // Task notifications are durable in PostgreSQL; poll modestly while the app is open.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [api, token, householdId]);

  useEffect(() => {
    if (!token || !historyLoaded || !scanProgress?.mediaId || scanProgress.phase !== "analyzing") return;
    let active = true;
    const started = Date.now();
    let missing = 0;
    let consecutiveErrors = 0;
    const poll = async () => {
      if (!active) return;
      if (Date.now() - started > 6 * 60 * 1000) {
        setScanProgress(current => current?.phase === "analyzing" ? { ...current, phase: "held", percent: null,
          detail: "This review is taking longer than expected. The job remains saved; check its status or return later." } : current);
        return;
      }
      try {
        const jobs = await api.autonomousScanJobs();
        if (!active) return;
        setScanJobs(jobs);
        const job = jobs.find(item => item.media_id === scanProgress.mediaId);
        consecutiveErrors = 0;
        if (!job) {
          missing += 1;
          if (missing >= 3) setScanProgress(current => current?.phase === "analyzing" ? { ...current, phase: "error", percent: null,
            detail: "No scan job was found for this photograph. Check your AI configuration or retry queuing." } : current);
          return;
        }
        if (job.state === "completed") {
          setScanProgress({ phase: "done", percent: 100, mediaId: job.media_id,
            detail: job.review_summary?.approved_count ? "Review complete. See Tasks for the approved suggestions." :
              job.review_summary?.proposed_count ? "Review complete. No task was approved; check the reviewer explanations in Tasks." :
              job.review_summary?.verification === "no_corroborated_evidence" ? "The models could not agree on enough visible evidence. A clearer photo or different angle may help." :
              "Review complete. No task was supported by the available evidence." });
          await loadAutonomousState();
        } else if (job.state === "held_unverified_room") {
          setScanProgress({ phase: "held", percent: null, mediaId: job.media_id,
            detail: "HomHive could not confirm whether this is an existing room. Choose Add as a new space if it is separate, or provide another view." });
        } else if (job.state === "failed") {
          setScanProgress({ phase: "error", percent: null, mediaId: job.media_id,
            detail: job.message || "AI review could not finish. The photo is saved; you can retry this scan." });
        }
      } catch {
        consecutiveErrors += 1;
        if (consecutiveErrors >= 3) setScanProgress(current => current?.phase === "analyzing" ? { ...current, phase: "error", percent: null,
          detail: "Could not reach the scan-status service. Your photograph remains saved." } : current);
      }
    };
    void poll();
    const timer = setInterval(() => { void poll(); }, 12000);
    return () => { active = false; clearInterval(timer); };
  }, [token, householdId, historyLoaded, scanProgress?.mediaId, scanProgress?.phase, api]);

  useEffect(() => {
    if (!scanProgress || !["error", "held"].includes(scanProgress.phase)) return;
    const signature = `${scanProgress.mediaId ?? "new"}:${scanProgress.phase}:${scanProgress.detail}`;
    if (lastScanNoticeRef.current === signature) return;
    lastScanNoticeRef.current = signature;
    notify(scanProgress.phase === "error" ? "error" : "warning",
      scanProgress.phase === "error" ? "Scan needs attention" : "Room confirmation needed", scanProgress.detail);
  }, [scanProgress?.mediaId, scanProgress?.phase, scanProgress?.detail]);

  useEffect(() => {
    if (view !== "tasks" || !showScanStatus) return;
    document.querySelector(".hh-diagnostics")?.scrollIntoView({ behavior: "smooth", block: "center" });
  }, [view, showScanStatus]);

  async function enrollHeldRoom(job: AutonomousScanJob) {
    if (job.state !== "held_unverified_room" || autonomousLoading || busy) return;
    setConfirmation({
      title: "Add this photo as a new space?",
      detail: "Only choose this if the photograph shows a separate physical room. HomHive will review the saved image again using paid AI credits.",
      actionLabel: "Add space and review",
      onConfirm: () => { void performEnrollHeldRoom(job); },
    });
  }

  async function performEnrollHeldRoom(job: AutonomousScanJob) {
    setAutonomousLoading(true);
    try {
      await api.enrollAutonomousRoom(job.media_id);
      setAutonomousNote("New space added. The saved photograph is queued for independent AI review.");
      notify("success", "Space added", "The saved photo has been queued for independent AI review.");
      setScanProgress({ phase: "analyzing", percent: null, mediaId: job.media_id,
        detail: "Reviewing the saved photograph for this newly added space" });
      await loadAutonomousState();
    } catch (error) {
      const message = error instanceof Error ? error.message : "Could not add this space";
      setAutonomousNote(message);
      notify("error", "Could not add space", message);
    } finally {
      setAutonomousLoading(false);
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
      if (!await selectPhoto(selected)) return;
      setDemoOpen(false);
      setStatus(`Selected ${image.title}. Ready for the same live analysis as a personal photo.`);
    } catch (error) {
      const message = error instanceof Error ? error.message : "Sample unavailable";
      setDemoSelectionError(message);
      notify("error", "Sample photo unavailable", message);
    } finally { setDemoSelecting(false); }
  }

  async function upload() {
    if (!file || !token || !historyLoaded || busy) return;
    if (!photoInspection) { notify("error", "Photo not checked", "Select the image again so HomHive can verify it opens correctly."); return; }
    setBusy(true);
    setShowScanStatus(false);
    setStatus("Uploading your photo…");
    setScanProgress({ phase: "uploading", percent: 0, mediaId: null, detail: "Securely saving your photo" });
    try {
      const stored = await api.upload(file, location, (percent) => {
        setScanProgress(current => current?.phase === "uploading" ? { ...current, percent } : current);
      });
      setMedia(stored);
      setScanOpen(false);
      setView("home");
      await loadAutonomousState();
      const jobs = await api.autonomousScanJobs();
      const job = jobs.find(item => item.media_id === stored.id);
      if (!job) {
        setScanProgress({ phase: "error", percent: null, mediaId: stored.id,
          detail: stored.autonomous_enqueue === "disabled" ? "Photo saved, but autonomous scanning is disabled on the server." : "Photo saved, but a scan job was not created. Check your AI configuration and retry." });
        notify("error", "Scan was not queued", stored.autonomous_enqueue === "disabled" ? "The AI scanning service is disabled. Your photo was saved." : "The photo was saved, but no scan job was created. Try again or contact support.");
        return;
      }
      setScanJobs(jobs);
      setScanProgress({ phase: "analyzing", percent: null, mediaId: stored.id,
        detail: "Queued for independent scene and task review. No preset chores or durations will be generated." });
      setStatus("Photo queued for autonomous review");
      notify("success", "Photo uploaded", "The saved image is queued for AI review.");
    } catch (error) {
      const message = friendlyError(error, "Upload failed");
      setStatus(message);
      setScanProgress(current => ({ phase: "error", percent: null, mediaId: current?.mediaId ?? null, detail: message }));
      notify("error", "Upload unsuccessful", message);
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
      const message = friendlyError(error, "Analysis could not be completed");
      setScanProgress({ phase: "error", percent: null, mediaId, detail: message });
      setStatus("Photo saved, but analysis needs another attempt");
      notify("error", "Analysis could not finish", message);
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

  async function acknowledgeAlert(alertId: string) {
    try {
      await api.acknowledgeAutonomousAlert(alertId);
      setAutonomousAlerts(items => items.map(item => item.id === alertId
        ? {...item, read_at: new Date().toISOString()} : item));
    } catch (error) { notify("error", "Could not dismiss update", friendlyError(error, "Please retry")); }
  }

  async function saveWorkWindow() {
    const validation = workWindowError(windowStart, windowEnd, windowWeekdays);
    if (validation) {
      notify("warning", "Check your household schedule", validation);
      return;
    }
    setSavingWindow(true);
    try {
      const window = await api.setWorkWindow({
        timezone: Intl.DateTimeFormat().resolvedOptions().timeZone || "UTC",
        start_time: windowStart, end_time: windowEnd, weekdays: windowWeekdays,
      });
      setWorkWindow(window);
      notify("success", "Preferred time saved", "HomHive can now recommend slots based on your recurring preference. Your calendar is not connected.");
      await loadAutonomousState();
    } catch (error) { notify("error", "Could not save preferred time", friendlyError(error, "Try again")); }
    finally { setSavingWindow(false); }
  }

  async function decideAutonomousTask(taskId: string, decision: "accept" | "decline" | "remind" | "done") {
    const result = await run(`Updating household work…`, () => api.decideAutonomousTask(taskId, decision));
    if (result) await loadAutonomousState();
  }

  async function retryFailedScan(mediaId: string) {
    try {
      await api.retryAutonomousScan(mediaId);
      setScanProgress({ phase: "analyzing", percent: null, mediaId, detail: "Review queued again. Your original photo is retained." });
      notify("success", "Scan queued again", "HomHive will retry the saved photograph.");
      await loadAutonomousState();
    } catch (error) {
      notify("error", "Couldn't retry scan", error instanceof Error ? error.message : "Please try again later.");
    }
  }

  async function retryLatestScan() {
    const mediaId = scanProgress?.mediaId ?? media?.id;
    if (!mediaId) return;
    try {
      await api.retryAutonomousScan(mediaId);
      setScanProgress({ phase: "analyzing", percent: null, mediaId,
        detail: "Scan requeued for independent review." });
      setView("home");
      await loadAutonomousState();
    } catch (error) {
      const message = error instanceof Error ? error.message : "Could not retry this scan";
      setStatus(message);
      notify("error", "Retry unavailable", message);
    }
  }

  async function saveRoomCorrection(roomId: string) {
    const label = roomLabelDraft.trim();
    if (label.length < 2 || label.length > 120) {
      setAutonomousNote("Choose a room name between 2 and 120 characters.");
      notify("warning", "Room name needed", "Choose a room name between 2 and 120 characters.");
      return;
    }
    setAutonomousLoading(true);
    try {
      await api.correctAutonomousRoom(roomId, label);
      setEditingRoomId(null);
      setRoomLabelDraft("");
      setAutonomousNote("Space label corrected by you. Earlier AI review history remains unchanged.");
      notify("success", "Room name updated", "Your correction is saved without changing previous AI results.");
      await loadAutonomousState();
    } catch (error) {
      const message = error instanceof Error ? error.message : "Could not update space label";
      setAutonomousNote(message);
      notify("error", "Room update failed", message);
    } finally {
      setAutonomousLoading(false);
    }
  }

  async function recheckCompletedJob(job: AutonomousScanJob) {
    if (job.state !== "completed" || recheckingMediaId) return;
    setConfirmation({
      title: "Reanalyze this saved photo?",
      detail: "The existing photo will be analyzed again using paid AI providers. Previous scan and task history will be preserved.",
      actionLabel: "Reanalyze using AI credits",
      onConfirm: () => { void performRecheck(job); },
    });
  }

  async function performRecheck(job: AutonomousScanJob) {
    setRecheckingMediaId(job.media_id);
    try {
      await api.recheckAutonomousScan(job.media_id);
      setAutonomousNote("Fresh review queued. Your original photo is retained.");
      notify("success", "AI review queued", "HomHive will reanalyze the saved photograph.");
      setScanProgress({phase: "analyzing", percent: null, mediaId: job.media_id,
        detail: "Re-reviewing the saved photograph with independent AI models"});
      await loadAutonomousState();
    } catch (error) {
      const message = error instanceof Error ? error.message : "Could not queue the re-review";
      setAutonomousNote(message);
      notify("error", "Could not restart review", message);
    } finally {
      setRecheckingMediaId(null);
    }
  }

  async function refreshAutonomousTasks() {
    await run("Refreshing autonomous state...", loadAutonomousState);
  }

  async function autonomousScan() {
    if (!media?.id || !roomReference.trim()) {
      setAutonomousNote("Upload a photograph and enter a reference media ID. Use this photograph's ID to enroll a new physical room.");
      notify("warning", "Reference photo required", "Select a photograph and room reference first.");
      return;
    }
    const result = await run<AutonomousScanResult>("Independently reviewing and tracking household work...", () =>
      api.autonomousScan(media.id, roomReference.trim()));
    if (result) {
      setAutonomousNote(result.status === "held_unverified_room"
        ? "Room continuity could not be verified. No changes saved."
        : `Saved: ${result.created.length} created, ${result.existing.length} existing, ${Object.values(result.completed).filter(v => v === "completed").length} completed.`);
      await loadAutonomousState();
    }
  }

  async function refresh() {
    await loadHousehold();
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
  const suggestedTasks = autonomousAvailable ? [] : taskEntries.filter(({task}) => !task.metadata?.accepted_at && task.status === "pending");
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
  const scheduleValidation = workWindowError(windowStart, windowEnd, windowWeekdays);
  const scheduleModified = !workWindow || workWindow.start_time !== windowStart || workWindow.end_time !== windowEnd ||
    [...workWindow.weekdays].sort().join(",") !== [...windowWeekdays].sort().join(",");
  const scheduleTimeOptions = [...new Set([...WORK_TIME_OPTIONS, windowStart, windowEnd])].sort();
  const scheduleZone = Intl.DateTimeFormat().resolvedOptions().timeZone || "UTC";
  const scheduleSummary = workWindow
    ? `${readableWorkDays(workWindow.weekdays)} · ${readableWorkTime(workWindow.start_time)} – ${readableWorkTime(workWindow.end_time)}`
    : "Not set up yet";
  const navItems = [
    { id: "home", label: "Home", icon: "⌂" },
    { id: "spaces", label: "Spaces", icon: "▦" },
    { id: "tasks", label: "Tasks", icon: "✓" },
    { id: "schedule", label: "Schedule", icon: "◷" },
    { id: "activity", label: "Activity", icon: "☷" },
  ] as const;

  return (
    <main className="hh-app" id="main-content">
      <aside className="hh-toast-stack" aria-label="App notifications">
        {notices.map(notice => <div key={notice.id} className={`hh-toast hh-toast-${notice.kind}`} role={notice.kind === "error" ? "alert" : "status"}>
          <span aria-hidden="true" className="hh-toast-icon">{notice.kind === "success" ? "✓" : notice.kind === "error" ? "!" : notice.kind === "warning" ? "!" : "i"}</span>
          <div><strong>{notice.title}</strong>{notice.detail && <p>{notice.detail}</p>}</div>
          <button type="button" aria-label={`Dismiss ${notice.title}`} onClick={() => setNotices(items => items.filter(item => item.id !== notice.id))}>×</button>
        </div>)}
      </aside>
      {confirmation && <div className="hh-modal-backdrop hh-confirm-backdrop" onClick={() => setConfirmation(null)}>
        <section role="alertdialog" aria-modal="true" aria-labelledby="hh-confirm-title" aria-describedby="hh-confirm-detail" className="hh-modal hh-confirm-dialog" onClick={event => event.stopPropagation()}>
          <h2 id="hh-confirm-title">{confirmation.title}</h2>
          <p id="hh-confirm-detail">{confirmation.detail}</p>
          <div className="hh-task-actions"><button type="button" className="secondary" autoFocus onClick={() => setConfirmation(null)}>Cancel</button><button type="button" onClick={() => {const callback = confirmation.onConfirm;setConfirmation(null); callback();}}>{confirmation.actionLabel}</button></div>
        </section>
      </div>}
      <a className="hh-skip-link" href="#household-content">Skip to household content</a>
      <header className="hh-header">
        <div className="hh-brand"><span className="hh-mark" aria-hidden="true">⌂</span><span>HomHive<small>Household intelligence</small></span></div>
        <nav className="hh-nav" aria-label="Main navigation">
          {navItems.map((item) => <button key={item.id} className={view === item.id ? "hh-nav-active" : "hh-nav-button"} aria-current={view === item.id ? "page" : undefined} onClick={() => setView(item.id)}><span aria-hidden="true">{item.icon}</span>{item.label}</button>)}
        </nav>
        <div className="hh-toolbar">{isConnected && <span className="hh-muted" aria-label="Connected household">Connected · My household</span>}<button className="hh-scan" onClick={() => setScanOpen(true)}>＋ Scan</button><button className="hh-icon-button" aria-label="Open settings" onClick={() => setSettingsOpen(true)}>⚙</button></div>
      </header>
      {isConnected && autonomousFetchError && <div className="hh-scan-message hh-scan-problem" role="status"><p>{autonomousFetchError}</p><button className="secondary" onClick={() => void loadAutonomousState()}>Try again</button></div>}
      <div id="household-content" className="hh-live" role="status" aria-live="polite"><span className={busy ? "pulse" : "dot"}/>{status}</div>

      {scanProgress && <section className={`hh-analysis-card hh-analysis-${scanProgress.phase}`} role="status" aria-live="polite" aria-label="Photo analysis progress">
        <div className="hh-panel-head"><div><p className="hh-kicker">Household scan</p><h2>{scanProgress.phase === "uploading" ? "Saving your photo" : scanProgress.phase === "analyzing" ? "Analyzing your space" : scanProgress.phase === "done" ? "Review complete" : scanProgress.phase === "held" ? "Room identification needed" : "Analysis needs attention"}</h2></div>{scanProgress.phase === "done" && <button className="hh-icon-button" aria-label="Dismiss completed scan" onClick={() => setScanProgress(null)}>✕</button>}</div>
        <p>{scanProgress.detail}</p>
        <div className={`hh-analysis-track ${scanProgress.percent === null && (scanProgress.phase === "uploading" || scanProgress.phase === "analyzing") ? "hh-analysis-indeterminate" : ""}`} role="progressbar" aria-label={scanProgress.phase === "uploading" ? "Photo upload" : "Photo analysis"} aria-valuemin={0} aria-valuemax={100} aria-valuenow={scanProgress.percent === null ? undefined : scanProgress.percent}>
          <div className="hh-analysis-fill" style={scanProgress.percent === null ? undefined : { width: `${scanProgress.percent}%` }}/>
        </div>
        <div className="hh-analysis-footer"><small>{scanProgress.phase === "uploading" ? `${scanProgress.percent ?? 0}% uploaded` : scanProgress.phase === "analyzing" ? "Analysis in progress · completion time varies" : scanProgress.phase === "done" ? "Review complete" : scanProgress.phase === "held" ? "Room match needs your decision" : "Your original photo is retained"}</small>{scanProgress.phase === "held" && scanJobs.filter(job => job.media_id === scanProgress.mediaId && job.state === "held_unverified_room").map(job => <button key={job.id} disabled={autonomousLoading || busy} onClick={() => void enrollHeldRoom(job)}>{autonomousLoading ? "Adding space…" : "Add as a new space"}</button>)}{(scanProgress.phase === "error" || scanProgress.phase === "held") && scanProgress.mediaId && <button className="secondary" disabled={busy} onClick={() => { setShowScanStatus(true); setView("tasks"); void loadAutonomousState(); }}>View scan status</button>}</div>
      </section>}

      {!isConnected && <section className="hh-notice" role="status"><strong>Connect your household</strong><span>Sign in to load your authorized household.</span><button onClick={() => setSettingsOpen(true)}>Open Settings</button></section>}

      {view === "home" && <section className="hh-view">
        <div className="hh-view-title"><div><p className="hh-kicker">HomHive / Home intelligence</p><h1>Good to be home.</h1><p>Your home, understood. The right actions, at the right time.</p></div><button className="secondary" disabled={busy || !token} onClick={loadHousehold}>↻ Refresh</button></div>
        {isConnected && <div className="hh-stats">
          <button onClick={() => setView("spaces")}><span>Spaces</span><strong>{enrolledRooms.length}</strong><small>Recognized spaces</small></button>
          <button onClick={() => setView("tasks")}><span>Suggested work</span><strong>{autonomousTasks.filter(task => ["pending", "accepted", "in_progress", "proposed"].includes(task.status)).length}</strong><small>Active household suggestions</small></button>
          <button onClick={() => { setShowScanStatus(true); setView("tasks"); }}><span>Updates</span><strong>{autonomousAlerts.filter(alert => !alert.read_at).length}</strong><small>New task and progress alerts</small></button>
        </div>}
        {isConnected && <section className="hh-panel hh-home-schedule" aria-label="Your preferred household schedule">
          <div className="hh-panel-head"><div><p className="hh-kicker">YOUR ROUTINE</p><h2>When should HomHive suggest work?</h2></div><button className="hh-schedule-link" onClick={() => setView("schedule")}>{workWindow ? "Change my schedule →" : "Set my schedule →"}</button></div>
          <p className="hh-schedule-summary">{scheduleSummary}</p>
          <p className="hh-muted">{workWindow ? "Saved for future recommendations. HomHive uses this when a researched task duration fits." : "Choose your usual household-work days and time. We'll use your preference when recommending new tasks."}</p>
          <small className="hh-schedule-disclaimer">Not a calendar connection; HomHive won't claim you're free or automatically book an event.</small>
        </section>}
        {isConnected && autonomousTasks.some(task => ["proposed", "pending", "accepted", "in_progress"].includes(task.status) && (!task.remind_at || Date.parse(task.remind_at) <= Date.now())) && <section className="hh-panel hh-home-priority"><div className="hh-panel-head"><div><p className="hh-kicker">NEXT UP</p><h2>{[...autonomousTasks].filter(task => ["proposed", "pending", "accepted", "in_progress"].includes(task.status) && (!task.remind_at || Date.parse(task.remind_at) <= Date.now())).sort((a,b) => b.created_at.localeCompare(a.created_at))[0].title}</h2></div><button className="hh-link" onClick={() => setView("tasks")}>View suggestion →</button></div><p className="hh-muted">{[...autonomousTasks].filter(task => ["proposed", "pending", "accepted", "in_progress"].includes(task.status) && (!task.remind_at || Date.parse(task.remind_at) <= Date.now())).sort((a,b) => b.created_at.localeCompare(a.created_at))[0].evidence_summary || "Independently reviewed household work"}</p></section>}
        <div className="hh-home-grid">
          <section className="hh-panel"><div className="hh-panel-head"><h2>Your spaces</h2><button className="hh-link" onClick={() => setView("spaces")}>View spaces →</button></div>
            {enrolledRooms.length === 0 ? <p className="hh-empty">Your spaces will appear after your first verified scan.</p> :
              <div className="hh-compact-list">{enrolledRooms.slice(0, 4).map(room => { const task = autonomousTasks.find(t => t.room_id === room.room_id); return <button key={room.room_id} className="hh-room-row" onClick={() => setView("spaces")}><span className="hh-room-symbol" aria-hidden="true">⌂</span><span><strong>{room.room_category ? capitalizeFirst(display(room.room_category)) : task?.room_category ? capitalizeFirst(display(task.room_category)) : "Recognized space"}</strong><small>{autonomousTasks.filter(t => t.room_id === room.room_id && ["pending", "proposed", "accepted", "in_progress"].includes(t.status)).length} active suggestions</small></span></button>; })}</div>}
          </section>
          <section className="hh-panel"><div className="hh-panel-head"><h2>Household automation</h2><button className="hh-link" onClick={() => setView("tasks")}>All tasks →</button></div>
            {autonomousTasks.filter(t => ["pending", "accepted", "in_progress", "proposed"].includes(t.status)).length === 0 ? <p className="hh-empty">No active suggestions yet. Scan a space to begin.</p> : <><p className="hh-muted">{autonomousTasks.filter(t => ["pending", "accepted", "in_progress", "proposed"].includes(t.status)).length} current suggestions · {autonomousTasks.filter(t => t.progress?.percent != null && t.status !== "completed").length} with observed progress.</p><button className="hh-inline-action" onClick={() => setView("tasks")}>View suggestions and updates →</button></>}
          </section>
        </div>
      </section>}

      {view === "schedule" && <section className="hh-view" aria-label="Household work schedule">
        <div className="hh-view-title"><div><p className="hh-kicker">HOMHIVE / YOUR ROUTINE</p><h1>Your household schedule</h1><p>Tell HomHive when you <em>prefer</em> to tackle household work. New suggestions can be matched to the time you set.</p></div></div>
        <section className="hh-panel hh-schedule-editor" aria-label="Preferred household work days and times">
          <div className="hh-panel-head"><div><p className="hh-kicker">RECURRING PREFERENCE</p><h2>Days and time</h2></div><span className={`hh-schedule-state ${workWindow && !scheduleModified ? "is-saved" : ""}`}>{scheduleModified && workWindow ? "Unsaved changes" : workWindow ? "✓ Saved preference" : "Not set"}</span></div>
          <p className="hh-muted">Start with a shortcut, or choose individual days and times below. This is a repeating preference, not a booked calendar appointment.</p>
          <fieldset className="hh-schedule-fieldset"><legend>Which days work for you?</legend>
            <div className="hh-schedule-shortcuts" aria-label="Quick day selection">
              {[{label:"Every day",days:[0,1,2,3,4,5,6]},{label:"Weekdays",days:[0,1,2,3,4]},{label:"Weekends",days:[5,6]}].map(preset => <button key={preset.label} type="button" className="secondary" onClick={() => setWindowWeekdays(preset.days)}>{preset.label}</button>)}
            </div>
            <div className="hh-schedule-days">{WORK_DAYS.map((day,index) => <button type="button" key={day} aria-pressed={windowWeekdays.includes(index)} className={windowWeekdays.includes(index) ? "hh-day-selected" : ""} onClick={() => setWindowWeekdays(old => old.includes(index) ? old.filter(value => value !== index) : [...old,index].sort())}>{day}</button>)}</div>
            <p className="hh-schedule-selection">Selected: {readableWorkDays(windowWeekdays)}</p>
          </fieldset>
          <fieldset className="hh-schedule-fieldset"><legend>What time of day do you prefer?</legend>
            <div className="hh-schedule-shortcuts" aria-label="Quick time selection">
              {[{label:"Morning",start:"09:00",end:"12:00"},{label:"Afternoon",start:"13:00",end:"16:00"},{label:"Evening",start:"18:00",end:"21:00"}].map(preset => <button type="button" className="secondary" key={preset.label} onClick={() => {setWindowStart(preset.start);setWindowEnd(preset.end);}}>{preset.label}</button>)}
            </div>
            <div className="hh-schedule-times"><label htmlFor="hh-window-from">From <select id="hh-window-from" value={windowStart} onChange={event => setWindowStart(event.target.value)}>{scheduleTimeOptions.map(value => <option value={value} key={value}>{readableWorkTime(value)}</option>)}</select></label>
              <span aria-hidden="true" className="hh-schedule-to">to</span><label htmlFor="hh-window-until">Until <select id="hh-window-until" value={windowEnd} onChange={event => setWindowEnd(event.target.value)}>{scheduleTimeOptions.map(value => <option value={value} key={value}>{readableWorkTime(value)}</option>)}</select></label>
            </div>
            <p className="hh-schedule-selection">Time zone: {scheduleZone} · Single-day windows only</p>
          </fieldset>
          {scheduleValidation && <p className="hh-schedule-error" role="alert">{scheduleValidation}</p>}
          {scheduleModified && !scheduleValidation && <p className="hh-schedule-unsaved" role="status">{workWindow ? "You have unsaved schedule changes." : "Your schedule isn't saved yet."}</p>}
          <div className="hh-schedule-save"><button type="button" disabled={!isConnected || savingWindow || Boolean(scheduleValidation) || !scheduleModified} onClick={() => void saveWorkWindow()}>{savingWindow ? "Saving…" : "Save my schedule"}</button>
            {workWindow && scheduleModified && <button type="button" className="secondary" onClick={() => {setWindowStart(workWindow.start_time);setWindowEnd(workWindow.end_time);setWindowWeekdays([...workWindow.weekdays]);}}>Discard changes</button>}
          </div>
          {!isConnected && <p className="hh-muted">Sign in to save your household preference.</p>}
          {workWindow && <p className="hh-schedule-saved" role="status"><strong>Saved:</strong> {scheduleSummary} ({workWindow.timezone})</p>}
        </section>
        <section className="hh-panel hh-schedule-explainer"><h2>What happens next?</h2><p>When HomHive discovers an evidence-supported task, it can research how long the task usually takes, then suggest a time within your chosen work window. You can still do the task whenever you want.</p><p><strong>No calendar access or automatic booking.</strong> HomHive uses your stated preference, not your actual availability. Existing tasks may not receive a newly calculated time until they are reviewed again.</p><button className="hh-link" onClick={() => setView("tasks")}>View suggested tasks →</button></section>
      </section>}

      {view === "spaces" && <section className="hh-view">
        <div className="hh-view-title"><div><p className="hh-kicker">Your household</p><h1>Spaces</h1><p>Rooms anchored to independently reviewed photographs.</p></div><button className="secondary" onClick={loadAutonomousState}>↻ Refresh</button></div>
        {enrolledRooms.length === 0 ? <div className="hh-panel hh-empty">No verified spaces yet. Scan a photograph and HomHive will establish the first space automatically once its room category is corroborated.</div> :
          <div className="hh-home-grid">{enrolledRooms.map(room => {
            const tasks = autonomousTasks.filter(task => task.room_id === room.room_id);
            const label = room.room_category || tasks.find(t => t.room_category)?.room_category;
            return <section className="hh-panel hh-space-card" key={room.room_id}>
              <p className="hh-kicker">SPACE</p>
              <h2>{label ? capitalizeFirst(display(label)) : "Recognized space"}</h2>
              <p className="hh-muted">{room.room_category_source === "user_confirmed" ? "Room name confirmed by you" : "Room type suggested by independent AI review"}</p>
              {editingRoomId === room.room_id ? <div className="hh-room-correction">
                <label>Correct room name<input autoFocus maxLength={120} value={roomLabelDraft}
                  onChange={event => setRoomLabelDraft(event.target.value)} placeholder="e.g. Walk-in closet" /></label>
                <div className="hh-task-actions"><button disabled={autonomousLoading} onClick={() => void saveRoomCorrection(room.room_id)}>Save</button><button className="secondary" onClick={() => setEditingRoomId(null)}>Cancel</button></div>
              </div> : <button className="hh-link" onClick={() => {setEditingRoomId(room.room_id); setRoomLabelDraft(label || "");}}>Correct room name</button>}
              <p className="hh-muted">{tasks.length} independently reviewed task{tasks.length === 1 ? "" : "s"} recorded</p>
              {tasks.length ? <div className="hh-compact-list">{tasks.filter(t => !["dismissed", "completed"].includes(t.status)).slice(0, 3).map(task => <div className="hh-history-entry" key={task.id}><strong>{task.title}</strong><small>Created {new Date(task.created_at).toLocaleString()}</small></div>)}</div> : <p className="hh-empty">No evidence-supported tasks recorded for this space.</p>}
              <button className="hh-link" onClick={() => setView("tasks")}>View household work →</button>
            </section>;
          })}</div>}
      </section>}

      {view === "tasks" && <section className="hh-view" aria-label="Household work">
        <div className="hh-view-title"><div><p className="hh-kicker">YOUR HOUSEHOLD</p><h1>Things worth doing</h1><p>Independent reviews turn household observations into useful suggestions.</p></div><button className="secondary" disabled={busy} onClick={refreshAutonomousTasks}>↻ Check updates</button></div>
        {scanJobs.some(job => ["pending", "processing", "queued", "retrying"].includes(job.state)) && <div className="hh-scan-message" role="status"><span className="pulse"/> Your latest space is being reviewed. Suggestions will appear once verified.</div>}
        {scanJobs.some(job => job.state === "held_unverified_room") && <div className="hh-scan-message"><strong>Some photographs need a room decision.</strong><p>HomHive couldn't verify which physical room they show. If a photograph is of a new space, you can add that specific space in Recent scan status below.</p><button className="secondary" onClick={() => setShowScanStatus(true)}>Review room matches</button></div>}
        {autonomousNote && <p className="hh-muted" role="status">{autonomousNote}</p>}
        {autonomousAlerts.some(alert => !alert.read_at) && <section className="hh-panel" aria-label="Household automation updates" style={{marginBottom:20}}>
          <h2>HomHive has suggestions for you</h2>
          <p className="hh-muted">New evidence-backed tasks and photo progress updates. No acceptance required for ordinary work.</p>
          {autonomousAlerts.filter(alert => !alert.read_at).slice(0,5).map(alert => <div key={alert.id} className="hh-history-entry" style={{marginTop:12}}>
            <strong>{alert.title}</strong><p>{alert.detail}</p><small>{new Date(alert.created_at).toLocaleString()}</small>
            <div className="hh-task-actions"><button className="secondary" onClick={() => void acknowledgeAlert(alert.id)}>Got it</button></div>
          </div>)}
        </section>}
        {autonomousTasks.filter(task => !["dismissed", "completed"].includes(task.status) && (!task.remind_at || Date.parse(task.remind_at) <= Date.now())).length === 0 ? <section className="hh-panel hh-friendly-empty"><h2>Nothing needs your attention yet</h2><p>When a scan uncovers independently supported work, you'll see it here. A scan can correctly result in no tasks.</p><button className="secondary" onClick={() => setScanOpen(true)}>Scan a space</button></section> :
          <div className="hh-task-grid">{[...autonomousTasks].filter(task => !["dismissed", "completed"].includes(task.status) && (!task.remind_at || Date.parse(task.remind_at) <= Date.now())).sort((a,b) => b.created_at.localeCompare(a.created_at)).map(task => <article className="hh-panel hh-intelligent-task" key={task.id}>
            <div className="hh-task-top"><span className="hh-task-space">{capitalizeFirst((enrolledRooms.find(room => room.room_id === task.room_id)?.room_category || task.room_category || "Your household").replaceAll("_", " "))}</span><span className="hh-task-date">Created {new Date(task.created_at).toLocaleString()}</span></div>
            <h2>{task.title}</h2><p className="hh-task-description">{task.evidence_summary || task.action}</p>
            <div className="hh-task-metadata"><span>{task.effort_min == null ? "Duration unknown" : `${task.effort_min}${task.effort_max != null && task.effort_max !== task.effort_min ? `–${task.effort_max}` : ""} min · researched estimate`}</span><span>{task.status === "accepted" ? "Accepted" : task.status === "in_progress" ? "In progress · upload another photo to check" : task.status === "proposed" ? "Your approval needed for this action" : "Suggested for you"}</span></div>
            {task.recommended_at && <p className="hh-muted"><strong>Suggested time:</strong> {new Date(task.recommended_at).toLocaleString([], {weekday:"short", hour:"numeric", minute:"2-digit"})} · Based on your preferred work window, not calendar availability.</p>}
            {!task.recommended_at && task.effort_min != null && <p className="hh-muted">This takes roughly {task.effort_min}{task.effort_max != null && task.effort_max !== task.effort_min ? `–${task.effort_max}` : ""} minutes. {workWindow ? "Your saved schedule can guide future suggestions; existing work may not be rescheduled automatically." : <button className="hh-inline-action" onClick={() => setView("schedule")}>Choose preferred work time →</button>}</p>}
            {task.progress && <div role="status" style={{padding:".6rem 0"}}>
              <strong>{task.progress.estimated ? "About " : ""}{task.progress.percent}% complete</strong>
              <div role="progressbar" aria-label={`Progress on ${task.title}`} aria-valuenow={task.progress.percent} aria-valuemin={0} aria-valuemax={100} style={{height:10, borderRadius:8, background:"#e2e9e3", overflow:"hidden", marginTop:8}}>
                <div style={{width:`${task.progress.percent}%`, height:"100%", background:"#1d6648"}} />
              </div><p className="hh-muted">{task.progress.explanation}</p>
              {task.progress.next_step && <p><strong>What remains:</strong> {task.progress.next_step}</p>}
              <small>Estimated from the latest reviewed photograph · {new Date(task.progress.reviewed_at).toLocaleString()}</small>
            </div>}
            <div className="hh-task-actions">{task.status === "proposed" && <button disabled={busy} onClick={() => decideAutonomousTask(task.id,"accept")}>Approve this action</button>}{["pending", "accepted", "in_progress"].includes(task.status) && <button disabled={busy} onClick={() => decideAutonomousTask(task.id,"done")}>I finished · verify later</button>}{["pending", "proposed"].includes(task.status) && <button className="secondary" disabled={busy} onClick={() => decideAutonomousTask(task.id,"remind")}>Snooze 30 min</button>}{["pending", "proposed", "accepted", "in_progress"].includes(task.status) && <button className="hh-text-danger" disabled={busy} onClick={() => decideAutonomousTask(task.id,"decline")}>Dismiss</button>}</div>
            <details><summary>Why HomHive suggested this</summary><p>{task.action}</p><p>Outcome to verify: {task.criteria}</p><p>Rescan this same space to update progress automatically. No acceptance is necessary for ordinary suggestions.</p>{task.estimate_rationale && <p><strong>Time estimate:</strong> {task.estimate_rationale}</p>}{task.estimate_sources?.length ? <p><strong>Sources:</strong> {task.estimate_sources.map((url,i) => <span key={url}><a href={url} target="_blank" rel="noopener noreferrer">Source {i+1}</a>{i+1 < (task.estimate_sources?.length ?? 0) ? " · " : ""}</span>)}</p> : null}<small>Updated {new Date(task.updated_at).toLocaleString()}</small></details>
          </article>)}</div>}
        {autonomousTasks.some(task => task.status === "completed") && <details className="hh-diagnostics">
          <summary>Verified completed work ({autonomousTasks.filter(task => task.status === "completed").length})</summary>
          {autonomousTasks.filter(task => task.status === "completed").slice(-15).reverse().map(task => <article className="hh-scan-review" key={task.id}>
            <strong>{task.title}</strong><p>Completed after independent comparison with a newer photograph from the same space.</p>
            {task.progress && <p>{task.progress.explanation}</p>}
            <small>Verified update {new Date(task.updated_at).toLocaleString()}</small>
          </article>)}
        </details>}
        <details className="hh-diagnostics" open={showScanStatus || undefined} onToggle={event => { if (!event.currentTarget.open) setShowScanStatus(false); }}>
          <summary>Recent scan status</summary>
          {!scanJobs.length ? <p>No scans recorded yet. Your photograph may have saved without creating a job.</p> :
            <div className="hh-review-list">{scanJobs.slice(0, 8).map(job => {
              const review = job.review_summary;
              return <article className="hh-scan-review" key={job.id}>
                <div className="hh-review-head"><strong>{job.state.replaceAll("_", " ")}</strong>
                  <small>{job.updated_at ? new Date(job.updated_at).toLocaleString() : ""}</small></div>
                {job.message && <p>{job.message}</p>}
                {job.state === "held_unverified_room" && <div className="hh-scan-message"><p>HomHive couldn't verify a unique existing space for this photograph. If it shows a separate physical room, confirm it as a new space. The saved image will be reviewed again using AI credits.</p><button className="secondary" disabled={autonomousLoading || busy} onClick={() => void enrollHeldRoom(job)}>{autonomousLoading ? "Adding space…" : "Add this photo as a new space"}</button></div>}
                {job.state === "failed" && <div className="hh-scan-message hh-scan-problem"><p>{job.message || "The AI review couldn't finish. Your uploaded photo is safe."} Try again if the issue was temporary, or choose a clearer photograph if the image itself is difficult to interpret.</p><button className="secondary" disabled={busy} onClick={() => void retryFailedScan(job.media_id)}>Retry saved photo</button></div>}
                {review ? <>
                  {job.state !== "completed" && <p>This is the previous completed review; a new review is in progress.</p>}
                  <p><strong>Room identified:</strong> {review.room_category || "Not established"}</p>
                  <p><strong>Proposed:</strong> {review.proposed_count ?? 0} · <strong>Approved:</strong> {review.approved_count ?? 0} · <strong>New tasks:</strong> {review.created_count ?? 0}</p>
                  {review.verification === "no_corroborated_evidence" ?
                    <p>The AI models could not agree on enough visible evidence to suggest work. Try a clearer, well-lit photo showing more of the space; this is an evidence-confidence issue, not proof that the room is tidy.</p> :
                    review.proposed_count === 0 ? <p>The planner proposed no task from the accepted evidence. This does not mean the room has been cleaned or checked by a person.</p> : null}
                  {(review.evidence?.length ?? 0) > 0 && <details><summary>What the models agreed was visible</summary>
                    <ul>{review.evidence?.map((fact, index) => <li key={index}>{fact}</li>)}</ul></details>}
                  {(review.proposal_reviews?.length ?? 0) > 0 && <details><summary>Suggested work and independent decisions</summary>
                    <ul>{review.proposal_reviews?.map((item, index) => <li key={index}>
                      <strong>{item.title}</strong> · {item.decision}
                      {item.reviewer_explanation && <p>{item.reviewer_explanation}</p>}
                      {item.reason && <small>{item.reason.replaceAll("_", " ")}</small>}
                    </li>)}</ul></details>}
                </> : job.state === "completed" ? <p>This older scan finished before detailed AI decisions were recorded. Its original reviewer reasoning cannot be recovered.</p> : null}
                {job.state === "completed" && <button className="secondary" disabled={busy || Boolean(recheckingMediaId)} onClick={() => void recheckCompletedJob(job)}>
                  Reanalyze saved photo (uses AI credits)
                </button>}
              </article>;
            })}</div>}
          {scanProgress?.mediaId && ["error", "held"].includes(scanProgress.phase) && <button className="secondary" disabled={busy} onClick={retryLatestScan}>Retry scan</button>}
        </details>
      </section>}

      {view === "activity" && <section className="hh-view"><div className="hh-view-title"><div><p className="hh-kicker">Timeline</p><h1>Activity</h1><p>Saved observation history and review records. Earlier entries may come from the legacy analysis pipeline.</p></div><button className="secondary" disabled={busy || !token} onClick={loadHousehold}>↻ Refresh</button></div>
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
              <input type="file" accept="image/jpeg,image/png,image/webp" capture="environment" aria-label="Upload a household photo" style={{position:"absolute",width:"1px",height:"1px",opacity:0,overflow:"hidden"}} onChange={e => {void selectPhoto(e.target.files?.[0] ?? null); e.target.value = "";}} />
            </label>
            {photoPreviewUrl && <img className="hh-photo-preview" src={photoPreviewUrl} alt="Preview of the household photograph selected for review" />}
            {file && <p className="hh-selected-photo" role="status">Selected: {file.name} · {(file.size / 1024 / 1024).toFixed(1)} MB</p>}
            {photoInspection && <p className="hh-muted">Image: {photoInspection.width} × {photoInspection.height} pixels. {photoInspection.warnings.length ? "You can still upload, but another photo may improve results." : "Ready for live AI analysis."}</p>}
            {photoInspection && photoInspection.warnings.length > 0 && <div className="hh-photo-warning" role="status"><strong>Photo quality advisory</strong><ul>{photoInspection.warnings.map(warning => <li key={warning}>{warning}</li>)}</ul></div>}
            <div className="hh-task-actions"><button disabled={busy || !file || !isConnected} onClick={upload}>{busy ? "Working…" : "Upload and analyze"}</button>{media?.processing === "retry_required" && <button className="secondary" disabled={busy || !isConnected} onClick={analyze}>Retry analysis</button>}</div>
            {!file && <p className="hh-muted" role="status">Select a photo from your device or browse the demo library to enable analysis.</p>}
            {observations.length > 0 && <div className="hh-compact-list"><h3>Observations</h3>{observations.map(item => <div className="hh-history-entry" key={item.id}><strong>{conditionSummary(item)}</strong><p>{observationEvidence(item)}</p><small>{needsReview(item) ? "Unverified" : evidenceStatus(item)}</small>{needsReview(item) && <button disabled={busy} onClick={() => confirm(item)}>Confirm observation</button>}</div>)}</div>}
            <p className="hh-muted">Independently approved household tasks are suggested automatically. Approval is only required for safety-sensitive actions.</p>
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
          <section className="hh-settings-section" aria-label="Household connection"><h3>Household connection</h3><p className="hh-muted">{isConnected ? "Your household is loaded. Scans and saved work are available." : token ? "Your household is connecting automatically. You can retry if needed." : "Sign in or create an account to connect your private household."}</p><button type="button" disabled={Boolean(householdDisabledReason)} onClick={async () => {if (await loadHousehold()) setSettingsOpen(false);}}>{busy ? "Connecting…" : isConnected ? "Household connected" : "Load household"}</button>{householdDisabledReason && <p role="status" className="hh-auth-reason">{householdDisabledReason}</p>}</section>
          <section className="hh-settings-section" aria-label="Household schedule"><h3>Your household schedule</h3><p className="hh-muted">{scheduleSummary}. Manage your days and preferred times in the Schedule tab.</p><button type="button" className="secondary" onClick={() => {setSettingsOpen(false);setView("schedule");}}>Open Schedule</button></section>
          <details className="hh-settings-details"><summary>Presence (optional)</summary><p className="hh-muted">Share whether you are home. This is manual and expires after one hour.</p><p className="hh-muted">Current: {presence?.state ?? "UNKNOWN"}</p><div className="hh-task-actions"><button className="secondary" disabled={!isConnected || busy} onClick={() => changePresence("HOME")}>I'm home</button><button className="secondary" disabled={!isConnected || busy} onClick={() => changePresence("AWAY")}>I'm away</button><button className="secondary" disabled={!isConnected || busy} onClick={() => changePresence("UNKNOWN")}>Stop sharing</button></div>{(!isConnected || busy) && <p className="hh-auth-reason">{!isConnected ? "Load your household before sharing presence." : "Please wait for the current request."}</p>}</details>
          <details className="hh-settings-details"><summary>Connection diagnostics</summary><label>API URL<input value={apiUrl} onChange={e => setApiUrl(e.target.value)}/></label><p className="hh-muted">Your session remains available when refreshing this tab until it expires, you close the tab, or you sign out. Shared devices should always use Sign out.</p>{token && <p className="hh-muted">Technical household ID (for troubleshooting): <code style={{overflowWrap:"anywhere"}}>{householdId}</code></p>}</details>
        </section></div>}
    </main>
  );
}
