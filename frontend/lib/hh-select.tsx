"use client";

import { useEffect, useId, useRef, useState } from "react";

export type Choice = { value: string; label: string; detail?: string };


export function HomHiveSelect({ id, label, value, choices, onChange, disabled = false, placeholder = "Choose an option", className = "" }: {
  id?: string;
  label: string;
  value: string;
  choices: Choice[];
  onChange: (value: string) => void;
  disabled?: boolean;
  placeholder?: string;
  className?: string;
}) {
  const generatedId = useId();
  const controlId = id ?? generatedId;
  const listId = `${controlId}-choices`;
  const [open, setOpen] = useState(false);
  const [active, setActive] = useState(0);
  const container = useRef<HTMLDivElement>(null);
  const trigger = useRef<HTMLButtonElement>(null);
  const optionsRef = useRef<Array<HTMLButtonElement | null>>([]);
  const selectedIndex = choices.findIndex(choice => choice.value === value);
  const chosen = choices[selectedIndex];

  useEffect(() => {
    if (!open) return;
    const handlePointer = (event: PointerEvent) => {
      if (!container.current?.contains(event.target as Node)) setOpen(false);
    };
    document.addEventListener("pointerdown", handlePointer);
    return () => document.removeEventListener("pointerdown", handlePointer);
  }, [open]);
  useEffect(() => {
    if (open) optionsRef.current[active]?.focus();
  }, [open, active]);

  function select(index: number) {
    if (!choices[index]) return;
    onChange(choices[index].value);
    setOpen(false);
    requestAnimationFrame(() => trigger.current?.focus());
  }
  function start() {
    if (disabled || choices.length === 0) return;
    setActive(Math.max(0, selectedIndex));
    setOpen(true);
  }
  function onKeys(event: React.KeyboardEvent<HTMLDivElement>) {
    if (!open) {
      if (["Enter", " ", "ArrowDown", "ArrowUp"].includes(event.key)) {
        event.preventDefault(); start();
      }
      return;
    }
    if (event.key === "Escape" || event.key === "Tab") {
      if (event.key === "Escape") event.preventDefault();
      setOpen(false);
      if (event.key === "Escape") trigger.current?.focus();
    } else if (event.key === "ArrowDown" || event.key === "ArrowUp") {
      event.preventDefault();
      setActive(index => Math.max(0, Math.min(choices.length - 1, index + (event.key === "ArrowDown" ? 1 : -1))));
    } else if (event.key === "Home" || event.key === "End") {
      event.preventDefault(); setActive(event.key === "Home" ? 0 : choices.length - 1);
    } else if (event.key === "Enter" || event.key === " ") {
      event.preventDefault(); select(active);
    }
  }

  return <div className={`hh-choice-field ${className}`} ref={container} onKeyDown={onKeys}>
    <span id={`${controlId}-label`} className="hh-choice-label">{label}</span>
    <button ref={trigger} id={controlId} className="hh-choice-trigger" type="button" disabled={disabled}
      aria-haspopup="listbox" aria-expanded={open} aria-controls={open ? listId : undefined}
      aria-labelledby={`${controlId}-label ${controlId}`}
      onClick={() => open ? setOpen(false) : start()}>
      <span>{chosen?.label ?? placeholder}</span><svg aria-hidden="true" width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><path d="m6 9 6 6 6-6" /></svg>
    </button>
    {open && <div id={listId} role="listbox" aria-labelledby={`${controlId}-label`} className="hh-choice-list">
      {choices.map((choice, index) => <button key={`${choice.value}-${index}`} ref={node => { optionsRef.current[index] = node; }}
        type="button" role="option" aria-selected={choice.value === value}
        tabIndex={index === active ? 0 : -1}
        className={`hh-choice-option ${choice.value === value ? "is-selected" : ""}`}
        onMouseEnter={() => setActive(index)} onFocus={() => setActive(index)} onClick={() => select(index)}>
        <span><strong>{choice.label}</strong>{choice.detail && <small>{choice.detail}</small>}</span>
        {choice.value === value && <svg aria-hidden="true" width="17" height="17" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5"><path d="m5 12 5 5 9-10" /></svg>}
      </button>)}
    </div>}
  </div>;
}
