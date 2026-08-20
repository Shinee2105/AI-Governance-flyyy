# Flyyy.ai — SaaS AI Discovery & Monitoring Platform

> Discovery, visibility, and honest monitoring of AI capabilities embedded in SaaS applications.

## Problem

Organisations deploy AI inside SaaS platforms (Salesforce Agentforce, Slack AI, Notion AI, Microsoft 365 Copilot) but cannot answer the fundamental governance questions:

- Which AI features are enabled across the organisation?
- Who has access to each AI capability?
- What interactions are taking place against the underlying LLMs?
- What does the platform expose versus withhold in its audit APIs?

This project implements a complete discovery-to-monitoring workflow with a pluggable connector framework that distinguishes **observable evidence** from **platform-withheld data**.

## Architecture

<pre>
  Browser (React 18 + Vite)
      |
      v
  FastAPI REST API
      |
      v
  Connector Framework
      |
      +---> Salesforce Connector     (real REST APIs + Session Trace OTel API)
      +---> Demo Connector           (simulated data, zero setup)
      |
      v
  SQLite (dev) | PostgreSQL (prod)
</pre>

**Data flow:**

1. A `Connection` entity represents a configured SaaS environment (e.g., a Salesforce org).
2. `DiscoveryService` invokes `connector.discover()` — queries SaaS APIs, upserts `AIAsset` + `AIAssetAccess` records, and records a `Run`.
3. `MonitoringService` invokes `connector.monitor()` — captures interaction data, inserts `AIInteraction` records linked to assets, and records a `Run`.
4. The React SPA consumes aggregated stats, the asset inventory, and the interaction log.

## Visibility Modelling

SaaS audit APIs routinely withhold model names, request/response content, or token usage. Rather than silently returning empty strings, every monitoring field carries a companion boolean:

| Field              | Availability Flag      |
|--------------------|------------------------|
| `model`            | `model_available`      |
| `request_info`     | `request_available`    |
| `response_info`    | `response_available`   |
| `token_usage`      | `usage_available`      |

The UI renders each as "Available" or "Not exposed" with a `visibility_note` explaining what the platform did not expose. This makes platform limitations first-class, which is the core challenge.

## Repository Structure

```
flyyy-ai-governance/
  backend/
    app/
      connectors/
        base.py              — BaseConnector interface
        salesforce.py        — Salesforce Agentforce connector (real APIs)
        salesforce_client.py — OAuth client-credentials + REST client
        demo.py              — Demo connector (simulated, zero setup)
        registry.py          — Connector type registration
      services/
        discovery_service.py — Orchestrates discover() across connectors
        monitoring_service.py — Orchestrates monitor() across connectors
      routers/
        assets.py            — Asset inventory + review status
        interactions.py      — Interaction list + visibility filters
        connections.py       — Connector CRUD + discover/monitor triggers
        stats.py             — Dashboard aggregates
        auth.py              — Login endpoint
      models.py              — SQLAlchemy models (Connection, AIAsset, etc.)
      schemas.py             — Pydantic response models
      security.py            — JWT auth helpers
      config.py              — Environment-driven settings
      seed.py                — Dev seed (creates demo + Salesforce connections)
    alembic/
      versions/              — Database migrations
    tests/
      test_salesforce_connector.py
      test_services.py
      test_api.py
    requirements.txt
    .env.example
  frontend/
    src/
      api.js                 — Thin API client (token storage, auto-login in dev)
      App.jsx                — Routes + auth state
      components/
        Sidebar.jsx          — Sticky navigation + user session
        ConnectorCard.jsx    — Expandable connector cards
        PageHeader.jsx
        ui.jsx               — Badge, statusBadge, DemoBadge, etc.
      pages/
        Dashboard.jsx        — Stat cards + visibility bars + recent runs
        Assets.jsx           — Asset inventory table with filters
        AssetDetail.jsx      — Per-asset detail view
        Interactions.jsx     — Interaction log with expandable rows
        Connectors.jsx       — Connector management + evidence
        Limitations.jsx      — Platform visibility reference
        Login.jsx
      styles.css
      main.jsx
    vite.config.js
    package.json
  README.md                  — This file
  architecture.excalidraw
```

## Quick Start (Zero Setup)

No database or credentials required. The demo connector seeds realistic data automatically.

