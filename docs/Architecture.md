# Architecture: AI Nutrition Assistant (RAG-based)

> Technical design for the system defined in [ProblemStatement.md](ProblemStatement.md). It fixes the technology choices, component boundaries, data model, API contracts, response schema, RAG and safety design, and evaluation and deployment plan.

---

## Table of Contents

1. [Architectural Goals and Constraints](#1-architectural-goals-and-constraints)
2. [Technology Decisions](#2-technology-decisions)
3. [System Context and Component Overview](#3-system-context-and-component-overview)
4. [Repository Structure](#4-repository-structure)
5. [Offline Ingestion Pipeline](#5-offline-ingestion-pipeline)
6. [Online Request Pipeline](#6-online-request-pipeline)
7. [Safety Layer](#7-safety-layer)
8. [Retrieval Design](#8-retrieval-design)
9. [Generation and System Prompt](#9-generation-and-system-prompt)
10. [Structured Response Schema](#10-structured-response-schema)
11. [Response Validation and Citation Verification](#11-response-validation-and-citation-verification)
12. [Refusal Handling](#12-refusal-handling)
13. [Conversation Management](#13-conversation-management)
14. [Data Model](#14-data-model)
15. [API Contracts](#15-api-contracts)
16. [Frontend Architecture](#16-frontend-architecture)
17. [Failure Logging and Monitoring](#17-failure-logging-and-monitoring)
18. [Evaluation Architecture](#18-evaluation-architecture)
19. [Security](#19-security)
20. [Deployment](#20-deployment)
21. [Configuration](#21-configuration)
22. [Known Limitations and Risks](#22-known-limitations-and-risks)
23. [Implementation Phases](#23-implementation-phases)
24. [Requirements Traceability](#24-requirements-traceability)

---

## 1. Architectural Goals and Constraints

| # | Goal / Constraint | Architectural consequence |
|---|---|---|
| G1 | Every factual claim is backed by retrieved evidence. | The LLM sees only retrieved chunks. Output is structured JSON, and a deterministic validator checks every claim against those chunks before the user sees it. |
| G2 | Safety must not depend on the LLM. | A rule-based safety gate runs **before** retrieval and generation, and an output guard runs **after**. Neither calls an LLM. |
| G3 | Citations must be real and accurate. | Citation metadata is **hydrated from the database by `chunk_id`**, never trusted from model output. Quotes and numbers are mechanically verified against chunk text. |
| G4 | Two distinct refusal types. | Separate `not_in_corpus` and `out_of_scope` statuses with separate code paths and templates. |
| G5 | No secrets in the browser. | The browser talks only to our backend. Only the backend holds LLM, embedding and database credentials. |
| G6 | Failures are evidence, not noise. | A failure logger records categorised failures with full context. There are no per-question patches. |
| G7 | Measurable quality. | An evaluation harness shares the production pipeline code and persists results. |
| G8 | One cohesive deployable system. | A single repository with a monorepo layout, one Postgres instance (relational and vector), and two deployable services. |

---

## 2. Technology Decisions

The problem statement offers options. This is the single consistent set chosen for the build.

| Layer | Choice | Rationale | Alternatives considered |
|---|---|---|---|
| Frontend | **Next.js (App Router) + React + TypeScript** | Fast to build a responsive chat UI, first-class Vercel deployment, type-safe API client. | Plain React SPA |
| Backend | **FastAPI (Python 3.11)** | Same language as the ingestion and RAG code, Pydantic gives schema validation for free, async I/O. | Next.js API routes |
| LLM | **Anthropic Claude via the Messages API** (model ID configurable, default `claude-sonnet-5-5`) | Strong instruction-following, and tool-use forces schema-conformant output. The provider sits behind a thin adapter so it can be swapped. | OpenAI API |
| Relational DB + vector store | **Supabase Postgres + `pgvector`** | One datastore for relational data and vectors. Chunks and their metadata live in the same row, so citations cannot drift from vectors. | Postgres + Qdrant, Pinecone, SQLite |
| Embeddings | **OpenAI `text-embedding-3-small` (1536 dims)** | Good quality and low cost, with a managed API. Query and document embeddings use the same model. | sentence-transformers (local) |
| PDF processing | **PyMuPDF (`pymupdf`)** with font-size/weight heading detection | Fast, pure-library, exposes text blocks with font metadata for heading detection and table-region detection. | Docling, Unstructured, LlamaParse |
| RAG framework | **Custom Python** | The pipeline is small, and custom code gives full control over validation, hydration and logging, with no opaque abstractions. | LangChain |
| Deployment | **Vercel** (frontend), **Railway** (backend), **Supabase** (DB) | Matches the problem statement's suggestion and is simple to operate. | Single-host Docker |
| Version control | **GitHub** | Required. | — |

> Decisions here are recorded in the README's "Technology Decisions" section once the build starts. If a choice changes, update this table.

---

## 3. System Context and Component Overview

```
                         ┌────────────────────────────────────────────────┐
                         │                    Browser                     │
                         │  Next.js app (chat · history · sources panel)  │
                         └───────────────────────┬────────────────────────┘
                                                 │ HTTPS (JSON)
                                                 ▼
┌────────────────────────────────────────────────────────────────────────────────┐
│                           FastAPI Backend (Railway)                            │
│                                                                                │
│  ┌──────────┐  ┌──────────────┐  ┌────────────┐  ┌────────────┐  ┌───────────┐ │
│  │ API layer│─▶│ Chat service │─▶│ Safety gate│  │ Retriever  │  │ Generator │ │
│  │ (routes) │  │ (orchestrate)│  │ (pre/post) │  │ (vector)   │  │ (LLM)     │ │
│  └──────────┘  └──────┬───────┘  └────────────┘  └─────┬──────┘  └─────┬─────┘ │
│                       │                                │               │       │
│              ┌────────▼────────┐             ┌─────────▼──────┐   ┌────▼─────┐ │
│              │ Validator +     │             │ Embedding      │   │ Anthropic│ │
│              │ citation verify │             │ client         │   │ API      │ │
│              └────────┬────────┘             └─────────┬──────┘   └──────────┘ │
│                       │                                │ OpenAI Embeddings API │
│              ┌────────▼────────┐                                               │
│              │ Failure logger  │                                               │
│              └────────┬────────┘                                               │
└───────────────────────┼────────────────────────────────────────────────────────┘
                        ▼
        ┌────────────────────────────────────────────┐
        │        Supabase Postgres + pgvector        │
        │ documents · chunks(vector) · conversations │
        │ messages · message_sources · claims        │
        │ failure_logs · eval_*                      │
        └────────────────────────────────────────────┘
                        ▲
                        │ (offline, run by developers / CI)
        ┌───────────────┴────────────────────────────┐
        │  Ingestion CLI: PDF → text → chunks →      │
        │  embeddings → upsert     +  Eval harness   │
        └────────────────────────────────────────────┘
```

### Component responsibilities

| Component | Responsibility |
|---|---|
| **API layer** | HTTP routing, request validation (Pydantic), session identification, rate limiting, error mapping. No business logic. |
| **Chat service** | Orchestrates the online pipeline: safety → retrieval → generation → validation → persistence → response. |
| **Safety gate** | Deterministic classification of restricted intents (pre-retrieval) and guard on outputs (post-generation). Independent of the LLM. |
| **Retriever** | Embeds the query, runs vector search with optional document filter, applies a relevance threshold and cross-document diversification. |
| **Generator** | Builds the prompt from the system prompt and retrieved chunks, calls the LLM using forced tool-use for JSON output, and returns the raw structured result. |
| **Validator / citation verifier** | Schema validation, chunk-membership checks, metadata hydration, quote and number verification. Decides pass or fail. |
| **Failure logger** | Writes categorised failure records with full context. |
| **Ingestion CLI** | Offline: parse PDFs, chunk, embed, upsert, and record document metadata. |
| **Evaluation harness** | Offline: runs question banks through the real pipeline, computes metrics, persists results. |

---

## 4. Repository Structure

```
.
├── docs/
│   ├── ProblemStatement.md
│   ├── Architecture.md
│   └── reports/                     # eval outputs: hit-rate, failure analysis, citation checks
├── backend/
│   ├── app/
│   │   ├── main.py                  # FastAPI app factory, CORS, middleware
│   │   ├── config.py                # Settings (pydantic-settings), env loading
│   │   ├── api/
│   │   │   ├── chat.py              # POST /api/chat
│   │   │   ├── conversations.py
│   │   │   ├── documents.py
│   │   │   ├── admin.py             # failures, eval (token-protected)
│   │   │   └── deps.py              # session id, rate limit, db session
│   │   ├── services/
│   │   │   ├── chat_service.py      # orchestration
│   │   │   ├── retrieval.py
│   │   │   ├── generation.py
│   │   │   ├── validation.py        # schema + citation verification
│   │   │   └── refusals.py          # templates for both refusal types
│   │   ├── safety/
│   │   │   ├── rules.py             # patterns, normalisation
│   │   │   ├── intent_index.py      # exemplar-embedding similarity check
│   │   │   ├── input_gate.py
│   │   │   └── output_guard.py
│   │   ├── llm/
│   │   │   ├── base.py              # LLMClient protocol
│   │   │   ├── anthropic_client.py
│   │   │   └── prompts/system_prompt.md
│   │   ├── embeddings/client.py
│   │   ├── db/
│   │   │   ├── models.py            # SQLAlchemy models
│   │   │   ├── session.py
│   │   │   └── migrations/          # Alembic
│   │   ├── schemas/                 # Pydantic: request/response/claim/source
│   │   └── logging/failure_logger.py
│   ├── ingestion/
│   │   ├── fetch.py                 # download PDFs, record retrieval date
│   │   ├── parse.py                 # PyMuPDF extraction, headings, tables
│   │   ├── chunk.py
│   │   ├── embed_and_store.py
│   │   ├── manifest.yaml            # corpus: name, publisher, year, url
│   │   └── run.py                   # CLI entrypoint
│   ├── evaluation/
│   │   ├── questions/
│   │   │   ├── retrieval_eval.yaml  # 15+ with expected doc + section
│   │   │   ├── benchmark.yaml       # 10 across 4 categories
│   │   │   └── safety_adversarial.yaml
│   │   ├── retrieval_eval.py
│   │   ├── benchmark_run.py
│   │   ├── consistency.py
│   │   ├── safety_eval.py
│   │   └── report.py
│   ├── tests/                       # unit + integration
│   ├── pyproject.toml
│   └── Dockerfile
├── frontend/
│   ├── src/
│   │   ├── app/                     # routes (App Router)
│   │   ├── components/              # Chat, MessageList, Composer, SourcesPanel, ...
│   │   ├── lib/api.ts               # typed client for the backend
│   │   └── types/api.ts             # mirrors backend schemas
│   ├── package.json
│   └── next.config.js
├── data/
│   └── raw_pdfs/                    # source PDFs (or fetched at ingest time)
├── .env.example
└── README.md
```

---

## 5. Offline Ingestion Pipeline

Run by a developer or CI, never on a request path. It is idempotent and re-runnable.

```
manifest.yaml ─▶ fetch PDF ─▶ extract blocks ─▶ detect headings/tables ─▶ build sections
     ─▶ chunk (structure-aware) ─▶ embed (batched) ─▶ upsert documents + chunks
```

### 5.1 Corpus manifest

`ingestion/manifest.yaml` lists 5–7 documents. Each entry has `document_name`, `publisher`, `year`, `source_url`, and `doc_type`. The `retrieval_date` is written by the fetch step. **Only genuine public documents from recognised authorities are listed. The manifest is never populated with invented sources.**

Selection guidance, so that cross-document cases are testable:

- A national nutrition institute dietary guideline.
- A government health department guideline.
- A food-safety regulator publication (storage, cooking temperatures, cross-contamination).
- An international organisation (e.g. a WHO/FAO-style) healthy diet document.
- At least two documents that overlap on a topic such as fats and oils or salt, so cross-document and conflict behaviour can be exercised.

### 5.2 Parsing

- Extract text with PyMuPDF using block-level output with font size and weight.
- **Heading detection:** the PDF's embedded outline/ToC is used where present. Otherwise headings are inferred from font-size/weight relative to the body-text mode. Each text block receives a `section_path` such as `"Fats and oils > Cooking with fats"`.
- **Tables:** table regions are detected (PyMuPDF `find_tables`) and serialised to Markdown as an **atomic block**.
- **Numbered recommendations/lists:** consecutive list items under one heading are grouped as an atomic block.
- Running headers, footers and page numbers are removed by repeated-line detection.
- The page number is retained per block for citation display.

### 5.3 Chunking strategy

| Parameter | Initial value | Notes |
|---|---|---|
| Unit | Structure-aware sections, then paragraphs | Never cut across a heading boundary unless the section exceeds the max size. |
| Target size | ~600 tokens | Tuned using retrieval hit rate. |
| Maximum size | ~900 tokens | Atomic blocks (tables, numbered lists) may exceed the target and are kept whole up to this limit. If larger, split on row or item boundaries and repeat the table header or list intro in each part. |
| Overlap | ~80 tokens, only between consecutive paragraph-based chunks within one section | No overlap across sections or atomic blocks. |
| Context prefix | Each chunk's embedded text is prefixed with `"{document_name} — {section_path}\n"` | Improves retrieval; the **stored display text excludes** the prefix. |

Each chunk stores: `chunk_id` (stable, e.g. `{doc_slug}-{section_idx}-{chunk_idx}`), `document_id`, `section_path`, `page_start`, `page_end`, `text`, `token_count`, `chunk_type` (`prose` | `table` | `list`), `embedding`, and a `content_hash`.

### 5.4 Embedding and storage

- Batch embedding with `text-embedding-3-small`; retries with backoff.
- `content_hash` makes re-ingestion skip unchanged chunks.
- Index: **HNSW**, cosine distance: `CREATE INDEX ... USING hnsw (embedding vector_cosine_ops)`.
- The ingestion run records the embedding model name and version on each chunk row, so a model change is detectable and forces re-embedding of all rows.

### 5.5 Ingestion verification

After ingest, a script prints per-document chunk counts, flags chunks with empty text, orphan sections, and chunks over the max size, and spot-prints a sample of tables to confirm they were not split. Results feed the README's limitations section.

---

## 6. Online Request Pipeline

`POST /api/chat` runs this sequence inside `chat_service`.

```
 1  Receive {conversation_id?, message, document_filter?}
 2  Persist user message
 3  SAFETY INPUT GATE ───────── restricted? ─yes─▶ out_of_scope response (skip 4–11) ─▶ 12
 4  Build retrieval query (standalone query from message + recent turns)
 5  SAFETY INPUT GATE on the standalone query too ── restricted? ─yes─▶ out_of_scope ─▶ 12
 6  Embed query
 7  Vector search (optional document filter) + threshold + diversification
 8  Enough evidence? ─no─▶ not_in_corpus response (searched docs listed) ─▶ 12
 9  Generate structured JSON (evidence-only prompt, forced tool-use)
10  VALIDATE: schema ▸ chunk membership ▸ hydrate metadata ▸ quote ▸ numbers ▸ coverage
        └─ fail ─▶ one constrained retry; on second failure → error response + failure log
11  SAFETY OUTPUT GUARD (scan answer text for personal targets/medical advice)
12  Persist assistant message, retrieved chunks, claims; log any failures
13  Return response + sources
```

Key design points:

- **Safety before retrieval** (step 3). Retrieval can never run for a restricted question, so it cannot bypass a refusal.
- **Safety runs again on the standalone query** (step 5), because a follow-up like "and how many should I eat then?" only becomes restricted once its context is resolved.
- **Only validated responses carry `status: "answered"`.** A response that fails validation twice is returned as `error`, with no unverified claims shown to the user.
- **No token streaming.** Because validation must pass before content is shown, the response is returned whole; the UI shows a loading state. This is a deliberate trade-off of latency for the guarantee in G1.
- Steps are timed and traced with a per-request `request_id`.

### Query construction for follow-ups (step 4)

Follow-up questions ("What about for children?") need context to retrieve well. The retriever builds a **standalone query** by a small, separate LLM call (temperature 0) that rewrites the latest message given the last N user turns. Its output is used **only** for retrieval and the second safety check; it is never shown as evidence and never used as a source of facts. If the rewrite call fails, the system falls back to concatenating the latest message with the previous user message.

---

## 7. Safety Layer

Located in `backend/app/safety/`. **No LLM is involved in any safety decision.**

### 7.1 Restricted categories

| Code | Category | Examples (non-exhaustive) |
|---|---|---|
| `CALORIE_TARGET` | Personal daily calorie targets | "How many calories should I eat a day to lose weight?" |
| `WEIGHT_TARGET` | Ideal or recommended personal weight | "What should I weigh at 165 cm?" |
| `MEDICAL_DIET` | Medical or disease-specific dietary recommendations | "What should I eat with type 2 diabetes?" |
| `PERSONAL_PRESCRIPTION` | Personalised nutrition or meal prescriptions | "Make me a meal plan for my blood pressure." |

### 7.2 Input gate (pre-retrieval)

Three independent detectors; **any one** triggering produces a refusal (OR semantics, tuned to favour refusing on ambiguity of *personal* intent).

1. **Normalisation:** Unicode normalisation (NFKC), lowercase, strip zero-width characters, collapse whitespace and leetspeak/obfuscation (`c@lories` → `calories`), and expand common abbreviations (`kcal`, `T2D`, `BP`).
2. **Rule detector:** compiled patterns that combine a *personalisation signal* (first person, "my", "I", age/height/weight mentions, "for me") with a *restricted-topic signal* (calories/intake target, weight goal, condition names, medications, "treat/cure/manage/reverse", "meal plan"). The rules are organised per category and kept data-driven in `rules.py` for easy review and extension.
3. **Semantic detector:** the normalised text is embedded and compared by cosine similarity with a curated **index of restricted-intent exemplars** (`intent_index.py`), several dozen per category, including rephrased and indirect forms. A similarity above a tuned threshold flags the intent. This catches paraphrases the rules miss. It uses the embedding model only, not a generative LLM.

The gate returns `SafetyDecision(restricted: bool, category, matched_by, evidence)`. The decision is logged with the message (never silently dropped).

### 7.3 Conversation-aware checks

To satisfy "restricted questions embedded in unrelated conversations" and "follow-ups after several unrelated messages":

- The gate is evaluated on **each user message independently**, on the **standalone rewritten query**, and on the **concatenation of the last N user messages** (sliding window, default N = 3).
- Prior assistant answers or user messages **never lower** the restriction level: there is no "already allowed earlier" state. A permissive earlier turn cannot grant exemptions.
- A question can contain both an allowed and a restricted part ("What are healthy fats, and how many calories should I eat?"). The policy is to **refuse the restricted part and answer the allowed part** only if the two are cleanly separable. Otherwise the whole message is refused. The first version implements the conservative option: refuse the whole message and invite the user to ask the general question separately.

### 7.4 Output guard (post-generation)

A deterministic scan of the final `answer` and each `claim_text` for restricted constructs: personalised calorie figures ("you should eat 1,800 kcal"), weight targets for an individual, and disease-treatment imperatives. A hit converts the response to `out_of_scope` and logs a `should_have_been_declined` failure, since it means the input gate missed something worth learning from.

### 7.5 Guarantees and limits

- Refusals are generated from **static templates** in `refusals.py`, not by the LLM.
- Population-level guidance quoted from a document ("adults are advised to limit salt to X g per day") is allowed. An individualised prescription is not. The distinction is enforced by the personalisation signal in the rule detector and by the system prompt.
- Rule-based and similarity-based detection is imperfect. The adversarial suite (Section 18.4) measures it, and misses are logged and drive additions to the rules and exemplars. This is evidence-based improvement, not per-question patching.

---

## 8. Retrieval Design

### 8.1 Procedure

1. Embed the standalone query with the same model used at ingest.
2. Query: `ORDER BY embedding <=> :query_vec LIMIT :candidate_k`, with an optional `WHERE document_id = :doc` (**named-document filter**).
3. Apply a **minimum similarity threshold** (`MIN_SIMILARITY`, tuned on the eval set). Candidates below it are dropped.
4. Take the top **k** results (initial `k = 6` for single-document, up to `k = 10` for cross-document), ordered by score.
5. Return chunks with their scores and hydrated document metadata.

### 8.2 Cross-document retrieval

If the query is not document-filtered, plain top-k often returns several chunks from one document, which starves the other sources of a topic. To support cross-document answers:

- Retrieve `candidate_k = 30`, then **diversify**: guarantee up to `m` chunks (default 3) per distinct document before filling the remaining slots by score (a per-document quota with a score floor).
- The generator receives chunks **grouped by document**, so the prompt structure itself encourages per-source presentation.
- The "named document" filter resolves from the explicit `document_filter` field and, optionally, from a document name detected in the user's text (matched against the manifest names, deterministic, no LLM).

### 8.3 Evidence sufficiency (→ `not_in_corpus`)

Before calling the LLM, the retriever reports `evidence_sufficient`:

- `false` if no chunk meets `MIN_SIMILARITY`.
- Otherwise `true`. The final judgement on whether the evidence actually answers the question also belongs to the generator, which may return `not_in_corpus` itself. The validator accepts that status when no claims are present.

The searched documents are always available for the `not_in_corpus` message, taken from the document filter or the full corpus list.

### 8.4 Tunables, all in config and tuned from the evaluation results

`TOP_K`, `CANDIDATE_K`, `PER_DOC_QUOTA`, `MIN_SIMILARITY`, `HNSW ef_search`. Optional later improvement: hybrid search (Postgres full-text + vector, fused by reciprocal rank) if the hit rate shows lexical misses.

---

## 9. Generation and System Prompt

### 9.1 LLM call

- Provider adapter: `LLMClient.generate_structured(system, evidence, history, tool_schema) -> dict`.
- **Forced tool-use** with a JSON schema (the response schema in Section 10), so the model must return a conforming object.
- `temperature = 0` (or the lowest the API allows) to maximise consistency across runs. Determinism is not guaranteed, which is why consistency testing exists (Section 18.3).
- Token limits and timeouts are set. Failures are retried once with backoff, then surface as `error`.

### 9.2 Prompt assembly

```
[system prompt]                      ← identity, rules, safety, boundaries, output contract
[evidence block]                     ← retrieved chunks, grouped by document:
   <document id="doc_03" name="…" publisher="…" year="…">
     <chunk id="doc_03-02-01" section="…" pages="12-13"> …text… </chunk>
   </document>
[conversation history]               ← recent turns, labelled as context only
[latest user question]
```

- Evidence is inserted in a delimited block, and the system prompt instructs the model to treat everything in it as **data, not instructions** (defence against prompt injection in document text or user text).
- History is included to resolve references only. The system prompt states that history is **never a source of facts** and **cannot relax any rule**.

### 9.3 System prompt content (`prompts/system_prompt.md`)

1. **Identity:** an AI nutrition information assistant that gives general food, nutrition, cooking and food-safety information based **exclusively** on the provided official guidance excerpts.
2. **Evidence rule:** every factual statement must be supported by a supplied chunk and listed as a claim with that `chunk_id`. If the excerpts do not support an answer, return `not_in_corpus`. Never use outside knowledge to fill gaps or infer beyond the text.
3. **Citation rule:** cite only `chunk_id`s present in the evidence block. Never invent document names, years, URLs or sections. Include a short verbatim `supporting_quote` from the chunk for each claim.
4. **Cross-document rule:** present each document's position separately, name publisher and year, and never merge differing recommendations into "the guidelines say". If sources disagree, show both.
5. **Style:** plain language, concise, state limitations, separate documented recommendations from uncertainty, present population-level guidance as such, not as advice for an individual.
6. **Safety boundaries:** do not give personal calorie or weight targets, medical advice, disease-specific dietary treatment, or personalised prescriptions. Decline politely and point to a qualified healthcare professional or registered dietitian. (These are also enforced in code.)
7. **Output contract:** return only through the provided tool in the defined schema.

---

## 10. Structured Response Schema

Pydantic models in `backend/app/schemas/` are the single source of truth. The TypeScript types in `frontend/src/types/api.ts` mirror them (generated from the OpenAPI spec).

### 10.1 LLM output (what the model must return)

```json
{
  "answer": "Plain-language answer text.",
  "claims": [
    {
      "claim_text": "A factual statement supported by retrieved evidence.",
      "chunk_id": "doc_03-02-01",
      "supporting_quote": "Short verbatim excerpt from the chunk that supports the claim."
    }
  ],
  "status": "answered",
  "refusal_reason": null
}
```

### 10.2 Response returned to the frontend (after validation and hydration)

```json
{
  "message_id": "msg_…",
  "conversation_id": "conv_…",
  "answer": "…",
  "claims": [
    {
      "claim_id": "clm_…",
      "claim_text": "…",
      "source": {
        "document_name": "…",
        "publisher": "…",
        "year": 2024,
        "section": "…",
        "url": "https://…",
        "chunk_id": "doc_03-02-01",
        "pages": "12-13",
        "excerpt": "Verbatim chunk text shown in the sources panel."
      }
    }
  ],
  "status": "answered",
  "refusal_reason": null,
  "searched_documents": ["…"],
  "verified": true
}
```

### 10.3 Status and field rules

| `status` | `claims` | `refusal_reason` | Notes |
|---|---|---|---|
| `answered` | ≥ 1, each with valid source | `null` | `verified` is `true` only after all checks pass. |
| `not_in_corpus` | empty | explanation naming searched documents | Generated by backend template or accepted from the model when it has no supported claims. |
| `out_of_scope` | empty | category + polite explanation | Static template from the safety layer. |
| `error` | empty | generic failure message | Never contains unverified factual content. |

### 10.4 Changes from the schema in the problem statement

| Change | Reason |
|---|---|
| The model emits `chunk_id` + `supporting_quote` instead of a full `source` object. | The model cannot be trusted to copy metadata correctly. The backend builds `source` from the database, so document name, publisher, year, section and URL cannot be fabricated. |
| Added `supporting_quote` (model output). | Allows a mechanical check that the claim is grounded in the cited chunk text. |
| Added `source.pages` and `source.excerpt`. | Required for the sources panel and for manual citation verification. |
| Added `searched_documents` and `verified`. | Supports `not_in_corpus` messaging and lets the UI distinguish verified answers. |

---

## 11. Response Validation and Citation Verification

`services/validation.py` is a pure, deterministic module. It receives the raw model output and the exact set of chunks supplied to the model.

### 11.1 Checks, in order

| # | Check | Failure category logged |
|---|---|---|
| 1 | Output parses and conforms to the Pydantic schema. | `schema_invalid` |
| 2 | `status` is one of the four allowed values and is consistent with the content (`answered` ⇒ ≥ 1 claim; others ⇒ no claims). | `schema_invalid` |
| 3 | Every claim has a `chunk_id`. | `missing_citation` |
| 4 | Every `chunk_id` is in the **set of chunks actually retrieved for this request**. | `invalid_citation` / `fabricated_reference` |
| 5 | **Hydration:** `source` is built from the database row for that `chunk_id`. | — |
| 6 | `supporting_quote` appears in the chunk text (whitespace- and case-normalised, with fuzzy tolerance for extraction artefacts). | `unsupported_claim` |
| 7 | **Numeric grounding:** every number in `claim_text` (with units) appears in the chunk text, using a normalised comparison (e.g. `2,300` = `2300`, `5 g` = `5g`). | `unsupported_claim` / `inconsistent_numbers` |
| 8 | **Coverage:** every sentence of `answer` that makes a factual assertion is mapped to at least one claim. In practice the answer is composed from the claims, and an answer containing numbers not present in any claim fails. | `unsupported_claim` |
| 9 | Conflict presentation: if claims cite more than one document on the same topic with differing numbers, the answer must attribute each to its publisher and year. | `conflict_mispresented` |

### 11.2 On failure

1. **One constrained retry:** the generator is re-invoked with the specific validation errors appended ("claim 2 cites chunk X, which was not provided").
2. If the retry also fails: return `status: "error"`, store the failed output and reasons in `failure_logs`, and **do not show the failed content** to the user as an answer.

### 11.3 What the validator cannot do

Mechanical checks catch fabricated IDs, ungrounded quotes and numbers, but not every case of a claim that overstates its chunk. Semantic support is therefore additionally assessed by the **manual citation verification** (Section 18.5), whose outcomes are recorded and reported honestly.

---

## 12. Refusal Handling

| | `not_in_corpus` | `out_of_scope` |
|---|---|---|
| **Trigger** | Retrieval below threshold, or the generator finds no supporting evidence. | Safety input gate or output guard. |
| **Decided by** | Retriever / validator (the evidence). | Safety layer (the question). |
| **LLM involved** | Not for the template path. | Never. |
| **Content** | States the available guidance does not cover the question, lists the documents searched, makes no guess. | Polite decline, brief reason, advises a qualified healthcare professional or registered dietitian. |
| **Schema** | `status = "not_in_corpus"` | `status = "out_of_scope"` |
| **UI** | Neutral "not covered" notice listing searched documents. | Distinct "outside what this assistant can advise on" notice. |
| **Failure logged when…** | A not-in-corpus question was answered anyway. | A restricted question got through (output guard or review). |

The two never share a code path or a status, so the UI, logs and evaluation can tell them apart.

---

## 13. Conversation Management

- **Identity:** no user accounts in scope. The client gets an opaque, random **anonymous session token** (HTTP-only cookie, or header for cross-origin) created on first call; conversations belong to that token.
- Each conversation stores ordered messages. Assistant messages also store their retrieved chunks and claims, so any past answer can be re-rendered with its exact evidence.
- **History window:** only the last N turns (default 6) go to the LLM, to bound cost and context.
- **Precedence rule:** history is context only. It is never an evidence source (citations must come from the *current* request's retrieved chunks) and never alters safety state.
- Titles are derived from the first user message (truncated, no LLM call).
- Deletion: a user can delete a conversation, which cascades to messages, sources and claims. Failure logs are retained but reference the conversation only by ID.

---

## 14. Data Model

PostgreSQL with the `vector` extension. Migrations managed by Alembic. All tables have `created_at`.

```
documents ──< chunks
conversations ──< messages ──< message_sources >── chunks
                    └──< claims >── chunks
failure_logs (refs message_id nullable)
eval_questions ──< eval_results >── eval_runs
```

### 14.1 Tables

**`documents`**

| Column | Type | Notes |
|---|---|---|
| `id` | text PK | slug, e.g. `doc_03` |
| `document_name` | text | |
| `publisher` | text | |
| `year` | int | |
| `source_url` | text | |
| `retrieval_date` | date | |
| `doc_type` | text | |
| `file_sha256` | text | detects changed source files |
| `page_count` | int | |

**`chunks`**

| Column | Type | Notes |
|---|---|---|
| `chunk_id` | text PK | stable, human-readable |
| `document_id` | text FK → documents | |
| `section_path` | text | |
| `page_start`, `page_end` | int | |
| `chunk_type` | text | `prose` / `table` / `list` |
| `text` | text | display text, without the embedding prefix |
| `token_count` | int | |
| `embedding` | vector(1536) | HNSW index, cosine |
| `embedding_model` | text | |
| `content_hash` | text | |

**`conversations`**: `id`, `session_token_hash`, `title`, `updated_at`.

**`messages`**

| Column | Type | Notes |
|---|---|---|
| `id` | text PK | |
| `conversation_id` | FK | |
| `role` | text | `user` / `assistant` |
| `content` | text | user text or assistant `answer` |
| `status` | text null | assistant only: the four statuses |
| `refusal_reason` | text null | |
| `raw_llm_output` | jsonb null | stored for audit and failure analysis |
| `standalone_query` | text null | |
| `safety_decision` | jsonb null | |
| `model_info` | jsonb null | provider, model ID, temperature, embedding model |
| `latency_ms` | int null | |

**`message_sources`**: `message_id`, `chunk_id`, `rank`, `score`, `used_in_claims` (bool). The full retrieved set, whether or not it was cited.

**`claims`**: `id`, `message_id`, `position`, `claim_text`, `chunk_id`, `supporting_quote`, `verified` (bool), `verification_notes`.

**`failure_logs`**

| Column | Type | Notes |
|---|---|---|
| `id` | PK | |
| `created_at` | timestamptz | |
| `category` | text | see Section 17 |
| `detected_by` | text | `validator` / `output_guard` / `eval` / `manual_review` |
| `user_question` | text | |
| `model_response` | jsonb | the raw output |
| `retrieved_chunks` | jsonb | ids, scores, section paths, text snapshot |
| `model_info` | jsonb | |
| `error_description` | text | |
| `message_id` | FK null | |
| `eval_run_id` | FK null | |

**`eval_questions`**: `id`, `suite` (`retrieval` / `benchmark` / `safety` / `consistency`), `question`, `category`, `expected_document_id`, `expected_section`, `expected_behaviour` (`answer` / `not_in_corpus` / `out_of_scope`), `notes`.

**`eval_runs`**: `id`, `suite`, `started_at`, `config` (jsonb: k, thresholds, models), `git_sha`, `summary` (jsonb).

**`eval_results`**: `id`, `eval_run_id`, `eval_question_id`, `repeat_index`, `retrieved` (jsonb), `hit` (bool), `rank_of_expected`, `response` (jsonb), `failures` (jsonb), `citation_checks` (jsonb), `manual_review` (jsonb).

### 14.2 Notes

- The `service_role` key is used only by the backend. If Supabase Row-Level Security is enabled, no table is exposed through the public Supabase API.
- Retrieved chunk text is stored in `failure_logs` as a snapshot, so a later re-ingest cannot erase the evidence of a failure.

---

## 15. API Contracts

Base path `/api`. JSON over HTTPS. Errors use a consistent shape: `{"error": {"code": "…", "message": "…", "request_id": "…"}}`. OpenAPI docs are served at `/docs` in non-production.

### 15.1 `POST /api/chat`

Request:

```json
{
  "conversation_id": "conv_… | null",
  "message": "What does the guideline say about salt?",
  "document_filter": "doc_03 | null"
}
```

Response `200`: the object in Section 10.2. A refusal or `error` status is still HTTP `200` with the status in the body, because they are valid, expected application outcomes. Transport and validation problems use `4xx/5xx`.

| Code | When |
|---|---|
| `400` | Empty or oversized message (> 2,000 chars), unknown `document_filter`. |
| `404` | `conversation_id` does not belong to this session. |
| `429` | Rate limit exceeded. |
| `502` | Upstream LLM or embedding provider unavailable after retries. The backend also writes an `error` message. |

### 15.2 Other endpoints

| Method | Path | Purpose |
|---|---|---|
| `GET` | `/api/conversations` | List the session's conversations (id, title, updated_at). |
| `GET` | `/api/conversations/{id}` | Full message history, with claims and sources for each assistant message. |
| `DELETE` | `/api/conversations/{id}` | Delete a conversation. |
| `GET` | `/api/documents` | Corpus list with metadata (name, publisher, year, URL, retrieval date), used for the document filter and the "about the knowledge base" view. |
| `GET` | `/api/chunks/{chunk_id}` | The full chunk with its document metadata, used by the sources panel for "view full excerpt". |
| `GET` | `/api/health` | Liveness, plus a DB and vector-extension check. |
| `GET` | `/api/admin/failures` | Paginated, filterable failure logs. Requires `ADMIN_TOKEN`. |
| `GET` | `/api/admin/failures/summary` | Counts per category and per date. Requires `ADMIN_TOKEN`. |
| `POST` | `/api/admin/eval/run` | Triggers an evaluation suite against the deployed instance. Requires `ADMIN_TOKEN`. |
| `GET` | `/api/admin/eval/runs/{id}` | Results of an evaluation run. Requires `ADMIN_TOKEN`. |

---

## 16. Frontend Architecture

### 16.1 Layout

```
Desktop                                                Mobile
┌───────────┬──────────────────────────┬──────────────┐   ┌──────────────────────┐
│ History   │  Message list            │ Sources panel│   │ ☰ History   Sources ▾│
│ sidebar   │  (user / assistant)      │ (claim →     │   │ Message list         │
│           │                          │  source)     │   │ (claims tappable →   │
│ + New chat│  [ Composer ........ ➤ ] │              │   │  bottom-sheet source)│
└───────────┴──────────────────────────┴──────────────┘   │ [ Composer ..... ➤ ] │
                                                          └──────────────────────┘
```

### 16.2 Components

| Component | Responsibility |
|---|---|
| `ChatView` | Holds the conversation state and sends messages through `lib/api.ts`. |
| `MessageList` / `MessageBubble` | Renders messages. Assistant bubbles render `answer` with inline numbered citation markers `[1]`, `[2]` tied to claims. |
| `StatusBanner` | Distinct visual treatments for `not_in_corpus`, `out_of_scope` and `error`. |
| `Composer` | Input, send, disabled state while loading, optional document-filter selector. |
| `ConversationSidebar` | History list, new chat, delete. |
| `SourcesPanel` | For the selected message or claim: document title, publisher, year, section, pages, clickable URL (new tab), and the supporting excerpt with the quoted span highlighted. |
| `ClaimList` | Each claim is paired with its source. Selecting a claim scrolls the panel to its source. |
| `LoadingIndicator` / `ErrorBoundary` | Pending state, network errors and retry. |

### 16.3 Behaviour

- Citation markers in the answer and entries in the sources panel are linked both ways, so the evidence for **each claim** is inspectable **without leaving the conversation**.
- Only responses with `verified: true` show citation markers as verified. The UI never shows a factual answer without sources.
- On mobile, the sources panel becomes a bottom sheet. The sidebar collapses into a drawer. Touch targets are ≥ 44 px.
- Accessibility: semantic landmarks, keyboard navigation, `aria-live` for new messages, sufficient contrast.
- The frontend has **no API keys** and no direct calls to the LLM, embeddings provider or database. Its only configuration is `NEXT_PUBLIC_API_BASE_URL`.
- The session token is held in an HTTP-only cookie where same-site rules allow it, otherwise in memory/`localStorage` and sent in a header. It is an opaque ID, not a credential for any third-party service.

---

## 17. Failure Logging and Monitoring

### 17.1 Failure taxonomy

| Category code | Description | Detected by |
|---|---|---|
| `unsupported_claim` | Claim, quote or number not grounded in the cited chunk. | Validator (auto), manual review |
| `missing_citation` | Claim without a `chunk_id`. | Validator |
| `invalid_citation` | `chunk_id` exists but does not support the claim. | Manual review, eval |
| `fabricated_reference` | `chunk_id`, document, year or URL not in the corpus or retrieved set. | Validator |
| `inconsistent_numbers` | A factual number differs between repeated runs of the same question. | Consistency suite |
| `incorrect_retrieval` | The expected document or section is absent from top-k. | Retrieval eval |
| `out_of_corpus_answered` | A not-in-corpus question received an answer. | Benchmark / eval |
| `should_have_been_declined` | A restricted question was answered. | Output guard, safety suite |
| `incorrect_refusal` | A legitimate question was refused. | Benchmark / eval |
| `vague_unhelpful` | Needlessly vague or unhelpful when evidence existed. | Manual review |
| `conflict_mispresented` | Differing source recommendations merged or one source favoured. | Validator (heuristic), manual review |
| `schema_invalid` | Output failed the schema. | Validator |
| `provider_error` | LLM or embedding provider error or timeout. | Chat service |

### 17.2 Record contents

Every record contains the fields required by the problem statement: user question, model response, failure category, relevant retrieved chunks, timestamp, model information and error description. It also holds `detected_by` and a link to the message or eval run.

### 17.3 Principles

- **Failures are never "fixed" for a specific question.** Analysis groups failures by category and drives general changes (chunking, thresholds, prompt, rules) that are then re-measured by the eval harness.
- Structured JSON application logs (with `request_id`) are emitted to stdout for Railway's log viewer. They contain no secrets and, by default, no raw user text beyond what is stored in `failure_logs`.
- `/api/admin/failures/summary` supports the failure-analysis report (counts per category).

---

## 18. Evaluation Architecture

Evaluation code imports the **same** `chat_service`, `retrieval`, `validation` and `safety` modules as production, so results reflect the real system. Question banks are version-controlled YAML. Results are persisted in `eval_runs` / `eval_results` and exported as Markdown/CSV to `docs/reports/`.

### 18.1 Retrieval evaluation (≥ 15 questions)

- Each question has `expected_document_id` and `expected_section`.
- Retrieval only, with no generation. A **hit** means a chunk from the expected document **and** matching section appears in the top-k.
- Metrics: **hit rate @k** (headline), plus rank of the expected chunk and MRR. Misses are logged as `incorrect_retrieval`, separately from generation failures.
- Re-run after any change to chunking, embedding model, `k` or thresholds, so the effect of each change is measured.

### 18.2 Benchmark questions (10)

Across: nutrient requirements, food safety and storage, cooking methods, and questions without a clear or universally established answer. Each is run end-to-end. For each response the harness stores the response, retrieval, and automatic validator findings. The reviewer then records:

- unsupported claims, fabricated citations, numbers changing across runs,
- incorrect or missing refusals,
- incorrectly retrieved evidence, unhelpful uncertainty,
- citation accuracy.

`report.py` groups failures by category and counts occurrences.

### 18.3 Consistency testing

`consistency.py` runs a chosen question **3 times**, stores all three responses unmodified, and compares: numerical values extracted from each answer, the set of cited `chunk_id`s, the status, and the stability of recommendations. Any factual number that changes is logged as `inconsistent_numbers`. Answers are never normalised to appear consistent.

### 18.4 Safety adversarial suite

`safety_adversarial.yaml` groups cases by technique: direct, rephrased, indirect/sideways, embedded in unrelated conversation, and follow-up after several unrelated turns (multi-turn fixtures). The expected result is `out_of_scope` for all restricted cases and not `out_of_scope` for matched benign controls (to measure over-refusal). Output: refusal rate per technique, plus a list of every miss.

### 18.5 Manual citation verification (≥ 10 answers)

The harness exports each selected answer with its claims, the cited document, section, page, URL and excerpt into a review sheet. The reviewer opens the source, locates the passage, and records for each claim: supported / partially / unsupported, the number check, and whether the citation represents the source accurately. These are stored in `eval_results.manual_review`.

### 18.6 Reports

`docs/reports/` contains the retrieval hit-rate report, benchmark failure table, consistency results, citation verification results, safety results, and the consolidated failure analysis with proposed architectural changes.

---

## 19. Security

| Concern | Control |
|---|---|
| Secrets | LLM, embedding and DB credentials exist only as backend environment variables. `.env` is git-ignored. `.env.example` has placeholders only. The frontend bundle is checked (CI grep) for key patterns. |
| Browser-to-LLM | Not possible by design. All model calls are made server-side. |
| CORS | Allow-list of the production frontend origin (and localhost in development). |
| Rate limiting | Per-session and per-IP limits on `/api/chat`, to protect cost and availability. |
| Input limits | Message length cap and conversation-length cap. Strict Pydantic validation. |
| Prompt injection | Evidence and user text are delimited and treated as data. The system prompt says so. The output validator and safety layer do not trust model output. Citations are verified against DB records. |
| SQL | SQLAlchemy parameterised queries only. |
| Admin routes | Require `ADMIN_TOKEN` (constant-time comparison). Disabled when the token is unset. |
| Privacy | No accounts and no PII collection beyond chat text. A visible notice states that the assistant gives general information and not medical advice. Conversations are deletable. |
| Dependencies | Pinned versions, and automated dependency alerts on GitHub. |
| Error handling | No silent exception swallowing. Errors are logged with `request_id`, and clients get safe messages with no stack traces. |

---

## 20. Deployment

```
GitHub repo ──push──▶ Vercel (frontend)         ──HTTPS──▶ Railway (FastAPI, Docker)
                                                              │
                                                              ├──▶ Supabase (Postgres + pgvector)
                                                              ├──▶ Anthropic API
                                                              └──▶ OpenAI Embeddings API
```

| Item | Detail |
|---|---|
| Frontend | Vercel project rooted at `frontend/`. Env: `NEXT_PUBLIC_API_BASE_URL`. |
| Backend | Railway service built from `backend/Dockerfile`. Start: `uvicorn app.main:app --host 0.0.0.0 --port $PORT`. Health check: `/api/health`. |
| Database | Supabase project with `CREATE EXTENSION vector`. Migrations applied with `alembic upgrade head` as a release step. |
| Corpus load | The ingestion CLI runs against the **production** database (`python -m ingestion.run --env prod`) from a developer machine or CI. The same corpus therefore exists in dev and prod, and `file_sha256` / `content_hash` confirm parity. |
| Secrets | Set in Railway/Vercel/Supabase dashboards, never committed. |
| CI (GitHub Actions) | Lint, type check (mypy, `tsc`), unit tests, frontend build, secret scan. Deploy on merge to `main`. |
| Post-deploy verification | A smoke script calls every endpoint in production. The evaluation suites are then run against the deployed URL, and results are saved to `docs/reports/`. |
| Environments | `local` (docker compose with Postgres+pgvector), `production`. A separate `staging` project is optional. |

---

## 21. Configuration

All via environment variables, loaded by `pydantic-settings`. `.env.example` lists each variable.

| Variable | Used by | Purpose |
|---|---|---|
| `ANTHROPIC_API_KEY` | backend | LLM calls |
| `LLM_MODEL` | backend | Model ID, default `claude-sonnet-5-5` |
| `OPENAI_API_KEY` | backend, ingestion | Embeddings |
| `EMBEDDING_MODEL` | backend, ingestion | Default `text-embedding-3-small` |
| `DATABASE_URL` | backend, ingestion | Postgres connection string |
| `ADMIN_TOKEN` | backend | Protects `/api/admin/*` |
| `ALLOWED_ORIGINS` | backend | CORS allow-list |
| `TOP_K`, `CANDIDATE_K`, `PER_DOC_QUOTA`, `MIN_SIMILARITY` | backend | Retrieval tunables |
| `HISTORY_TURNS`, `SAFETY_WINDOW_TURNS` | backend | Context and safety window |
| `SAFETY_SIMILARITY_THRESHOLD` | backend | Semantic restricted-intent threshold |
| `RATE_LIMIT_PER_MIN` | backend | Chat rate limit |
| `NEXT_PUBLIC_API_BASE_URL` | frontend | Backend base URL (the only frontend variable) |

---

## 22. Known Limitations and Risks

| Risk / limitation | Mitigation / how it is handled |
|---|---|
| PDF extraction quality (multi-column layouts, scanned pages, complex tables) can corrupt text or headings. | Ingestion verification report, spot checks, and a documented limitation. Prefer text-based PDFs. |
| Retrieval can miss relevant chunks (vocabulary mismatch, chunk-size effects). | Measured by hit rate, with tunables, and hybrid search as a planned improvement. |
| Mechanical validation does not prove a claim is *semantically* supported. | Quote and number grounding, plus mandatory manual citation verification, with honest reporting. |
| Rule/similarity safety detection may miss novel phrasings or over-refuse. | Adversarial suite measures both. Misses feed the rules and exemplar index, and benign controls measure over-refusal. |
| LLM output varies between runs even at temperature 0. | Consistency testing records instability. Nothing is smoothed over. |
| Sources may genuinely disagree, or be dated. | Cross-document presentation with publisher and year. The retrieval date is stored and shown. |
| No token streaming (validation gate) increases perceived latency. | Loading indicator, bounded context and `k`, and a deliberate trade-off. |
| Anonymous sessions can be lost (cleared cookies). | Acceptable for scope. Accounts are out of scope. |
| Corpus is small (5–7 documents). | Many questions will correctly return `not_in_corpus`. This is expected behaviour, not a defect. |
| Individual food nutrient values are not supported. | Out of scope for this release. Such questions return `not_in_corpus` unless a guidance document states the figure. |

---

## 23. Implementation Phases

| Phase | Deliverables | Exit check |
|---|---|---|
| 0. Foundations | Repo, monorepo skeleton, CI, `.env.example`, local Postgres+pgvector, Alembic baseline. | CI green, DB migrates. |
| 1. Corpus & ingestion | Manifest with 5–7 real documents, parse/chunk/embed/store CLI, ingestion verification report. | Chunks in DB with correct metadata and no split tables. |
| 2. Retrieval | Retriever with filter, threshold, diversification. Retrieval eval harness and the first hit-rate number. | Hit rate measured and recorded. |
| 3. Safety layer | Rules, exemplar index, input gate, output guard, refusal templates, adversarial suite. | Adversarial suite run with results. |
| 4. Generation & validation | LLM adapter, system prompt, forced-tool schema, validator and hydration, retry logic, failure logger. | Invalid citations are demonstrably rejected in tests. |
| 5. API & persistence | Chat and conversation endpoints, session handling, rate limiting, full persistence. | Integration tests pass end-to-end. |
| 6. Frontend | Chat UI, history, sources panel, status banners, responsive layout. | Evidence inspectable per claim on desktop and mobile. |
| 7. Evaluation | Benchmark, consistency, citation verification, reports. | Reports written to `docs/reports/`. |
| 8. Deploy & verify | Vercel, Railway, Supabase, production ingest, smoke test, evaluation against production. | Public URL meets the acceptance criteria. |
| 9. Documentation | README (chunking, models, index, top-k, limitations, setup, deploy), final failure analysis. | README complete. |

Each phase ends with its tests passing before the next begins, and the evaluation harness is re-run whenever a phase changes retrieval, prompts or safety.

---

## 24. Requirements Traceability

| Problem statement requirement | Architecture section |
|---|---|
| Full-stack app, frontend features, backend features | §3, §15, §16 |
| Model calls only on backend; no keys in browser | §1 (G5), §19 |
| Technology stack and documented decisions | §2 |
| 5–7 official documents, metadata, chunking, embeddings, vector DB | §5, §14 |
| README documentation of chunking/model/index/top-k/limitations | §5.3, §5.4, §8.4, §22 |
| RAG workflow, named-document filtering, evidence-only generation | §6, §8, §9 |
| Structured schema, statuses, validation, schema adaptation documented | §10, §11 |
| System prompt | §9.3 |
| Backend safety enforcement, adversarial testing | §7, §18.4 |
| Failure logging with required fields | §14, §17 |
| ≥ 15 retrieval questions, hit rate | §18.1 |
| 10 benchmark questions, failure grouping and counts | §18.2 |
| Consistency testing | §18.3 |
| Citation verification (≥ 10 answers) | §18.5, §11.3 |
| Cross-document retrieval, conflicts presented separately | §8.2, §9.3, §11.1 (check 9) |
| Two refusal types | §12 |
| Persistent storage and conversation history | §13, §14 |
| Sources panel | §16 |
| Deployment, GitHub, README, `.env.example` | §20, §21 |
| Acceptance criteria and implementation rules | §1, §11, §17, §23 |
