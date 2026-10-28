export type VideoStatus = "pending" | "processing" | "ready" | "failed";
export type SearchMode = "all" | "speech" | "screen_text" | "visual";

export type Video = {
  id: string;
  title: string;
  original_filename: string;
  duration_sec: number | null;
  status: VideoStatus;
  stage: string;
  stage_label: string;
  stage_message: string | null;
  error_message: string | null;
  warnings: string[];
  has_audio: boolean | null;
  width: number | null;
  height: number | null;
  created_at: string | null;
  thumbnail_url: string | null;
  modalities: { speech: boolean; screen_text: boolean; visual: boolean };
  file_size_bytes: number | null;
};

export type TranscriptSegment = { id: string; start_sec: number; end_sec: number; text: string };

export type Evidence = {
  type: "transcript" | "ocr" | "visual";
  text: string | null;
  start_sec: number;
  end_sec: number;
  similarity: number | null;
};

export type Channel = {
  name: string;
  similarity: number | null;
  keyword_strength: number | null;
  rank: number | null;
};

export type SearchHit = {
  video_id: string;
  video_title: string;
  segment_id: string;
  start_sec: number;
  end_sec: number;
  fusion_score: number;
  rank_score: number | null;
  display_score: number;
  score_label: string;
  excerpt: string;
  thumbnail_url: string | null;
  channels: Channel[];
  evidence: Evidence[];
};

export type SearchResponse = {
  query: string;
  mode: SearchMode;
  ranker_applied: boolean;
  ranker_version: string | null;
  latency_ms: number;
  notice: string | null;
  results: SearchHit[];
};

export type Moment = {
  id: string;
  video_id: string;
  video_title: string;
  start_sec: number;
  end_sec: number;
  title: string;
  note: string;
  query: string;
  created_at: string | null;
  thumbnail_url: string | null;
};

export type Collection = {
  id: string;
  name: string;
  description: string;
  created_at: string | null;
  item_count: number;
  items?: Moment[];
};

export type EvalMethod = {
  name: string;
  recall_at_1: number;
  recall_at_5: number;
  recall_at_10: number;
  ndcg_at_10: number;
  mean_best_iou_at_1: number;
  mean_best_iou_at_5: number;
  mean_latency_ms: number;
};

export type EvaluationReport = {
  available: boolean;
  message?: string;
  dataset_name?: string;
  dataset_label?: string;
  evaluated_at?: string;
  model_versions?: Record<string, string>;
  split?: { train: number; val: number; test: number };
  query_count?: number;
  relevance_definition?: string;
  caveat?: string;
  methods?: EvalMethod[];
  cross_video_top1?: {
    name: string;
    top1_accuracy: number;
    queries: { query: string; expected_video: string; top_video: string | null; top1_match: boolean }[];
  }[];
  by_query_type?: { query_type: string; method: string; recall_at_5: number; count: number }[];
  ingestion?: {
    videos: number;
    mean_seconds_per_video_minute: number | null;
    note?: string;
    per_video?: { title: string; duration_sec: number; processing_sec: number }[];
  } | null;
  ranker_improved?: boolean | null;
  ranker_note?: string;
};
