import { useState, type FormEvent } from "react";
import { Link } from "react-router-dom";
import { api, ApiError } from "../api.ts";
import { channelLabel, formatTimestamp } from "../format.ts";
import type { SearchHit, SearchMode, SearchResponse } from "../types.ts";

const modes: { id: SearchMode; label: string }[] = [
  { id: "all", label: "All" },
  { id: "speech", label: "Speech" },
  { id: "screen_text", label: "Screen text" },
  { id: "visual", label: "Visual" },
];

export function SearchPage() {
  return (
    <section>
      <h1 className="font-serif text-4xl">Search</h1>
      <p className="mt-2 max-w-2xl text-muted">Scores are retrieval match scores, not confidence percentages.</p>
      <SearchBox videoId={null} />
    </section>
  );
}

export function SearchBox({ videoId }: { videoId: string | null }) {
  const [query, setQuery] = useState("");
  const [mode, setMode] = useState<SearchMode>("all");
  const [result, setResult] = useState<SearchResponse | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const [saved, setSaved] = useState<string | null>(null);

  async function onSubmit(event: FormEvent) {
    event.preventDefault();
    setLoading(true);
    setError(null);
    setSaved(null);
    try {
      const payload = await api<SearchResponse>("/api/search", {
        method: "POST",
        body: JSON.stringify({ query, mode, video_id: videoId, limit: 12 }),
      });
      setResult(payload);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Search failed.");
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="mt-6">
      <form onSubmit={(event) => void onSubmit(event)} className="space-y-4">
        <label className="block" htmlFor={videoId ? "video-query" : "library-query"}>
          <span className="text-sm text-muted">{videoId ? "Search this video" : "Search the library"}</span>
          <input
            id={videoId ? "video-query" : "library-query"}
            value={query}
            onChange={(event) => setQuery(event.target.value)}
            required
            className="mt-1 w-full rounded-xl border border-line bg-panel px-4 py-3 text-lg"
            placeholder="Where does the instructor explain deadlocks?"
          />
        </label>
        <fieldset>
          <legend className="text-sm text-muted">Search mode</legend>
          <div className="mt-2 flex flex-wrap gap-2">
            {modes.map((item) => (
              <label key={item.id} className={`cursor-pointer rounded-full border px-3 py-1.5 text-sm ${mode === item.id ? "border-amber bg-amber text-ink" : "border-line"}`}>
                <input className="sr-only" type="radio" name={`mode-${videoId ?? "library"}`} checked={mode === item.id} onChange={() => setMode(item.id)} />
                {item.label}
              </label>
            ))}
          </div>
        </fieldset>
        <button type="submit" className="rounded-full bg-amber px-4 py-2 font-medium text-ink" disabled={loading}>
          {loading ? "Searching…" : "Search"}
        </button>
      </form>
      {error && <p className="mt-4 text-danger" role="alert">{error}</p>}
      {result && (
        <div className="mt-6 space-y-4" aria-live="polite">
          <p className="text-sm text-muted">
            {result.results.length} result{result.results.length === 1 ? "" : "s"} in {result.latency_ms} ms.
            {result.ranker_applied ? ` Trained ranker ${result.ranker_version} reordered them.` : " Fusion order only; no trained ranker was applied."}
          </p>
          {result.notice && <p className="text-sm text-amber">{result.notice}</p>}
          {result.results.length === 0 && <p className="text-muted">No moments matched.</p>}
          <ul className="space-y-4">
            {result.results.map((hit) => (
              <ResultCard
                key={hit.segment_id}
                hit={hit}
                query={result.query}
                mode={result.mode}
                onSaved={setSaved}
              />
            ))}
          </ul>
          {saved && <p className="text-sage">{saved}</p>}
        </div>
      )}
    </div>
  );
}

function ResultCard({
  hit,
  query,
  mode,
  onSaved,
}: {
  hit: SearchHit;
  query: string;
  mode: SearchMode;
  onSaved: (message: string) => void;
}) {
  const [feedback, setFeedback] = useState<string | null>(null);

  async function save() {
    const title = window.prompt("Name this moment", query) ?? "";
    if (!title.trim()) return;
    await api("/api/moments", {
      method: "POST",
      body: JSON.stringify({
        video_id: hit.video_id,
        start_sec: hit.start_sec,
        end_sec: hit.end_sec,
        title: title.trim(),
        query,
      }),
    });
    onSaved(`Saved “${title.trim()}”.`);
  }

  async function mark(relevant: boolean) {
    await api("/api/feedback", {
      method: "POST",
      body: JSON.stringify({
        video_id: hit.video_id,
        segment_id: hit.segment_id,
        query,
        mode,
        start_sec: hit.start_sec,
        end_sec: hit.end_sec,
        relevant,
      }),
    });
    setFeedback(relevant ? "Marked relevant" : "Marked not relevant");
  }

  return (
    <li className="grid gap-4 rounded-2xl border border-line bg-panel p-4 sm:grid-cols-[180px_1fr]">
      {hit.thumbnail_url ? (
        <img src={hit.thumbnail_url} alt="" className="aspect-video w-full rounded-lg object-cover" />
      ) : (
        <div className="grid aspect-video place-items-center rounded-lg bg-panel-2 text-sm text-muted">No frame</div>
      )}
      <div>
        <div className="flex flex-wrap items-baseline justify-between gap-2">
          <h2 className="font-serif text-2xl">{hit.video_title}</h2>
          <p className="text-sm text-muted">
            {hit.score_label} {hit.display_score.toFixed(3)}
            <span className="block text-xs">Not a confidence percentage</span>
          </p>
        </div>
        <p className="mt-1 text-sm text-amber">
          {formatTimestamp(hit.start_sec)}–{formatTimestamp(hit.end_sec)}
        </p>
        <blockquote className="mt-3 border-l-2 border-line pl-3 text-cream">{hit.excerpt}</blockquote>
        <ul className="mt-3 space-y-1 text-sm text-muted">
          {hit.evidence.map((item, index) => (
            <li key={`${item.type}-${index}`}>
              {item.type === "transcript" && `Speech: “${item.text}”`}
              {item.type === "ocr" && `On screen: “${item.text}”`}
              {item.type === "visual" && `Visual similarity ${item.similarity?.toFixed(3) ?? "n/a"}`}
            </li>
          ))}
          {hit.channels.map((channel) => (
            <li key={channel.name}>
              {channelLabel(channel.name)}
              {channel.similarity != null ? ` similarity ${channel.similarity.toFixed(3)}` : ""}
              {channel.keyword_strength != null ? ` keyword strength ${channel.keyword_strength.toFixed(3)}` : ""}
              {channel.rank != null ? `, rank ${channel.rank}` : ""}
            </li>
          ))}
        </ul>
        <div className="mt-4 flex flex-wrap gap-2">
          <Link className="rounded-full bg-amber px-3 py-1.5 text-sm font-medium text-ink" to={`/videos/${hit.video_id}?t=${hit.start_sec}&q=${encodeURIComponent(query)}`}>
            Play from here
          </Link>
          <button type="button" className="rounded-full border border-line px-3 py-1.5 text-sm" onClick={() => void save()}>Save moment</button>
          <button type="button" className="rounded-full border border-line px-3 py-1.5 text-sm" onClick={() => void mark(true)}>Relevant</button>
          <button type="button" className="rounded-full border border-line px-3 py-1.5 text-sm" onClick={() => void mark(false)}>Not relevant</button>
        </div>
        {feedback && <p className="mt-2 text-sm text-sage">{feedback}</p>}
      </div>
    </li>
  );
}
