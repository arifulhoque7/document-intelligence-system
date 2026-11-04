import uuid
from datetime import date, datetime
from decimal import Decimal

from pgvector.sqlalchemy import Vector
from sqlalchemy import (
    BigInteger,
    Boolean,
    Computed,
    Date,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    String,
    Text,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB, TSVECTOR, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.config import get_settings
from app.core.db import Base

DIM = get_settings().embedding_dim


def _uuid() -> uuid.UUID:
    return uuid.uuid4()


class User(Base):
    __tablename__ = "users"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    email: Mapped[str] = mapped_column(String(255), unique=True)
    password_hash: Mapped[str] = mapped_column(String(255))
    role: Mapped[str] = mapped_column(String(20), default="reviewer")  # admin | reviewer
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class ProviderSetting(Base):
    __tablename__ = "provider_settings"
    provider: Mapped[str] = mapped_column(String(20), primary_key=True)  # claude|openai|gemini|ollama
    api_key_enc: Mapped[str | None] = mapped_column(Text)
    base_url: Mapped[str | None] = mapped_column(String(500))
    model: Mapped[str | None] = mapped_column(String(100))
    embedding_model: Mapped[str | None] = mapped_column(String(100))
    active_llm: Mapped[bool] = mapped_column(Boolean, default=False)
    active_embedding: Mapped[bool] = mapped_column(Boolean, default=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


class Document(Base):
    __tablename__ = "documents"
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=_uuid)
    filename: Mapped[str] = mapped_column(String(255))
    file_type: Mapped[str] = mapped_column(String(10))  # pdf|image|tiff|xlsx|xls|csv|unknown
    size_bytes: Mapped[int] = mapped_column(BigInteger)
    sha256: Mapped[str] = mapped_column(String(64), index=True)
    storage_path: Mapped[str] = mapped_column(String(500))
    status: Mapped[str] = mapped_column(String(20), default="queued", index=True)
    progress: Mapped[int] = mapped_column(Integer, default=0)  # 0-100
    page_count: Mapped[int | None] = mapped_column(Integer)
    error: Mapped[str | None] = mapped_column(Text)
    attempts: Mapped[int] = mapped_column(Integer, default=0)
    processing_ms: Mapped[int | None] = mapped_column(Integer)
    uploaded_by: Mapped[int | None] = mapped_column(ForeignKey("users.id"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), index=True)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    pages: Mapped[list["DocumentPage"]] = relationship(
        back_populates="document", cascade="all, delete-orphan", order_by="DocumentPage.page_no"
    )
    invoices: Mapped[list["Invoice"]] = relationship(back_populates="document", cascade="all, delete-orphan")
    events: Mapped[list["ProcessingEvent"]] = relationship(
        back_populates="document", cascade="all, delete-orphan", order_by="ProcessingEvent.id"
    )


class DocumentPage(Base):
    __tablename__ = "document_pages"
    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    document_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("documents.id", ondelete="CASCADE"), index=True)
    page_no: Mapped[int] = mapped_column(Integer)  # 1-based page, frame or sheet index
    sheet_name: Mapped[str | None] = mapped_column(String(255))
    text: Mapped[str] = mapped_column(Text, default="")
    method: Mapped[str] = mapped_column(String(10))  # text|ocr|sheet
    ocr_confidence: Mapped[float | None] = mapped_column(Float)
    tsv: Mapped[str] = mapped_column(TSVECTOR, Computed("to_tsvector('simple', coalesce(text, ''))", persisted=True))

    document: Mapped[Document] = relationship(back_populates="pages")
    __table_args__ = (Index("ix_pages_tsv", "tsv", postgresql_using="gin"),)


