# Architecture Diagrams

Companion to [`README.md`](README.md) in this directory — that file is the
authoritative implemented-vs-planned text description; these diagrams
visualize the same real system. If a diagram and the text ever disagree,
the text file and the actual code win; open an issue.

## 1. High-level system

```mermaid
flowchart TB
    Customer["Customer's system\n(publishes events via API key)"]
    SDK["SDKs / CLI\n(node, python, go, java, cli)"]
    subgraph API["Backend API (FastAPI)"]
        Events["events/\nPOST /v1/events"]
        Endpoints["endpoints/"]
        Auth["auth/\nlogin, RBAC, OAuth"]
        Billing["billing/"]
        Insights["insights/\nhealth, incidents, AI"]
    end
    subgraph Async["Celery"]
        Worker["worker\n(default queue)"]
        WorkerInsights["worker-insights\n(insights queue)"]
        Beat["beat\n(scheduler)"]
    end
    DB[("PostgreSQL")]
    Redis[("Redis\nbroker + rate limiter")]
    Dest["Destination webhook endpoint\n(customer's server)"]
    Dashboard["Next.js dashboard\n(apps/web)"]
    Browser["Browser"]

    Customer --> SDK --> Events
    Events --> DB
    Events -- enqueue --> Redis
    Redis --> Worker
    Worker -- HTTP POST, signed --> Dest
    Worker --> DB
    Beat -- "check_due_retries,\ncleanup, insights schedule" --> Redis
    Redis --> WorkerInsights
    WorkerInsights --> DB
    Browser --> Dashboard --> API
    API --> DB
    API -- rate limits --> Redis
    Insights -.AI calls.-> AIGW["ai_gateway/"]
    AIGW -.-> Provider["Anthropic / OpenAI /\nGemini / xAI"]
```

## 2. Webhook delivery lifecycle

```mermaid
sequenceDiagram
    participant Customer
    participant EventsAPI as events/ (POST /v1/events)
    participant DB
    participant Queue as Redis (Celery broker)
    participant Executor as delivery/executor.py
    participant Dest as Destination endpoint
    participant Realtime as realtime/events.py

    Customer->>EventsAPI: POST /v1/events (API key)
    EventsAPI->>DB: create Event row
    EventsAPI->>DB: create one DeliveryJob per subscribed endpoint (status=queued)
    EventsAPI->>Queue: enqueue each job (queue_client.enqueue)
    Queue->>Executor: deliver_webhook(job_id) task picked up
    Executor->>DB: claim job (queued/retrying -> processing, CAS)
    Executor->>Executor: sign payload (HMAC-SHA256)
    Executor->>Dest: HTTP POST (signed payload)
    Dest-->>Executor: response (or timeout/error)
    Executor->>DB: record DeliveryAttempt
    alt success
        Executor->>DB: job.status = success
    else failure, attempts remain
        Executor->>DB: job.status = retrying, next_attempt_at = now + backoff
    else failure, attempts exhausted
        Executor->>DB: job.status = dead_letter
    end
    Executor->>Realtime: emit_delivery_update(job)
```

## 3. Retry / DLQ lifecycle

```mermaid
stateDiagram-v2
    [*] --> queued: event published
    queued --> processing: worker claims job
    processing --> success: 2xx response
    processing --> retrying: failure, attempts remain
    processing --> dead_letter: failure, attempts exhausted
    retrying --> processing: check_due_retries (beat, every 10s)\nfinds next_attempt_at <= now,\nre-enqueues
    dead_letter --> processing: POST /v1/dlq/{id}/retry\n(manual replay, fresh attempt budget)
    success --> [*]
    dead_letter --> [*]: discarded (POST /v1/dlq/{id} DELETE)

    note right of retrying
        Real incident (fixed this repo's history):
        if no `celery beat` process is running,
        this transition never fires -- jobs
        stay in `retrying` forever with a
        next_attempt_at in the past that
        nothing notices.
    end note
```

## 4. Realtime delivery status lifecycle

```mermaid
sequenceDiagram
    participant Executor as delivery/executor.py
    participant Emit as realtime/events.py\nemit_delivery_update()
    participant PubSub as Redis pub/sub
    participant SSE as realtime/routes.py\nGET /v1/realtime/deliveries/stream
    participant Frontend as apps/web/lib/realtime.ts

    Executor->>Emit: called after every status transition
    Emit->>PubSub: publish (organization-scoped channel)
    Note over Emit: publish failure is caught and logged,\nnever raised -- realtime is UX/observability\ninfrastructure, not delivery infrastructure
    Frontend->>SSE: EventSource connects (org-scoped)
    PubSub->>SSE: message delivered
    SSE-->>Frontend: SSE event (delivery.updated)
    Frontend->>Frontend: update UI (dashboard, deliveries list, DLQ page)
```

## 5. AI Gateway architecture

```mermaid
flowchart LR
    subgraph Callers
        RCA["insights/ai/\n(incident root-cause analysis)"]
        Copilot["insights/copilot/\n(dashboard chat)"]
    end
    subgraph Gateway["ai_gateway/"]
        Contracts["contracts.py\nprovider-neutral request/\nresponse/error shapes"]
        Registry["registry.py\nwhich providers exist,\nwhat each supports"]
        GW["gateway.py\nresolve provider -> model ->\nvalidate capability -> call ->\nnormalize -> optional fallback"]
    end
    subgraph Adapters["adapters/"]
        A1["openai.py"]
        A2["anthropic.py"]
        A3["gemini.py"]
        A4["xai.py"]
    end
    Ext1["OpenAI API"]
    Ext2["Anthropic API"]
    Ext3["Gemini API"]
    Ext4["xAI API"]

    RCA --> GW
    Copilot --> GW
    GW --> Registry
    GW --> Contracts
    GW -->|"_ADAPTER_CLASSES dict lookup"| Adapters
    A1 --> Ext1
    A2 --> Ext2
    A3 --> Ext3
    A4 --> Ext4

    Note1["Neither RCA nor Copilot ever\ntalks to a provider SDK directly --\nonly through this gateway."]
```

## 6. Authentication / multi-tenancy flow

```mermaid
flowchart TB
    Login["POST /v1/auth/login or\nGET /v1/auth/github/callback"]
    JWT["Access token issued\n(claims: user_id, org_id, role)"]
    Request["Any protected request\nAuthorization: Bearer ..."]
    Depend["auth/dependencies.py\nget_current_auth()"]
    AuthCtx["AuthContext\n(user_id, organization_id, role)"]
    RoleCheck["require_role(min_role)\nchecked per-route"]
    Route["route handler"]
    Service["service.py"]
    Tenant["db/tenant_query.py\ntenant_select(Model, organization_id)"]
    DB[("PostgreSQL\nevery org-scoped table\nhas an organization_id column")]

    Login --> JWT
    JWT --> Request
    Request --> Depend
    Depend --> AuthCtx
    AuthCtx --> RoleCheck
    RoleCheck -->|"role sufficient"| Route
    RoleCheck -->|"role insufficient"| Reject["403"]
    Route --> Service
    Service --> Tenant
    Tenant -->|"organization_id from AuthContext,\nnever from the request body"| DB

    Note1["AuthContext's organization_id/role come\nstraight from the JWT's claims -- not\nre-checked against the DB on every request.\nA token stays valid with its original claims\nuntil it expires, even if membership/role\nchanged since. Short access-token lifetime\n(15 min default) is the mitigation."]
```
