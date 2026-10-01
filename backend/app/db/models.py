"""SQLAlchemy models for every table in Architecture §14."""

from __future__ import annotations

from datetime import date, datetime
from typing import Any

from pgvector.sqlalchemy import Vector
from sqlalchemy import (
    BigInteger,
    Boolean,
    CheckConstraint,
    Date,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    MetaData,
    Text,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

EMBEDDING_DIM = 1536  # text-embedding-3-small

NAMING_CONVENTION = {
    "ix": "ix_%(column_0_label)s",
    "uq": "uq_%(table_name)s_%(column_0_name)s",
    "ck": "ck_%(table_name)s_%(constraint_name)s",
    "fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s",
    "pk": "pk_%(table_name)s",
}


class Base(DeclarativeBase):
    metadata = MetaData(naming_convention=NAMING_CONVENTION)


def _created_at() -> Mapped[datetime]:
    return mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)


class Document(Base):
    __tablename__ = "documents"

    id: Mapped[str] = mapped_column(Text, primary_key=True)  # slug, e.g. "doc_03"
    document_name: Mapped[str] = mapped_column(Text, nullable=False)
    publisher: Mapped[str] = mapped_column(Text, nullable=False)
    year: Mapped[int] = mapped_column(Integer, nullable=False)
    source_url: Mapped[str] = mapped_column(Text, nullable=False)
    retrieval_date: Mapped[date | None] = mapped_column(Date)  # written by the fetch step
    doc_type: Mapped[str | None] = mapped_column(Text)
    file_sha256: Mapped[str | None] = mapped_column(Text)
    page_count: Mapped[int | None] = mapped_column(Integer)
    created_at: Mapped[datetime] = _created_at()


class Chunk(Base):
    __tablename__ = "chunks"
    __table_args__ = (
        CheckConstraint("chunk_type IN ('prose', 'table', 'list')", name="chunk_type"),
        Index("ix_chunks_document_id", "document_id"),
        Index(
            "ix_chunks_embedding_hnsw",
            "embedding",
            postgresql_using="hnsw",
            postgresql_ops={"embedding": "vector_cosine_ops"},
        ),
    )

    chunk_id: Mapped[str] = mapped_column(Text, primary_key=True)
    document_id: Mapped[str] = mapped_column(ForeignKey("documents.id"), nullable=False)
    section_path: Mapped[str] = mapped_column(Text, nullable=False)
    page_start: Mapped[int] = mapped_column(Integer, nullable=False)
    page_end: Mapped[int] = mapped_column(Integer, nullable=False)
    chunk_type: Mapped[str] = mapped_column(Text, nullable=False)
    text: Mapped[str] = mapped_column(Text, nullable=False)  # display text, no embedding prefix
    token_count: Mapped[int] = mapped_column(Integer, nullable=False)
    embedding: Mapped[list[float]] = mapped_column(Vector(EMBEDDING_DIM), nullable=False)
    embedding_model: Mapped[str] = mapped_column(Text, nullable=False)
    content_hash: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = _created_at()


class Conversation(Base):
    __tablename__ = "conversations"
    __table_args__ = (Index("ix_conversations_session_token_hash", "session_token_hash"),)

    id: Mapped[str] = mapped_column(Text, primary_key=True)
    session_token_hash: Mapped[str] = mapped_column(Text, nullable=False)
    title: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = _created_at()
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )


class Message(Base):
    __tablename__ = "messages"
    __table_args__ = (
        CheckConstraint("role IN ('user', 'assistant')", name="role"),
        CheckConstraint(
            "status IS NULL OR status IN ('answered', 'not_in_corpus', 'out_of_scope', 'error')",
            name="status",
        ),
        Index("ix_messages_conversation_id_created_at", "conversation_id", "created_at"),
    )

    id: Mapped[str] = mapped_column(Text, primary_key=True)
    conversation_id: Mapped[str] = mapped_column(
        ForeignKey("conversations.id", ondelete="CASCADE"), nullable=False
    )
    role: Mapped[str] = mapped_column(Text, nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str | None] = mapped_column(Text)
    refusal_reason: Mapped[str | None] = mapped_column(Text)
    raw_llm_output: Mapped[dict[str, Any] | None] = mapped_column(JSONB)
    standalone_query: Mapped[str | None] = mapped_column(Text)
    safety_decision: Mapped[dict[str, Any] | None] = mapped_column(JSONB)
    model_info: Mapped[dict[str, Any] | None] = mapped_column(JSONB)
    latency_ms: Mapped[int | None] = mapped_column(Integer)
    # clock_timestamp() (not now()) so messages written in one transaction still order correctly.
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.clock_timestamp(), nullable=False
    )