class Invoice(Base):
    __tablename__ = "invoices"
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=_uuid)
    document_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("documents.id", ondelete="CASCADE"), index=True)
    seq: Mapped[int] = mapped_column(Integer, default=1)  # position inside the document
    source_ref: Mapped[str | None] = mapped_column(String(100))  # "pages 3-4" / "sheet Jan rows 2-9"
    source_text: Mapped[str] = mapped_column(Text, default="")

    invoice_number: Mapped[str | None] = mapped_column(String(100), index=True)
    invoice_number_norm: Mapped[str | None] = mapped_column(String(100), index=True)
    invoice_date: Mapped[date | None] = mapped_column(Date, index=True)
    supplier_name: Mapped[str | None] = mapped_column(String(255))
    customer_name: Mapped[str | None] = mapped_column(String(255))
    subtotal: Mapped[Decimal | None] = mapped_column(Numeric(18, 2))
    tax: Mapped[Decimal | None] = mapped_column(Numeric(18, 2))
    total: Mapped[Decimal | None] = mapped_column(Numeric(18, 2), index=True)
    currency: Mapped[str | None] = mapped_column(String(3))
    line_items: Mapped[list] = mapped_column(JSONB, default=list)
    confidence: Mapped[dict] = mapped_column(JSONB, default=dict)  # field -> 0..1

    status: Mapped[str] = mapped_column(String(20), default="extracted")  # extracted|needs_review|approved
    needs_review: Mapped[bool] = mapped_column(Boolean, default=False, index=True)
    extracted_by: Mapped[str | None] = mapped_column(String(100))  # provider/model or "spreadsheet"
    embedding: Mapped[list[float] | None] = mapped_column(Vector(DIM))
    embedding_model: Mapped[str | None] = mapped_column(String(100))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )
    search_tsv: Mapped[str] = mapped_column(
        TSVECTOR,
        Computed(
            "setweight(to_tsvector('simple', coalesce(invoice_number, '') || ' ' || coalesce(supplier_name, '')"
            " || ' ' || coalesce(customer_name, '')), 'A') || "
            "setweight(to_tsvector('simple', coalesce(source_text, '')), 'B')",
            persisted=True,
        ),
    )

    document: Mapped[Document] = relationship(back_populates="invoices")
    issues: Mapped[list["ValidationIssue"]] = relationship(
        back_populates="invoice", cascade="all, delete-orphan", order_by="ValidationIssue.id"
    )
    revisions: Mapped[list["InvoiceRevision"]] = relationship(
        back_populates="invoice", cascade="all, delete-orphan", order_by="InvoiceRevision.version"
    )
    __table_args__ = (
        Index("ix_invoices_tsv", "search_tsv", postgresql_using="gin"),
        Index(
            "ix_invoices_embedding",
            "embedding",
            postgresql_using="hnsw",
            postgresql_ops={"embedding": "vector_cosine_ops"},
        ),
    )


class InvoiceRevision(Base):
    __tablename__ = "invoice_revisions"
    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    invoice_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("invoices.id", ondelete="CASCADE"), index=True)
    version: Mapped[int] = mapped_column(Integer)
    source: Mapped[str] = mapped_column(String(20))  # extraction|manual|approval
    data: Mapped[dict] = mapped_column(JSONB)
    changes: Mapped[dict] = mapped_column(JSONB, default=dict)  # field -> [old, new]
    user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    invoice: Mapped[Invoice] = relationship(back_populates="revisions")


class ValidationIssue(Base):
    __tablename__ = "validation_issues"
    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    invoice_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("invoices.id", ondelete="CASCADE"), index=True)
    code: Mapped[str] = mapped_column(String(40), index=True)
    field: Mapped[str | None] = mapped_column(String(40))
    severity: Mapped[str] = mapped_column(String(10))  # error|warning
    message: Mapped[str] = mapped_column(Text)

    invoice: Mapped[Invoice] = relationship(back_populates="issues")


class ProcessingEvent(Base):
    __tablename__ = "processing_events"
    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    document_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("documents.id", ondelete="CASCADE"), index=True)
    stage: Mapped[str] = mapped_column(String(30))  # queued|detect|text|ocr|parse|segment|extract|validate|embed|done|error
    status: Mapped[str] = mapped_column(String(10))  # started|ok|warning|failed
    message: Mapped[str | None] = mapped_column(Text)
    duration_ms: Mapped[int | None] = mapped_column(Integer)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    document: Mapped[Document] = relationship(back_populates="events")
