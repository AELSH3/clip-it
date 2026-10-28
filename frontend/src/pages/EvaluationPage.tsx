import { useEffect, useState } from "react";
import { api } from "../api.ts";
import type { EvaluationReport } from "../types.ts";

export function EvaluationPage() {
  const [report, setReport] = useState<EvaluationReport | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    api<EvaluationReport>("/api/evaluation")
      .then(setReport)
      .catch((err: unknown) => setError(err instanceof Error ? err.message : "Could not load evaluation."));
  }, []);

  if (error) return <p className="text-danger" role="alert">{error}</p>;
  if (!report) return <p className="text-muted">Loading evaluation…</p>;
  if (!report.available) {
    return (
      <section>
        <h1 className="font-serif text-4xl">Evaluation</h1>
        <p className="mt-4 max-w-2xl text-muted">{report.message}</p>
        <p className="mt-4 text-sm text-muted">From the backend folder, run <code className="text-cream">python -m scripts.evaluate</code> after the fixture videos are ingested. This page stays empty until that file exists. It will not show placeholder scores.</p>
      </section>
    );
  }

  return (
    <section>
      <h1 className="font-serif text-4xl">Evaluation</h1>
      <p className="mt-3 max-w-3xl rounded-2xl border border-amber/40 bg-panel p-4 text-amber">{report.caveat}</p>
      <dl className="mt-6 grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
        <Stat label="Dataset" value={report.dataset_name ?? "Unknown"} />
        <Stat label="Queries" value={String(report.query_count ?? 0)} />
        <Stat label="Evaluated" value={report.evaluated_at ? new Date(report.evaluated_at).toLocaleString() : "Unknown"} />
        <Stat label="Split sizes" value={`train ${report.split?.train ?? 0} / val ${report.split?.val ?? 0} / test ${report.split?.test ?? 0}`} />
      </dl>
      <p className="mt-4 text-sm text-muted">{report.dataset_label}</p>
      <p className="mt-2 text-sm text-muted">{report.relevance_definition}</p>
      <h2 className="mt-8 font-serif text-2xl">Model versions</h2>
      <ul className="mt-2 text-sm text-muted">
        {Object.entries(report.model_versions ?? {}).map(([key, value]) => (
          <li key={key}>{key}: {value}</li>
        ))}
      </ul>
      <div className="mt-6 overflow-x-auto">
        <table className="w-full min-w-[720px] border-collapse text-left text-sm">
          <thead>
            <tr className="border-b border-line text-muted">
              <th className="py-2 pr-3">Method</th>
              <th className="py-2 pr-3">R@1</th>
              <th className="py-2 pr-3">R@5</th>
              <th className="py-2 pr-3">R@10</th>
              <th className="py-2 pr-3">nDCG@10</th>
              <th className="py-2 pr-3">IoU@1</th>
              <th className="py-2 pr-3">IoU@5</th>
              <th className="py-2">Latency ms</th>
            </tr>
          </thead>
          <tbody>
            {(report.methods ?? []).map((method) => (
              <tr key={method.name} className="border-b border-line">
                <td className="py-2 pr-3">{method.name}</td>
                <td className="py-2 pr-3">{method.recall_at_1.toFixed(3)}</td>
                <td className="py-2 pr-3">{method.recall_at_5.toFixed(3)}</td>
                <td className="py-2 pr-3">{method.recall_at_10.toFixed(3)}</td>
                <td className="py-2 pr-3">{method.ndcg_at_10.toFixed(3)}</td>
                <td className="py-2 pr-3">{method.mean_best_iou_at_1.toFixed(3)}</td>
                <td className="py-2 pr-3">{method.mean_best_iou_at_5.toFixed(3)}</td>
                <td className="py-2">{method.mean_latency_ms.toFixed(1)}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      {(report.cross_video_top1 ?? []).length > 0 && (
        <>
          <h2 className="mt-8 font-serif text-2xl">Whole library, first hit</h2>
          <p className="mt-2 max-w-3xl text-sm text-muted">
            These rows search every ready video. In-video recall above only searches inside the labeled video, so a single-window clip can score a hit even when another video would rank first.
          </p>
          <ul className="mt-3 space-y-2 text-sm">
            {(report.cross_video_top1 ?? []).map((row) => (
              <li key={row.name} className="rounded-xl border border-line px-3 py-2">
                <span className="font-medium">{row.name}</span>
                <span className="text-muted"> · top-1 {row.top1_accuracy.toFixed(3)}</span>
                {row.queries.map((query) => (
                  <span key={query.query} className="mt-1 block text-muted">
                    “{query.query}” expected {query.expected_video}, first hit {query.top_video ?? "none"}
                  </span>
                ))}
              </li>
            ))}
          </ul>
        </>
      )}
      <h2 className="mt-8 font-serif text-2xl">By query type</h2>
      <ul className="mt-2 text-sm text-muted">
        {(report.by_query_type ?? []).map((row) => (
          <li key={`${row.method}-${row.query_type}`}>{row.query_type} / {row.method}: Recall@5 {row.recall_at_5.toFixed(3)} on {row.count} queries</li>
        ))}
      </ul>
      <p className="mt-6 text-sm text-muted">
        {report.ranker_improved === true
          ? "On this held-out run, fusion plus the ranker beat fusion alone on Recall@5."
          : report.ranker_note || "This run does not show that the trained ranker improves retrieval."}
      </p>
      {report.ingestion && (
        <p className="mt-2 text-sm text-muted">
          Ingestion: {report.ingestion.videos} videos, mean {report.ingestion.mean_seconds_per_video_minute ?? "n/a"} seconds of processing per minute of video.
        </p>
      )}
    </section>
  );
}

function Stat({ label, value }: { label: string; value: string }) {
  return (
    <div className="rounded-2xl border border-line bg-panel p-4">
      <dt className="text-xs uppercase tracking-wide text-muted">{label}</dt>
      <dd className="mt-1 text-lg">{value}</dd>
    </div>
  );
}