class MessageSource(Base):
    """The full retrieved set for an assistant message, whether or not it was cited."""

    __tablename__ = "message_sources"

    message_id: Mapped[str] = mapped_column(
        ForeignKey("messages.id", ondelete="CASCADE"), primary_key=True
    )
    chunk_id: Mapped[str] = mapped_column(ForeignKey("chunks.chunk_id"), primary_key=True)
    rank: Mapped[int] = mapped_column(Integer, nullable=False)
    score: Mapped[float] = mapped_column(nullable=False)
    used_in_claims: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default="false")
    created_at: Mapped[datetime] = _created_at()


class Claim(Base):
    __tablename__ = "claims"
    __table_args__ = (Index("ix_claims_message_id", "message_id"),)

    id: Mapped[str] = mapped_column(Text, primary_key=True)
    message_id: Mapped[str] = mapped_column(
        ForeignKey("messages.id", ondelete="CASCADE"), nullable=False
    )
    position: Mapped[int] = mapped_column(Integer, nullable=False)
    claim_text: Mapped[str] = mapped_column(Text, nullable=False)
    chunk_id: Mapped[str] = mapped_column(ForeignKey("chunks.chunk_id"), nullable=False)
    supporting_quote: Mapped[str] = mapped_column(Text, nullable=False)
    verified: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default="false")
    verification_notes: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = _created_at()


class EvalQuestion(Base):
    __tablename__ = "eval_questions"
    __table_args__ = (
        CheckConstraint(
            "suite IN ('retrieval', 'benchmark', 'safety', 'consistency')", name="suite"
        ),
        CheckConstraint(
            "expected_behaviour IS NULL OR "
            "expected_behaviour IN ('answer', 'not_in_corpus', 'out_of_scope')",
            name="expected_behaviour",
        ),
    )

    id: Mapped[str] = mapped_column(Text, primary_key=True)  # stable id from the question YAML
    suite: Mapped[str] = mapped_column(Text, nullable=False)
    question: Mapped[str] = mapped_column(Text, nullable=False)
    category: Mapped[str | None] = mapped_column(Text)
    expected_document_id: Mapped[str | None] = mapped_column(Text)
    expected_section: Mapped[str | None] = mapped_column(Text)
    expected_behaviour: Mapped[str | None] = mapped_column(Text)
    notes: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = _created_at()


class EvalRun(Base):
    __tablename__ = "eval_runs"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    suite: Mapped[str] = mapped_column(Text, nullable=False)
    started_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    config: Mapped[dict[str, Any] | None] = mapped_column(JSONB)  # k, thresholds, models
    git_sha: Mapped[str | None] = mapped_column(Text)
    summary: Mapped[dict[str, Any] | None] = mapped_column(JSONB)
    created_at: Mapped[datetime] = _created_at()


class EvalResult(Base):
    __tablename__ = "eval_results"
    __table_args__ = (Index("ix_eval_results_eval_run_id", "eval_run_id"),)

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    eval_run_id: Mapped[int] = mapped_column(
        ForeignKey("eval_runs.id", ondelete="CASCADE"), nullable=False
    )
    eval_question_id: Mapped[str] = mapped_column(ForeignKey("eval_questions.id"), nullable=False)
    repeat_index: Mapped[int] = mapped_column(Integer, nullable=False, server_default="0")
    retrieved: Mapped[Any | None] = mapped_column(JSONB)
    hit: Mapped[bool | None] = mapped_column(Boolean)
    rank_of_expected: Mapped[int | None] = mapped_column(Integer)
    response: Mapped[dict[str, Any] | None] = mapped_column(JSONB)
    failures: Mapped[Any | None] = mapped_column(JSONB)
    citation_checks: Mapped[Any | None] = mapped_column(JSONB)
    manual_review: Mapped[Any | None] = mapped_column(JSONB)
    created_at: Mapped[datetime] = _created_at()


class FailureLog(Base):
    """Categorised failures with full context. Kept after a conversation is deleted."""

    __tablename__ = "failure_logs"
    __table_args__ = (
        Index("ix_failure_logs_category", "category"),
        Index("ix_failure_logs_created_at", "created_at"),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    created_at: Mapped[datetime] = _created_at()
    category: Mapped[str] = mapped_column(Text, nullable=False)  # taxonomy in Architecture §17.1
    detected_by: Mapped[str] = mapped_column(Text, nullable=False)
    user_question: Mapped[str] = mapped_column(Text, nullable=False)
    model_response: Mapped[Any | None] = mapped_column(JSONB)
    retrieved_chunks: Mapped[Any | None] = mapped_column(JSONB)  # snapshot incl. text
    model_info: Mapped[dict[str, Any] | None] = mapped_column(JSONB)
    error_description: Mapped[str | None] = mapped_column(Text)
    message_id: Mapped[str | None] = mapped_column(ForeignKey("messages.id", ondelete="SET NULL"))
    eval_run_id: Mapped[int | None] = mapped_column(ForeignKey("eval_runs.id", ondelete="SET NULL"))
