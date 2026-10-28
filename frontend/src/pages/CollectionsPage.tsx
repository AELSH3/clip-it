import { useEffect, useState, type FormEvent } from "react";
import { Link } from "react-router-dom";
import { api, ApiError } from "../api.ts";
import { formatTimestamp } from "../format.ts";
import type { Collection, Moment } from "../types.ts";

export function CollectionsPage() {
  const [collections, setCollections] = useState<Collection[]>([]);
  const [moments, setMoments] = useState<Moment[]>([]);
  const [open, setOpen] = useState<Collection | null>(null);
  const [name, setName] = useState("");
  const [description, setDescription] = useState("");
  const [error, setError] = useState<string | null>(null);

  async function refresh() {
    const [collectionPayload, momentPayload] = await Promise.all([
      api<{ items: Collection[] }>("/api/collections"),
      api<{ items: Moment[] }>("/api/moments"),
    ]);
    setCollections(collectionPayload.items);
    setMoments(momentPayload.items);
  }

  useEffect(() => {
    refresh().catch((err: unknown) => setError(err instanceof Error ? err.message : "Could not load collections."));
  }, []);

  async function create(event: FormEvent) {
    event.preventDefault();
    try {
      await api("/api/collections", { method: "POST", body: JSON.stringify({ name, description }) });
      setName("");
      setDescription("");
      await refresh();
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Could not create the collection.");
    }
  }

  async function openCollection(id: string) {
    const payload = await api<Collection>(`/api/collections/${id}`);
    setOpen(payload);
  }

  async function add(momentId: string) {
    if (!open) return;
    await api(`/api/collections/${open.id}/items`, { method: "POST", body: JSON.stringify({ moment_id: momentId }) });
    await openCollection(open.id);
    await refresh();
  }

  async function removeItem(momentId: string) {
    if (!open) return;
    await api(`/api/collections/${open.id}/items/${momentId}`, { method: "DELETE" });
    await openCollection(open.id);
    await refresh();
  }

  async function removeCollection(id: string) {
    if (!window.confirm("Delete this collection? Saved moments stay in the library.")) return;
    await api(`/api/collections/${id}`, { method: "DELETE" });
    if (open?.id === id) setOpen(null);
    await refresh();
  }

  return (
    <section>
      <h1 className="font-serif text-4xl">Collections</h1>
      <p className="mt-2 text-muted">Group saved moments. Playback still opens the source video at that timestamp.</p>
      {error && <p className="mt-4 text-danger" role="alert">{error}</p>}
      <form onSubmit={(event) => void create(event)} className="mt-6 grid gap-3 rounded-2xl border border-line bg-panel p-4 sm:grid-cols-2">
        <label className="text-sm">
          Name
          <input required value={name} onChange={(event) => setName(event.target.value)} className="mt-1 w-full rounded-lg border border-line bg-ink px-3 py-2" />
        </label>
        <label className="text-sm">
          Description
          <input value={description} onChange={(event) => setDescription(event.target.value)} className="mt-1 w-full rounded-lg border border-line bg-ink px-3 py-2" />
        </label>
        <button type="submit" className="w-fit rounded-full bg-amber px-4 py-2 font-medium text-ink">Create collection</button>
      </form>
      {collections.length === 0 && <p className="mt-6 text-muted">No collections yet.</p>}
      <ul className="mt-6 grid gap-3 sm:grid-cols-2">
        {collections.map((collection) => (
          <li key={collection.id} className="rounded-2xl border border-line bg-panel p-4">
            <button type="button" className="text-left" onClick={() => void openCollection(collection.id)}>
              <h2 className="font-serif text-2xl">{collection.name}</h2>
              <p className="text-sm text-muted">{collection.item_count} moments</p>
            </button>
            <button type="button" className="mt-3 text-sm text-danger" onClick={() => void removeCollection(collection.id)}>Delete</button>
          </li>
        ))}
      </ul>
      {open && (
        <div className="mt-8">
          <h2 className="font-serif text-3xl">{open.name}</h2>
          {(open.items ?? []).length === 0 && <p className="mt-2 text-muted">This collection is empty.</p>}
          <ul className="mt-4 space-y-3">
            {(open.items ?? []).map((moment) => (
              <li key={moment.id} className="flex flex-wrap items-center justify-between gap-3 rounded-xl border border-line px-3 py-2">
                <Link to={`/videos/${moment.video_id}?t=${moment.start_sec}`}>{moment.title}</Link>
                <span className="text-sm text-muted">{moment.video_title} · {formatTimestamp(moment.start_sec)}</span>
                <button type="button" className="text-sm" onClick={() => void removeItem(moment.id)}>Remove</button>
              </li>
            ))}
          </ul>
          <label className="mt-4 block text-sm" htmlFor="add-moment">
            Add a saved moment
            <select id="add-moment" className="mt-1 w-full rounded-lg border border-line bg-ink px-3 py-2" defaultValue="" onChange={(event) => { if (event.target.value) void add(event.target.value); event.target.value = ""; }}>
              <option value="">Choose a moment</option>
              {moments.map((moment) => (
                <option key={moment.id} value={moment.id}>{moment.title} ({moment.video_title})</option>
              ))}
            </select>
          </label>
        </div>
      )}
      <h2 className="mt-10 font-serif text-2xl">All saved moments</h2>
      {moments.length === 0 && <p className="mt-2 text-muted">Save a search result to see it here.</p>}
      <ul className="mt-3 space-y-2">
        {moments.map((moment) => (
          <li key={moment.id}>
            <Link to={`/videos/${moment.video_id}?t=${moment.start_sec}`}>{moment.title}</Link>
            <span className="ml-2 text-sm text-muted">{formatTimestamp(moment.start_sec)}–{formatTimestamp(moment.end_sec)}</span>
          </li>
        ))}
      </ul>
    </section>
  );
}
