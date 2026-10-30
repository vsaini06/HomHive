"use client";



import { useEffect, useMemo, useRef, useState } from "react";

import { inspectHouseholdPhoto, type PhotoInspection } from "../lib/photo-check";

import { clearAccountSession, readAccountSession, saveAccountSession } from "../lib/account-session";

import { WORK_DAYS, readableWorkDays, readableWorkTime, workWindowError } from "../lib/work-schedule";

import { TimeWheelField } from "../lib/time-wheel";
import { currentTimeZone, isValidTimeZone, quietHoursActiveAt, timeInZone } from "../lib/quiet-hours";

import { HomHiveSelect } from "../lib/hh-select";

import {preloadGoogleCalendar, requestGoogleCalendarAccess, type GoogleCalendarSession} from "../lib/google-calendar";

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

  AutonomousObject,

  AutonomousScanResult,

  AutonomousAlert,

  WorkWindow,

  HouseholdPulse,

  TaskTimeline,

  CoordinationPlan,

  NemotronAdvice,

  type HouseholdResearchPurpose,

  type HouseholdResearchResult,

} from "../lib/api";





function readableResearchExcerpt(raw: string): string {

  return raw

    .replace(/\[([^\]]+)\]\(https?:\/\/[^)]+\)/g, "$1")

    .replace(/#{1,6}\s+/g, "")

    .replace(/\*\*|__/g, "")

    .replace(/\s+/g, " ")

    .trim();

}



function InterfaceIcon({name, size = 18}: {name: "home" | "spaces" | "objects" | "tasks" | "schedule" | "automations" | "activity" | "more" | "scan" | "settings" | "arrow"; size?: number}) {
  return <svg width={size} height={size} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true" focusable="false">
    {name === "home" && <><path d="m3 10 9-7 9 7v10a1 1 0 0 1-1 1H4a1 1 0 0 1-1-1z"/><path d="M9 21v-7h6v7"/></>}
    {name === "spaces" && <><rect x="3" y="3" width="8" height="8" rx="1.5"/><rect x="13" y="3" width="8" height="8" rx="1.5"/><rect x="3" y="13" width="8" height="8" rx="1.5"/><rect x="13" y="13" width="8" height="8" rx="1.5"/></>}
    {name === "objects" && <><path d="m12 2 9 5-9 5-9-5 9-5Z"/><path d="m3 7 9 5 9-5v10l-9 5-9-5V7Z"/><path d="M12 12v10"/></>}
    {name === "tasks" && <><rect x="4" y="4" width="16" height="16" rx="3"/><path d="m8 12 3 3 5-6"/></>}
    {name === "schedule" && <><rect x="3" y="5" width="18" height="16" rx="2"/><path d="M7 3v4M17 3v4M3 10h18M8 15h3"/></>}
    {name === "automations" && <><path d="m12 2 2 4.5L19 8l-5 1.5L12 14l-2-4.5L5 8l5-1.5L12 2ZM19 15l1 2 2 1-2 1-1 2-1-2-2-1 2-1 1-2Z"/></>}
    {name === "activity" && <><path d="M3 12h4l3-7 4 14 3-7h4"/></>}
    {name === "more" && <><circle cx="5" cy="12" r="1.5"/><circle cx="12" cy="12" r="1.5"/><circle cx="19" cy="12" r="1.5"/></>}
    {name === "scan" && <><path d="M12 5v14M5 12h14"/></>}
    {name === "settings" && <><path d="M12 2v3m0 14v3M4.9 4.9 7 7m10 10 2.1 2.1M2 12h3m14 0h3M4.9 19.1 7 17M17 7l2.1-2.1"/><circle cx="12" cy="12" r="4"/></>}
    {name === "arrow" && <><path d="M4 12h16m-7-7 7 7-7 7"/></>}
  </svg>;
}

const defaultApi = process.env.NEXT_PUBLIC_HOMHIVE_API_URL ?? "http://127.0.0.1:8000";

const googleCalendarClientId = process.env.NEXT_PUBLIC_HOMHIVE_GOOGLE_CLIENT_ID ?? "";

