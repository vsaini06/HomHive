export type QuietHoursSettings = {
  enabled: boolean;
  start_time: string;
  end_time: string;
  timezone: string;
};

export function currentTimeZone(): string {
  try {
    return Intl.DateTimeFormat().resolvedOptions().timeZone || "UTC";
  } catch {
    return "UTC";
  }
}

export function isValidTimeZone(zone: string): boolean {
  if (!zone || zone.length > 64) return false;
  try {
    new Intl.DateTimeFormat("en-US", { timeZone: zone });
    return true;
  } catch {
    return false;
  }
}

export function timeInZone(date: Date, timeZone: string): string {
  if (!isValidTimeZone(timeZone)) return "Unavailable";
  return new Intl.DateTimeFormat("en-US", {timeZone, hour: "numeric", minute: "2-digit", hour12: true}).format(date);
}

export function quietHoursActiveAt(date: Date, settings: QuietHoursSettings): boolean {
  if (!settings.enabled || !isValidTimeZone(settings.timezone)) return false;
  const parts = new Intl.DateTimeFormat("en-GB", {
    timeZone: settings.timezone, hour: "2-digit", minute: "2-digit", hourCycle: "h23",
  }).formatToParts(date);
  const hour = Number(parts.find(part => part.type === "hour")?.value);
  const minute = Number(parts.find(part => part.type === "minute")?.value);
  const start = /^([01]\d|2[0-3]):[0-5]\d$/.test(settings.start_time) ? settings.start_time : null;
  const end = /^([01]\d|2[0-3]):[0-5]\d$/.test(settings.end_time) ? settings.end_time : null;
  if (!start || !end || start === end || !Number.isFinite(hour) || !Number.isFinite(minute)) return false;
  const current = hour * 60 + minute;
  const from = Number(start.slice(0, 2)) * 60 + Number(start.slice(3));
  const until = Number(end.slice(0, 2)) * 60 + Number(end.slice(3));
  return from < until ? current >= from && current < until : current >= from || current < until;
}
