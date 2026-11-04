"""Keyword (Postgres full-text), semantic (pgvector cosine) and hybrid (reciprocal rank fusion) search."""

from sqlalchemy import func, select
from sqlalchemy.orm import Session, selectinload

from app.llm import LLMError, active_config, embed
from app.models import Invoice

RRF_K = 60


def keyword(db: Session, q: str, limit: int) -> list[tuple[Invoice, float, str]]:
    query = func.websearch_to_tsquery("simple", q)
    rank = func.ts_rank_cd(Invoice.search_tsv, query)
    snippet = func.ts_headline(
        "simple", func.left(Invoice.source_text, 5000), query, "MaxFragments=2, MaxWords=18, MinWords=6, StartSel=<<, StopSel=>>"
    )
    rows = db.execute(
        select(Invoice, rank, snippet)
        .options(selectinload(Invoice.document), selectinload(Invoice.issues))
        .where(Invoice.search_tsv.op("@@")(query))
        .order_by(rank.desc())
        .limit(limit)
    ).all()
    return [(inv, float(score), snip) for inv, score, snip in rows]


def semantic(db: Session, q: str, limit: int) -> list[tuple[Invoice, float, str]]:
    cfg = active_config(db, "embedding")
    if not cfg:
        raise LLMError("No embedding provider active. An admin can enable one in Settings.")
    vector = embed(cfg, [q])[0]
    distance = Invoice.embedding.cosine_distance(vector)
    rows = db.execute(
        select(Invoice, distance)
        .options(selectinload(Invoice.document), selectinload(Invoice.issues))
        # Only vectors from the current model are comparable with the query vector.
        .where(Invoice.embedding.is_not(None), Invoice.embedding_model == f"{cfg.provider}/{cfg.embedding_model}")
        .order_by(distance)
        .limit(limit)
    ).all()
    return [(inv, round(1 - float(d), 4), (inv.source_text or "")[:200]) for inv, d in rows]


def hybrid(db: Session, q: str, limit: int) -> list[tuple[Invoice, float, str]]:
    lists = [keyword(db, q, limit * 2)]
    try:
        lists.append(semantic(db, q, limit * 2))
    except LLMError:
        pass  # degrade to keyword-only when embeddings are not configured
    scores: dict = {}
    for results in lists:
        for rank, (inv, _, snip) in enumerate(results, start=1):
            entry = scores.setdefault(inv.id, [inv, 0.0, snip])
            entry[1] += 1 / (RRF_K + rank)
    ranked = sorted(scores.values(), key=lambda e: e[1], reverse=True)[:limit]
    return [(inv, round(score, 5), snip) for inv, score, snip in ranked]


MODES = {"keyword": keyword, "semantic": semantic, "hybrid": hybrid}
