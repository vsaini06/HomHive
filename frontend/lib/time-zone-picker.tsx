"use client";

import { useEffect, useId, useMemo, useRef, useState } from "react";

const COMMON_ZONES = [
  "America/Phoenix", "America/Los_Angeles", "America/Denver", "America/Chicago",
  "America/New_York", "America/Toronto", "America/Mexico_City",
  "America/Sao_Paulo", "Europe/London", "Europe/Paris", "Europe/Berlin",
  "Asia/Dubai", "Asia/Kolkata", "Asia/Singapore", "Asia/Tokyo",
  "Australia/Sydney", "Pacific/Auckland", "UTC",
];

const SEARCH_TERMS: Record<string, string> = {
  "America/Phoenix": "Arizona MST",
  "America/Los_Angeles": "California Pacific PST PDT San Francisco Seattle",
  "America/Denver": "Mountain MST MDT Colorado",
  "America/Chicago": "Central CST CDT Texas",
  "America/New_York": "Eastern EST EDT Boston Washington DC",
  "America/Toronto": "Canada Eastern",
  "Europe/London": "UK United Kingdom GMT BST",
  "Asia/Kolkata": "India Indian Standard Time IST Mumbai Delhi Bangalore Bengaluru",
  "Asia/Calcutta": "India Indian Standard Time IST Mumbai Delhi Bangalore Bengaluru",
  "Asia/Dubai": "United Arab Emirates UAE",
  "Australia/Sydney": "New South Wales Australia",
  "Pacific/Auckland": "New Zealand",
  "UTC": "Coordinated Universal Time GMT",
};

function supportedZones(): string[] {
  let zones: string[] = [];
  try {
    zones = Intl.supportedValuesOf("timeZone");
  } catch {
    zones = [];
  }
  return [...new Set([...COMMON_ZONES, ...zones])].filter(zone => {
    try {
      new Intl.DateTimeFormat("en-US", { timeZone: zone });
      return true;
    } catch {
      return false;
    }
  });
}

const ALL_ZONES = supportedZones();

function zoneMatches(zone: string, query: string): boolean {
  const words = `${zone.replace(/[/_]/g, " ")} ${SEARCH_TERMS[zone] || ""}`.toLowerCase();
  return query.toLowerCase().trim().split(/\s+/).every(term => words.includes(term));
}

export function HouseholdTimeZonePicker({ value, onChange }: {
  value: string;
  onChange: (zone: string) => void;
}) {
  const id = useId();
  const rootRef = useRef<HTMLDivElement>(null);
  const searchRef = useRef<HTMLInputElement>(null);
  const [open, setOpen] = useState(false);
  const [query, setQuery] = useState("");
  const [activeIndex, setActiveIndex] = useState(0);

  const zones = useMemo(() => {
    const available = ALL_ZONES.includes(value) ? ALL_ZONES : [value, ...ALL_ZONES];
    if (query.trim()) return available.filter(zone => zoneMatches(zone, query)).slice(0, 40);
    return [...new Set([value, ...COMMON_ZONES])].filter(zone => available.includes(zone));
  }, [query, value]);

  useEffect(() => {
    if (!open) return;
    searchRef.current?.focus();
    function dismiss(event: PointerEvent) {
      if (!rootRef.current?.contains(event.target as Node)) setOpen(false);
    }
    document.addEventListener("pointerdown", dismiss);
    return () => document.removeEventListener("pointerdown", dismiss);
  }, [open]);

  function choose(zone: string) {
    onChange(zone);
    setOpen(false);
    setQuery("");
  }

  function handleKeys(event: React.KeyboardEvent<HTMLDivElement>) {
    if (!open) return;
    if (event.key === "Escape") {
      event.preventDefault();
      setOpen(false);
      rootRef.current?.querySelector<HTMLButtonElement>(".hh-zone-trigger")?.focus();
    } else if (event.key === "ArrowDown" || event.key === "ArrowUp") {
      event.preventDefault();
      setActiveIndex(index => Math.max(0, Math.min(zones.length - 1, index + (event.key === "ArrowDown" ? 1 : -1))));
    } else if (event.key === "Enter" && zones[activeIndex]) {
      event.preventDefault();
      choose(zones[activeIndex]);
    }
  }

  return <div className="hh-zone-field" ref={rootRef} onKeyDown={handleKeys}>
    <span id={`${id}-label`} className="hh-zone-label">Household time zone</span>
    <button type="button" className="hh-zone-trigger" aria-haspopup="dialog" aria-expanded={open}
      aria-labelledby={`${id}-label ${id}-value`}
      onClick={() => { setQuery(""); setActiveIndex(0); setOpen(current => !current); }}>
      <span id={`${id}-value`}>{value}</span><span aria-hidden="true" className="hh-zone-chevron">⌄</span>
    </button>
    {open && <div className="hh-zone-popup" role="dialog" aria-label="Choose a time zone">
      <input ref={searchRef} type="search" className="hh-zone-search" placeholder="Search city, country, or time zone"
        aria-label="Search time zones" autoComplete="off" value={query}
        onChange={event => { setQuery(event.target.value); setActiveIndex(0); }} />
      <p className="hh-zone-list-title">{query.trim() ? "Matching time zones" : "Common time zones"}</p>
      <div className="hh-zone-options" role="listbox" aria-label="Time zones">
        {zones.length ? zones.map((zone, index) => <button type="button" role="option" key={zone}
          aria-selected={zone === value} className={`hh-zone-option${zone === value ? " is-selected" : ""}${index === activeIndex ? " is-active" : ""}`}
          onMouseEnter={() => setActiveIndex(index)} onClick={() => choose(zone)}>
          <span>{zone.replaceAll("_", " ")}</span>{zone === value && <span aria-hidden="true">✓</span>}
        </button>) : <p className="hh-zone-empty">No matching time zones. Try a city or region.</p>}
      </div>
      {query.trim() && zones.length === 40 && <small className="hh-zone-hint">Keep typing to narrow the results.</small>}
    </div>}
  </div>;
}
