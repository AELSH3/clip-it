"""Initial Clip-It schema.

Revision ID: 001_initial
Revises:
Create Date: 2026-10-27
"""

from alembic import op
import sqlalchemy as sa
from pgvector.sqlalchemy import Vector
from sqlalchemy.dialects import postgresql

revision = "001_initial"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("CREATE EXTENSION IF NOT EXISTS vector")
    op.create_table(
        "videos",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("title", sa.String(300), nullable=False),
        sa.Column("original_filename", sa.String(300), nullable=False),
        sa.Column("extension", sa.String(16), nullable=False),
        sa.Column("file_size_bytes", sa.Integer()),
        sa.Column("duration_sec", sa.Float()),
        sa.Column("width", sa.Integer()),
        sa.Column("height", sa.Integer()),
        sa.Column("fps", sa.Float()),
        sa.Column("has_audio", sa.Boolean()),
        sa.Column("status", sa.String(32), nullable=False),
        sa.Column("stage", sa.String(32), nullable=False),
        sa.Column("stage_label", sa.String(120), nullable=False),
        sa.Column("stage_message", sa.Text()),
        sa.Column("error_message", sa.Text()),
        sa.Column("warnings", postgresql.JSONB(), nullable=False),
        sa.Column("modalities", postgresql.JSONB(), nullable=False),
        sa.Column("speech_model_id", sa.String(200)),
        sa.Column("text_model_id", sa.String(200)),
        sa.Column("visual_model_id", sa.String(200)),
        sa.Column("processing_started_at", sa.DateTime(timezone=True)),
        sa.Column("processing_finished_at", sa.DateTime(timezone=True)),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_videos_status", "videos", ["status"])
    op.create_table(
        "transcript_segments",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("video_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("videos.id", ondelete="CASCADE"), nullable=False),
        sa.Column("start_sec", sa.Float(), nullable=False),
        sa.Column("end_sec", sa.Float(), nullable=False),
        sa.Column("text", sa.Text(), nullable=False),
        sa.Column("words", postgresql.JSONB(), nullable=False),
    )
    op.create_index("ix_transcript_segments_video_id", "transcript_segments", ["video_id"])
    op.create_table(
        "ocr_observations",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("video_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("videos.id", ondelete="CASCADE"), nullable=False),
        sa.Column("timestamp_sec", sa.Float(), nullable=False),
        sa.Column("text", sa.Text(), nullable=False),
        sa.Column("frame_relpath", sa.String(300), nullable=False),
    )
    op.create_index("ix_ocr_observations_video_id", "ocr_observations", ["video_id"])
    op.create_table(
        "search_segments",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("video_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("videos.id", ondelete="CASCADE"), nullable=False),
        sa.Column("start_sec", sa.Float(), nullable=False),
        sa.Column("end_sec", sa.Float(), nullable=False),
        sa.Column("transcript_text", sa.Text(), nullable=False),
        sa.Column("ocr_text", sa.Text(), nullable=False),
        sa.Column("transcript_tsv", postgresql.TSVECTOR()),
        sa.Column("ocr_tsv", postgresql.TSVECTOR()),
        sa.Column("frame_relpath", sa.String(300)),
    )
    op.create_index("ix_search_segments_video_id", "search_segments", ["video_id"])
    op.create_index("ix_search_segments_transcript_tsv", "search_segments", ["transcript_tsv"], postgresql_using="gin")
    op.create_index("ix_search_segments_ocr_tsv", "search_segments", ["ocr_tsv"], postgresql_using="gin")
    op.create_table(
        "text_embeddings",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("segment_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("search_segments.id", ondelete="CASCADE"), nullable=False),
        sa.Column("video_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("videos.id", ondelete="CASCADE"), nullable=False),
        sa.Column("source", sa.String(32), nullable=False),
        sa.Column("model_id", sa.String(200), nullable=False),
        sa.Column("embedding", Vector(384), nullable=False),
        sa.UniqueConstraint("segment_id", "source", "model_id", name="uq_text_embedding_source"),
    )
    op.create_index("ix_text_embeddings_segment_id", "text_embeddings", ["segment_id"])
    op.create_index("ix_text_embeddings_video_id", "text_embeddings", ["video_id"])
    op.execute(
        "CREATE INDEX ix_text_embeddings_hnsw ON text_embeddings USING hnsw (embedding vector_cosine_ops)"
    )
    op.create_table(
        "frame_embeddings",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("video_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("videos.id", ondelete="CASCADE"), nullable=False),
        sa.Column("timestamp_sec", sa.Float(), nullable=False),
        sa.Column("frame_relpath", sa.String(300), nullable=False),
        sa.Column("model_id", sa.String(200), nullable=False),
        sa.Column("embedding", Vector(512), nullable=False),
    )
    op.create_index("ix_frame_embeddings_video_id", "frame_embeddings", ["video_id"])
    op.execute(
        "CREATE INDEX ix_frame_embeddings_hnsw ON frame_embeddings USING hnsw (embedding vector_cosine_ops)"
    )
    op.create_table(
        "moments",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("video_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("videos.id", ondelete="CASCADE"), nullable=False),
        sa.Column("start_sec", sa.Float(), nullable=False),
        sa.Column("end_sec", sa.Float(), nullable=False),
        sa.Column("title", sa.String(200), nullable=False),
        sa.Column("note", sa.Text(), nullable=False),
        sa.Column("query", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_moments_video_id", "moments", ["video_id"])
    op.create_table(
        "collections",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("name", sa.String(200), nullable=False),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_table(
        "collection_items",
        sa.Column("collection_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("collections.id", ondelete="CASCADE"), primary_key=True),
        sa.Column("moment_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("moments.id", ondelete="CASCADE"), primary_key=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_table(
        "feedback",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("video_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("videos.id", ondelete="CASCADE"), nullable=False),
        sa.Column("segment_id", postgresql.UUID(as_uuid=True)),
        sa.Column("query", sa.Text(), nullable=False),
        sa.Column("mode", sa.String(32), nullable=False),
        sa.Column("start_sec", sa.Float(), nullable=False),
        sa.Column("end_sec", sa.Float(), nullable=False),
        sa.Column("relevant", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_feedback_video_id", "feedback", ["video_id"])


def downgrade() -> None:
    op.drop_table("feedback")
    op.drop_table("collection_items")
    op.drop_table("collections")
    op.drop_table("moments")
    op.drop_table("frame_embeddings")
    op.drop_table("text_embeddings")
    op.drop_table("search_segments")
    op.drop_table("ocr_observations")
    op.drop_table("transcript_segments")
    op.drop_table("videos")
