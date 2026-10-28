import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { api, ApiError, uploadVideo } from "../api.ts";
import { formatDate, formatTimestamp } from "../format.ts";
import type { Video } from "../types.ts";

export function LibraryPage() {
  const [items, setItems] = useState<Video[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [dragOver, setDragOver] = useState(false);
  const [progress, setProgress] = useState<number | null>(null);
  const [title, setTitle] = useState("");

  async function refresh() {
    const payload = await api<{ items: Video[]; total: number }>("/api/videos");
    setItems(payload.items);
  }

  useEffect(() => {
    refresh()
      .catch((err: unknown) => setError(err instanceof Error ? err.message : "Could not load the library."))
      .finally(() => setLoading(false));
  }, []);

  useEffect(() => {
    if (!items.some((video) => video.status === "pending" || video.status === "processing")) return;
    const timer = window.setInterval(() => {
      void refresh().catch(() => undefined);
    }, 2000);
    return () => window.clearInterval(timer);
  }, [items]);

  async function send(file: File) {
    setError(null);
    setProgress(0);
    try {
      await uploadVideo(file, title, setProgress);
      setTitle("");
      await refresh();
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Upload failed.");
    } finally {
      setProgress(null);
    }
  }

  async function remove(video: Video) {
    if (!window.confirm(`Delete “${video.title}” and its index?`)) return;
    await api(`/api/videos/${video.id}`, { method: "DELETE" });
    await refresh();
  }

  async function retry(video: Video) {
    await api(`/api/videos/${video.id}/retry`, { method: "POST" });
    await refresh();
  }

  return (
    <section>
      <div className="mb-8 flex flex-wrap items-end justify-between gap-4">
        <div>
          <h1 className="font-serif text-4xl">Library</h1>
          <p className="mt-2 max-w-xl text-muted">Upload a video. Clip-It transcribes speech, reads on-screen text, and indexes frames so you can jump to a moment.</p>
        </div>
      </div>
      <form
        className={`rounded-2xl border border-dashed p-6 ${dragOver ? "border-amber bg-panel" : "border-line bg-panel"}`}
        onDragOver={(event) => {
          event.preventDefault();
          setDragOver(true);
        }}
        onDragLeave={() => setDragOver(false)}
        onDrop={(event) => {
          event.preventDefault();
          setDragOver(false);
          const file = event.dataTransfer.files[0];
          if (file) void send(file);
        }}
      >
        <label className="block text-sm text-muted" htmlFor="title">Title (optional)</label>
        <input id="title" value={title} onChange={(event) => setTitle(event.target.value)} className="mt-1 w-full rounded-lg border border-line bg-ink px-3 py-2" />
        <label className="mt-4 inline-flex cursor-pointer rounded-full bg-amber px-4 py-2 font-medium text-ink" htmlFor="file">
          Choose a video
          <input
            id="file"
            className="sr-only"
            type="file"
            accept="video/*,.mp4,.mov,.m4v,.webm,.mkv,.avi"
            onChange={(event) => {
              const file = event.target.files?.[0];
              if (file) void send(file);
              event.target.value = "";
            }}
          />
        </label>
        <p className="mt-3 text-sm text-muted">Or drop a file here. mp4, mov, webm, mkv, and avi.</p>
        {progress != null && (
          <p className="mt-3 text-sm" aria-live="polite">Uploading {Math.round(progress * 100)}%</p>
        )}
      </form>
      {error && <p className="mt-4 text-danger" role="alert">{error}</p>}
      {loading && <p className="mt-8 text-muted">Loading the library…</p>}
      {!loading && items.length === 0 && <p className="mt-8 text-muted">No videos yet. Upload one to start a search index.</p>}
      <ul className="mt-8 grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
        {items.map((video) => (
          <li key={video.id} className="overflow-hidden rounded-2xl border border-line bg-panel">
            <Link to={`/videos/${video.id}`} className="block">
              {video.thumbnail_url ? (
                <img src={video.thumbnail_url} alt="" className="aspect-video w-full object-cover" />
              ) : (
                <div className="grid aspect-video place-items-center bg-panel-2 text-muted">No thumbnail yet</div>
              )}
            </Link>
            <div className="space-y-2 p-4">
              <div className="flex items-start justify-between gap-3">
                <h2 className="font-serif text-xl leading-tight">
                  <Link to={`/videos/${video.id}`}>{video.title}</Link>
                </h2>
                <span className="shrink-0 text-sm text-muted">{formatTimestamp(video.duration_sec)}</span>
              </div>
              <p className="text-sm text-muted">{formatDate(video.created_at)}</p>
              <p className="text-sm" aria-live="polite">
                <Status video={video} />
              </p>
              {video.error_message && <p className="text-sm text-danger">{video.error_message}</p>}
              <div className="flex gap-2">
                {video.status === "failed" && (
                  <button type="button" className="rounded-full border border-line px-3 py-1 text-sm" onClick={() => void retry(video)}>
                    Retry
                  </button>
                )}
                <button type="button" className="rounded-full border border-line px-3 py-1 text-sm" onClick={() => void remove(video)}>
                  Delete
                </button>
              </div>
            </div>
          </li>
        ))}
      </ul>
    </section>
  );
}

function Status({ video }: { video: Video }) {
  if (video.status === "ready" && video.warnings.length > 0) return <span className="text-amber">Ready, with warnings</span>;
  if (video.status === "ready") return <span className="text-sage">Ready</span>;
  if (video.status === "failed") return <span className="text-danger">Failed</span>;
  return <span className="text-amber">{video.stage_label}</span>;
}
