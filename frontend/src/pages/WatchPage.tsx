import { useEffect, useRef, useState } from "react";
import { useParams, useSearchParams } from "react-router-dom";
import { api, ApiError } from "../api.ts";
import { formatTimestamp } from "../format.ts";
import { SearchBox } from "./SearchPage.tsx";
import type { TranscriptSegment, Video } from "../types.ts";

export function WatchPage() {
  const { id = "" } = useParams();
  const [params] = useSearchParams();
  const startAt = Number(params.get("t") ?? "");
  const videoRef = useRef<HTMLVideoElement>(null);
  const [video, setVideo] = useState<Video | null>(null);
  const [segments, setSegments] = useState<TranscriptSegment[]>([]);
  const [active, setActive] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let stop = false;
    let timer = 0;
    async function load() {
      try {
        const next = await api<Video>(`/api/videos/${id}`);
        if (stop) return;
        setVideo(next);
        if (next.status === "ready" || next.status === "failed") {
          const transcript = await api<{ segments: TranscriptSegment[] }>(`/api/videos/${id}/transcript`);
          if (!stop) setSegments(transcript.segments);
          window.clearInterval(timer);
        }
      } catch (err) {
        if (!stop) setError(err instanceof ApiError ? err.message : "Could not open this video.");
      }
    }
    void load();
    timer = window.setInterval(() => {
      void load();
    }, 2000);
    return () => {
      stop = true;
      window.clearInterval(timer);
    };
  }, [id]);

  useEffect(() => {
    const element = videoRef.current;
    if (!element || !Number.isFinite(startAt)) return;
    const seek = () => {
      element.currentTime = startAt;
      void element.play().catch(() => undefined);
    };
    if (element.readyState >= 1) seek();
    else element.addEventListener("loadedmetadata", seek, { once: true });
  }, [startAt, video?.id]);

  function onTime() {
    const current = videoRef.current?.currentTime ?? 0;
    const match = segments.find((segment) => current >= segment.start_sec && current < segment.end_sec);
    setActive(match?.id ?? null);
  }

  function seekTo(seconds: number) {
    const element = videoRef.current;
    if (!element) return;
    element.currentTime = seconds;
    void element.play().catch(() => undefined);
  }

  if (error) return <p className="text-danger" role="alert">{error}</p>;
  if (!video) return <p className="text-muted">Loading video…</p>;

  return (
    <section className="grid gap-8 lg:grid-cols-[minmax(0,1.4fr)_minmax(280px,0.8fr)]">
      <div>
        <h1 className="font-serif text-4xl">{video.title}</h1>
        <p className="mt-2 text-sm text-muted" aria-live="polite">
          {video.status === "ready" ? `Ready · ${formatTimestamp(video.duration_sec)}` : video.stage_label}
        </p>
        {video.error_message && <p className="mt-2 text-danger">{video.error_message}</p>}
        {video.warnings.map((warning) => (
          <p key={warning} className="mt-2 text-sm text-amber">{warning}</p>
        ))}
        <video
          ref={videoRef}
          className="mt-4 aspect-video w-full rounded-2xl bg-black"
          controls
          preload="metadata"
          src={`/api/videos/${video.id}/stream`}
          onTimeUpdate={onTime}
        >
          <track kind="descriptions" label="Transcript is listed beside the player" />
        </video>
        <SearchBox videoId={video.id} />
      </div>
      <aside>
        <h2 className="font-serif text-2xl">Transcript</h2>
        {segments.length === 0 && <p className="mt-3 text-sm text-muted">No transcript yet. Silent videos and failed speech recognition show up here as empty.</p>}
        <ul className="mt-3 max-h-[70vh] space-y-2 overflow-auto pr-1">
          {segments.map((segment) => (
            <li key={segment.id}>
              <button
                type="button"
                onClick={() => seekTo(segment.start_sec)}
                className={`w-full rounded-xl border px-3 py-2 text-left ${active === segment.id ? "border-amber bg-panel-2" : "border-line"}`}
              >
                <span className="block text-xs text-amber">{formatTimestamp(segment.start_sec)}</span>
                {segment.text}
              </button>
            </li>
          ))}
        </ul>
      </aside>
    </section>
  );
}
