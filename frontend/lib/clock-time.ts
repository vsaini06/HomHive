export function splitClock(value: string): {hour: string; minute: string; period: string} {
  const valid = /^([01]\d|2[0-3]):([0-5]\d)$/.exec(value);
  const h = valid ? Number(valid[1]) : 9;
  return {hour: String(h % 12 || 12), minute: valid ? valid[2] : "00", period: h >= 12 ? "PM" : "AM"};
}
export function joinClock(hour: string, minute: string, period: string): string {
  const h = Number(hour);
  const m = Number(minute);
  if (!Number.isInteger(h) || h < 1 || h > 12 || !Number.isInteger(m) || m < 0 || m > 59 || !["AM", "PM"].includes(period)) {
    throw new Error("Invalid time selection");
  }
  const clockHour = (h % 12) + (period === "PM" ? 12 : 0);
  return `${String(clockHour).padStart(2, "0")}:${String(m).padStart(2, "0")}`;
}
