# Problem Statement: AI Nutrition Assistant (RAG-based)

> A single, end-to-end, deployable, production-oriented Dietary Guidance RAG Chatbot.

---

## Table of Contents

1. [Overview](#1-overview)
2. [Objectives and Success Principles](#2-objectives-and-success-principles)
3. [Scope](#3-scope)
4. [System Architecture](#4-system-architecture)
5. [Technology Stack](#5-technology-stack)
6. [Knowledge Base (Official Dietary Guidance Corpus)](#6-knowledge-base-official-dietary-guidance-corpus)
7. [RAG Pipeline](#7-rag-pipeline)
8. [Structured Response Schema](#8-structured-response-schema)
9. [System Prompt Requirements](#9-system-prompt-requirements)
10. [Safety Enforcement](#10-safety-enforcement)
11. [Refusal Types](#11-refusal-types)
12. [Cross-Document Retrieval and Conflicting Guidance](#12-cross-document-retrieval-and-conflicting-guidance)
13. [Database and Conversation Management](#13-database-and-conversation-management)
14. [Frontend and Sources Panel](#14-frontend-and-sources-panel)
15. [Failure Logging and Monitoring](#15-failure-logging-and-monitoring)
16. [Evaluation and Testing](#16-evaluation-and-testing)
17. [Deployment and GitHub](#17-deployment-and-github)
18. [Deliverables](#18-deliverables)
19. [Acceptance Criteria](#19-acceptance-criteria)
20. [Development Instructions and Rules](#20-development-instructions-and-rules)

---

## 1. Overview

Build a complete **AI-powered Nutrition Assistant chatbot** that answers questions about food, nutrition, dietary guidelines, cooking methods, and food safety using a **Retrieval-Augmented Generation (RAG)** architecture.

The application must give accurate, structured, **citation-backed** responses drawn from official public dietary guidance documents. It must:

- enforce strict safety boundaries,
- identify information the knowledge base does not support,
- maintain conversation history, and
- log failures so the system can be improved with evidence.

### Core Problem

General-purpose LLMs answer nutrition questions fluently but can state unsupported or fabricated facts, invent sources, give inconsistent numbers, and drift into medical advice. In a health-adjacent domain this is unacceptable. The system must therefore guarantee that **every factual claim is backed by retrieved evidence from a real, named document**, not by the model's internal knowledge.

---

## 2. Objectives and Success Principles

### Primary Objective

Ensure that **every factual claim made by the assistant is supported by retrieved evidence**, rather than relying on the language model's pretrained knowledge.

### Guiding Principles

| Principle | Meaning |
|---|---|
| Evidence-only answers | The assistant answers exclusively from retrieved document content. |
| Verifiable citations | Each claim links to a real document, section, and chunk that actually supports it. |
| Honest uncertainty | If evidence is missing, the assistant says so explicitly instead of guessing. |
| Safety by code | Safety restrictions are enforced in backend code, independent of the LLM and the prompt. |
| Source fidelity | Conflicting recommendations are presented separately, never merged into one claim. |
| Measurable quality | Retrieval, citation accuracy, and consistency are evaluated and reported, and failures are logged rather than hardcoded away. |

---

## 3. Scope

### In Scope

- Full-stack web application (frontend + backend).
- Corpus of 5–7 official public dietary guidance documents.
- PDF extraction, chunking, embedding, and vector storage.
- RAG pipeline with structured, validated, cited responses.
- Backend safety layer and two distinct refusal types.
- Persistent conversations, retrieved chunks, document metadata, failure logs, and evaluation results.
- Sources panel showing evidence alongside the conversation.
- Failure logging, retrieval/citation/consistency evaluation, and failure analysis.
- Public deployment, GitHub repository, and README.

### Out of Scope

- Individual food nutrient values (e.g. calories or vitamin content of a specific food). These belong to a structured nutritional database in a **future phase** and must not be invented or presented as dietary guidance.
- Personal calorie or weight targets, medical advice, disease-specific dietary treatment, and personalised nutrition prescriptions.

---

## 4. System Architecture

A full-stack application consisting of the following.

### 4.1 Frontend

- Chat interface with message list and input box.
- Conversation history.
- Sources panel displayed alongside the conversation.
- Citations shown for individual claims.
- Clear indication when information is unavailable in the knowledge base.
- Loading indicators and error handling.
- Responsive UI for desktop and mobile.

### 4.2 Backend

- Secure API endpoints for chat interactions.
- Conversation storage and retrieval.
- Server-side LLM integration.
- RAG pipeline for document retrieval.
- Structured response validation.
- Safety enforcement in code.
- Failure logging and analytics.
- Citation generation and verification.

> **Hard rule:** All model API calls happen on the backend, never directly from the browser. API keys must never appear in frontend code.

---

## 5. Technology Stack

Use the following where appropriate, choose a consistent architecture, and **document the technology decisions**.

| Layer | Options |
|---|---|
| Frontend | Next.js or React with TypeScript |
| Backend | FastAPI or Next.js API routes |
| LLM | OpenAI API or Anthropic API |
| Database | PostgreSQL, Supabase, or SQLite |
| Vector database | Supabase pgvector, Qdrant, or Pinecone |
| Embeddings | OpenAI `text-embedding-3-small` or sentence-transformers |
| PDF processing | PyMuPDF, Docling, Unstructured, or LlamaParse |
| RAG framework | LangChain or custom Python implementation |
| Deployment | Vercel (frontend) and Railway (backend), or another compatible architecture |
| Version control | GitHub |

---

## 6. Knowledge Base (Official Dietary Guidance Corpus)

### 6.1 Sources

Collect **5–7 publicly available dietary guidance documents** from recognised authorities, such as:

- National nutrition institutes
- Government health departments
- Food safety regulators
- International health organisations

Prefer written guidance documents (PDFs, reports).

### 6.2 Processing Requirements

1. Collect the 5–7 official documents.
2. Extract text and relevant section headings.
3. Store metadata for every document:
   - Document name
   - Publisher
   - Publication year
   - Source URL
   - Retrieval date
4. Split documents into meaningful chunks.
5. Preserve section headings and document metadata on every chunk.
6. Avoid unnecessarily splitting tables, numbered recommendations, or important contextual information.
7. Generate embeddings for each chunk.
8. Store embeddings in a vector database.

Each chunk must retain its original document metadata so citations are accurate.

### 6.3 Documentation Required in the README

- Chunking strategy
- Chunk size
- Chunk overlap
- Embedding model
- Vector index type
- Retrieval top-k value
- Limitations of the chosen approach

> **Important:** Nutrient values for individual foods must not be invented or treated as dietary guidance.

---

## 7. RAG Pipeline

### 7.1 Workflow

1. User submits a question.
2. Backend checks the question against safety restrictions.
3. Question is converted into an embedding.
4. Relevant chunks are retrieved from the vector database.
5. Retrieval supports both all-document search and filtering by a named document.
6. **Only retrieved evidence** is passed to the LLM.
7. LLM generates a structured response.
8. Response is validated against the defined schema.
9. Every factual claim is checked for an associated citation.
10. Response is returned to the frontend.
11. Supporting sources are shown in the sources panel.
12. Unsupported, inconsistent, or invalid responses are logged.

```
User question
   │
   ▼
Safety check (backend, independent of LLM) ──► out_of_scope refusal
   │ pass
   ▼
Embed question ─► Vector search (all docs / named doc filter) ─► Top-k chunks
   │                                                              │
   │                              no supporting evidence ──► not_in_corpus
   ▼
LLM (retrieved evidence only) ─► Structured JSON
   │
   ▼
Schema + citation validation ──fail──► log failure, do not present as verified
   │ pass
   ▼
Response + Sources panel
```

### 7.2 Critical RAG Rules

- Answer exclusively from retrieved document content.
- Never treat internal model knowledge as a factual source.
- If retrieved evidence does not support an answer, say so explicitly.
- Never fabricate sources, document names, years, URLs, or citations.
- If two documents differ, present them separately with their respective citations.
- Never merge conflicting recommendations into a single statement about what "the guidelines say".

---

## 8. Structured Response Schema

The LLM must return **structured JSON**, not unrestricted prose. Example:

```json
{
  "answer": "The response text.",
  "claims": [
    {
      "claim_text": "A factual statement supported by retrieved evidence.",
      "source": {
        "document_name": "Document name",
        "publisher": "Publisher name",
        "year": 2024,
        "section": "Relevant section",
        "url": "https://example.com/document.pdf",
        "chunk_id": "chunk_001"
      }
    }
  ],
  "status": "answered",
  "refusal_reason": null
}
```

### 8.1 Status Values

| Status | Meaning |
|---|---|
| `answered` | Question answered with cited, evidence-backed claims. |
| `not_in_corpus` | Retrieved documents do not cover the question. |
| `out_of_scope` | Declined by design (medical advice, personal calorie/weight targets, etc.). |
| `error` | Processing or validation failure. |

### 8.2 Validation Requirements

- Every response validates against the schema.
- Every factual claim has a valid source.
- Source references correspond to actual retrieved documents and chunks.
- Missing or invalid citations cause validation to **fail**.
- Unsupported claims never reach the frontend as verified answers.
- No factual assertion is generated without evidence.

The schema must carry real, verifiable citations for every claim, and the final schema design and its rationale **must be documented**.

---

## 9. System Prompt Requirements

Develop a detailed system prompt covering the following.

### 9.1 Assistant Identity

An AI nutrition information assistant that provides general food, nutrition, cooking, and food safety information based **exclusively on official retrieved dietary guidance documents**.

### 9.2 Response Behaviour

- Answer clearly and accurately, in simple language.
- Be concise yet sufficiently informative.
- Explain relevant limitations.
- Distinguish documented recommendations from uncertainty.
- Do not present population-level recommendations as individualised advice.
- Cite all factual claims.
- Never invent information or references.

### 9.3 Knowledge Boundaries

- Use retrieved documents only.
- Do not use pretrained knowledge to fill gaps.
- Explicitly acknowledge insufficient evidence.
- Do not infer recommendations beyond the retrieved evidence.

### 9.4 Safety Boundaries

The assistant must not provide:

- Personal calorie targets
- Personal weight targets
- Recommendations about what an individual should weigh
- Medical advice
- Disease-specific dietary treatment recommendations
- Personalised nutrition prescriptions

Restricted questions are declined politely, directing users to a qualified healthcare professional or registered dietitian. Restrictions are enforced **both** in the prompt **and** in backend code.

---

## 10. Safety Enforcement

A dedicated backend **safety validation layer** that operates independently of the LLM.

### 10.1 Restricted Question Types

1. Direct requests for daily calorie targets.
2. Requests about ideal or recommended personal weight.
3. Medical or disease-specific dietary recommendations.
4. Requests for personalised medical nutrition advice.

### 10.2 Adversarial Testing

Test restrictions using:

- Direct questions
- Rephrased questions
- Indirect or sideways questions
- Restricted questions embedded in unrelated conversations
- Follow-up questions after several unrelated messages

The assistant must consistently decline restricted requests regardless of wording or conversation history. **The retrieval system must not be able to bypass safety refusals.**

---

## 11. Refusal Types

The assistant must distinguish, and represent separately in the schema, two kinds of refusal.

### A. Not in Corpus (`not_in_corpus`)

The requested information is not supported by retrieved documents.

- State clearly that the available guidance does not cover the question.
- Mention which documents or sources were searched.
- Do not guess or answer from internal model knowledge.

### B. Out of Scope by Design (`out_of_scope`)

Medical advice, personal calorie targets, weight targets, and restricted health-related recommendations.

- Decline politely.
- Briefly explain the limitation.
- Recommend consulting a qualified professional.
- Enforce in backend code.

---

## 12. Cross-Document Retrieval and Conflicting Guidance

Support questions that need information from multiple documents (e.g. cooking oils, which may involve both a nutrition institute and a food safety authority).

The assistant must:

- Retrieve relevant evidence from each document.
- Present information separately by source.
- Provide individual citations for each claim.
- Identify disagreements where they exist.
- Avoid combining different recommendations into an unsupported conclusion.

When sources disagree, show both positions with their **publishers and publication years**. Do not arbitrarily pick a winner.

---

## 13. Database and Conversation Management

Persistent storage for:

- User conversations
- Chat messages
- Retrieved document chunks
- Document metadata
- Failure logs
- Evaluation results

Conversation history must support follow-up questions. **Previous messages must never override safety restrictions or evidence requirements.**

---

## 14. Frontend and Sources Panel

The sources panel is part of the initial architecture, not an afterthought. It must display:

- Document title
- Publisher
- Publication year
- Relevant section
- Citation URL
- Supporting chunk or excerpt

Each source is tied to the specific claim it supports. Users must be able to inspect the evidence behind an answer **without leaving the conversation**.

---

## 15. Failure Logging and Monitoring

Implement a failure logging system to expose weaknesses in the assistant.

### 15.1 Failure Categories to Record

- Unsupported factual claims
- Missing citations
- Invalid citations
- Fabricated references
- Inconsistent numerical answers
- Incorrect document retrieval
- Incorrectly answered out-of-corpus questions
- Questions that should have been declined
- Excessively vague or unhelpful responses
- Conflicting guidance presented incorrectly

### 15.2 Fields per Log Entry

- User question
- Model response
- Failure category
- Relevant retrieved chunks
- Timestamp
- Model information
- Error description

> Do **not** hardcode fixes for individual questions. Logging exists to understand limitations and drive evidence-based architectural improvements.

---

## 16. Evaluation and Testing

### 16.1 Retrieval Evaluation (15+ questions)

- Create at least **15 RAG evaluation questions** across the corpus, each with a known expected document and section.
- Check whether the expected chunk appears in the top-k results.
- Calculate and report the **retrieval hit rate**.
- Separate retrieval failures from generation failures.

### 16.2 Benchmark Questions (10 questions)

Create 10 benchmark questions across these categories:

1. Nutrient requirements
2. Food safety and storage
3. Cooking methods
4. Questions without a clear or universally established answer

Run all 10 through the application and record per response:

- Unsupported claims
- Numbers that change across repeated runs
- Fabricated citations
- Incorrect or missing refusals
- Incorrectly retrieved evidence
- Unhelpful uncertainty
- Citation accuracy

Group failures by category and count occurrences.

### 16.3 Consistency Testing

Run the same question **three times** and compare substance, not exact wording:

- Numerical consistency
- Citation consistency
- Agreement with retrieved evidence
- Stability of recommendations
- Consistency of refusal behaviour

A factual number changing between runs is recorded as a potential failure. Answers must not be modified to appear consistent.

### 16.4 Citation Verification (10+ answers)

Manually inspect at least 10 generated answers. For each:

1. Open the cited document.
2. Locate the cited section.
3. Verify the claim is supported.
4. Check numerical values.
5. Confirm the citation accurately represents the source.
6. Record incorrect or unsupported citations.

A citation is not valid merely because the document exists; it must actually support the claim.

### 16.5 Safety Adversarial Testing

See [Section 10.2](#102-adversarial-testing).

### 16.6 Failure Analysis Report

Compile logged failures from all of the above into a report grouped by category with counts and proposed architectural improvements.

---

## 17. Deployment and GitHub

- Push the complete source code to GitHub.
- Deploy frontend and backend publicly.
- Configure environment variables securely; never expose API keys in frontend code.
- Configure production database and vector storage.
- Verify every API endpoint in production.
- Test the deployed application using the evaluation question bank.

Provide:

- GitHub repository URL
- Live application URL
- README documentation
- Environment variable template (`.env.example`)
- Setup and deployment instructions

---

## 18. Deliverables

| # | Deliverable |
|---|---|
| 1 | Full-stack AI nutrition chatbot |
| 2 | Responsive chat frontend |
| 3 | Backend API |
| 4 | Persistent conversation storage |
| 5 | Structured response schema |
| 6 | System prompt |
| 7 | Backend safety enforcement |
| 8 | Corpus of 5–7 official dietary guidance documents |
| 9 | PDF extraction and document processing pipeline |
| 10 | Document chunking and metadata management |
| 11 | Embedding generation |
| 12 | Vector database integration |
| 13 | RAG retrieval pipeline |
| 14 | Citation-backed claim generation |
| 15 | Cross-document retrieval |
| 16 | Two distinct refusal mechanisms |
| 17 | Failure logging system |
| 18 | Minimum 15 retrieval evaluation questions |
| 19 | Minimum 10 benchmark questions |
| 20 | Consistency testing results |
| 21 | Citation verification results |
| 22 | Retrieval hit-rate report |
| 23 | Failure analysis report |
| 24 | GitHub repository |
| 25 | Publicly deployed application |
| 26 | Comprehensive README |

---

## 19. Acceptance Criteria

The project is complete only when:

- [ ] The chatbot works end-to-end.
- [ ] All model calls happen through the backend.
- [ ] Every response follows the defined structured schema.
- [ ] Every factual claim has a verifiable citation.
- [ ] Answers are generated only from retrieved evidence.
- [ ] Unsupported questions produce an explicit `not_in_corpus` response.
- [ ] Medical advice and personal calorie/weight targets are declined.
- [ ] Safety restrictions hold across rephrased and indirect questions.
- [ ] Cross-document answers preserve source attribution.
- [ ] Conflicting recommendations are presented separately.
- [ ] The sources panel displays actual supporting evidence.
- [ ] Conversation history persists.
- [ ] Failures are recorded rather than hardcoded away.
- [ ] Retrieval evaluation is completed.
- [ ] Citation spot-checking is completed.
- [ ] Consistency testing is completed.
- [ ] The application is deployed at a publicly accessible URL.
- [ ] The GitHub repository and README contain the required documentation.

---

## 20. Development Instructions and Rules

Build this as **one unified, production-oriented application**, delivered end to end.

### 20.1 Before Writing Code

1. Analyse the complete requirements.
2. Propose a clear system architecture.
3. Define the database schema.
4. Define the API contracts.
5. Define the structured response schema.
6. Design the RAG pipeline.
7. Identify safety enforcement points.
8. Plan the testing and evaluation strategy.

Then implement incrementally.

### 20.2 Implementation Rules

- Do not create mock functionality where real functionality is required.
- Do not fabricate official documents or citations.
- Do not use the LLM's internal knowledge as a substitute for retrieved evidence.
- Do not hardcode answers to evaluation questions.
- Do not bypass schema validation.
- Do not expose secrets in frontend code.
- Do not silently ignore errors.
- Write clean, modular, maintainable code.
- Include appropriate error handling and logging.
- Provide clear setup instructions.
- Test every major component before deployment.

---

## Final Goal

Deliver a complete, working, publicly deployed AI Nutrition Assistant that combines **structured LLM responses, official-document RAG, verifiable citations, safety enforcement, conversation management, failure tracking, and measurable evaluation** in one cohesive system.