```bash
# Backend (Python 3.11+)
cd backend
python -m pip install -r requirements.txt
python -m uvicorn app.main:app --host 127.0.0.1 --port 8000

# Frontend (Node 18+)
cd ../frontend
npm install
npm run dev
```

| Endpoint         | URL                        |
|------------------|----------------------------|
| API              | http://127.0.0.1:8000      |
| API Docs (Swagger) | http://127.0.0.1:8000/docs |
| Frontend         | http://localhost:5173      |

The dashboard initially shows 3 simulated AI assets, 12 access grants, and 32 monitored interactions — all tagged as **SIMULATED**.

## Salesforce Configuration

To discover real evidence from a Salesforce org:

1. **Enable External Client Apps** in your Salesforce org:
   - Setup → External Client Apps → Settings → "Allow creation of connected apps"

2. **Create an External Client App (Connected App)**:
   - Setup → External Client Apps → New
   - Select OAuth 2.0 with the **Client Credentials** grant type
   - Assign scopes: `api`, `refresh_token`, `openid`
   - Set a **Run-As** integration user

3. **Configure the backend** (`backend/.env`):

```ini
SFDC_ENABLED=true
SFDC_DOMAIN=your-org.my.salesforce.com
SFDC_CLIENT_ID=your-connected-app-consumer-key
SFDC_CLIENT_SECRET=your-connected-app-consumer-secret
SFDC_API_VERSION=62.0

# (Monitoring) Agentforce session IDs, comma-separated.
# Obtain from the Salesforce Session Trace UI / Data Explorer.
SFDC_OTEL_SESSION_IDS=session-id-1,session-id-2
```

4. **Restart the backend**, navigate to Connectors, and click **Run Discovery** on the Salesforce connection.

### Verified Salesforce APIs

| Capability | API | Verified |
|---|---|---|
| Agent discovery | SOQL `BotDefinition` | Yes |
| User discovery | SOQL `User` | Yes |
| OAuth token | Client Credentials grant | Yes |
| Session traces | OTel API `GET /services/data/v{ver}/einstein/audit/otel/{session-id}` | Yes (Beta) |

## Monitoring Limitations (Documented)

- The OTel API returns **one session per request**. Session IDs must be obtained from the Salesforce Session Trace UI / Data Explorer.
- Sessions older than **72 hours** are not queryable.
- **Developer Edition**: The OTel endpoint (`/einstein/audit/otel/{session-id}`) is not available in DE unless Session Trace is explicitly enabled. The connector detects the 404 and records a diagnostic note instead of crashing. Use a production or Sandbox org with Session Tracing enabled for monitoring.

## API Reference

All endpoints are under `GET /api/v1`. Mutation endpoints require a Bearer token from `/auth/login`.

| Method | Endpoint | Description |
|---|---|---|
| `POST` | `/auth/login` | Returns JWT token |
| `GET` | `/stats/dashboard` | Dashboard aggregates (public) |
| `GET` | `/assets` | Asset inventory with filters |
| `GET` | `/assets/{id}` | Single asset detail |
| `PATCH` | `/assets/{id}` | Update review status |
| `GET` | `/interactions` | Interaction log with filters |
| `GET` | `/connections` | List all connections |
| `POST` | `/connections` | Create a new connection |
| `GET` | `/connections/types` | Available connector types |
| `GET` | `/connections/{id}/capabilities` | Connector evidence summary |
| `POST` | `/connections/{id}/discover` | Run discovery |
| `POST` | `/connections/{id}/monitor` | Run monitoring |
| `GET` | `/connections/{id}/runs` | Recent run history |

Interactive docs: http://127.0.0.1:8000/docs

## Development

```bash
# Backend: run tests
cd backend
python -m pytest -v

# Frontend: build for production
cd frontend
npm run build
```

## Tech Stack

| Layer | Technology |
|---|---|
| Backend | Python 3.11+, FastAPI, SQLAlchemy 2.0, Pydantic v2, httpx |
| Frontend | React 18, Vite, vanilla CSS (no UI framework) |
| Database | SQLite (dev) — PostgreSQL (prod) |
| Migrations | Alembic |
| Auth | Signed JWT bearer tokens |
| Deployment | Uvicorn / Gunicorn |

## License

This project is provided as-is for governance and discovery purposes.
