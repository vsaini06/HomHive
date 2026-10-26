export const WORK_DAYS = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"] as const;

export const WORK_TIME_OPTIONS = Array.from({ length: 48 }, (_, index) => {
  const hours = Math.floor(index / 2);
  const minutes = index % 2 ? "30" : "00";
  return `${String(hours).padStart(2, "0")}:${minutes}`;
});

export function readableWorkTime(value: string): string {
  const match = /^(\d{2}):(\d{2})$/.exec(value);
  if (!match) return value;
  const hours = Number(match[1]);
  const minutes = Number(match[2]);
  if (hours > 23 || minutes > 59) return value;
  return `${hours % 12 || 12}:${String(minutes).padStart(2, "0")} ${hours >= 12 ? "PM" : "AM"}`;
}

export function readableWorkDays(days: number[]): string {
  const unique = [...new Set(days)].filter(day => Number.isInteger(day) && day >= 0 && day < 7).sort();
  if (!unique.length) return "No days selected";
  if (unique.length === 7) return "Every day";
  if (unique.join(",") === "0,1,2,3,4") return "Weekdays";
  if (unique.join(",") === "5,6") return "Weekends";
  return unique.map(day => WORK_DAYS[day]).join(", ");
}

export function workWindowError(start: string, end: string, days: number[]): string | null {
  if (!days.length) return "Choose at least one day.";
  if (!/^([01]\d|2[0-3]):[0-5]\d$/.test(start) || !/^([01]\d|2[0-3]):[0-5]\d$/.test(end)) {
    return "Choose a start and end time.";
  }
  if (end <= start) return "Your end time must be later than the start time on the same day.";
  return null;
}
