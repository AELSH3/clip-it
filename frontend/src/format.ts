export function formatTimestamp(seconds: number | null | undefined): string {
  if (seconds == null || Number.isNaN(seconds)) return "–";
  const total = Math.max(0, Math.floor(seconds));
  const hours = Math.floor(total / 3600);
  const minutes = Math.floor((total % 3600) / 60);
  const secs = total % 60;
  if (hours > 0) return `${hours}:${String(minutes).padStart(2, "0")}:${String(secs).padStart(2, "0")}`;
  return `${minutes}:${String(secs).padStart(2, "0")}`;
}

export function formatDate(value: string | null): string {
  if (!value) return "Unknown date";
  return new Date(value).toLocaleDateString(undefined, { month: "short", day: "numeric", year: "numeric" });
}

export function channelLabel(name: string): string {
  return {
    transcript_keyword: "Speech keywords",
    ocr_keyword: "Screen-text keywords",
    transcript_semantic: "Speech similarity",
    ocr_semantic: "Screen-text similarity",
    visual: "Visual similarity",
  }[name] ?? name;
}