function HouseholdObjectCard({item, api, tasks, rooms, onMove}: {

  item: AutonomousObject;

  api: HomHiveApi;

  tasks: AutonomousTask[];

  rooms: AutonomousRoom[];

  onMove: (objectId: string, roomId: string | null) => Promise<void>;

}) {

  const [photoUrl, setPhotoUrl] = useState<string | null>(null);

  const [photoFailed, setPhotoFailed] = useState(false);

  const [moving, setMoving] = useState(false);

  const [expanded, setExpanded] = useState(false);

  const [locationError, setLocationError] = useState("");

  const kind = item.kind === "plant" ? "Plant" : item.kind === "appliance" ? "Appliance" : "Object";

  const icon = item.kind === "plant" ? "🌿" : item.kind === "appliance" ? "⚙" : "◈";

  const roomLabel = (room: AutonomousRoom): string => {

    const raw = (room.room_category || "Recognized space").replaceAll("_", " ").trim();

    const label = raw.replace(/\b\w/g, char => char.toUpperCase());

    const peers = rooms.filter(other =>

      (other.room_category || "Recognized space").trim().toLowerCase() ===

      (room.room_category || "Recognized space").trim().toLowerCase());

    const index = peers.findIndex(other => other.room_id === room.room_id);

    return peers.length > 1 && index >= 0 ? `${label} · Room ${index + 1}` : label;

  };

  const linkedRoom = rooms.find(room => room.room_id === item.room_id);

  const related = tasks.filter(task => task.object_id === item.id);

  const taskGuidance = related.find(task => Boolean(task.automatic_guidance))?.automatic_guidance;

  const researchSources = (item.research_sources?.length ? item.research_sources : taskGuidance?.sources || []).slice(0, 3);



  const candidateIdentity = item.identity_hint;

  useEffect(() => {

    let active = true;

    let resource: string | null = null;

    void api.autonomousObjectPhoto(item.id).then(blob => {

      if (!active) return;

      resource = URL.createObjectURL(blob);

      setPhotoUrl(resource);

    }).catch(() => { if (active) setPhotoFailed(true); });

    return () => { active = false; if (resource) URL.revokeObjectURL(resource); };

  }, [api, item.id]);



  async function setRoom(roomId: string | null) {

    setMoving(true);

    setLocationError("");

    try { await onMove(item.id, roomId); }

    catch { setLocationError("Could not save the location. Your previous setting is unchanged."); }

    finally { setMoving(false); }

  }



  return <article className="hh-object-card">

    <div className="hh-object-card-photo">

      {photoUrl ? <img src={photoUrl} alt={`Reference photograph of ${item.name}`} /> :

        <div className="hh-object-card-placeholder" aria-label="Object photo unavailable">{photoFailed ? "Photo not available" : icon}</div>}

      <span className="hh-object-card-kind">{kind}</span>

    </div>

    <div className="hh-object-card-body">

      <div className="hh-object-card-heading">

        <span className="hh-object-card-kind-icon" aria-hidden="true">{icon}</span>

        <div><p className="hh-kicker">TRACKED OBJECT</p><h2>{item.name}</h2>

          <p className="hh-object-card-identity">{candidateIdentity ? `Possible ${candidateIdentity.replace(/^Possible\s+/i, "")}` : `${kind} identity not yet established`}</p>

          <p className="hh-object-card-location">{item.location_confirmed ? `Located in ${linkedRoom ? roomLabel(linkedRoom) : "a linked room"}` : "Room not confirmed"}</p>

        </div>

      </div>



      <div className="hh-object-card-section"><strong>Visible condition</strong>

        <p>{item.evidence[0] || "No condition recorded yet."}</p>

      </div>

      <div className="hh-object-card-section"><strong>Possible explanations</strong>

        {researchSources.length ? <>

          <p className="hh-object-source-caution">These sources suggest possible explanations, not a confirmed diagnosis.</p>

          <div className="hh-object-card-research">{researchSources.map((source,i) =>

            <div key={`${source.url}-${i}`} className="hh-object-research-item">

              {"excerpt" in source && typeof source.excerpt === "string" && source.excerpt && <p>{readableResearchExcerpt(source.excerpt).slice(0, 220)}</p>}

              <a href={source.url} target="_blank" rel="noopener noreferrer">{source.title || `Read source ${i + 1}`} ↗</a>

            </div>)}</div>

        </> : <p>No guidance is available yet. A photo alone cannot establish the cause.</p>}

      </div>

      <div className="hh-object-card-section"><strong>Suggested next steps</strong>

        {related.length ? <ul className="hh-object-next-steps">{related.slice(0,3).map(task =>

          <li key={task.id}>{task.title}<small>{task.action || task.status.replaceAll("_", " ")}</small></li>)}</ul>

        : <p>{item.kind === "plant" ? "Check soil moisture and recent watering, then consult the linked sources before changing care." :

          "Review the observed condition and any manufacturer guidance before making changes."}</p>}

        <p className="hh-object-source-caution">Actions are suggestions. HomHive cannot confirm unseen watering, repairs, or results from a photo.</p>

      </div>

      <button type="button" className="hh-object-card-details" aria-expanded={expanded} onClick={() => setExpanded(!expanded)}>

        {expanded ? "Hide evidence and location" : "Evidence and location"} <span aria-hidden="true">{expanded ? "−" : "+"}</span>

      </button>

      {expanded && <div className="hh-object-card-expanded">

        <p className="hh-muted">Location is optional. Choose only a room you recognize; the object keeps its identity and history if moved.</p>

        <div className="hh-object-room-control" role="group" aria-label={`Set location for ${item.name}`}>

          <strong>Located in</strong>

          <div className="hh-object-room-options">

            {[{id:"",label:"Not confirmed"},...rooms.map(room => ({id:room.room_id,label:roomLabel(room)}))].map(choice =>

              <button key={choice.id || "none"} className={`hh-object-room-choice ${item.room_id === (choice.id || null) ? "is-selected" : ""}`}

                type="button" aria-pressed={item.room_id === (choice.id || null)} disabled={moving}

                onClick={() => void setRoom(choice.id || null)}>{choice.label}</button>)}

          </div>

        </div>

        {locationError && <p className="hh-object-error" role="alert">{locationError}</p>}

        {item.evidence.length > 1 && <div><strong>More observations</strong><ul className="hh-object-card-evidence">{item.evidence.slice(1,6).map((fact,i) => <li key={i}>{fact}</li>)}</ul></div>}



      </div>}

    </div>

  </article>;

}



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

  const [householdPulse, setHouseholdPulse] = useState<HouseholdPulse | null>(null);

  const [taskTimelines, setTaskTimelines] = useState<Record<string, TaskTimeline>>({});

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

  const [trackedObjects, setTrackedObjects] = useState<AutonomousObject[]>([]);

  const [heldRoomChoices, setHeldRoomChoices] = useState<Record<string, string>>({});

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

  const [coordination, setCoordination] = useState<CoordinationPlan | null>(null);

  const [calendarSession, setCalendarSession] = useState<GoogleCalendarSession | null>(null);

  const [calendarPlan, setCalendarPlan] = useState<CoordinationPlan | null>(null);

  const [calendarBusy, setCalendarBusy] = useState(false);

  const [calendarError, setCalendarError] = useState("");

  const [nemotronAdvice, setNemotronAdvice] = useState<NemotronAdvice | null>(null);

  const [nemotronAdviceContext, setNemotronAdviceContext] = useState("");

  const nemotronRequestId = useRef(0);

  const [nemotronBusy, setNemotronBusy] = useState(false);

  const [nemotronError, setNemotronError] = useState("");

  const [guidanceQuery, setGuidanceQuery] = useState("");

  const [guidanceResult, setGuidanceResult] = useState<HouseholdResearchResult | null>(null);

  const [guidanceError, setGuidanceError] = useState("");

  const [guidanceBusy, setGuidanceBusy] = useState(false);

  const [autoPlanEnabled, setAutoPlanEnabled] = useState(false);

  const lastAutoPlanSignature = useRef("");



  const [quietEnabled, setQuietEnabled] = useState(true);

  const [quietStart, setQuietStart] = useState("22:00");

  const [quietEnd, setQuietEnd] = useState("07:00");

  const [quietTimezone, setQuietTimezone] = useState("UTC");

  const [deviceTimezone, setDeviceTimezone] = useState("UTC");

  const [quietEditorOpen, setQuietEditorOpen] = useState(false);

  const quietEditorOpenRef = useRef(false);

  const [clockNow, setClockNow] = useState(() => new Date());

  const [savingContext, setSavingContext] = useState(false);

  const [plan, setPlan] = useState<PlanResponse | null>(null);

  const [availableMinutes, setAvailableMinutes] = useState(30);

  const [atHome, setAtHome] = useState(true);

  const [quietHours, setQuietHours] = useState(false);

  const [researchQuery, setResearchQuery] = useState("");

  const [status, setStatus] = useState("Ready");

  const [view, setView] = useState<"home" | "spaces" | "objects" | "tasks" | "activity" | "schedule" | "automations">("home");

  const [simpleInterface, setSimpleInterface] = useState(true);

  const [moreNavigationOpen, setMoreNavigationOpen] = useState(false);

  const [moreMenuPosition, setMoreMenuPosition] = useState({ top: 0, left: 0 });

  const moreButtonRef = useRef<HTMLButtonElement>(null);

  const moreMenuRef = useRef<HTMLElement>(null);

  const [navigationReady, setNavigationReady] = useState(false);

  const [settingsOpen, setSettingsOpen] = useState(false);

  const [scanOpen, setScanOpen] = useState(false);

  const [demoOpen, setDemoOpen] = useState(false);

  const [demoQuery, setDemoQuery] = useState("");

  const [demoCategory, setDemoCategory] = useState("All");

  const [demoMode, setDemoMode] = useState<"sequences" | "standalone">("sequences");

  const [taskRoomFilter, setTaskRoomFilter] = useState("all");

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

      return "HomHive couldn't connect. Check your internet connection and try again.";

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

    const tabs = ["home", "spaces", "objects", "tasks", "activity", "schedule", "automations"] as const;

    const param = new URLSearchParams(window.location.search).get("tab");

    if (param && tabs.some(tab => tab === param)) setView(param as typeof tabs[number]);

    setNavigationReady(true);

  }, []);

  useEffect(() => {

    if (!navigationReady) return;

    const url = new URL(window.location.href);

    if (view === "home") url.searchParams.delete("tab");

    else url.searchParams.set("tab", view);

    window.history.replaceState(window.history.state, "", url.pathname + url.search + url.hash);

  }, [view, navigationReady]);

  useEffect(() => {
    if (navigationReady) window.scrollTo({top: 0, behavior: "instant"});
  }, [view, navigationReady]);



  useEffect(() => {

    try {

      const saved = readAccountSession(window.sessionStorage, defaultApi);

      if (!saved) return;

      setHouseholdId(saved.householdId);

      setToken(saved.accessToken);

      setStatus("Restoring your household session...");

    } catch {

      notify("warning", "Your session won't survive a refresh", "This browser is blocking tab storage. Your current sign-in can still be used.");

    }

  }, []);



  useEffect(() => {

    try { setSimpleInterface(window.localStorage.getItem("homhive.interfaceMode") !== "full"); } catch {}

    setDeviceTimezone(currentTimeZone());

    const clock = window.setInterval(() => setClockNow(new Date()), 30000);

    return () => window.clearInterval(clock);

  }, []);



  useEffect(() => {

    if (!moreNavigationOpen) return;

    const closeOutside = (event: PointerEvent) => {

      if (event.target instanceof Node &&

        (moreButtonRef.current?.contains(event.target) || moreMenuRef.current?.contains(event.target))) return;

      setMoreNavigationOpen(false);

    };

    const closeOnEscape = (event: KeyboardEvent) => {

      if (event.key === "Escape") {

        setMoreNavigationOpen(false);

        moreButtonRef.current?.focus();

      }

    };

    const closeOnMove = () => setMoreNavigationOpen(false);

    document.addEventListener("pointerdown", closeOutside);

    document.addEventListener("keydown", closeOnEscape);

    window.addEventListener("resize", closeOnMove);

    window.addEventListener("scroll", closeOnMove, true);

    return () => {

      document.removeEventListener("pointerdown", closeOutside);

      document.removeEventListener("keydown", closeOnEscape);

      window.removeEventListener("resize", closeOnMove);

      window.removeEventListener("scroll", closeOnMove, true);

    };

  }, [moreNavigationOpen]);



  useEffect(() => {
    if (!quietEditorOpen) return;
    const onEscape = (event: KeyboardEvent) => {
      if (event.key === "Escape" && !savingContext) closeQuietHoursEditor();
    };
    document.addEventListener("keydown", onEscape);
    return () => document.removeEventListener("keydown", onEscape);
  }, [quietEditorOpen, savingContext]);

  function changeInterfaceMode(simple: boolean) {

    setSimpleInterface(simple);

    setMoreNavigationOpen(false);

    try { window.localStorage.setItem("homhive.interfaceMode", simple ? "simple" : "full"); } catch {}

  }



  useEffect(() => {

    try { const saved = window.sessionStorage.getItem("homhive.taskRoomFilter"); if (saved) setTaskRoomFilter(saved); } catch {}

  }, []);

  useEffect(() => {

    try { window.sessionStorage.setItem("homhive.taskRoomFilter", taskRoomFilter); } catch {}

  }, [taskRoomFilter]);



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

        setAutonomousTasks([]); setHouseholdPulse(null); setTaskTimelines({});

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

      setStatus("Signed in. Connecting your household...");

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

      setNotifications([]); setObservations([]); setPlan(null); setCoordination(null);

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

      api.autonomousAlerts(), api.workWindow(), api.householdPulse(), api.coordinationPlan(), api.autonomousObjects()

    ]);

    if (results[0].status === "fulfilled") setAutonomousTasks(results[0].value);

    if (results[7].status === "fulfilled") setTrackedObjects(results[7].value);

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

    if (results[5].status === "fulfilled") setHouseholdPulse(results[5].value);

    if (results[6].status === "fulfilled") {

      setCoordination(results[6].value);

      if (!quietEditorOpenRef.current) {
        setQuietEnabled(results[6].value.quiet_hours.enabled);
        setQuietStart(results[6].value.quiet_hours.start_time);
        setQuietEnd(results[6].value.quiet_hours.end_time);
        setQuietTimezone(results[6].value.quiet_hours.timezone);
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



  const advisorPlan = calendarPlan ?? coordination;

  const currentAdvisorContext = advisorPlan ? JSON.stringify({

    householdId,

    presence: advisorPlan.presence.state,

    availability: advisorPlan.availability.state,

    quietHours: advisorPlan.quiet_hours.active,

    workWindow: advisorPlan.work_window,

    calendar: advisorPlan.calendar ? [advisorPlan.calendar.busy_now, advisorPlan.calendar.effective_work_minutes,

      advisorPlan.calendar.next_busy_starts_at] : null,

    tasks: advisorPlan.tasks.map(task => [

      task.task_id, task.title, task.status, task.priority, task.duration_min, task.duration_max,

    ]).sort((a, b) => String(a[0]).localeCompare(String(b[0]))),

  }) : "";



  useEffect(() => {

    nemotronRequestId.current += 1;

    setNemotronAdvice(null);

    setNemotronAdviceContext("");

    setNemotronError("");

    setNemotronBusy(false);

    setCalendarSession(null);

    setCalendarPlan(null);

    setCalendarError("");

  }, [token, householdId]);



  useEffect(() => {

    if (googleCalendarClientId) void preloadGoogleCalendar().catch(() => undefined);

  }, []);



  async function connectCalendar() {

    if (!isConnected) return;

    setCalendarBusy(true);

    setCalendarError("");

    try {

      const session = await requestGoogleCalendarAccess(googleCalendarClientId);

      const plan = await api.googleCalendarPlan(session.accessToken);

      setCalendarSession(session);

      setCalendarPlan(plan);

      notify("success", "Google Calendar connected", "Only busy times are read. No event titles or details are accessed.");

    } catch (error) {

      setCalendarSession(null);

      setCalendarPlan(null);

      setCalendarError(friendlyError(error, "Calendar connection failed. Please try again."));

    } finally { setCalendarBusy(false); }

  }



  async function refreshCalendar() {

    if (!calendarSession) return;

    if (Date.now() >= calendarSession.expiresAt - 15000) {

      setCalendarPlan(null);

      setCalendarError("Calendar access expired. Reconnect to check your schedule.");

      return;

    }

    setCalendarBusy(true);

    setCalendarError("");

    try { setCalendarPlan(await api.googleCalendarPlan(calendarSession.accessToken)); }

    catch (error) {

      setCalendarPlan(null);

      setCalendarError(friendlyError(error, "Could not refresh Google Calendar availability."));

    } finally { setCalendarBusy(false); }

  }





  const askNemotron = async () => {

    const requestId = ++nemotronRequestId.current;

    const contextAtRequest = currentAdvisorContext;

    setNemotronBusy(true);

    setNemotronError("");

    try {

      if (calendarSession && Date.now() >= calendarSession.expiresAt - 15000) {

        throw new Error("Google Calendar access has expired. Reconnect before requesting calendar-aware advice.");

      }

      if (calendarSession && !calendarPlan) {

        throw new Error("Refresh your Google Calendar check before requesting advice.");

      }

      const advice = calendarSession

        ? await api.googleCalendarNemotronAdvice(calendarSession.accessToken)

        : await api.nemotronAdvice();

      if (nemotronRequestId.current !== requestId) return;

      setNemotronAdviceContext(contextAtRequest);

      setNemotronAdvice(advice);

    } catch (error) {

      if (nemotronRequestId.current === requestId) {

        setNemotronAdviceContext("");

        setNemotronError(friendlyError(error, "Suggestions are unavailable right now. Your tasks are safe."));

      }

    } finally {

      if (nemotronRequestId.current === requestId) setNemotronBusy(false);

    }

  };



  async function researchHousehold() {

    const query = guidanceQuery.trim();

    if (query.length < 3 || query.length > 500 || guidanceBusy) return;

    const lowered = query.toLowerCase();

    const purpose: HouseholdResearchPurpose = /plant|soil|watering|leaf|leaves|garden/.test(lowered)

      ? "plant_care" : /fridge|refrigerator|dishwasher|washer|dryer|furnace|heater|appliance|microwave/.test(lowered)

      ? "appliance_guidance" : /maintenance|repair|filter|leak|drain|plumbing|mold|smoke alarm/.test(lowered)

      ? "maintenance" : "household_context";

    setGuidanceBusy(true);

    setGuidanceResult(null);

    setGuidanceError("");

    try {

      const result = await api.researchHouseholdGuidance(query, purpose);

      setGuidanceResult(result);

    } catch (error) {

      setGuidanceError(friendlyError(error, "Research is temporarily unavailable. Please try again shortly."));

    } finally {

      setGuidanceBusy(false);

    }

  }



  const planSignature = currentAdvisorContext;

  useEffect(() => {

    if (!autoPlanEnabled || view !== "automations" || !token || !coordination?.tasks.length || !planSignature || nemotronBusy) return;

    if (lastAutoPlanSignature.current === planSignature) return;

    lastAutoPlanSignature.current = planSignature;

    void askNemotron();



    // eslint-disable-next-line react-hooks/exhaustive-deps

  }, [autoPlanEnabled, view, token, planSignature]);



  useEffect(() => {

    if (!token || !householdId) return;

    const interval = setInterval(() => { void loadAutonomousState(); }, 60000);

    return () => clearInterval(interval);



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

            detail: "Your photo was saved, but the review could not start. Please try again." } : current);

          return;

        }

        if (job.state === "completed") {
          setTaskRoomFilter("all");
          setStatus("Review complete");

          setScanProgress({ phase: "done", percent: 100, mediaId: job.media_id,

            detail: Object.values(job.review_summary?.progress_results ?? {}).includes("completed")

              ? "Review complete. Fresh evidence verified an existing task as finished. See your updates." :

              Object.keys(job.review_summary?.progress_results ?? {}).length

              ? "Review complete. Existing household work was re-evaluated; see its evidence and progress in Tasks." :

              job.review_summary?.approved_count ? "Review complete. See Tasks for the approved suggestions." :

              job.review_summary?.proposed_count ? "Review complete. No task was approved; check the reviewer explanations in Tasks." :

              job.review_summary?.evidence_reason === "no_visible_claims" ? "No visible household condition was proposed from this photograph. Try a clearer view if something needs attention." :

              job.review_summary?.evidence_reason === "claims_not_corroborated" ? "The photo did not provide enough evidence for a task." :

              job.review_summary?.verification === "no_corroborated_evidence" ? "The photo did not show enough clear details. Try a different angle." :

              "Review complete. No task was supported by the available evidence." });

          await loadAutonomousState();

        } else if (job.state === "held_unverified_room") {
          setStatus("Room confirmation needed");

          setScanProgress({ phase: "held", percent: null, mediaId: job.media_id,

            detail: "This photo could not be safely linked to one registered space. Choose a known room or add a separate space only if you recognize it as new." });

        } else if (job.state === "failed") {
          setStatus("Scan needs attention");

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

      detail: "Choose this only if the photo shows a different physical room. HomHive will review it again.",

      actionLabel: "Add space and review",

      onConfirm: () => { void performEnrollHeldRoom(job); },

    });

  }



  async function performEnrollHeldRoom(job: AutonomousScanJob) {

    setAutonomousLoading(true);

    try {

      await api.enrollAutonomousRoom(job.media_id);

      setAutonomousNote("New room added. Your photo is queued for review.");

      notify("success", "Space added", "Your photo is queued for review.");

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



  function confirmExistingRoom(job: AutonomousScanJob) {

    const roomId = heldRoomChoices[job.media_id];

    const room = enrolledRooms.find(item => item.room_id === roomId);

    if (!room || job.state !== "held_unverified_room" || busy || autonomousLoading) return;

    setConfirmation({

      title: "Is this the exact same physical space?",

      detail: `Only confirm if you recognize the same room, not merely another ${room.room_category || "space"}. HomHive will review the photo again and record your confirmation.`,

      actionLabel: "Confirm space and review",

      onConfirm: () => { void performExistingRoomSelection(job, roomId); },

    });

  }



  async function performExistingRoomSelection(job: AutonomousScanJob, roomId: string) {

    setAutonomousLoading(true);

    try {

      await api.assignAutonomousRoom(job.media_id, roomId);

      setScanProgress({phase: "analyzing", percent: null, mediaId: job.media_id,

        detail: "Reviewing this photo against the space you identified"});

      notify("success", "Existing space selected", "HomHive will review the saved photograph and existing tasks. Your room confirmation is retained.");

      setAutonomousNote("User-confirmed space selected. Reviewing saved evidence.");

      await loadAutonomousState();

    } catch (error) {

      notify("error", "Couldn't select existing space", friendlyError(error, "Please retry"));

    } finally { setAutonomousLoading(false); }

  }









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







  const roomTasks = useMemo(() => {

    if (!activeRoom || !report) return [];

    const room = activeRoom.room.toLowerCase();

    return report.ranked_tasks.filter(({ task }) => {

      const storedLocation = task.metadata?.location;

      if (typeof storedLocation === "string" && storedLocation.toLowerCase() === room) return true;

      return task.task_key.toLowerCase().split(":").includes(room);

    });

  }, [activeRoom, report]);



  const demoFamilyTitles = useMemo(() => new Map(

    demoCatalog.filter(item => item.group === "original").map(item => [item.family_id, item.source_title] as const),

  ), []);

  const demoCategories = useMemo(() => ["All", ...Array.from(new Set(demoCatalog.map(item => item.category))).sort()], []);

  const demoFamilies = useMemo(() => demoCatalog.filter(item => item.group === "original").map(original => ({

    original,

    variants: demoCatalog.filter(item => item.family_id === original.family_id &&

      item.group === "variant" && item.relationship_status === "manifest_sha256_verified")

      .sort((a, b) => a.title.localeCompare(b.title, undefined, {numeric: true})),

  })).filter(family => family.variants.length > 0).sort((a, b) => {

    if (a.original.title === "Original 30") return -1;

    if (b.original.title === "Original 30") return 1;

    return a.original.title.localeCompare(b.original.title, undefined, {numeric: true});

  }), []);

  const standaloneDemoImages = useMemo(() => {

    const paired = new Set(demoFamilies.map(family => family.original.family_id));

    return demoCatalog.filter(image => !paired.has(image.family_id))

      .sort((a,b) => a.title.localeCompare(b.title, undefined, {numeric: true}));

  }, [demoFamilies]);

  const demoSearch = demoQuery.trim().toLowerCase();

  const filteredDemoFamilies = demoFamilies.filter(family =>

    (demoCategory === "All" || family.original.category === demoCategory) &&

    [family.original, ...family.variants].some(image =>

      `${image.title} ${image.category} ${image.source_title} ${image.variant_note} ${demoFamilyTitles.get(image.family_id) ?? ""}`

        .toLowerCase().includes(demoSearch)));

  const filteredStandaloneImages = standaloneDemoImages.filter(image =>

    (demoCategory === "All" || image.category === demoCategory) &&

    `${image.title} ${image.category} ${image.source_title} ${image.variant_note}`.toLowerCase().includes(demoSearch));



  async function chooseDemoImage(image: (typeof demoCatalog)[number]) {

    if (!token || !historyLoaded) { setDemoSelectionError("Load your household before choosing a sample photo."); return; }

    setDemoSelecting(true);

    setDemoSelectionError("");

    try {

      const response = await fetch(image.image, { cache: "force-cache" });

      if (!response.ok) throw new Error("Could not load this sample photograph");

      const bytes = await response.blob();

      const selected = new File([bytes], `${image.title}.jpg`, { type: "image/jpeg" });

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

    setStatus("Uploading your photo...");

    setScanProgress({ phase: "uploading", percent: 0, mediaId: null, detail: "Securely saving your photo" });

    try {

      const stored = await api.upload(file, location, (percent) => {

        setScanProgress(current => current?.phase === "uploading" ? { ...current, percent } : current);

      });

      setMedia(stored);

      setFile(null);

      setPhotoInspection(null);

      setPhotoPreviewUrl(null);

      setScanOpen(false);

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

        detail: "Your photo is queued for review." });

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

    setScanProgress({ phase: "analyzing", percent: null, mediaId, detail: "Reviewing the details in your photo" });

    setStatus("Analyzing saved photo...");

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

        timezone: workWindow?.timezone || coordination?.quiet_hours.timezone || deviceTimezone,

        start_time: windowStart, end_time: windowEnd, weekdays: windowWeekdays,

      });

      setWorkWindow(window);

      notify("success", "Preferred time saved", "HomHive can now recommend slots based on your recurring preference. Your calendar is not connected.");

      await loadAutonomousState();

    } catch (error) { notify("error", "Could not save preferred time", friendlyError(error, "Try again")); }

    finally { setSavingWindow(false); }

  }



  async function decideAutonomousTask(taskId: string, decision: "accept" | "decline" | "remind" | "done") {

    const result = await run(`Updating household work...`, () => api.decideAutonomousTask(taskId, decision));

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

        detail: "Photo queued for review." });

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

      title: "Review this photo again?",

      detail: "HomHive will review the saved photo again. Your previous scans and tasks will remain.",

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

        detail: "Reviewing your saved photo again"});

      await loadAutonomousState();

    } catch (error) {

      const message = error instanceof Error ? error.message : "Could not queue the re-review";

      setAutonomousNote(message);

      notify("error", "Could not restart review", message);

    } finally {

      setRecheckingMediaId(null);

    }

  }



  async function showTaskTimeline(taskId: string) {

    if (taskTimelines[taskId]) return;

    try {

      const timeline = await api.taskTimeline(taskId);

      setTaskTimelines(current => ({...current, [taskId]: timeline}));

    } catch (error) {

      notify("warning", "Couldn't load task history", friendlyError(error, "Please retry the task timeline."));

    }

  }



  function exportCalendarTask(task: AutonomousTask) {

    if (!task.recommended_at || !task.effort_max) return;

    const start = new Date(task.recommended_at);

    const end = new Date(start.getTime() + task.effort_max * 60000);

    if (!Number.isFinite(start.getTime()) || !Number.isFinite(end.getTime())) return;

    const stamp = (value: Date) => value.toISOString().replace(/[-:]/g, "").replace(/\.\d{3}Z$/, "Z");

    const escape = (value: string) => value.replace(/\\/g, "\\\\").replace(/\r?\n/g, " ").replace(/,/g, "\\,").replace(/;/g, "\\;");

    const lines = ["BEGIN:VCALENDAR", "VERSION:2.0", "PRODID:-//HomHive//Household planning//EN",

      "BEGIN:VEVENT", `UID:${task.id}@homhive.local`, `DTSTAMP:${stamp(new Date())}`,

      `DTSTART:${stamp(start)}`, `DTEND:${stamp(end)}`, `SUMMARY:${escape(task.title)}`,

      `DESCRIPTION:${escape(`HomHive suggested household work. ${task.action}. This is a suggested slot, not a calendar availability check.`)}`,

      "END:VEVENT", "END:VCALENDAR", ""];

    const url = URL.createObjectURL(new Blob([lines.join("\r\n")], {type: "text/calendar;charset=utf-8"}));

    const link = document.createElement("a");

    link.href = url; link.download = "homhive-household-task.ics";

    document.body.appendChild(link); link.click(); link.remove();

    setTimeout(() => URL.revokeObjectURL(url), 1000);

    notify("success", "Calendar event prepared", "Import the downloaded event into Google Calendar, Outlook, or Apple Calendar. HomHive has not checked whether you're free.");

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

    if (result) {

      setPresence(result);

      setCalendarPlan(null);

      try { setCoordination(await api.coordinationPlan()); }

      catch { notify("warning", "Decision status unavailable", "Presence was saved, but recommendations could not refresh."); }

    }

  }



  async function changeAvailability(state: "FREE" | "BUSY" | "UNKNOWN") {

    const result = await run("Updating household availability...", () => api.updateAvailability(state));

    if (result) {

      setCoordination(result);

      setCalendarPlan(null);

      notify("info", "Recommendations updated", `Your availability is now ${state.toLowerCase()}. Changes expire automatically.`);

    }

  }



  function openQuietHoursEditor() {
    const saved = coordination?.quiet_hours;
    setQuietEnabled(saved?.enabled ?? true);
    setQuietStart(saved?.start_time ?? "22:00");
    setQuietEnd(saved?.end_time ?? "07:00");
    setQuietTimezone(saved?.timezone ?? deviceTimezone);
    quietEditorOpenRef.current = true;
    setQuietEditorOpen(true);
  }

  function closeQuietHoursEditor() {
    quietEditorOpenRef.current = false;
    setQuietEditorOpen(false);
  }

  function reviewHouseholdReadiness() {
    const section = document.getElementById("hh-household-readiness");
    section?.scrollIntoView({behavior: "smooth", block: "center"});
    section?.focus({preventScroll: true});
  }

  async function saveQuietHours() {
    if (!isValidTimeZone(quietTimezone)) {
      notify("warning", "Choose a valid time zone", "Use a recognized time zone, such as America/Phoenix.");
      return;
    }
    setSavingContext(true);
    try {
      const result = await api.updateQuietHours(quietEnabled, quietStart, quietEnd, quietTimezone);
      setCoordination(result);
      setCalendarPlan(null);
      closeQuietHoursEditor();
      notify("success", "Quiet hours saved", "Your household time zone and quiet hours will be remembered across sign-ins.");
    } catch (error) {
      notify("error", "Couldn't save quiet hours", friendlyError(error, "Try again."));
    } finally { setSavingContext(false); }
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

  const roomDisplayName = (roomId: string, fallback?: string | null) => {

    const room = enrolledRooms.find(item => item.room_id === roomId);

    const roomName = (room?.room_category || fallback || "Unassigned space").replaceAll("_", " ");

    const matches = enrolledRooms.filter(item => (item.room_category || "Unassigned space").toLowerCase() === roomName.toLowerCase());

    const occurrence = matches.findIndex(item => item.room_id === roomId);

    return matches.length > 1 && occurrence >= 0

      ? `${capitalizeFirst(roomName)} · Room ${occurrence + 1}`

      : capitalizeFirst(roomName);

  };

  const objectKindForTask = (task: AutonomousTask): "plant" | "appliance" | null => {

    if (task.observed_object?.kind) return task.observed_object.kind;

    const content = `${task.title} ${task.evidence_summary || ""}`;

    if (/\b(plant|pothos|leaf|leaves|foliage|fern|monstera|orchid|succulent)\b/i.test(content)) return "plant";

    if (/\b(appliance|dishwasher|refrigerator|washing machine|dryer|microwave|furnace|hvac)\b/i.test(content)) return "appliance";

    return null;

  };

  const objectDisplayName = (task: AutonomousTask) => {

    const kind = objectKindForTask(task);

    if (!kind) return null;

    const linked = task.observed_object;

    if (linked) return linked.label;

    return kind === "plant" ? "Houseplant" : "Household appliance";

  };

  const taskOriginLabel = (task: AutonomousTask) => {

    const object = trackedObjects.find(item => item.id === task.object_id);

    if (object) return object.name + (object.location_confirmed ? "" : " · location unconfirmed");

    const room = enrolledRooms.find(item => item.room_id === task.room_id);

    const category = (room?.room_category || task.room_category || "").toLowerCase();

    const unlocated = !category || category === "unassigned space" || category === "indoor plants";

    if (!unlocated) return roomDisplayName(task.room_id, task.room_category);

    const name = objectDisplayName(task);

    return name ? `${name} · location unconfirmed` : roomDisplayName(task.room_id, task.room_category);

  };

  const activeHouseholdTasks = [...autonomousTasks]

    .filter(task => !["dismissed", "completed"].includes(task.status) && (!task.remind_at || Date.parse(task.remind_at) <= Date.now()))

    .sort((a,b) => b.created_at.localeCompare(a.created_at));

  const visibleHouseholdTasks = activeHouseholdTasks.filter(task => taskRoomFilter === "all" || task.room_id === taskRoomFilter);

  const groupedHouseholdTasks = Array.from(new Set(visibleHouseholdTasks.map(task => task.room_id))).map(roomId => ({

    roomId,

    label: taskOriginLabel(visibleHouseholdTasks.find(task => task.room_id === roomId)!),

    tasks: visibleHouseholdTasks.filter(task => task.room_id === roomId),

  })).sort((a,b) => a.label.localeCompare(b.label));



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

  const scheduleZone = workWindow?.timezone || coordination?.quiet_hours.timezone || deviceTimezone;
  const savedQuiet = coordination?.quiet_hours;
  const quietActiveNow = savedQuiet ? quietHoursActiveAt(clockNow, savedQuiet) : false;
  const quietLocalTime = savedQuiet ? timeInZone(clockNow, savedQuiet.timezone) : "";

  const scheduleSummary = workWindow

    ? `${readableWorkDays(workWindow.weekdays)} · ${readableWorkTime(workWindow.start_time)} - ${readableWorkTime(workWindow.end_time)}`

    : "Not set up yet";

  const simpleReason = (reason: string) => {

    if (reason.startsWith("Presence is unknown;")) return "Confirm you are home to see if this can be scheduled.";

    if (reason.startsWith("Home is not the same as available")) return "Let HomHive know when you are free for household work.";

    if (reason.startsWith("Duration has not been independently supported")) return "The time estimate needs more evidence before scheduling.";

    if (reason.startsWith("Waiting for your approval")) return "Your approval is needed before scheduling.";

    if (reason.startsWith("Quiet hours are active")) return "This may need to wait until quiet hours end.";

    if (reason.startsWith("Not enough time remains")) return "There isn't enough time left in your preferred work window.";

    return reason;

  };

  const simpleHomeTasks = advisorPlan?.tasks.length ? [...advisorPlan.tasks]

    .sort((a, b) => ({ NOW: 0, SOON: 1, DEFERRED: 2, BLOCKED: 3 }[a.status] - { NOW: 0, SOON: 1, DEFERRED: 2, BLOCKED: 3 }[b.status]))

    .slice(0, 3).map(task => ({

      id: task.task_id, title: task.title,

      status: task.status === "NOW" ? "Ready for review" : task.status === "SOON" ? "For later" : task.status === "DEFERRED" ? "Deferred" : "More information needed",

      detail: simpleReason(task.reasons[0] || "Based on reviewed household evidence."),

      progress: task.progress_percent,

    })) : activeHouseholdTasks.slice(0, 3).map(task => ({

      id: task.id, title: task.title, status: "Review suggested",

      detail: task.evidence_summary || "Based on a reviewed household photo.",

      progress: task.progress?.percent ?? null,

    }));

  const simpleActiveTaskCount = advisorPlan?.tasks.length ?? activeHouseholdTasks.length;

  const navItems = [

    { id: "home", label: "Overview" },

    { id: "spaces", label: "Spaces" },

    { id: "objects", label: "Objects" },

    { id: "tasks", label: "Tasks" },

    { id: "schedule", label: "Schedule" },

    { id: "automations", label: "Automation" },

    { id: "activity", label: "Activity" },

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

      {quietEditorOpen && <div className="hh-modal-backdrop" onClick={() => !savingContext && closeQuietHoursEditor()}>
        <section role="dialog" aria-modal="true" aria-labelledby="hh-quiet-modal-title" className="hh-modal hh-quiet-modal" onClick={event => event.stopPropagation()}>
          <div className="hh-panel-head"><div><h2 id="hh-quiet-modal-title">Quiet hours</h2><p className="hh-muted">Choose when HomHive should hold noisy task suggestions.</p></div><button type="button" className="hh-icon-button" aria-label="Close quiet hours" disabled={savingContext} onClick={closeQuietHoursEditor}>✕</button></div>
          <div className="hh-quiet-control"><div><strong>Enable quiet hours</strong><small>Keep household tasks on hold during your chosen hours.</small></div>
            <button type="button" role="switch" aria-label="Enable quiet hours" aria-checked={quietEnabled} className={`hh-toggle-switch ${quietEnabled ? "is-on" : ""}`} onClick={() => setQuietEnabled(value => !value)}><span /></button></div>
          <div className="hh-schedule-times"><TimeWheelField id="hh-quiet-from" label="From" value={quietStart} onChange={setQuietStart}/><span className="hh-schedule-to" aria-hidden="true">to</span><TimeWheelField id="hh-quiet-until" label="Until" value={quietEnd} onChange={setQuietEnd}/></div>
          <label htmlFor="hh-household-timezone">Household time zone</label>
          <input id="hh-household-timezone" list="hh-common-timezones" value={quietTimezone} onChange={event => setQuietTimezone(event.target.value)} autoComplete="off" spellCheck={false} aria-invalid={!isValidTimeZone(quietTimezone)} />
          <datalist id="hh-common-timezones">{["America/Phoenix", "America/Los_Angeles", "America/Denver", "America/Chicago", "America/New_York", "America/Toronto", "Europe/London", "Europe/Paris", "Asia/Kolkata", "Asia/Tokyo", "Australia/Sydney", "UTC"].map(zone => <option key={zone} value={zone} />)}</datalist>
          <p className="hh-quiet-zone-hint">{isValidTimeZone(quietTimezone) ? `Current household time: ${timeInZone(clockNow, quietTimezone)}.` : "Enter a recognized time zone, such as America/Phoenix."}</p>
          <button type="button" className="hh-quiet-use-device" onClick={() => setQuietTimezone(deviceTimezone)}>Use this device's time zone ({deviceTimezone})</button>
          <p className="hh-quiet-zone-hint">Your chosen time zone is saved with the household, not this browser. Travel and daylight saving changes will not silently reset your schedule.</p>
          <div className="hh-quiet-modal-actions"><button type="button" className="secondary" disabled={savingContext} onClick={closeQuietHoursEditor}>Cancel</button><button type="button" disabled={savingContext || quietStart === quietEnd || !isValidTimeZone(quietTimezone)} onClick={() => void saveQuietHours()}>{savingContext ? "Saving..." : "Save quiet hours"}</button></div>
        </section>
      </div>}

      {confirmation && <div className="hh-modal-backdrop hh-confirm-backdrop" onClick={() => setConfirmation(null)}>

        <section role="alertdialog" aria-modal="true" aria-labelledby="hh-confirm-title" aria-describedby="hh-confirm-detail" className="hh-modal hh-confirm-dialog" onClick={event => event.stopPropagation()}>

          <h2 id="hh-confirm-title">{confirmation.title}</h2>

          <p id="hh-confirm-detail">{confirmation.detail}</p>

          <div className="hh-task-actions"><button type="button" className="secondary" autoFocus onClick={() => setConfirmation(null)}>Cancel</button><button type="button" onClick={() => {const callback = confirmation.onConfirm;setConfirmation(null); callback();}}>{confirmation.actionLabel}</button></div>

        </section>

      </div>}

      <a className="hh-skip-link" href="#household-content">Skip to household content</a>

      <header className="hh-header">

        <div className="hh-brand"><img className="hh-logo" src="/branding/homhive-192.png" alt="" width="44" height="44" /><span>HomHive<small>Your home, understood.</small></span></div>

        <nav className="hh-nav" aria-label="Main navigation">

          {(simpleInterface ? navItems.filter(item => ["home", "spaces", "tasks"].includes(item.id)) : navItems).map((item) => <button key={item.id} className={view === item.id ? "hh-nav-active" : "hh-nav-button"} aria-current={view === item.id ? "page" : undefined} onClick={() => { if (item.id === "tasks") { setTaskRoomFilter("all"); void loadAutonomousState(); } setView(item.id); }}><InterfaceIcon name={item.id} />{simpleInterface && item.id === "home" ? "Overview" : simpleInterface && item.id === "spaces" ? "Rooms" : item.label}</button>)}

          {simpleInterface && <button ref={moreButtonRef} type="button" className={["objects", "schedule", "automations", "activity"].includes(view) ? "hh-nav-active" : "hh-nav-button"} aria-expanded={moreNavigationOpen} aria-haspopup="true" aria-controls="hh-more-pages" onClick={(event) => {

            const bounds = event.currentTarget.getBoundingClientRect();

            setMoreMenuPosition({ top: bounds.bottom + 7, left: Math.max(12, Math.min(bounds.left, window.innerWidth - 300)) });

            setMoreNavigationOpen(open => !open);

          }}><InterfaceIcon name="more" />More</button>}

        </nav>

        <div className="hh-toolbar">{isConnected && <span className="hh-connection-status"><span className="hh-connection-dot" />Connected</span>}<button type="button" className="hh-mode-switch" onClick={() => changeInterfaceMode(!simpleInterface)}>{simpleInterface ? "Advanced view" : "Simple view"}</button><button className="hh-scan" onClick={() => setScanOpen(true)}><InterfaceIcon name="scan" />New scan</button><button className="hh-icon-button" aria-label="Open settings" title="Settings" onClick={() => setSettingsOpen(true)}><InterfaceIcon name="settings" size={20} /></button></div>

      </header>

      {simpleInterface && moreNavigationOpen && <nav ref={moreMenuRef} id="hh-more-pages" className="hh-more-links" aria-label="More household pages" style={{ top: moreMenuPosition.top, left: moreMenuPosition.left, right: "auto" }}>

        {navItems.filter(item => ["objects", "schedule", "automations", "activity"].includes(item.id)).map(item =>

          <button type="button" key={item.id} aria-current={view === item.id ? "page" : undefined} onClick={() => { setView(item.id); setMoreNavigationOpen(false); }}>{item.label}</button>)}

      </nav>}

      {isConnected && autonomousFetchError && <div className="hh-scan-message hh-scan-problem" role="status"><p>{autonomousFetchError}</p><button className="secondary" onClick={() => void loadAutonomousState()}>Try again</button></div>}

      <div id="household-content" className={`hh-live${busy || /expired|failed|error|attention/i.test(status) ? " is-visible" : ""}`} role="status" aria-live="polite"><span className={busy ? "pulse" : "dot"}/>{status}</div>



      {scanProgress && <section className={`hh-analysis-card hh-analysis-${scanProgress.phase}`} role="status" aria-live="polite" aria-label="Photo analysis progress">

        <div className="hh-panel-head"><div><p className="hh-kicker">Household scan</p><h2>{scanProgress.phase === "uploading" ? "Saving your photo" : scanProgress.phase === "analyzing" ? "Analyzing your space" : scanProgress.phase === "done" ? "Review complete" : scanProgress.phase === "held" ? "Room identification needed" : "Analysis needs attention"}</h2></div>{scanProgress.phase === "done" && <button className="hh-icon-button" aria-label="Dismiss completed scan" onClick={() => setScanProgress(null)}>✕</button>}</div>

        <p>{scanProgress.detail}</p>

        <div className={`hh-analysis-track ${scanProgress.percent === null && (scanProgress.phase === "uploading" || scanProgress.phase === "analyzing") ? "hh-analysis-indeterminate" : ""}`} role="progressbar" aria-label={scanProgress.phase === "uploading" ? "Photo upload" : "Photo analysis"} aria-valuemin={0} aria-valuemax={100} aria-valuenow={scanProgress.percent === null ? undefined : scanProgress.percent}>

          <div className="hh-analysis-fill" style={scanProgress.percent === null ? undefined : { width: `${scanProgress.percent}%` }}/>

        </div>

        <div className="hh-analysis-footer"><small>{scanProgress.phase === "uploading" ? `${scanProgress.percent ?? 0}% uploaded` : scanProgress.phase === "analyzing" ? "Analysis in progress · completion time varies" : scanProgress.phase === "done" ? "Review complete" : scanProgress.phase === "held" ? "Room match needs your decision" : "Your original photo is retained"}</small>{scanProgress.phase === "held" && scanJobs.filter(job => job.media_id === scanProgress.mediaId && job.state === "held_unverified_room").map(job => <div key={job.id}><button disabled={autonomousLoading || busy} onClick={() => void enrollHeldRoom(job)}>{autonomousLoading ? "Adding space..." : "Add as a new space"}</button><div className="hh-room-match-panel"><p className="hh-room-match-heading">Or link to a space you already know</p>

              <HomHiveSelect id={`scan-room-${job.id}`} label="Matching physical room" value={heldRoomChoices[job.media_id] || ""}

                onChange={value => setHeldRoomChoices(current => ({...current, [job.media_id]: value}))}

                choices={[{value: "", label: "Choose a registered space"}, ...enrolledRooms.map(room => ({value: room.room_id, label: roomDisplayName(room.room_id), detail: "Previously registered space"}))]} /><button className="hh-confirm-room" disabled={!heldRoomChoices[job.media_id] || autonomousLoading || busy}

                onClick={() => confirmExistingRoom(job)}>Confirm this is the same room</button>

              <p className="hh-room-match-help">Only confirm a real physical match. Similar kitchens are not necessarily the same kitchen.</p></div></div>)}{(scanProgress.phase === "error" || scanProgress.phase === "held") && scanProgress.mediaId && <button className="secondary" disabled={busy} onClick={() => { setShowScanStatus(true); setTaskRoomFilter("all"); setView("tasks"); void loadAutonomousState(); }}>View scan status</button>}</div>

      </section>}



      {!isConnected && !(view === "home" && simpleInterface) && <section className="hh-notice" role="status"><strong>Connect your household</strong><span>Sign in to load your authorized household.</span><button onClick={() => setSettingsOpen(true)}>Open Settings</button></section>}



      {view === "home" && simpleInterface && <section className="hh-view hh-consumer-home hh-minimal-today" aria-label="Today at home">

        <div className="hh-minimal-heading">

          <div><p className="hh-kicker">YOUR HOME TODAY</p><h1>A clearer picture of home.</h1>

            <p>See what needs attention, and what can wait.</p></div>

          {isConnected && <span className="hh-minimal-overview">{simpleActiveTaskCount} suggestion{simpleActiveTaskCount === 1 ? "" : "s"} to review</span>}

        </div>

        {isConnected ? <>

          <section className="hh-panel hh-minimal-primary" aria-label="Next household suggestion">

            <div className="hh-minimal-eyebrow"><span className="hh-kicker">RECOMMENDED NEXT</span>{simpleHomeTasks.length > 0 && <span className="hh-consumer-status">{simpleHomeTasks[0].status}</span>}</div>

            {simpleHomeTasks.length > 0 ? <>

              <h2>{capitalizeFirst(simpleHomeTasks[0].title.trim())}</h2>

              <p className="hh-minimal-explanation">{capitalizeFirst(simpleHomeTasks[0].detail.trim())}</p>

              {simpleHomeTasks[0].progress != null && <p className="hh-minimal-context">The latest photo suggests {simpleHomeTasks[0].progress}% progress. Completion still needs confirmation.</p>}

              <div className="hh-minimal-actions"><button type="button" onClick={() => { setTaskRoomFilter("all"); setView("tasks"); void loadAutonomousState(); }}>View task</button><button type="button" className="secondary" onClick={() => setScanOpen(true)}>Add a photo</button></div>

            </> : <>

              <h2>You’re all caught up.</h2>

              <p className="hh-minimal-explanation">Add another photo whenever you want to check for changes.</p>

              <div className="hh-minimal-actions"><button type="button" onClick={() => setScanOpen(true)}>Add a photo</button></div>

            </>}

            {simpleHomeTasks.length > 1 && <details className="hh-minimal-extra"><summary>{simpleHomeTasks.length - 1} more suggestion{simpleHomeTasks.length === 2 ? "" : "s"} to preview</summary>

              <div className="hh-consumer-task-list">{simpleHomeTasks.slice(1).map(task =>

                <button type="button" key={task.id} className="hh-consumer-task" onClick={() => { setTaskRoomFilter("all"); setView("tasks"); void loadAutonomousState(); }}>

                  <span className="hh-consumer-task-icon" aria-hidden="true">→</span>

                  <span className="hh-consumer-task-copy"><strong>{capitalizeFirst(task.title.trim())}</strong><small>{capitalizeFirst(task.detail.trim())}</small></span>

                  <span className="hh-consumer-status">{task.status}</span>

                </button>)}</div>

              </details>}

            {simpleActiveTaskCount > 1 && <button type="button" className="hh-link hh-minimal-all" onClick={() => { setTaskRoomFilter("all"); setView("tasks"); void loadAutonomousState(); }}>View all {simpleActiveTaskCount} suggestions</button>}

          </section>

          <div className="hh-minimal-quicklinks" aria-label="Your household shortcuts">

            <button type="button" onClick={() => setView("spaces")}><span className="hh-shortcut-icon"><InterfaceIcon name="spaces" size={19} /></span><span className="hh-shortcut-description"><strong>{enrolledRooms.length}</strong><span>Rooms</span></span><InterfaceIcon name="arrow" size={16} /></button>

            <button type="button" onClick={() => setView("objects")}><span className="hh-shortcut-icon"><InterfaceIcon name="objects" size={19} /></span><span className="hh-shortcut-description"><strong>{trackedObjects.length}</strong><span>Objects</span></span><InterfaceIcon name="arrow" size={16} /></button>

            <button type="button" onClick={() => { setShowScanStatus(true); setTaskRoomFilter("all"); setView("tasks"); void loadAutonomousState(); }}><span className="hh-shortcut-icon"><InterfaceIcon name="activity" size={19} /></span><span className="hh-shortcut-description"><strong>{autonomousAlerts.filter(alert => !alert.read_at).length}</strong><span>Updates</span></span><InterfaceIcon name="arrow" size={16} /></button>

          </div>

          <p className="hh-minimal-footnote">Suggestions are based on reviewed photos. Confirm completion before marking a task as finished.</p>

        </> : <section className="hh-panel hh-consumer-empty"><h2>Welcome to HomHive</h2><p>Sign in to see your rooms, tasks, and recent updates.</p><button type="button" onClick={() => setSettingsOpen(true)}>Sign in</button></section>}

      </section>}



      {view === "home" && !simpleInterface && <section className="hh-view">

        <div className="hh-view-title"><div><p className="hh-kicker">HomHive / Home</p><h1>Your home, in focus.</h1><p>Understand what is happening at home and decide what to do next.</p></div><button className="secondary" disabled={busy || !token} onClick={loadHousehold}>↻ Refresh</button></div>

        {isConnected && <div className="hh-stats">

          <button onClick={() => setView("spaces")}><span>Spaces</span><strong>{enrolledRooms.length}</strong><small>Recognized spaces</small></button>

          <button onClick={() => setView("objects")}><span>Objects</span><strong>{trackedObjects.length}</strong><small>Tracked household objects</small></button>

          <button onClick={() => { setTaskRoomFilter("all"); setView("tasks"); void loadAutonomousState(); }}><span>Suggested work</span><strong>{autonomousTasks.filter(task => ["pending", "accepted", "in_progress", "proposed"].includes(task.status)).length}</strong><small>Active household suggestions</small></button>

          <button onClick={() => { setShowScanStatus(true); setTaskRoomFilter("all"); setView("tasks"); void loadAutonomousState(); }}><span>Updates</span><strong>{autonomousAlerts.filter(alert => !alert.read_at).length}</strong><small>Recent changes and updates</small></button>

        </div>}

        {isConnected && <section className="hh-panel hh-decision-center" aria-label="Household decision center">

          <div className="hh-panel-head"><div><p className="hh-kicker">HOMHIVE / LIVE DECISIONS</p><h2>Your next best step</h2></div><button className="hh-link" onClick={() => setView("schedule")}>Set household routine →</button></div>

          <p className="hh-muted">Recommendations use your household routine and availability. Connect Calendar to check for meetings.</p>

          {coordination ? <>

            <div className="hh-context-controls">

              <fieldset><legend>Are you home?</legend><div className="hh-schedule-shortcuts">

                <button aria-pressed={coordination.presence.state === "HOME"} disabled={busy} onClick={() => void changePresence("HOME")}>Home</button>

                <button aria-pressed={coordination.presence.state === "AWAY"} disabled={busy} onClick={() => void changePresence("AWAY")}>Away</button>

                <button aria-pressed={coordination.presence.state === "UNKNOWN"} disabled={busy} onClick={() => void changePresence("UNKNOWN")}>Unknown</button>

              </div><small>This setting resets automatically.</small></fieldset>

              <fieldset><legend>Are you free for household work?</legend><div className="hh-schedule-shortcuts">

                <button aria-pressed={coordination.availability.state === "FREE"} disabled={busy} onClick={() => void changeAvailability("FREE")}>Free</button>

                <button aria-pressed={coordination.availability.state === "BUSY"} disabled={busy} onClick={() => void changeAvailability("BUSY")}>Busy</button>

                <button aria-pressed={coordination.availability.state === "UNKNOWN"} disabled={busy} onClick={() => void changeAvailability("UNKNOWN")}>Unknown</button>

              </div><small>Being home doesn't always mean being free</small></fieldset>

            </div>

            <div className="hh-decision-counts" aria-label="Current decision categories">{(["NOW", "SOON", "DEFERRED", "BLOCKED"] as const).map(group =>

              <div key={group}><strong>{coordination.groups[group]}</strong><span>{group === "NOW" ? "Ready now" : group === "SOON" ? "Soon" : group === "DEFERRED" ? "Deferred" : "Blocked"}</span></div>)}</div>

            <p className="hh-muted">{coordination.quiet_hours.active ? "Quiet hours active | " : ""}{!coordination.work_window ? "No preferred time set" : coordination.preferred_minutes_remaining ? `${coordination.preferred_minutes_remaining} minutes left in your preferred window` : "Outside your preferred work window"} | {coordination.timezone}</p>

            <div className="hh-compact-list">{coordination.tasks.slice(0, 4).map(task => <div key={task.task_id} className="hh-decision-row">

              <div><strong>{task.title}</strong><small className="hh-task-update-source">{roomDisplayName(task.room_id)}</small><p>{task.reasons.join(" · ")}</p>

                <small>{task.duration_max != null ? `${task.duration_min}-${task.duration_max} min · researched` : "Duration unknown"}{task.progress_percent != null ? ` · About ${task.progress_percent}% complete` : ""}</small>

              </div><span className={`hh-decision-badge hh-decision-${task.status.toLowerCase()}`}>{task.status === "NOW" ? "Ready" : task.status === "SOON" ? "Soon" : task.status === "DEFERRED" ? "Deferred" : "Blocked"}</span>

            </div>)}</div>

            {coordination.tasks.length === 0 && <p className="hh-empty">No tasks need attention right now. Another photo may reveal new tasks.</p>}

          </> : <p className="hh-muted">Household recommendations are temporarily unavailable.</p>}

        </section>}

        {isConnected && <section className="hh-panel hh-advisor-shortcut" aria-label="Household AI and research">

          <div><p className="hh-kicker">HELP FOR YOUR WHOLE HOME</p><h2>Helpful guidance, grounded in evidence.</h2>

            <p className="hh-muted">Get practical advice based on what HomHive has observed.</p></div>

          <button type="button" className="secondary" onClick={() => setView("automations")}>Explore recommendations</button>

        </section>}

        {isConnected && <section className="hh-panel hh-home-schedule" aria-label="Your preferred household schedule">

          <div className="hh-panel-head"><div><p className="hh-kicker">YOUR ROUTINE</p><h2>Choose when to receive suggestions</h2></div><button className="hh-schedule-link" onClick={() => setView("schedule")}>{workWindow ? "Change my schedule →" : "Set my schedule →"}</button></div>

          <p className="hh-schedule-summary">{scheduleSummary}</p>

          <p className="hh-muted">{workWindow ? "Saved for future recommendations. HomHive uses this when a researched task duration fits." : "Choose your usual household-work days and time. We'll use your preference when recommending new tasks."}</p>

          <small className="hh-schedule-disclaimer">Your routine doesn't automatically reserve time on your calendar.</small>

        </section>}

        {isConnected && householdPulse && householdPulse.suggestions.length > 0 && <section className="hh-panel" aria-label="Your household intelligence pulse" style={{marginBottom:20}}>

          <div className="hh-panel-head"><div><p className="hh-kicker">YOUR HOUSEHOLD PULSE</p><h2>What HomHive suggests next</h2></div><button className="hh-link" onClick={() => { setTaskRoomFilter("all"); setView("tasks"); void loadAutonomousState(); }}>See all work →</button></div>

          <p className="hh-muted">Suggestions are based on what HomHive has observed and how long tasks have been waiting.</p>

          <div className="hh-compact-list">{householdPulse.suggestions.slice(0,3).map(item => <div className="hh-history-entry" key={item.task_id}>

            <strong>{item.title}</strong>

            <p>{item.reasons.join(" · ")}</p>

            {item.progress_percent !== null && <p>About {item.progress_percent}% done · {item.remaining_work || item.progress_explanation || "Rescan to review what remains."}</p>}

            <small>{item.recommended_at ? `Suggested ${new Date(item.recommended_at).toLocaleString([], {weekday:"short", hour:"numeric", minute:"2-digit"})} within your preferred window` : item.research_needed ? "Time estimate not yet available" : `${item.estimate_min}-${item.estimate_max} min · source-backed estimate`}</small>

          </div>)}</div>

        </section>}

        {isConnected && autonomousTasks.some(task => ["proposed", "pending", "accepted", "in_progress"].includes(task.status) && (!task.remind_at || Date.parse(task.remind_at) <= Date.now())) && <section className="hh-panel hh-home-priority"><div className="hh-panel-head"><div><p className="hh-kicker">NEXT UP</p><h2>{[...autonomousTasks].filter(task => ["proposed", "pending", "accepted", "in_progress"].includes(task.status) && (!task.remind_at || Date.parse(task.remind_at) <= Date.now())).sort((a,b) => b.created_at.localeCompare(a.created_at))[0].title}</h2></div><button className="hh-link" onClick={() => { setTaskRoomFilter("all"); setView("tasks"); void loadAutonomousState(); }}>View task</button></div><p className="hh-muted">{[...autonomousTasks].filter(task => ["proposed", "pending", "accepted", "in_progress"].includes(task.status) && (!task.remind_at || Date.parse(task.remind_at) <= Date.now())).sort((a,b) => b.created_at.localeCompare(a.created_at))[0].evidence_summary || "Independently reviewed household work"}</p></section>}

        <div className="hh-home-grid">

          <section className="hh-panel"><div className="hh-panel-head"><h2>Your rooms</h2><button className="hh-link" onClick={() => setView("spaces")}>View rooms</button></div>

            {enrolledRooms.length === 0 ? <p className="hh-empty">Your rooms will appear after your first verified scan.</p> :

              <div className="hh-compact-list">{enrolledRooms.slice(0, 4).map(room => { const task = autonomousTasks.find(t => t.room_id === room.room_id); return <button key={room.room_id} className="hh-room-row" onClick={() => setView("spaces")}><span className="hh-room-symbol" aria-hidden="true">⌂</span><span><strong>{room.room_category ? capitalizeFirst(display(room.room_category)) : task?.room_category ? capitalizeFirst(display(task.room_category)) : "Recognized space"}</strong><small>{autonomousTasks.filter(t => t.room_id === room.room_id && ["pending", "proposed", "accepted", "in_progress"].includes(t.status)).length} active suggestions</small></span></button>; })}</div>}

          </section>

          <section className="hh-panel"><div className="hh-panel-head"><h2>Household tasks</h2><button className="hh-link" onClick={() => { setTaskRoomFilter("all"); setView("tasks"); void loadAutonomousState(); }}>All tasks →</button></div>

            {autonomousTasks.filter(t => ["pending", "accepted", "in_progress", "proposed"].includes(t.status)).length === 0 ? <p className="hh-empty">No suggestions yet. Add a photo to get started.</p> : <><p className="hh-muted">{autonomousTasks.filter(t => ["pending", "accepted", "in_progress", "proposed"].includes(t.status)).length} current suggestions · {autonomousTasks.filter(t => t.progress?.percent != null && t.status !== "completed").length} with observed progress.</p><button className="hh-inline-action" onClick={() => { setTaskRoomFilter("all"); setView("tasks"); void loadAutonomousState(); }}>View suggestions and updates →</button></>}

          </section>

        </div>

      </section>}



      {view === "automations" && <section className="hh-view" aria-label="Home automation controls">

        <div className="hh-view-title"><div><p className="hh-kicker">YOUR HOME, ON YOUR TERMS</p><h1>Automation</h1><p>Manage how HomHive helps with your home.</p></div></div>

        <div className="hh-automation-overview" role="status">

          <span className="hh-automation-signal" aria-hidden="true" />

          <div><strong>{isConnected ? "Household connected" : "Connect your household"}</strong><p>{isConnected ? "Add photos and review suggested tasks." : "Sign in to use household automation."}</p></div>

          {!isConnected && <button className="secondary" onClick={() => setSettingsOpen(true)}>Connect</button>}

        </div>

        <section className="hh-advisor-section" aria-label="Household intelligence and research">

          <div className="hh-advisor-heading"><p className="hh-kicker">HOUSEHOLD INTELLIGENCE</p><h2>Clear guidance for your home</h2><p>Get a practical suggestion or look up an unfamiliar household issue.</p></div>

          <div className="hh-advisor-grid">

            <section className="hh-panel hh-advisor-card" aria-label="AI household planner">

              <div className="hh-advisor-card-heading"><span className="hh-advisor-symbol" aria-hidden="true">✧</span><div><h3>What should I focus on?</h3><small>Powered by NVIDIA Nemotron on Nebius Token Factory</small></div></div>

              <p>Get a useful recommendation based on your tasks and availability. You can connect Google Calendar to check for conflicts.</p>

              <div className="hh-advisor-context"><span>{advisorPlan?.tasks.length ?? 0} reviewed tasks</span><span>{advisorPlan?.groups.NOW ?? 0} ready now</span><span>{advisorPlan?.groups.BLOCKED ?? 0} need attention first</span></div>

              <button type="button" disabled={!isConnected || !advisorPlan?.tasks.length || nemotronBusy || (Boolean(calendarSession) && !calendarPlan)} onClick={() => void askNemotron()}>{nemotronBusy ? "Checking your household…" : "Suggest my next step"}</button>

              <div className="hh-advisor-autoplan">

                <div><strong>Update recommendations automatically</strong><small>Updates advice when your household plan changes. Additional AI usage may incur charges.</small></div>

                <button type="button" role="switch" aria-label="Automatically refresh Nemotron suggestions" aria-checked={autoPlanEnabled} className={`hh-advisor-switch${autoPlanEnabled ? " is-on" : ""}`} onClick={() => {lastAutoPlanSignature.current = ""; setAutoPlanEnabled(current => !current);}}><span aria-hidden="true" /></button>

              </div>

              {coordination?.latest_automatic_coordination?.status === "completed" && <div className="hh-advisor-result" role="status">

                <p className="hh-kicker">AUTOMATIC UPDATE FROM LAST SCAN</p>

                <p>{coordination.latest_automatic_coordination.advice?.summary || "HomHive reviewed the latest household evidence."}</p>

                {coordination.latest_automatic_coordination.advice?.reason && <p><strong>Why:</strong> {coordination.latest_automatic_coordination.advice.reason}</p>}

                <small>{coordination.latest_automatic_coordination.researched_tasks ? `${coordination.latest_automatic_coordination.researched_tasks} task researched with Tavily · ` : ""}Planning: {coordination.latest_automatic_coordination.planning_status.replaceAll("_", " ")}</small>

              </div>}

              {nemotronError && <p className="hh-advisor-error" role="alert">{nemotronError}</p>}

              {nemotronAdvice && <div className="hh-advisor-result" role="status">

                <p className="hh-kicker">{nemotronAdviceContext === currentAdvisorContext ? "HOMHIVE RECOMMENDS" : "PREVIOUS HOMHIVE RECOMMENDATION"}</p>

                {nemotronAdviceContext !== currentAdvisorContext && <p className="hh-muted">Your household conditions changed since this advice was generated. Refresh the suggestion before acting.</p>}

                {nemotronAdvice.selected_task_id ? <>

                  <h4>{advisorPlan?.tasks.find(task => task.task_id === nemotronAdvice.selected_task_id)?.title ?? nemotronAdvice.summary}</h4>

                  <p>{nemotronAdvice.summary}</p><p><strong>Why:</strong> {nemotronAdvice.reason}</p>

                </> : <>

                  <h4>Here's what needs to happen first</h4>

                  <p>{nemotronAdvice.summary}</p>

                  <p><strong>Why:</strong> {nemotronAdvice.reason}</p>

                  <button type="button" className="secondary" onClick={reviewHouseholdReadiness}>Review household readiness</button>

                  <small>No task is ready to schedule yet. Check the details before proceeding.</small>

                </>}

                <small>{nemotronAdvice.model ? `NVIDIA Nemotron on Nebius · ${nemotronAdvice.model}` : "Based on existing household status"}</small>

              </div>}

              <small>Suggestions only. Your existing approval and safety rules always apply.</small>

            </section>

            <section className="hh-panel hh-advisor-card" aria-label="Tavily household research">

              <div className="hh-advisor-card-heading"><span className="hh-advisor-symbol" aria-hidden="true">⌕</span><div><h3>Find a trustworthy answer</h3><small>Research powered by Tavily</small></div></div>

              <p>Ask about a plant, appliance, repair, or unfamiliar household situation. You'll see sources you can open.</p>

              <form onSubmit={event => {event.preventDefault(); void researchHousehold();}}>

                <label htmlFor="hh-guidance-question">What would you like help with?</label>

                <textarea id="hh-guidance-question" value={guidanceQuery} maxLength={500} rows={3} onChange={event=>setGuidanceQuery(event.target.value)} placeholder="Example: What should I check if my dishwasher smells bad?" />

                <div className="hh-advisor-examples" aria-label="Example household questions">

                  {["Why are my houseplant leaves turning yellow?", "How can I check a dishwasher odor safely?", "When should I replace an HVAC filter?"].map(example => <button className="secondary" type="button" key={example} onClick={() => {setGuidanceQuery(example);setGuidanceResult(null);setGuidanceError("");}}>{example}</button>)}

                </div>

                <button type="submit" disabled={!isConnected || guidanceBusy || guidanceQuery.trim().length < 3}>{guidanceBusy ? "Looking for sources…" : "Find guidance"}</button>

              </form>

              {guidanceError && <p className="hh-advisor-error" role="alert">{guidanceError}</p>}

              {guidanceResult && <div className="hh-advisor-result" role="status"><p className="hh-kicker">SOURCES FOUND</p>

                {guidanceResult.evidence.length === 0 ? <p>No useful sources were found. Try a more specific question.</p> :

                  <div className="hh-advisor-sources">{guidanceResult.evidence.map((entry, i) => {

                    const excerpt = readableResearchExcerpt(entry.content);

                    return <article key={`${entry.url}-${i}`}>

                      <strong>{entry.title}</strong><p>{excerpt.slice(0, 230)}{excerpt.length > 230 ? "…" : ""}</p>

                      <a href={entry.url} target="_blank" rel="noopener noreferrer">Open source {i + 1}</a>

                    </article>;

                  })}</div>}

                <small>Web results are informational, not evidence that a household condition exists. Follow manufacturer instructions for risky work.</small>

              </div>}

              <small>Only your question is used for this search. Your photos and household history aren't included.</small>

            </section>

          </div>

        </section>

        <div className="hh-automation-grid">

          <section className="hh-panel hh-automation-card"><span className="hh-automation-icon" aria-hidden="true">▣</span><h2>Photo intelligence</h2><p>Analyze a household photo to discover tasks. New photos can update existing tasks.</p><span className="hh-automation-status">{isConnected ? "Ready for scans" : "Sign in required"}</span><button disabled={!isConnected} onClick={() => setScanOpen(true)}>Add a photo</button></section>

          <section className="hh-panel hh-automation-card"><span className="hh-automation-icon" aria-hidden="true">◷</span><h2>My household routine</h2><p>Choose when to suggest chores. Your preferences help with recommendations. Nothing is booked automatically.</p><span className="hh-automation-status">{workWindow ? "Routine saved" : "Not set up"}</span><button className="secondary" onClick={() => setView("schedule")}>{workWindow ? "Edit my routine" : "Set my routine"}</button></section>

          <section className="hh-panel hh-automation-card"><span className="hh-automation-icon" aria-hidden="true">☾</span><h2>Quiet hours</h2><p>Defer noisy or unclassified work during your chosen hours without losing task priority.</p><span className="hh-automation-status">{coordination ? savedQuiet?.enabled ? `Enabled${quietActiveNow ? " · active now" : ""}` : "Disabled" : "Available when connected"}</span>{savedQuiet && <p className="hh-muted">Household time: {quietLocalTime} ({savedQuiet.timezone})</p>}<button className="secondary" onClick={openQuietHoursEditor}>Manage quiet hours</button></section>

          <section id="hh-household-readiness" tabIndex={-1} className="hh-panel hh-automation-card"><span className="hh-automation-icon" aria-hidden="true">⌂</span><h2>Presence and availability</h2><p>Tell HomHive if you are home and free. These are separate, expiring signals.</p><span className="hh-automation-status">{coordination ? `${coordination.presence.state.toLowerCase()} · ${coordination.availability.state.toLowerCase()}` : "Not set"}</span>

            {coordination && <div className="hh-automation-controls"><strong>Where are you?</strong><div className="hh-automation-chips">{(["HOME","AWAY","UNKNOWN"] as const).map(state => <button key={state} type="button" disabled={busy} aria-pressed={coordination.presence.state === state} onClick={() => void changePresence(state)}>{state === "HOME" ? "Home" : state === "AWAY" ? "Away" : "Unknown"}</button>)}</div>

            <strong>Available for chores?</strong><div className="hh-automation-chips">{(["FREE","BUSY","UNKNOWN"] as const).map(state => <button key={state} type="button" disabled={busy} aria-pressed={coordination.availability.state === state} onClick={() => void changeAvailability(state)}>{state === "FREE" ? "Free" : state === "BUSY" ? "Busy" : "Unknown"}</button>)}</div></div>}

          </section>

          <section className="hh-panel hh-automation-card"><span className="hh-automation-icon" aria-hidden="true">✓</span><h2>Suggestions and progress</h2><p>Evidence-backed suggestions are saved to their rooms. View progress from newer photographs.</p><span className="hh-automation-status">{activeHouseholdTasks.length} active tasks</span><button className="secondary" onClick={() => {setTaskRoomFilter("all");setView("tasks");}}>View household tasks</button></section>



        </div>

        <section className="hh-panel hh-automation-card" aria-label="Google Calendar free busy connection">

          <div className="hh-advisor-card-heading"><span className="hh-advisor-symbol" aria-hidden="true">▦</span><div><h2>Google Calendar</h2><small>Checks busy times, not event details</small></div></div>

          <p>Connect your calendar to avoid scheduling chores during meetings. HomHive checks busy times without reading event titles or creating events.</p>

          {calendarPlan?.calendar ? <div className="hh-advisor-result" role="status">

            <strong>Connected: Google Calendar (primary)</strong>

            <p>{calendarPlan.calendar.busy_now ? "You're currently marked busy in Google Calendar." : calendarPlan.calendar.next_busy_starts_at

              ? `Next busy event: ${new Date(calendarPlan.calendar.next_busy_starts_at).toLocaleTimeString([], {hour: "numeric", minute: "2-digit"})}`

              : "No scheduled conflicts found in the checked time range."}</p>

            <p>{calendarPlan.calendar.effective_work_minutes} minutes fit before the next calendar conflict or your routine ends. This does not prove you are personally available.</p>

            <small>Last checked {new Date(calendarPlan.evaluated_at).toLocaleTimeString([], {hour: "numeric", minute: "2-digit"})}. Only live Google results are used.</small>

          </div> : <p className="hh-muted">{calendarSession ? "Calendar check needs refreshing." : "Not connected. HomHive currently uses your preferred routine and manually confirmed availability."}</p>}

          {calendarError && <p className="hh-advisor-error" role="alert">{calendarError}</p>}

          <div className="hh-automation-chips">

            {!calendarSession && <button type="button" disabled={!isConnected || calendarBusy || !googleCalendarClientId} onClick={() => void connectCalendar()}>{calendarBusy ? "Connecting…" : "Connect Google Calendar"}</button>}

            {calendarSession && <><button type="button" disabled={calendarBusy} onClick={() => void refreshCalendar()}>{calendarBusy ? "Checking…" : "Refresh calendar"}</button>

              <button type="button" className="secondary" onClick={() => {setCalendarSession(null);setCalendarPlan(null);setCalendarError("");}}>Disconnect</button></>}

          </div>

          {!googleCalendarClientId && <small>Google Calendar connection isn't available yet.</small>}

          <small>Calendar access lasts for this browser session. You can disconnect anytime.</small>

        </section>

        <section className="hh-panel hh-automation-roadmap"><h2>Additional connections</h2><p></p></section>

      </section>}



      {view === "schedule" && <section className="hh-view" aria-label="Household work schedule">

        <div className="hh-view-title"><div><p className="hh-kicker">HOMHIVE / YOUR ROUTINE</p><h1>Your schedule</h1><p>Tell HomHive when you <em>prefer</em> to tackle household work. New suggestions can be matched to the time you set.</p></div></div>

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

            <div className="hh-schedule-times"><TimeWheelField id="hh-window-from" label="From" value={windowStart} onChange={setWindowStart}/>

              <span aria-hidden="true" className="hh-schedule-to">to</span><TimeWheelField id="hh-window-until" label="Until" value={windowEnd} onChange={setWindowEnd}/>

            </div>

            <p className="hh-schedule-selection">Time zone: {scheduleZone} · Single-day windows only</p>

          </fieldset>

          {scheduleValidation && <p className="hh-schedule-error" role="alert">{scheduleValidation}</p>}

          {scheduleModified && !scheduleValidation && <p className="hh-schedule-unsaved" role="status">{workWindow ? "You have unsaved schedule changes." : "Your schedule isn't saved yet."}</p>}

          <div className="hh-schedule-save"><button type="button" disabled={!isConnected || savingWindow || Boolean(scheduleValidation) || !scheduleModified} onClick={() => void saveWorkWindow()}>{savingWindow ? "Saving..." : "Save my schedule"}</button>

            {workWindow && scheduleModified && <button type="button" className="secondary" onClick={() => {setWindowStart(workWindow.start_time);setWindowEnd(workWindow.end_time);setWindowWeekdays([...workWindow.weekdays]);}}>Discard changes</button>}

          </div>

          {!isConnected && <p className="hh-muted">Sign in to save your household preference.</p>}

          {workWindow && <p className="hh-schedule-saved" role="status"><strong>Saved:</strong> {scheduleSummary} ({workWindow.timezone})</p>}

        </section>

        {isConnected && savedQuiet && <section className="hh-panel hh-schedule-editor" aria-label="Quiet hours settings">
          <div className="hh-panel-head"><div><p className="hh-kicker">HOUSEHOLD SETTINGS</p><h2>Quiet hours</h2></div><span className="hh-schedule-state">{savedQuiet.enabled ? quietActiveNow ? "Active now" : "Outside quiet hours" : "Off"}</span></div>
          <p className="hh-muted">{savedQuiet.enabled ? `${readableWorkTime(savedQuiet.start_time)} to ${readableWorkTime(savedQuiet.end_time)} in ${savedQuiet.timezone}.` : "Quiet hours are currently off."}</p>
          <p className="hh-muted">Local household time: {quietLocalTime}. These settings stay with your household when you sign in from another time zone.</p>
          <button type="button" className="secondary" onClick={openQuietHoursEditor}>Edit quiet hours</button>
        </section>}

                <section className="hh-panel hh-schedule-explainer"><h2>What happens next?</h2><p>When HomHive discovers an evidence-supported task, it can research how long the task usually takes, then suggest a time within your chosen work window. You can still do the task whenever you want.</p><p><strong>Your routine is not a calendar booking.</strong> Connect Google Calendar in Automation to check for conflicts when requesting advice. HomHive does not book events automatically.</p><button className="hh-link" onClick={() => { setTaskRoomFilter("all"); setView("tasks"); void loadAutonomousState(); }}>View suggested tasks →</button></section>

      </section>}



      {view === "spaces" && <section className="hh-view">

        <div className="hh-view-title"><div><p className="hh-kicker">Your household</p><h1>{simpleInterface ? "Rooms" : "Spaces"}</h1><p>Rooms identified from your photos.</p></div><button className="secondary" onClick={loadAutonomousState}>↻ Refresh</button></div>

        {enrolledRooms.length === 0 ? <div className="hh-panel hh-empty">No rooms added yet. Add a photo of the room to get started.</div> :

          <div className="hh-home-grid">{enrolledRooms.map(room => {

            const tasks = autonomousTasks.filter(task => task.room_id === room.room_id);

            const label = room.room_category || tasks.find(t => t.room_category)?.room_category;

            return <section className="hh-panel hh-space-card" key={room.room_id}>

              <p className="hh-kicker">SPACE</p>

              <h2>{label ? capitalizeFirst(display(label)) : "Recognized space"}</h2>

              <p className="hh-muted">{room.room_category_source === "user_confirmed" ? "Room name confirmed by you" : "Room type suggested from your photo"}</p>

              {editingRoomId === room.room_id ? <div className="hh-room-correction">

                <label>Correct room name<input autoFocus maxLength={120} value={roomLabelDraft}

                  onChange={event => setRoomLabelDraft(event.target.value)} placeholder="e.g. Walk-in closet" /></label>

                <div className="hh-task-actions"><button disabled={autonomousLoading} onClick={() => void saveRoomCorrection(room.room_id)}>Save</button><button className="secondary" onClick={() => setEditingRoomId(null)}>Cancel</button></div>

              </div> : <button className="hh-link" onClick={() => {setEditingRoomId(room.room_id); setRoomLabelDraft(label || "");}}>Correct room name</button>}

              <p className="hh-muted">{tasks.length} task{tasks.length === 1 ? "" : "s"} recorded</p>

              {tasks.length ? <div className="hh-compact-list">{tasks.filter(t => !["dismissed", "completed"].includes(t.status)).slice(0, 3).map(task => <div className="hh-history-entry" key={task.id}><strong>{task.title}</strong><small>Created {new Date(task.created_at).toLocaleString()}</small></div>)}</div> : <p className="hh-empty">No tasks found in this room yet.</p>}

              <button className="hh-link" onClick={() => { setTaskRoomFilter(room.room_id); setView("tasks"); }}>View room tasks</button>

            </section>;

          })}</div>}

      </section>}



      {view === "objects" && <section className="hh-view" aria-label="Tracked household objects">

        <div className="hh-view-title"><div><p className="hh-kicker">HomHive / Object intelligence</p><h1>Tracked objects</h1>

          <p>Plants, appliances and other observed objects, with their evidence and related household tasks.</p></div>

          <button className="secondary" disabled={busy || !token} onClick={() => void loadAutonomousState()}>↻ Refresh</button></div>

        {trackedObjects.length ? <div className="hh-object-card-grid">{trackedObjects.map(item =>

          <HouseholdObjectCard key={item.id} item={item} api={api} tasks={autonomousTasks} rooms={enrolledRooms}

            onMove={async (id,roomId) => {

              await api.updateObjectLocation(id,roomId);

              await loadAutonomousState();

            }}/>)}</div> : <div className="hh-panel hh-empty">No tracked objects yet. Scan a close-up of a plant or appliance to begin.</div>}

      </section>}

      {view === "tasks" && <section className="hh-view" aria-label="Household work">

        <div className="hh-view-title"><div><p className="hh-kicker">YOUR HOUSEHOLD</p><h1>Your tasks</h1><p>Review tasks suggested from your household photos.</p></div><button className="secondary" disabled={busy} onClick={refreshAutonomousTasks}>↻ Check updates</button></div>

        {scanJobs.some(job => ["pending", "processing", "queued", "retrying"].includes(job.state)) && <div className="hh-scan-message" role="status"><span className="pulse"/> Your photo is being reviewed. Any verified suggestions will appear here.</div>}

        {scanJobs.some(job => job.state === "held_unverified_room") && <div className="hh-scan-message"><strong>Some photos need a room match.</strong><p>HomHive couldn't verify which physical room they show. If a photograph is of a new space, you can add that specific space in Recent scan status below.</p><button className="secondary" onClick={() => setShowScanStatus(true)}>Review room matches</button></div>}

        {autonomousNote && <p className="hh-muted" role="status">{autonomousNote}</p>}

        {autonomousAlerts.some(alert => !alert.read_at) && <section className="hh-panel" aria-label="Household task updates" style={{marginBottom:20}}>

          <h2>HomHive has suggestions for you</h2>

          <p className="hh-muted">New tasks and photo-based progress updates.</p>

          {autonomousAlerts.filter(alert => !alert.read_at).slice(0,5).map(alert => {

            const task = autonomousTasks.find(item => item.id === alert.task_id);

            const room = task ? roomDisplayName(task.room_id, task.room_category) : "";

            const isEarlierTimingAdvice = /^a good time for:/i.test(alert.title) || /preferred household.work window|availability isn't synchronized|check your real calendar before starting/i.test(alert.detail);

            const heading = alert.title.replace(/^a good time for:\s*/i, "Suggested: ");

            return <div key={alert.id} className={`hh-history-entry hh-consumer-alert${simpleInterface ? " hh-consumer-alert-compact" : ""}`}>

              <strong>{heading}</strong>

              <p className="hh-task-update-source">{task ? (/unassigned|unknown/i.test(room) ? "Location not confirmed" : room) : "Household update"}</p>

              {isEarlierTimingAdvice ? <>

                <p className="hh-muted">Earlier suggestion. This is not confirmation that the time is free now.</p>

                <details className="hh-alert-history"><summary>Original scheduling note</summary>

                  <p>The original suggestion used the household routine at that time, not a verified current calendar opening.</p>

                  <p>{alert.detail}</p><small>{new Date(alert.created_at).toLocaleString()}</small>

                </details>

              </> : <><p>{alert.detail}</p>{!simpleInterface && <small>{new Date(alert.created_at).toLocaleString()}</small>}</>}

              <div className="hh-task-actions"><button className="secondary" onClick={() => void acknowledgeAlert(alert.id)}>Got it</button></div>

            </div>;

          })}

        </section>}

        <div className="hh-room-task-toolbar">

          <div><strong>Tasks by space or object</strong><p>See which room or photographed object prompted each task, with the supporting evidence.</p></div>

          <HomHiveSelect id="hh-task-room-filter" label="Space" className="hh-task-choice"

            value={taskRoomFilter} onChange={setTaskRoomFilter}

            choices={[{value:"all",label:`All spaces (${activeHouseholdTasks.length})`}, ...enrolledRooms.map(room => ({value:room.room_id,label:`${roomDisplayName(room.room_id)} (${activeHouseholdTasks.filter(task => task.room_id === room.room_id).length})`}))]} />

        </div>

        {visibleHouseholdTasks.length === 0 ? <section className="hh-panel hh-friendly-empty"><h2>No tasks {taskRoomFilter === "all" ? "to review" : "for this room"}</h2><p>New suggestions will appear here after a photo is reviewed.</p><button className="secondary" onClick={() => {setScanOpen(true);setTaskRoomFilter("all");}}>Add a photo</button></section> :

          <div className="hh-room-task-sections">{groupedHouseholdTasks.map(group => <section key={group.roomId} className="hh-room-task-section" aria-label={`${group.label} tasks`}>

            <div className="hh-room-task-heading"><div><p className="hh-kicker">{group.tasks.some(task => objectKindForTask(task) && ["", "unassigned space", "indoor plants"].includes((enrolledRooms.find(room => room.room_id === task.room_id)?.room_category || task.room_category || "").toLowerCase())) ? "OBSERVED OBJECT" : "SPACE"}</p><h2>{group.label}</h2></div><span>{group.tasks.length} active {group.tasks.length === 1 ? "task" : "tasks"}</span></div>

            <div className="hh-task-grid">{group.tasks.map(task => <article className={`hh-panel hh-intelligent-task${simpleInterface ? " hh-simple-task-card" : ""}`} key={task.id}>

              <div className="hh-task-top"><span className="hh-task-space">{group.label}</span><span className="hh-task-date">Added {new Date(task.created_at).toLocaleDateString()}</span></div>

              <h3>{capitalizeFirst(task.title.trim())}</h3>

              <p className="hh-task-description">{(task.action || task.evidence_summary || "Photo-supported household suggestion").slice(0,220)}{(task.action || task.evidence_summary || "").length > 220 ? "…" : ""}</p>

              <div className="hh-task-metadata"><span>{task.status === "in_progress" ? "In progress" : task.status === "proposed" ? "Needs approval" : task.status === "accepted" ? "Accepted" : "Suggested"}</span><span>{task.effort_min == null ? "Time not estimated" : `${task.effort_min}${task.effort_max != null && task.effort_max !== task.effort_min ? `-${task.effort_max}` : ""} min estimated`}</span></div>

              {task.progress && <div className="hh-task-progress" role="status">

                <strong>{task.progress.estimated ? "About " : ""}{task.progress.percent}% of visible goal reached</strong>

                <div role="progressbar" aria-label={`Visible progress for ${task.title}`} aria-valuenow={task.progress.percent} aria-valuemin={0} aria-valuemax={100} className="hh-task-progress-track"><div style={{width:`${task.progress.percent}%`}} /></div>

                {task.progress.next_step && <p className="hh-task-next"><strong>Still needed:</strong> {task.progress.next_step}</p>}

                {/dish|sink|plate|wash|clean|sanitize|wipe|scrub/i.test(task.title + " " + task.action) && <p className="hh-task-caution">A cleared surface does not prove items were washed or put away. Confirm the actual work separately.</p>}

                <details className="hh-task-evidence"><summary>Photo review details</summary><p>{task.progress.explanation}</p><small>Reviewed {new Date(task.progress.reviewed_at).toLocaleString()}</small></details>

              </div>}

              {objectKindForTask(task) && <section className="hh-object-insight" aria-label={`About ${objectDisplayName(task)}`}>

                <strong>{objectKindForTask(task) === "plant" ? "Plant insight" : "Appliance insight"} · {objectDisplayName(task)}</strong>

                <p>{task.observed_object?.identity_status === "tentative" ? "Possible identity from the reviewed image, not a confirmed identification." : "Exact species or model not yet verified."}</p>

                <p><b>What HomHive observed:</b> {task.observed_object?.visible_evidence?.join(" ") || task.evidence_summary || "The object needs further visual inspection."}</p>

                <p className="hh-muted">Web research provides possible explanations and next steps, not a definitive diagnosis.</p>

              </section>}

              {task.automatic_guidance && <details className="hh-task-evidence" open={Boolean(objectKindForTask(task))}><summary>Related guidance</summary>

                <p>{task.automatic_guidance.note}</p><ul>{task.automatic_guidance.sources.map((source,i) => <li key={source.url}><a href={source.url} target="_blank" rel="noopener noreferrer">{source.title || `Source ${i+1}`}</a></li>)}</ul>

              </details>}

              {task.recommended_at && <details className="hh-task-evidence"><summary>Earlier suggested time</summary><p>{new Date(task.recommended_at).toLocaleString([], {weekday:"short",hour:"numeric",minute:"2-digit"})} was suggested from the household routine. Check current availability and calendar conflicts before starting.</p>{!simpleInterface && task.effort_max != null && task.effort_max > 0 && new Date(task.recommended_at).getTime() > Date.now() && <button type="button" className="secondary" onClick={() => exportCalendarTask(task)}>Download suggested calendar slot (.ics)</button>}</details>}

              <div className="hh-task-actions">{task.status === "proposed" && <button disabled={busy} onClick={() => decideAutonomousTask(task.id,"accept")}>Approve</button>}{["pending", "accepted", "in_progress"].includes(task.status) && <button disabled={busy} onClick={() => decideAutonomousTask(task.id,"done")}>I did this · verify later</button>}{["pending", "proposed"].includes(task.status) && <button className="secondary" disabled={busy} onClick={() => decideAutonomousTask(task.id,"remind")}>Remind later</button>}{["pending", "proposed", "accepted", "in_progress"].includes(task.status) && <button className="hh-text-danger" disabled={busy} onClick={() => decideAutonomousTask(task.id,"decline")}>Dismiss</button>}</div>

              <details className="hh-task-evidence" onToggle={event => {if (event.currentTarget.open) void showTaskTimeline(task.id);}}><summary>Why was this suggested?</summary><p><strong>Observed:</strong> {task.evidence_summary || "Reviewed photo evidence"}</p><p><strong>Desired result:</strong> {task.criteria}</p><p><strong>Action:</strong> {task.action}</p>{task.estimate_rationale && <p><strong>Time estimate:</strong> {task.estimate_rationale}</p>}{task.estimate_sources?.length ? <p><strong>References:</strong> {task.estimate_sources.map((url,i) => <span key={url}><a href={url} target="_blank" rel="noopener noreferrer">Source {i+1}</a> </span>)}</p> : null}

              {taskTimelines[task.id] && <div className="hh-compact-list"><h4>Previous photo reviews</h4>{taskTimelines[task.id].events.filter(event => ["discovery", "verification", "user_decision"].includes(event.kind)).map((event,index) => <div className="hh-history-entry" key={`${event.kind}-${index}`}><strong>{event.kind === "verification" ? "Photo recheck" : event.kind === "discovery" ? "Task found" : "Your decision"}</strong><p>{String(event.detail.reason || event.detail.decision || "Review recorded")}</p><small>{new Date(event.created_at).toLocaleString()}</small></div>)}</div>}

              </details>

            </article>)}</div>

          </section>)}</div>}

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

          {!scanJobs.length ? <p>Your scans will appear here after you add a photo.</p> :

            <div className="hh-review-list">{scanJobs.slice(0, 8).map(job => {

              const review = job.review_summary;

              return <article className="hh-scan-review" key={job.id}>

                <div className="hh-review-head"><strong>{job.state.replaceAll("_", " ")}</strong>

                  <small>{job.updated_at ? new Date(job.updated_at).toLocaleString() : ""}</small></div>

                {job.message && <p>{job.message}</p>}

                {job.state === "held_unverified_room" && <div className="hh-scan-message"><p>HomHive isn't sure which room this shows. Confirm whether it is a new room or an existing one.</p><button className="secondary" disabled={autonomousLoading || busy} onClick={() => void enrollHeldRoom(job)}>{autonomousLoading ? "Adding space..." : "Add this photo as a new space"}</button><div className="hh-room-match-panel"><p className="hh-room-match-heading">Or link this image to an existing space</p>

              <HomHiveSelect id={`task-room-${job.id}`} label="Matching physical room" value={heldRoomChoices[job.media_id] || ""}

                onChange={value => setHeldRoomChoices(current => ({...current, [job.media_id]: value}))}

                choices={[{value: "", label: "Choose a registered space"}, ...enrolledRooms.map(room => ({value: room.room_id, label: roomDisplayName(room.room_id), detail: "Previously registered space"}))]} /><button className="hh-confirm-room" disabled={!heldRoomChoices[job.media_id] || autonomousLoading || busy}

                onClick={() => confirmExistingRoom(job)}>Confirm this is the same room</button>

              <p className="hh-room-match-help">Use this only when both photos depict the same physical room.</p></div></div>}

                {job.state === "failed" && <div className="hh-scan-message hh-scan-problem"><p>{job.message || "The photo review couldn't finish. Your photo is saved."} Try again if the issue was temporary, or choose a clearer photograph if the image itself is difficult to interpret.</p><button className="secondary" disabled={busy} onClick={() => void retryFailedScan(job.media_id)}>Retry saved photo</button></div>}

                {review ? <>

                  {job.state !== "completed" && <p>This is the previous completed review; a new review is in progress.</p>}

                  {review.scene_focus && <section className="hh-object-insight" aria-label="Photo focus">

                    <strong>{review.scene_focus.focus === "object" ? "Close-up: object" : review.scene_focus.focus === "hybrid" ? "Object within a space" : review.scene_focus.focus === "space" ? "Wide view: space" : "View still uncertain"}</strong>

                    <p>{review.scene_focus.basis}</p>

                    {review.scene_focus.focus === "object" && <p>You can review this object even if its room is unknown.</p>}

                    {review.scene_focus.focus === "hybrid" && <p>The object and room are tracked separately until the location is clear.</p>}

                  </section>}

                  <p><strong>Room context:</strong> {review.room_category || "Not established"}</p>

                  {review.room_identity_source === "user_confirmed" && <p>Room match confirmed by you.</p>}

                  <p><strong>Proposed:</strong> {review.proposed_count ?? 0} · <strong>Approved:</strong> {review.approved_count ?? 0} · <strong>New tasks:</strong> {review.created_count ?? 0}</p>

                  {review.automatic_coordination && <div className="hh-scan-message"><strong>Planning update</strong>

                    <details className="hh-plan-detail"><summary>Research and planning details</summary><p>Research: {capitalizeFirst(review.automatic_coordination.research_status?.replaceAll("_", " ") || "Pending")} · Recommendation: {capitalizeFirst(review.automatic_coordination.planning_status?.replaceAll("_", " ") || "Pending")}</p></details>

                    {review.automatic_coordination.advice && <p>{review.automatic_coordination.advice.summary} {review.automatic_coordination.advice.reason}</p>}

                    {review.automatic_coordination.object_insights?.map(item => <div className="hh-object-insight" key={item.object_id}>

                      <strong>{item.kind === "plant" ? "Plant" : "Appliance"}: {item.label}</strong>

                      <p>{item.explanation}</p>

                      <p><b>Observed:</b> {item.visible_evidence.join(" ")}</p>

                      {item.research_sources?.length ? <div><b>What research suggests:</b><ul>{item.research_sources.map((source, i) =>

                        <li key={`${source.url}-${i}`}>{source.excerpt && <span>{source.excerpt} </span>}<a href={source.url} target="_blank" rel="noopener noreferrer">{source.title}</a></li>)}</ul></div> : null}

                    </div>)}

                    {review.automatic_coordination.scene_research?.map((topic,index) => <div key={`${topic.topic}-${index}`}>

                      <p><strong>{topic.topic === "plant_care" ? "Plant information" : "Appliance information"}:</strong> {topic.note}</p>

                      {topic.sources.length ? <ul>{topic.sources.map((source,i) =>

                        <li key={`${source.url}-${i}`}><a href={source.url} target="_blank" rel="noopener noreferrer">{source.title || `Research source ${i+1}`}</a></li>)}</ul> : <p>No useful reference sources were found for this photo.</p>}

                    </div>)}

                  </div>}

                  {review.evidence_reason === "no_visible_claims" ? <p>No issue was identified in this photo. That does not mean the area is completely clean.</p> :

                    review.evidence_reason === "claims_not_corroborated" ? <p>Not enough clear evidence to suggest a task.</p> : null}

                  {review.verification === "no_corroborated_evidence" && !review.evidence_reason ?

                    <p>The photo wasn't clear enough to suggest a task. Try a well-lit photo showing more of the room.</p> :

                    review.proposed_count === 0 ? <p>No task was suggested from this photo. The image may not show everything.</p> : null}

                  {(review.evidence?.length ?? 0) > 0 && <details><summary>What HomHive noticed</summary>

                    <ul>{review.evidence?.map((fact, index) => <li key={index}>{fact}</li>)}</ul></details>}

                  {(review.proposal_reviews?.length ?? 0) > 0 && <details><summary>How tasks were reviewed</summary>

                    <ul>{review.proposal_reviews?.map((item, index) => <li key={index}>

                      <strong>{item.title}</strong> · {item.decision}

                      {item.reviewer_explanation && <p>{item.reviewer_explanation}</p>}

                      {item.reason && <small>{item.reason.replaceAll("_", " ")}</small>}

                    </li>)}</ul></details>}

                </> : job.state === "completed" ? <p>Detailed notes are unavailable for this earlier scan.</p> : null}

                {job.state === "completed" && <button className="secondary" disabled={busy || Boolean(recheckingMediaId)} onClick={() => void recheckCompletedJob(job)}>

                  Reanalyze saved photo (uses AI credits)

                </button>}

              </article>;

            })}</div>}

          {scanProgress?.mediaId && ["error", "held"].includes(scanProgress.phase) && <button className="secondary" disabled={busy} onClick={retryLatestScan}>Retry scan</button>}

        </details>

      </section>}



      {view === "activity" && <section className="hh-view"><div className="hh-view-title"><div><p className="hh-kicker">Timeline</p><h1>Activity</h1><p>See recent scans and changes to your home.</p></div><button className="secondary" disabled={busy || !token} onClick={loadHousehold}>↻ Refresh</button></div>

        <section className="hh-panel">{!historyLoaded ? <p className="hh-empty">Load household history to see activity.</p> : history.length === 0 ? <p className="hh-empty">Your activity will appear here after your first scan.</p> : <div className="hh-compact-list">{[...history].sort((a,b)=>b.timestamp.localeCompare(a.timestamp)).map(item => <div key={item.id} className="hh-history-entry"><strong>{capitalizeFirst(display(item.location))} · {conditionSummary(item)}</strong><p>{needsReview(item) ? "Unverified" : evidenceStatus(item)} · {new Date(item.timestamp).toLocaleString()}</p><details><summary>Evidence</summary><p>{observationEvidence(item)}</p><small>{displayCategory(item.category)} · Estimated level {Math.round(item.value * 100)}%</small></details></div>)}</div>}</section>

      </section>}



      {scanOpen && <div className="hh-modal-backdrop" onClick={() => setScanOpen(false)}>

        <section role="dialog" aria-modal="true" aria-labelledby="hh-scan-title" className="hh-modal" onClick={e => e.stopPropagation()}>

          <div className="hh-panel-head"><h2 id="hh-scan-title">Add a household photo</h2><button type="button" className="hh-icon-button" aria-label="Close scan" onClick={() => setScanOpen(false)}>✕</button></div>

          {!isConnected ? <div className="hh-pending" role="status" style={{display:"grid",gap:".75rem",padding:"1.2rem",marginTop:"1.2rem"}}>

            <strong style={{fontSize:"1.05rem"}}>Sign in to upload files</strong>

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

            <div className="hh-task-actions"><button disabled={busy || !file || !isConnected} onClick={upload}>{busy ? "Working..." : "Upload and analyze"}</button>{media?.processing === "retry_required" && <button className="secondary" disabled={busy || !isConnected} onClick={analyze}>Retry analysis</button>}</div>

            {!file && <p className="hh-muted" role="status">Choose a photo to get started.</p>}

            {observations.length > 0 && <div className="hh-compact-list"><h3>Observations</h3>{observations.map(item => <div className="hh-history-entry" key={item.id}><strong>{conditionSummary(item)}</strong><p>{observationEvidence(item)}</p><small>{needsReview(item) ? "Unverified" : evidenceStatus(item)}</small>{needsReview(item) && <button disabled={busy} onClick={() => confirm(item)}>Confirm observation</button>}</div>)}</div>}

            <p className="hh-muted">HomHive suggests tasks from your photos. Some actions need your approval.</p>

          </>}

        </section>

      </div>}

      {demoOpen && (

        <div className="hh-modal-backdrop hh-demo-backdrop" onClick={() => setDemoOpen(false)}>

          <section role="dialog" aria-modal="true" aria-labelledby="hh-demo-title" className="hh-modal hh-demo-dialog" onClick={e => e.stopPropagation()}>

            <div className="hh-panel-head">

              <div>

                <p className="hh-kicker">HomHive demo library</p>

                <h2 id="hh-demo-title">Choose a household scene</h2>

                <p className="hh-muted">{demoCatalog.length} sample photographs. Selecting one uses real AI analysis when you submit it.</p>

              </div>

              <button className="hh-icon-button" aria-label="Close image library" onClick={() => setDemoOpen(false)}>✕</button>

            </div>

            <div className="hh-demo-mode-tabs" role="group" aria-label="Photo collection">

              <button type="button" className={demoMode === "sequences" ? "is-active" : ""} aria-pressed={demoMode === "sequences"} onClick={() => {setDemoMode("sequences");setDemoCategory("All");}}>Before & after sets <span>{demoFamilies.length}</span></button>

              <button type="button" className={demoMode === "standalone" ? "is-active" : ""} aria-pressed={demoMode === "standalone"} onClick={() => {setDemoMode("standalone");setDemoCategory("All");}}>Other scenes <span>{standaloneDemoImages.length}</span></button>

            </div>

            <div className="hh-demo-filters">

              <label>Search photographs

                <input value={demoQuery} onChange={e => setDemoQuery(e.target.value)} placeholder="e.g. kitchen, dishes, Original 30" />

              </label>

              <HomHiveSelect label="Room category" value={demoCategory} onChange={setDemoCategory}

                choices={demoCategories.map(category => ({value:category,label:category === "All" ? "All room categories" : category}))} />

            </div>

            <p className="hh-demo-count" aria-live="polite">{demoMode === "sequences" ? `${filteredDemoFamilies.length} photo sets with original and follow-up images` : `${filteredStandaloneImages.length} individual photos relationship`}</p>

            {demoSelectionError && <p role="alert" className="hh-demo-error">{demoSelectionError}</p>}

            <div className="hh-demo-library-scroll">

              {demoMode === "sequences" ? (filteredDemoFamilies.length ? <div className="hh-demo-family-list">

                {filteredDemoFamilies.map(family => <section className="hh-demo-family" key={family.original.family_id}>

                  <div className="hh-demo-family-heading"><div><strong>{family.original.title} · {family.original.source_title}</strong><small>{family.original.category} · {family.variants.length} verified {family.variants.length === 1 ? "variation" : "variations"}</small></div></div>

                  <div className="hh-demo-sequence-grid">{[family.original, ...family.variants].map(image => <button className="hh-demo-item" type="button" disabled={demoSelecting} key={image.id} onClick={() => chooseDemoImage(image)} aria-label={`Select ${image.title}: ${family.original.source_title}`}>

                    <img src={image.thumbnail} alt={`${image.title} · ${family.original.source_title}`} loading="lazy" />

                    <span><strong>{image.title}</strong><small>{image.group === "original" ? "Original · reference scene" : `Variation · ${image.variant_note || "controlled change"}`}</small></span>

                  </button>)}</div>

                </section>)}

              </div> : <p className="hh-demo-no-results">No matching photo sets. Try another category or search term.</p>) :

              (filteredStandaloneImages.length ? <><p className="hh-demo-standalone-notice">These photos can be analyzed individually. They are not part of a verified before-and-after set.</p>

                <div className="hh-demo-grid">{filteredStandaloneImages.map(image => <button className="hh-demo-item" type="button" disabled={demoSelecting} key={image.id} onClick={() => chooseDemoImage(image)} aria-label={`Select ${image.title}: ${image.source_title}`}><img src={image.thumbnail} alt={`${image.title} · ${image.source_title}`} loading="lazy"/><span><strong>{image.title}</strong><small>{image.source_title}</small><small>{image.category}</small></span></button>)}</div></> : <p className="hh-demo-no-results">No matching photos found.</p>)}

            </div>

          </section>

        </div>

      )}

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

              <button className="hh-auth-submit" type="submit" disabled={Boolean(authDisabledReason)}>{busy ? "Please wait..." : authMode === "login" ? "Sign in" : "Create account"}</button>

              {authDisabledReason && <p className="hh-auth-reason" role="status">{authDisabledReason}</p>}

            </form>

            <p className="hh-auth-footnote">{authMode === "register" ? "Your account creates a private household. Sessions expire after seven days." : "Use the password you created with this email. Account recovery is not yet available."}</p>

          </div> : <div className="hh-auth-connected"><strong>Signed in</strong><p>Your account has a private household. Select <strong>Load household</strong> to access scans and saved work.</p><button type="button" className="secondary" disabled={busy} onClick={signOut}>Sign out</button></div>}

          <section className="hh-settings-section" aria-label="Household connection"><h3>Household connection</h3><p className="hh-muted">{isConnected ? "Your household is loaded. Scans and saved work are available." : token ? "Your household is connecting automatically. You can retry if needed." : "Sign in or create an account to connect your private household."}</p><button type="button" disabled={Boolean(householdDisabledReason)} onClick={async () => {if (await loadHousehold()) setSettingsOpen(false);}}>{busy ? "Connecting..." : isConnected ? "Household connected" : "Load household"}</button>{householdDisabledReason && <p role="status" className="hh-auth-reason">{householdDisabledReason}</p>}</section>

          <section className="hh-settings-section" aria-label="Household schedule"><h3>Your schedule</h3><p className="hh-muted">{scheduleSummary}. Manage your days and preferred times in the Schedule tab.</p><button type="button" className="secondary" onClick={() => {setSettingsOpen(false);setView("schedule");}}>Open Schedule</button></section>

          <details className="hh-settings-details"><summary>Presence (optional)</summary><p className="hh-muted">Share whether you are home. This is manual and expires after one hour.</p><p className="hh-muted">Current: {presence?.state ?? "UNKNOWN"}</p><div className="hh-task-actions"><button className="secondary" disabled={!isConnected || busy} onClick={() => changePresence("HOME")}>I'm home</button><button className="secondary" disabled={!isConnected || busy} onClick={() => changePresence("AWAY")}>I'm away</button><button className="secondary" disabled={!isConnected || busy} onClick={() => changePresence("UNKNOWN")}>Stop sharing</button></div>{(!isConnected || busy) && <p className="hh-auth-reason">{!isConnected ? "Load your household before sharing presence." : "Please wait for the current request."}</p>}</details>

          <details className="hh-settings-details"><summary>Connection diagnostics</summary><label>API URL<input value={apiUrl} onChange={e => setApiUrl(e.target.value)}/></label><p className="hh-muted">Your session remains available when refreshing this tab until it expires, you close the tab, or you sign out. Shared devices should always use Sign out.</p>{token && <p className="hh-muted">Technical household ID (for troubleshooting): <code style={{overflowWrap:"anywhere"}}>{householdId}</code></p>}</details>

        </section></div>}

    </main>

  );

}

