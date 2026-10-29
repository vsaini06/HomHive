"use client";

import { useEffect, useRef, useState } from "react";
import { readableWorkTime } from "./work-schedule";
import { splitClock, joinClock } from "./clock-time";

const ITEM_HEIGHT = 40;
const hours = Array.from({ length: 12 }, (_, i) => String(i + 1));
const minutes = Array.from({ length: 60 }, (_, i) => String(i).padStart(2, "0"));
const periods = ["AM", "PM"];

type Part = "hour" | "minute" | "period";
function Wheel({id, label, values, value, choose}: {id:string; label:string; values:string[]; value:string; choose:(value:string)=>void}) {
  const el = useRef<HTMLDivElement>(null);
  const timer = useRef<ReturnType<typeof setTimeout> | null>(null);
  useEffect(() => {
    if (el.current) el.current.scrollTop = Math.max(0, values.indexOf(value)) * ITEM_HEIGHT;
  }, [value, values]);
  useEffect(() => () => {if(timer.current) clearTimeout(timer.current);}, []);
  const activeIndex = Math.max(0, values.indexOf(value));
  function step(direction: number) {choose(values[Math.min(values.length - 1, Math.max(0, activeIndex + direction))]);}
  return <div className="hh-wheel-column">
    <span className="hh-wheel-heading">{label}</span>
    <div ref={el} className="hh-wheel-scroll" role="listbox" tabIndex={0} aria-label={label} aria-activedescendant={`wheel-${id}-${activeIndex}`}
      onKeyDown={event => {if (event.key === "ArrowDown" || event.key === "ArrowUp") {event.preventDefault();step(event.key === "ArrowDown" ? 1 : -1);}}}
      onScroll={event => {
        if (timer.current) clearTimeout(timer.current);
        const target = event.currentTarget;
        timer.current = setTimeout(() => {
          const index = Math.max(0, Math.min(values.length - 1, Math.round(target.scrollTop / ITEM_HEIGHT)));
          if (values[index] !== value) choose(values[index]);
        }, 100);
      }}>
      {values.map((candidate, index) => <button id={`wheel-${id}-${index}`} key={candidate} type="button" role="option" aria-selected={candidate === value}
        className={candidate === value ? "hh-wheel-selected" : ""} onClick={() => choose(candidate)}>{candidate}</button>)}
    </div>
  </div>;
}

export function TimeWheelField({id, label, value, onChange}: {id:string; label:string; value:string; onChange:(value:string)=>void}) {
  const [open, setOpen] = useState(false);
  const [draft, setDraft] = useState(value);
  const container = useRef<HTMLDivElement>(null);
  useEffect(() => {if (!open) setDraft(value);}, [value, open]);
  useEffect(() => {
    if (!open) return;
    function outside(event: MouseEvent) {if (container.current && !container.current.contains(event.target as Node)) setOpen(false);}
    document.addEventListener("mousedown", outside);
    return () => document.removeEventListener("mousedown", outside);
  }, [open]);
  const selected = splitClock(draft);
  function pick(part: Part, choice: string) {
    const updated = {...selected, [part]: choice};
    setDraft(joinClock(updated.hour, updated.minute, updated.period));
  }
  return <div className="hh-time-field" ref={container}>
    <label id={`${id}-label`}>{label}</label>
    <button id={id} type="button" aria-labelledby={`${id}-label ${id}`} aria-expanded={open} aria-haspopup="dialog" className="hh-time-trigger"
      onClick={() => {setDraft(value);setOpen(!open);}}>{readableWorkTime(value)} <span aria-hidden="true">⌄</span></button>
    {open && <div className="hh-time-popover" role="dialog" aria-modal="false" aria-label={`${label} time picker`} onKeyDown={event => {if (event.key === "Escape") setOpen(false);}}>
      <p>Scroll or tap to set a precise time</p>
      <div className="hh-time-wheel-row">
        <Wheel id={`${id}-hour`} label="Hour" values={hours} value={selected.hour} choose={v => pick("hour", v)} />
        <Wheel id={`${id}-minute`} label="Minute" values={minutes} value={selected.minute} choose={v => pick("minute", v)} />
        <Wheel id={`${id}-period`} label="Period" values={periods} value={selected.period} choose={v => pick("period", v)} />
      </div>
      <div className="hh-time-actions"><button type="button" className="secondary" onClick={() => setOpen(false)}>Cancel</button>
        <button type="button" onClick={() => {onChange(draft);setOpen(false);}}>Set time</button></div>
    </div>}
  </div>;
}
