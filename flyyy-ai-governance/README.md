# Flyyy.ai - SaaS AI Discovery & Monitoring Platform

> Challenge: Discovering and Monitoring AI Inside SaaS Applications.
> Build a working application that discovers AI capabilities embedded in SaaS
> applications, identifies who can use them, and monitors the AI interactions
> taking place through them.

This repository is a complete, runnable implementation of that workflow, focused
on Microsoft 365 Copilot (the challenge's primary example) with a connector
framework that cleanly separates what a SaaS platform exposes from what it
withholds. A demonstration connector ships so the entire flow works with NO
credentials, and a real Microsoft 365 connector uses actual Graph + Management
Activity APIs once configured.

## Problem & Approach

Organisations know they use Microsoft 365, Slack, Notion, etc., but not which
AI is enabled, who can use it, how it is used, or what is sent to the LLM.

1. Discovery - determine which AI features exist, whether enabled, and which
   users/groups have access (evidence-based, not assumed).
2. Monitoring - capture the requests/responses sent to the underlying LLM where
   the platform exposes them, and clearly state where it does not.

We chose depth over breadth: one platform (Microsoft 365) researched
thoroughly, plus a demo connector, rather than many shallow integrations.

## What We Built

- AI Asset Inventory - every discovered capability becomes a governed asset
  (type, provider, platform, capability, status, purpose, accessible resources,
  discovery source, monitoring & review status).
- Access Evidence - users/groups with access, their license/entitlement, and the
  source of that evidence.
- Interaction Monitoring - captured AI interactions with identity, app, feature,
  model, timestamp, request/response, token usage, and a per-record
  visibility_note explaining exactly what the platform did NOT expose.
- Honest dashboards - visibility bars show, across all interactions, how much
  request/response/model/usage data is actually available.

## Architecture

Browser -> React SPA -> FastAPI REST -> Connector Framework -> (Microsoft365
Connector | Demo Connector) -> (MS Graph API | Office 365 Mgmt Activity API).
FastAPI also writes to PostgreSQL / SQLite.

An interactive version of this diagram is committed as architecture.excalidraw
(open in excalidraw.com or the VS Code extension).

Data flow:
1. A Connection represents a configured SaaS environment.
2. DiscoveryService runs a connector discover() -> upserts AIAsset + AIAssetAccess, records a Run.
3. MonitoringService runs monitor() -> inserts AIInteraction linked to the matching asset, records a Run.
4. The React UI reads aggregated stats, the inventory, and the interaction log.

## Key Design Decision: Modelling Visibility

Most SaaS platforms do NOT expose the prompt, response, model, or token counts
through their audit APIs. Rather than silently returning empty strings, every
monitoring field carries a companion boolean:

- model        -> model_available
- request_info -> request_available
- response_info-> response_available
- token_usage  -> usage_available

The UI renders these as "Available" / "Not exposed" with a visibility_note. This
makes the platform limitations first-class, which is the core of the challenge.

## SaaS Research: Observable vs Withheld

Microsoft 365 Copilot:
  Discoverable: Copilot license SKUs; per-user license assignment; associated workloads.
  Monitorable: User identity, workload/app, operation, timestamp (unified audit log, RecordType 305).
  Withheld: prompt, response, model name, token counts.

Slack AI:
  Discoverable: workspace AI settings; channel enablement.
  Monitorable: action type (summary/search/recap); user & channel.
  Withheld: generated text, model.

Notion AI:
  Discoverable: workspace add-on; plan entitlements.
  Monitorable: model name (some plans), usage/tokens (some plans), request type.
  Withheld: full response text (most plans).

Microsoft 365 is implemented with real endpoints:
- Discovery: GET /subscribedSkus + GET /users?$select=...assignedLicenses.
- Monitoring: Office 365 Management Activity API (subscriptions/start,
  subscriptions/content) for Audit.General/Exchange/SharePoint/..., parsing
  Copilot records (Operation CopilotInteraction, RecordType 305).

## Tech Stack

- Language: Python 3.11+
- Backend: FastAPI, SQLAlchemy 2.0, Pydantic v2, httpx
- Frontend: React 18 + Vite (JavaScript)
- Database: PostgreSQL (preferred) - SQLite for zero-setup dev
- Migrations: Alembic
- Auth: Signed JWT bearer tokens for mutating endpoints
- Agent framework: Not used - the problem is a connector/discovery problem; an
  LLM agent would add latency and obfuscate the evidence chain, so it is
  deliberately omitted (per the challenge guidance).

## Repository Layout

backend/app - FastAPI app, config, database, models, schemas, security, seed.
backend/app/connectors - base + microsoft365 + demo + registry.
backend/app/services - discovery & monitoring orchestration.
backend/app/routers - assets, interactions, connections, stats, auth.
backend/alembic - migrations.
frontend/src - api.js, App.jsx, components, pages (Dashboard, Assets,
  AssetDetail, Interactions, Connectors, Limitations).
architecture.excalidraw - system diagram.

## Quick Start (zero setup)

No database or credentials required - demo data seeds automatically.

  cd backend
  python -m pip install -r requirements.txt
  cp .env.example .env          # optional; defaults work out of the box
  python -m uvicorn app.main:app --host 127.0.0.1 --port 8000
  # API docs at http://127.0.0.1:8000/docs

  cd frontend
  npm install
  npm run dev
  # http://localhost:5173

The dashboard shows 3 discovered AI assets (Microsoft 365 Copilot, Slack AI,
Notion AI), 12 access grants, and 32 monitored interactions - all clearly tagged
as SIMULATED so they are never confused with real evidence.

## Configure a Real Microsoft 365 Tenant

1. In Entra ID, register an app and grant Application permissions:
   Directory.Read.All, User.Read.All, Organization.Read.All (discovery) and
   Office 365 Management API: ActivityFeed.Read (monitoring). Admin-consent all.
2. Create a client secret.
3. Fill backend/.env:
   MS365_ENABLED=true
   MS365_TENANT_ID=your-tenant-id
   MS365_CLIENT_ID=your-app-client-id
   MS365_CLIENT_SECRET=your-client-secret
4. Restart the backend, open Connectors, and click Run Discovery / Run
   Monitoring on the "Microsoft 365 (configure me)" connection. Real evidence is
   captured; prompt/response/model stay marked Not exposed (honest limitation).

Other credentials (ADMIN_USERNAME/PASSWORD, SECRET_KEY, DATABASE_URL) are also
placeholders in .env.example - replace before any real deployment.

## Production (PostgreSQL + Alembic)

  DATABASE_URL=postgresql+psycopg://USER:PASSWORD@HOST:5432/flyyy
  pip install "psycopg[binary]"      # uncomment in requirements.txt
  alembic upgrade head               # create schema (instead of auto-create)
  python -m uvicorn app.main:app --host 0.0.0.0 --port 8000

## API Reference (all under /api/v1; mutations need Bearer token from /auth/login)

  GET  /stats/dashboard
  GET  /assets                 (filters)
  GET  /assets/{id}
  PATCH /assets/{id}
  GET  /interactions           (filters)
  GET  /interactions/filters
  GET  /connections
  POST /connections
  GET  /connections/{id}/capabilities
  POST /connections/{id}/discover
  POST /connections/{id}/monitor
  GET  /connections/{id}/runs
  POST /auth/login

Interactive docs: http://127.0.0.1:8000/docs

## Limitations & Future Work

- Content gap is by design. SaaS audit APIs expose metadata, not prompts. Where a
  vendor offers a dedicated compliance/DLP export, the connector flips the
  relevant *_available flag to capture content - the schema already supports it.
- Multi-platform breadth. Only Microsoft 365 is wired to real APIs; Slack AI and
  Notion AI appear only in demo data. Each is a single new connector module.
- Scale. Discovery paginates Microsoft Graph; the current implementation fetches
  a single page for clarity and can be extended with @odata.nextLink walking.
- No agent. Deliberately omitted; the evidence chain is explicit and reviewable.

## Evaluation Map

- Problem understanding: README approach + Visibility page
- Depth of technical research: connectors/microsoft365.py real endpoints + table
- Engineering quality: typed models/schemas, services, Alembic, error handling
- System design: architecture.excalidraw + README diagram
- Handling edge cases: fallback to demo connector, idempotent runs, graceful API failures
- Clarity of documentation: this README
- Explain approach / limitations: Modelling Visibility + Limitations sections
