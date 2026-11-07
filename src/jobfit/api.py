"""FastAPI service over the JobFit index.

Everything here is a thin layer: the pipeline lives in ingest/search/scoring, so
these handlers stay readable and the logic stays testable without HTTP.
"""

from __future__ import annotations

from contextlib import asynccontextmanager
from typing import Annotated, Literal

from fastapi import FastAPI, File, HTTPException, Query, UploadFile
from psycopg.rows import dict_row
from psycopg_pool import ConnectionPool
from pydantic import BaseModel, Field

from . import agent as agent_mod
from .config import Settings
from .embed import EmbeddingError, OllamaEmbedder
from .ingest import count_rows
from .resume import Resume, ResumeParseError, parse, pdf_to_text
from .scoring import score_resume
from .search import search as run_search

settings = Settings.load()
embedder = OllamaEmbedder(settings.ollama_url, settings.embed_model)
pool: ConnectionPool | None = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    global pool
    # dict_row on the pool: every query in this app reads columns by name
    pool = ConnectionPool(
        settings.database_url,
        min_size=1,
        max_size=4,
        open=True,
        timeout=10,
        kwargs={"row_factory": dict_row},
    )
    yield
    pool.close()


app = FastAPI(
    title="JobFit",
    version="0.2.0",
    summary="Semantic search and resume matching over a local job-posting index.",
    lifespan=lifespan,
)


def _pool() -> ConnectionPool:
    if pool is None:
        raise HTTPException(503, "connection pool not ready")
    return pool


# ---------------------------------------------------------------- models
class Hit(BaseModel):
    id: int
    title: str
    company: str
    location: str = ""
    source: str = ""
    url: str = ""
    score: float


class SearchResponse(BaseModel):
    query: str
    count: int
    results: list[Hit]


class MatchBody(BaseModel):
    resume_text: str = Field(min_length=1, description="Plain text of the resume")
    k: int = Field(10, ge=1, le=50)
    min_score: float = Field(0.0, ge=0.0, le=1.0)
    rank_by: Literal["semantic", "hybrid"] = Field(
        "semantic", description="semantic = vectors only; hybrid = vectors + shared-skill bonus"
    )


class MatchHit(Hit):
    matched_terms: list[str] = []
    best_chunk: str = ""


class MatchResponse(BaseModel):
    rank_by: str = "semantic"
    k: int
    count: int
    resume_chunks: int
    resume_keywords: list[str]
    results: list[MatchHit]


class AskBody(BaseModel):
    question: str = Field(min_length=3)
    resume_text: str | None = None
    model: str | None = Field(None, description="Override the local model")


# ---------------------------------------------------------------- routes
@app.get("/health", summary="Is the index alive?")
def health():
    with _pool().connection() as c:
        total, embedded = count_rows(c)
    try:
        embedder.check()
        model_state = "ready"
    except EmbeddingError as exc:
        model_state = f"unavailable: {exc}"
    return {
        "status": "ok" if embedded else "empty",
        "postings": total,
        "embedded": embedded,
        "embed_model": settings.embed_model,
        "embed_model_state": model_state,
    }


@app.get("/search", response_model=SearchResponse, summary="Semantic search over postings")
def search(q: Annotated[str, Query(min_length=2)], k: Annotated[int, Query(ge=1, le=50)] = 5):
    with _pool().connection() as c:
        rows = run_search(c, embedder, q, k=k)
    return SearchResponse(query=q, count=len(rows), results=[Hit(**r) for r in rows])


@app.post("/match", response_model=MatchResponse, summary="Rank postings against a resume")
def match(body: MatchBody):
    try:
        resume = parse(body.resume_text)
    except ResumeParseError as exc:
        raise HTTPException(422, str(exc)) from exc
    with _pool().connection() as c:
        rows = score_resume(
            c, embedder, resume, k=body.k, min_score=body.min_score, rank_by=body.rank_by
        )
    return MatchResponse(
        rank_by=body.rank_by,
        k=body.k,
        count=len(rows),
        resume_chunks=len(resume.chunks),
        resume_keywords=list(resume.keywords),
        results=[MatchHit(**r) for r in rows],
    )


@app.post("/match/upload", response_model=MatchResponse, summary="Same as /match, from a PDF")
async def match_upload(file: Annotated[UploadFile, File()], k: int = 10):
    data = await file.read()
    if file.filename and file.filename.lower().endswith(".pdf"):
        try:
            text = pdf_to_text(data)
        except ResumeParseError as exc:
            raise HTTPException(422, str(exc)) from exc
    else:
        text = data.decode("utf-8", errors="replace")
    return match(MatchBody(resume_text=text, k=k))


@app.post("/ask", summary="Ask in plain English; the local model picks the tool")
def ask(body: AskBody):
    def search_jobs(args: dict):
        q = args.get("query") or body.question
        k = min(int(args.get("k") or 5), 20)
        with _pool().connection() as c:
            return run_search(c, embedder, q, k=k)

    def match_resume_tool(args: dict):
        if not body.resume_text:
            return {"error": "no resume supplied with this request"}
        resume: Resume = parse(body.resume_text)
        k = min(int(args.get("k") or 5), 20)
        with _pool().connection() as c:
            return score_resume(c, embedder, resume, k=k)

    result = agent_mod.run(
        body.question,
        ollama_url=settings.ollama_url,
        model=body.model or settings.agent_model,
        tools_impl={"search_jobs": search_jobs, "match_resume": match_resume_tool},
        resume_text=body.resume_text,
    )
    return result


