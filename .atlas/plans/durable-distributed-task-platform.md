# Durable Distributed Task Processing Platform

Short name: **Durable Task Platform**. Local-first, with Azure as the deployment
target. "Distributed" means API and worker processes can run separately and share
work across machines; a single local worker is still enough for the first lesson.

Status: proposal, not an implementation commitment.

Audience: the author has navigated the Azure portal at work but has not provisioned
infrastructure. The course must teach infrastructure concepts and setup rather
than treating them as prerequisites.

## Goal

Build a general-purpose platform, and a course around building it, for submitting
and monitoring durable tasks: registered functions with typed arguments and
results. An argument might be `x=5`, a date, a structured object, or a file reference.
Document processing is one application, not the platform's core data model.
Develop and test locally with Docker Compose, then deploy the same application
images and task contracts to Azure.

The course should grow one working system in stages. Each stage should include
an explanation, a runnable checkpoint, an experiment that exposes a failure
mode, and acceptance tests. Avoid starting with a large cloud architecture.

**Feasible does not mean identical infrastructure everywhere.** Application
contracts and images can stay consistent; identity, networking, storage behavior,
broker operation, and shutdown behavior still require Azure integration tests.

## Recommended starting decisions

### Read this first: the learning path

The technical detail below is a reference, not material to master before starting.
The practical sequence is:

1. **Run one function locally.** Learn the input/output contract.
2. **Run it in a background worker.** Submit through an API and check its status.
3. **Make it survive failure.** Kill the worker and inspect a safe retry.
4. **Develop functions in a notebook.** Test, register, and run them through workers.
5. **See what is happening.** Add a small task/worker monitoring page.
6. **Learn Azure one resource at a time.** Budget, storage, one container, identity.
7. **Move the working system to Azure.** Automate setup only after understanding it.

Real application examples can be introduced between steps 4 and 5, including
transcription or analysis. There is no need to provision a database, broker,
networking, and workers in Azure on day one.

### Provisional technical choices

- Python, FastAPI, Pydantic, PostgreSQL, Celery, RabbitMQ, and Azure Blob Storage
  through its SDK, with Azurite for local development.
- PostgreSQL owns business task state, attempt history, and dispatch intent.
  Celery transports execution requests; its result backend and Flower are not the
  authoritative task database.
- Store small validated arguments/results as JSON in PostgreSQL. Use object
  storage only for large or binary inputs/outputs; tasks need not have artifacts.
  Queue messages contain IDs, not large payloads, secrets, arbitrary Python
  objects, or pickled notebook functions.
- Use one installable application package and separate API, dispatcher,
  reconciler, and worker processes. Initially some control processes can share a
  deployment, but their responsibilities should remain explicit.
- Route task executions to queues and bind worker groups to queues, not individual
  task types. A group can run many task types using compatible installed code.
- Local workers **always run in Docker containers**, managed through Compose and
  built from a Dockerfile. Azure runs images built from the same package; a
  Dockerfile is not required per task/queue. There is no host-process worker mode.
- Local workers are **CPU-only**. No local GPU runtime, device passthrough, or GPU
  dependency is required. GPU-backed cloud workers are an optional later extension.
- Use two logical queue classes, `cpu` and `gpu`, with environment-specific worker
  configuration. Initially only `cpu` is enabled, with low concurrency, a simple
  monitoring page, and deterministic fake providers. Enable `gpu` only after
  provisioning a compatible cloud runtime. Split further only for measured needs.
- Start Azure with a continuously running worker and a minimum replica count,
  rather than immediately attempting scale-to-zero.
- Treat execution as **at least once**. Design for duplicate delivery and process
  death; do not promise exactly-once external effects or unlimited task duration.
- Learn one new boundary at a time: local application behavior first, small Azure
  exercises second, the full deployment third. Do not require learning Celery,
  networking, identity, and infrastructure as code in the same lesson.

RabbitMQ is the provisional broker recommendation because it is a conventional
Celery pairing and can use the same protocol locally and in Azure. Its hosted
operation and long-task acknowledgement settings are a decision gate, not a
reason to run an unplanned production broker inside an ephemeral container.
Confirm an acceptable managed offering, networking, region, cost, and operational
ownership before committing. Do not silently substitute Azure Service Bus and
assume identical Celery behavior.

## Architecture

```text
Notebook / SDK / monitoring UI
                |
                v
          FastAPI + task catalog
                |
                v
      PostgreSQL: tasks, attempts,
      events, definitions, outbox
                |
           dispatcher
                |
                v
             RabbitMQ
                |
                v
          Celery workers ----------> registered functions
            |       |
            |       +-------------> optional external services / blob storage
            v
         PostgreSQL

Reconciler: detects expired execution leases and stranded dispatches.
Monitoring: persisted task counts + worker heartbeats + broker/worker telemetry.
```

Accepting a request, sending a queue message, and executing work are separate
steps. PostgreSQL and the broker do not share an atomic transaction.

### Minimum durable execution contract

1. Validate the task definition, input schema, access to referenced artifacts,
   and submission idempotency key.
2. Commit a task and an outbox entry in the same PostgreSQL transaction. Return
   `202 Accepted` with a task ID and status URL; never hold HTTP open for the work.
3. A dispatcher publishes an execution request and records dispatch progress.
   A crash between publish and recording success can produce duplicates.
4. A worker uses an atomic database claim to acquire an attempt lease. A duplicate
   message must not acquire the same active attempt or overwrite a completed task.
5. The worker heartbeats, reports progress, and commits the result JSON and/or
   artifact references plus outcome. Broker acknowledgement is not the business
   success record.
6. A reconciler handles expired leases and tasks whose dispatch stalled. New
   attempts get new fencing tokens so an old worker cannot overwrite a newer
   attempt. This does not automatically fence external provider side effects.
7. Retries use a persisted policy, backoff, jitter, and attempt/deadline limits.
   Choose one application-level retry authority rather than independently
   layering uncoordinated database retries and Celery `autoretry`.

For expensive external calls, use provider idempotency keys where available and
persist provider job IDs. A provider may accept a request just before the worker
dies. Without provider support or a reliable lookup, the result can be ambiguous:
flag it for reconciliation rather than claiming a retry is cost-free or unique.

### General task model, typed task contracts

Use a stable envelope, not a single unvalidated JSON blob and not a table per
task type.

The platform accepts any arguments supported by a definition's serialization and
validation contract, not literally any in-memory Python object. Start with named
JSON arguments: numbers, strings, booleans, null, lists, and nested objects. Encode
dates as ISO 8601 strings and decode them through the declared schema. Use
artifact references for files, not open file handles or machine-local paths.

Illustrative submissions to a generic `POST /tasks` endpoint:

```json
{"task_type": "math.square", "version": "1", "arguments": {"x": 5}}
```

```json
{"task_type": "calendar.describe_day", "version": "1", "arguments": {"day": "2026-11-13"}}
```

Both use the same submission, status, retry, and monitoring machinery. Neither
requires a document ID or file upload. Results might be `{"value": 25}` or
`{"weekday": "Friday"}`.

For "today," define when and in which timezone it is resolved. Prefer resolving
it to an explicit date at submission so retries use the same input even after
midnight. Execution-time clock access is possible, but is a different contract.

| Record | Suggested responsibilities |
| --- | --- |
| `task_definitions` | Name, immutable version, input/output schemas, implementation artifact reference/digest, default queue and allowed routing, resource class, retry/deadline policy, lifecycle state. |
| `tasks` | ID, definition/version, arguments JSON, optional artifact references, state, queue, owner/security scope, timestamps, next retry time, deadline, idempotency key, progress, result JSON and/or references, safe error summary. |
| `task_attempts` | Task ID, attempt number, execution/lease token, worker identity, start/end/heartbeat times, outcome, error classification, provider operation IDs. |
| `task_events` | Append-only operational timeline of state changes and selected progress; avoid storing sensitive arguments, results, or secrets. |
| `artifacts` | Storage key, media type, size/hash, owner/security scope, retention metadata; signed URLs are temporary access mechanisms, not durable identifiers. |
| `dispatch_outbox` | Dispatch intent, availability time, publication attempts, and publication state. |
| `queues` | Approved queue names, execution/resource class, access policy, and lifecycle state; explicit broker declarations. |
| `worker_groups` | Named execution configuration: subscribed queues, package/image version, resource/concurrency settings, and local/Azure deployment binding. |
| `worker_heartbeats` | Live instance identity, group, actual subscribed queues, supported implementation versions, resource class, heartbeat freshness, and current capacity. |

Initial public states:

```text
queued -> running -> succeeded
              |----> failed
              |----> retry_wait -> queued
queued / retry_wait / running -> cancelled
```

Keep scheduling intent separate from observed facts: a `queued` database task
may still be waiting for dispatch, and a stale `running` task may have lost its
worker. Expose dispatch status and heartbeat freshness where useful.

- Every input is checked against the selected definition's schema.
- The same definition version and implementation remain pinned across retries.
  Changing implementation or execution-affecting configuration creates a new
  version, including prompts/model settings for tasks that use them.
- Scope idempotency keys to the caller/security boundary; reject key reuse with
  different input instead of returning an unrelated task.
- A failed task retains its attempts. An explicit manual retry appends a new
  attempt under a documented policy; rerunning with changed input/version creates
  a new task linked to the original.
- Cancellation is cooperative: record the request, check at safe points, and
  distinguish requested from confirmed cancellation. It cannot undo provider calls.
- Do not rely on Celery revocation to implement a durable cancellation contract.

## Queue routing and worker registration

Separate four concepts:

1. **Task definition:** a versioned function and its argument/result contract.
2. **Queue:** where an execution request waits for a consumer.
3. **Worker group:** a named configuration for interchangeable workers that consume
   one or more queues with compatible code, dependencies, and resources.
4. **Worker instance:** an actual running worker container belonging to that group.

Initial routing model:

```text
math.square ----------\
calendar.describe_day -+--> cpu queue --> CPU worker group
data.summarize -------/

model.infer ----------\
image.generate --------+--> gpu queue --> GPU worker group (cloud, later)
```

The GPU examples mean running a model inside the worker, not calling a hosted
model API. A worker that submits/polls an external model or transcription API
normally belongs on `cpu`, even if the provider uses GPUs internally.

This is a task-to-queue and worker-to-queue relationship, not a task-to-worker
assignment. Multiple workers compete for each queue's messages; a message is not
broadcast to every worker. A group can subscribe to several queues if that is
useful, though this is not a strict priority/fairness guarantee.

### Shared queue names, environment-specific configuration

Keep the logical task routes stable while changing deployment settings:

| Setting | Local | Cloud |
| --- | --- | --- |
| `cpu` | Enabled; CPU-only Docker workers via Compose | Enabled; CPU worker containers, initially fixed capacity |
| `gpu` | Disabled; reject GPU-required submissions to this environment | Disabled initially; enable after a suitable GPU deployment is verified |
| Worker image | Build the CPU image from the project Dockerfile | Pin approved CPU/GPU images from the registry as appropriate |
| Resources/capacity | Local CPU/memory limits and worker count | Cloud CPU/memory, optional GPU class, concurrency, replica bounds |
| Dependencies/access | Local broker/database/storage configuration | Cloud endpoints, identity/secrets, and network settings |

Use a shared configuration contract plus local/cloud overlays, not separate task
implementations for each environment. Reference secrets rather than embedding
credentials. Validate the effective configuration before starting workers or
enabling task definitions.

Local and cloud use **separate brokers or explicitly isolated broker namespaces
and credentials**. Reusing names `cpu` and `gpu` does not mean sharing physical
queues. Local workers must never accidentally consume cloud work.

Distinguish an environment-disabled queue from an enabled queue temporarily
having zero replicas: reject the former; the latter can retain work while
capacity returns under its configured policy. A disabled logical queue need not
be physically declared in that environment's broker.

CPU/GPU is the first resource split, not a guarantee that all tasks in a class
are interchangeable. Installed implementation versions, memory, GPU memory/model,
and other dependencies must remain compatible across that queue's consumers.
Later split queues if long work starves short work, dependencies conflict, or
hardware requirements diverge. Do not introduce those extra queues upfront.

### Routing rules and compatibility

- Set a default queue on each definition and resolve/persist the actual queue at
  submission. An authorized caller may select an allowed override; do not accept
  arbitrary broker queue names from API requests.
- Keep the selected route stable across automatic retries. Any operational move
  to another compatible queue must be explicit and recorded.
- Register/declare queues deliberately. Avoid accidental empty queues caused by
  typos or automatic creation of arbitrary names.
- Every consumer of a queue must be able to execute every definition/version that
  can be delivered there. RabbitMQ/Celery does not inspect function capabilities
  and automatically select the right worker from incompatible consumers.
- A shared framework task, such as `execute_task(task_id)`, can load the pinned
  definition and invoke its implementation. A newly registered platform function
  therefore need not create a new HTTP endpoint or a bespoke Celery worker.
  The implementation still has to be installed in the worker runtime.
- Start with the same application package/image across a queue's consumers.
  Specialized dependency/resource bundles are a later reason to split queues.
  Enforce compatibility when configuring groups and publishing new definitions.
- Include execution requirements such as `accelerator: cpu` or `accelerator: gpu`
  in definition/group compatibility checks. Local groups support CPU only.
  Reject routing GPU-required work to the local execution profile with a clear
  explanation; do not silently fall back to CPU or leave it indefinitely waiting
  for a local GPU worker that cannot exist under this profile. A local SDK may
  still submit to an explicitly configured compatible cloud environment later.
- CPU-only describes the local runtime, not a ban on external services. Local
  workers can call approved cloud APIs; offline tests use fakes or CPU-compatible
  implementations. These are explicit alternatives, not silent GPU fallbacks.
- A new image serving an existing queue must retain implementations needed by
  queued/running/retrying tasks. Otherwise use an explicit versioned queue/group
  rollout rather than mixing incompatible workers on a shared queue.
- A valid queue can temporarily have zero live workers. Accept work under a
  documented policy, show "waiting for capacity," and alert on queue age instead
  of confusing a stopped worker with an unknown implementation.

### Register configurations; discover live instances

Register a queue and a worker-group configuration through versioned configuration
initially; a management API/UI can come later. An instance authenticates and
announces its actual identity, group, subscriptions, and capabilities on startup,
then sends heartbeats. Stale instances become unavailable in monitoring.

Registration records desired configuration; it does **not** start a container or
provision Azure infrastructure. Locally a developer starts/scales worker containers
through Compose; in Azure a deployment creates replicas. Leave API-driven
infrastructure provisioning out of the MVP.

The UI should distinguish configured groups/desired capacity from observed live
instances, concurrency slots, and stale instances.

### Local Docker versus Azure containers

| Concern | Local worker | Azure Container Apps worker |
| --- | --- | --- |
| Execution unit | Docker container, always | Container running a built image |
| Code/dependencies | Installed into the image; explicit development source mounts allowed | Installed into the image during build |
| Compute | CPU-only; configurable CPU/memory limits for containers | CPU initially; GPU is a separate later deployment decision |
| Queue subscription | Startup command/configuration | Container startup command/configuration |
| Starting capacity | Start/scale worker containers through Compose | Set replica bounds/deploy more replicas |
| Connectivity | Compose service names and internal container network | Configured cloud endpoints, network access, identity/secrets |

The packaging path is:

```text
Python package + Dockerfile
             |
          build image
             |
     push to container registry
             |
  deploy image to Container Apps
             |
  start worker with queue configuration
```

Container Apps runs the **image**, not a Dockerfile directly. The Dockerfile is
the recipe used by a local or CI build. Deployment configuration separately
specifies the image reference, startup command, queue subscriptions, environment,
identity, resources, and replica settings.

One worker image can back multiple groups by changing startup configuration;
there is no need for one Dockerfile per task or per queue. Use different images
only when dependencies, resources, isolation, or release requirements justify it.

Provide a CPU-only worker image/profile usable both locally and in the initial
Azure deployment. Use CPU-compatible dependencies and configure local Compose
CPU/memory limits without requesting GPU devices. Validate image architecture
for the host and Azure target; build appropriate platform variants if local
development uses a different CPU architecture.

Notebooks and the SDK may run on the host and call the published local API.
Inline function tests in a notebook are not workers: they do not consume queues
or provide durable execution. Every queued local execution runs inside a worker
container. This keeps worker dependencies and startup behavior aligned with the
Azure deployment path.

## Notebook-first function development

Support two honest modes rather than implying that remote workers can import
an arbitrary live notebook closure.

### Interactive exploration

A lightweight SDK/decorator creates a definition from explicit schemas and
allows direct invocation with the same task context used by workers:

```python
# Illustrative interface, not an implemented API.
from pydantic import BaseModel

class SquareInput(BaseModel):
    x: int

class SquareOutput(BaseModel):
    value: int

@platform.task(name="math.square", version="dev", input=SquareInput,
               output=SquareOutput)
def square(ctx, request):
    ctx.report_progress(step="calculating")
    return SquareOutput(value=request.x ** 2)

result = square.run_inline({"x": 5}, context=local_context)
```

Inline execution is for fast debugging. It is not a durability test and stops
when the kernel stops. Supply a fake clock, temporary artifacts, or fake provider
clients when the particular function needs them. Exercise the schema and error
contract here.

### Registered execution

The catalog must distinguish a draft definition from a runnable implementation.

1. Register metadata/schema in a local or isolated development catalog. This can
   make the definition discoverable through the API as a **draft**, not magically
   make the notebook's memory available to workers.
2. To submit through the durable API before committing to Git, put the candidate
   function in an importable local module and start/reload an isolated development
   worker with that module mounted. Bind the registration to an immutable
   development snapshot/digest; keep old versions available while tasks use them.
3. Mark a definition runnable only when its route has a compatible approved worker
   runtime/deployment configuration. Live instances may temporarily be offline.
   API validation cannot import and execute arbitrary user-submitted code.
4. Promote the same function and contract into a tested package, build an image,
   and publish an immutable production definition tied to that image/artifact.
5. In production, catalog publication requires authorization and an approved
   deployment artifact. API submission is allowed only for approved definitions.

A notebook kernel never acts as a queue-consuming worker. Use it for inline tests
and SDK submission; use the Docker worker for durable execution. Remote code
upload, arbitrary `cloudpickle`, and multi-user untrusted execution are explicitly
out of scope for the first platform.

## Azure foundations track — no infrastructure experience assumed

These are short companion labs, not an expectation to provision the whole
architecture independently. Early work can remain entirely local. Docker,
Compose, container images, volumes, and service networking also need a short
introductory lab if unfamiliar.

Each Azure lab should explain the resource's purpose, what it costs, the exact
creation steps, how to verify it works, and how to delete it. Include a small
glossary and troubleshooting notes. Start with the portal to make resources
visible, repeat a small example with the Azure CLI, and only then encode the
repeatable environment in Bicep.

### Lab A — Account, permissions, and spending safety

- Explain tenant/directory, subscription, resource group, region, and resource.
  Show how to confirm the active subscription before creating anything.
- Distinguish permission to navigate the portal from permission to provision
  resources or assign roles. Confirm workplace policy and use an approved
  sandbox/subscription; do not experiment in production.
- Explain the difference between Azure management permissions and permissions
  to read actual application data.
- Set a budget and alerts before paid experiments. Budget alerts are **not a hard
  spending cap**. Discuss always-on database/broker charges and log ingestion.
- Establish resource names/tags and a cleanup checklist. Explain that deleting
  a dedicated lab resource group is destructive and requires checking its contents.

**Exit:** identify where resources would be created, which permissions are
available, and who pays. No platform deployment is required.

### Lab B — One storage resource

- Create a small storage account and private blob container using synthetic data.
- Upload/download a file, then access it with the same SDK used with Azurite.
- Explain connection strings versus identity-based access, storage roles, and
  why access keys and signed URLs must not be committed.
- Delete the lab resources after verifying the result.

**Exit:** understand one concrete local-to-cloud substitution and its limits.

### Lab C — One disposable container

- Deploy a tiny stateless sample to Container Apps, not the full platform.
- Explain registry/image, app/environment, revision, ingress, replica, environment
  variable, secret, and application log.
- Test a health endpoint, inspect logs, deploy a new revision, and clean up.
- First use a suitable public sample image; add a private registry and image push
  as a separate step, rather than making registry permissions the first obstacle.
- Explain that private worker processes need no public HTTP endpoint.

**Exit:** understand how a local image becomes a running Azure application.

### Lab D — Reproducible setup

- Translate the small understood deployment into Bicep and configuration.
- Show preview/what-if, deployment, verification, and cleanup.
- Explain which resources persist data and why deleting/replacing them differs
  from updating stateless application containers.
- Add managed identity and a narrowly scoped Blob Storage role, then verify both
  allowed access and a denied operation.

**Exit:** recreate a small environment without memorizing portal clicks.

Labs A–C can follow the local vertical slice when desired; Lab D should precede
the full Azure stage. Do not require paid Azure resources to complete local course
checkpoints. No Azure resources should be created merely to write this plan.

## Staged implementation and course outline

### Stage 0 — Define the contract and failure budget

**Learn:** what “durable” means and which failures the system must recover from.

- Pick simple tasks with different inputs: `square(x=5)` and
  `describe_day(day="2026-11-13")`. Add a slow/failure-injection variant for recovery
  tests; squaring a number alone does not demonstrate long-running behavior.
- Record expected task duration, maximum argument/result size, daily volume,
  burst size, external rate limits, sensitivity, and acceptable recovery delay.
  Unknown values stay explicit; do not invent capacity requirements.
- Decide whether tasks can checkpoint or resume external operations.
- Write state transitions, API examples, schema/versioning rules, and retry/error
  classification. Separate transient provider errors from invalid input.
- Decide local-only versus team use, authentication boundary, and data retention.
- Use synthetic or approved test data; no sensitive organizational inputs.

**Exit:** an agreed contract, test fixtures, and a failure-test checklist.

### Stage 1 — Local vertical slice

**Learn:** how a task travels from API submission to a visible result.

- Create a separate supporting project, provisionally
  `projects/durable-task-platform/`, with its own environment and README.
  Do not add platform dependencies to Atlas's root environment.
- Compose PostgreSQL, RabbitMQ, API, and one worker. Add Azurite as an optional
  artifact-storage profile/example; basic numeric/date tasks must work without it.
  Keep development credentials local and ports private to the host where practical.
- Document notebook-friendly development with host-side notebooks/SDK and all
  workers in Compose. Mount explicit candidate modules into a development worker
  container or rebuild its image; do not start a worker in the notebook/host.
- Keep local workers CPU-only. Verify the worker container starts without GPU
  drivers/devices and that GPU-required task routes fail validation locally.
- Declare one active `cpu` queue and a CPU worker group, initially using simple
  versioned configuration. Route multiple task types through it; configure `gpu`
  as unavailable locally without declaring an unserviceable broker queue.
- Validate local/cloud configuration overlays and environment isolation. A task's
  logical queue class stays the same when its submission targets either
  environment; deployment details do not leak into the function implementation.
- Implement schema migrations, typed task definitions, submission/status/catalog
  endpoints, JSON arguments/results, and a minimal dispatcher/outbox. Keep an
  extension point for optional artifact references.
- Add numeric/date example tasks and a deterministic slow task with configurable
  duration and failure mode. No files or paid model calls are needed to understand
  the platform.
- Demonstrate SDK inline execution and durable API submission.

**Exit:** one local command starts the system; submit, poll, and inspect a stored
result. Restarting services preserves task records and artifacts. This proves
persistence, not yet complete crash recovery.

### Stage 2 — Prove recovery before adding real workloads

**Learn:** delivery guarantees, acknowledgement, leases, and idempotency.

- Implement attempts, leases/heartbeats, fencing, reconciliation, bounded retries,
  deadlines, and a durable event timeline.
- Configure and test long-running Celery work: late acknowledgements where
  appropriate, worker-loss policy, low prefetch, explicit concurrency, graceful
  shutdown, and broker acknowledgement settings.
- Explicitly configure durable broker queues/messages and publisher confirmations.
  A task's database record remains authoritative even if broker delivery must be
  reconstructed; persistence defaults alone are not a recovery design.
- Keep worker-loss redelivery bounded by the application attempt policy so a
  crashing task cannot circulate forever.
- Give external calls explicit timeouts. Celery hard time limits are a last-resort
  safety boundary, not a substitute for cooperative deadlines and cleanup.
- Use a separate heartbeat mechanism that is not blocked by the task's main
  function. Checkpoint large work into resumable units where practical.

**Failure labs:**

- Kill a worker during a task, including with `SIGKILL`.
- Deliver the same execution request twice.
- Stop/restart the broker and database separately.
- Crash the dispatcher after publish but before recording dispatch success.
- Let a lease expire, then let the old worker return.
- Simulate provider acceptance followed by loss of the client response.

**Exit:** accepted work has an explainable eventual state; no silent disappearance
or stale-worker overwrite. Demonstrate limitations of external exactly-once
effects. This is the first durable MVP.

### Stage 3 — Notebook-to-worker development loop

**Learn:** the boundary between a function, a task definition, and deployed code.

- Build the small SDK/decorator, explicit context, schema generation, inline
  harness, catalog registration, and development worker module-loading workflow.
- Provide one notebook that develops, tests, registers, and submits a candidate
  function before Git commit, then promotes it into the package.
- Ensure draft/runnable status and implementation versions are visible in the API.
- Add tests proving notebook inline and worker execution share validation,
  output, progress, and error contracts.
- Reject registrations or submissions referencing missing/incompatible worker
  implementation artifacts/routes; never silently run whatever “latest” code
  happens to exist. Do not require a live worker heartbeat to accept valid work
  when the configured policy allows waiting for capacity.

**Exit:** a new typed function becomes an API-discoverable, submit-ready task
without writing a new HTTP endpoint, once its implementation is actually loaded.
Restarting the notebook does not invalidate already deployed worker versions.

### Stage 4 — Application examples and long-running workloads

**Learn:** long-running I/O, reproducibility, rate limits, and sensitive artifacts.

- Keep document processing as an example package, not a required core dependency.
  Demonstrate a structured-data calculation or date-based report alongside a
  file-based task. Transcription and prompt-based document analysis remain useful
  examples of provider-backed, long-running work.
- Introduce optional artifact storage and provider adapters here; small typed
  arguments/results should continue to work without file storage.
- Keep fake/offline modes for local tests; live provider access is opt-in.
- Preserve prompt/template version, provider/model configuration, input hash,
  external operation IDs, and output schema. Do not claim model determinism.
- Validate document types and sizes; treat uploaded content as untrusted. Bound
  parsers, downloads, and output sizes, and isolate risky parsing where needed.
- Implement bounded retries, provider-level rate/concurrency controls, and cost
  telemetry. Worker count alone cannot enforce a shared provider rate limit.
- If the provider already offers durable async jobs, persist its operation ID and
  poll/resume it rather than holding a worker slot unnecessarily.
- Split or checkpoint lengthy processing around real recovery boundaries.

**Exit:** scalar/date, structured-data, and file-based tasks use the same platform
envelope, recover under controlled failures, and retain enough metadata to explain
their results and any external costs.

### Stage 5 — Operator UI and observability

**Learn:** the difference between business status and infrastructure telemetry.

- Start with a simple UI over the API: counts by state/type, task list/detail,
  attempt/event timeline, progress, artifact links, and authorized retry/cancel.
- Show active worker replicas/process slots separately, capabilities, heartbeat
  age, busy slots, queue age/depth, and retry/failure trends.
- Show queue-to-task routes and group/instance subscriptions. Distinguish desired
  group capacity from live instances, including queues with no current consumers.
- Mark stale/unknown telemetry explicitly. An empty broker queue does not mean
  all work is complete, and a running container does not prove a healthy worker.
- Use structured logs and correlation IDs for task, attempt, and provider operation.
- Add Flower as a development/operator supplement, not the product's source of
  truth. Keep Flower and broker dashboards authenticated and non-public.
- Start with polling; add streaming updates only if justified.

**Exit:** an operator can explain why a task is waiting or failing, see available
capacity, and perform safe recovery without database edits.

### Stage 6 — First Azure deployment, fixed capacity

**Learn:** what transfers unchanged and what cloud deployment changes.

- Complete the Azure foundations labs first. Build this deployment incrementally:
  storage/identity, API, database, broker, then worker/control processes. Verify
  and explain each dependency before adding the next.
- Use infrastructure as code, preferably Bicep initially, with a cost estimate
  and a reliable teardown procedure. This is now automation of resources already
  introduced, not an unexplained template to copy and run.
- Deploy API and worker as separate Azure Container Apps using the same tested
  application image with different startup commands.
- Build the image from a Dockerfile and push it to the registry. Bind each worker
  group to a worker app/deployment and configure its queue subscriptions; group
  registration alone does not deploy anything. Reuse the image across groups.
- Apply the cloud configuration overlay and use isolated cloud broker resources.
  Keep `cpu` enabled and `gpu` disabled for this first deployment; GPU availability,
  region/quota, runtime support, and cost are a separate extension decision.
- Select Azure Database for PostgreSQL, Blob Storage, Azure Container Registry,
  a broker meeting the Stage 0 operational decision, and Azure Monitor /
  Log Analytics. Provision control processes explicitly; they are not notebook jobs.
- Start with one worker replica, conservative concurrency, and no public worker
  ingress. Prove connectivity and recovery before autoscaling.
- Use managed identity and least privilege where supported, scoped access to
  artifacts, and secure secrets for services that still need credentials.
- Authenticate API/UI, authorize task/artifact access, restrict registry writes,
  redact logs, and establish retention/deletion procedures before real org data.
- Test image pull, migrations, DNS/TLS, network boundaries, worker rollout/shutdown,
  broker disconnects, and service restarts with Azure smoke/failure tests.

**Exit:** the same SDK and task contracts work against local and Azure
environments, without notebook credentials or local filesystem assumptions.
Long tasks recover when a replica disappears; they do not depend on an
uninterruptible container.

### Stage 7 — Scale, rollout, and operational readiness

**Learn:** elasticity without breaking durability or overwhelming providers.

- Test broker-based Container Apps scaling with the chosen broker and credentials.
  Set replica bounds and application-level concurrency/rate limits.
- Combine backlog age, task-duration distribution, running work, and provider
  limits when evaluating capacity; broker queue length alone is insufficient.
- Separate CPU-heavy, long-running, and short I/O tasks only when measurements
  justify it. Test fair scheduling and starvation.
- Handle scale-in and rolling deployments as ordinary interruptions. Retain old
  implementation versions until their pinned tasks finish or are explicitly
  migrated; do not strand pending tasks during upgrades.
- Measure latency, throughput, recovery time, memory, retry cost, and spend.
- Exercise database/broker backups and restore, retention, stuck-task alerts,
  incident runbooks, and poison-task handling.

**Exit:** documented operating limits, tested recovery, upgrade/rollback procedure,
and a cost envelope. Do not equate this milestone with unlimited organizational
production readiness.

### Stage 8 — Optional extensions, chosen from evidence

- Multi-step workflows: extraction -> analysis -> review -> export.
- Human approval and long waits, callbacks, timers, and compensation.
- Per-team quotas, fairness, stronger tenant isolation, or GPU worker classes.
- Azure Container Apps Jobs for suitable finite batch executions.
- A dedicated durable workflow engine if the workflow, not just individual task
  execution, becomes the central problem.

Do not build a homegrown DAG engine by accumulating ad hoc Celery chains and
database flags. Revisit Temporal or Azure Durable Functions when workflows need
durable orchestration; assess local development and Python ergonomics separately.

## Local-to-Azure mapping

| Local | Azure | Parity boundary |
| --- | --- | --- |
| Compose API/worker images | Container Apps | Same code; different identity, networking, lifecycle, scaling. |
| PostgreSQL container | Azure Database for PostgreSQL | Same migrations; verify extensions, roles, connections, backup/restore. |
| RabbitMQ container | Approved hosted RabbitMQ deployment/service | Same protocol; explicitly verify persistence, confirmations, ack timeout, TLS, limits, and recovery. |
| Azurite | Blob Storage | Same SDK contract subset; cloud identity/features/limits need integration tests. |
| Development environment variables | Managed identity plus secure configuration/secrets | No production secrets in notebooks, images, or Git. |
| Local logs and Flower | Centralized logs/metrics plus product UI | Telemetry is separate from authoritative business state. |

## Decisions to defer, and their triggers

| Decision | Default now | Revisit when |
| --- | --- | --- |
| RabbitMQ vs Redis vs Service Bus | RabbitMQ, subject to hosted feasibility | Managed-service constraints or operational cost invalidate the default. |
| Celery vs workflow engine | Celery for independent tasks | Multi-step recovery, long waits, human approval, or compensation dominate. |
| Worker apps vs Container Apps Jobs | Continuously running Celery workers | Independent finite jobs need stronger per-execution isolation/resource allocation. |
| Dynamic production code registration | Approved packaged implementations only | A separately secured code-build/execution service is explicitly required. |
| Task duration | Bounded tasks, resumable checkpoints | Actual workload measurements establish necessary duration/resource classes. |
| Frontend framework | Small API-backed UI | Monitoring requirements justify more frontend complexity. |

## Suggested first delivery

Begin with Stages 0–2 and a minimal notebook example, not the Azure deployment.
The first useful demo should:

1. Start locally with Compose.
2. Register numeric and date-based task definitions, plus a slow recovery example.
3. Submit through the API and receive a task ID immediately.
4. Kill the worker mid-task.
5. Recover through a visible new attempt with an inspectable result.
6. Show the task history and current worker health.

This validates the difficult platform assumptions before paying for cloud
infrastructure or building a polished dashboard.

## Open questions before implementation

1. Typical and worst-case runtime: minutes, hours, or multi-day provider jobs?
2. Daily volume/bursts and largest arguments/results, including files if needed?
3. Which initial real-world task types and external services matter? For async
   providers, do they expose resumable operation IDs?
4. Is development individual, shared within a trusted team, or multi-tenant?
5. Which compliance, network isolation, retention, and Azure-region constraints?
6. Is managed RabbitMQ acceptable, or is using only Azure-native managed services
   a requirement?
7. Is registration of trusted developer code sufficient, or must non-developers
   upload arbitrary code? The latter is a substantially different security scope.
8. Is the first priority a teaching course, an internal pilot, or both? Course
   checkpoints should remain small even if the eventual pilot needs more controls.

## Research notes

Official documentation checked for this proposal on 13 November 2026. Pin versions
and recheck behavior when implementing the labs.

- [Celery task semantics](https://docs.celeryq.dev/en/stable/userguide/tasks.html)
  and [configuration](https://docs.celeryq.dev/en/stable/userguide/configuration.html):
  late acknowledgement requires idempotency; worker child-process death can still
  be acknowledged unless configured otherwise. `task_reject_on_worker_lost` can
  cause redelivery loops. Ordinary exceptions need an explicit retry policy.
- [Celery optimization](https://docs.celeryq.dev/en/stable/userguide/optimizing.html):
  start long-running work with `worker_prefetch_multiplier=1` and explicit worker
  concurrency. Measure rather than assuming that this is optimal for every task.
- [Celery Redis transport](https://docs.celeryq.dev/en/stable/getting-started/backends-and-brokers/redis.html):
  visibility timeout can redeliver a still-running task; increasing it also
  delays recovery after failure. This is a material long-task broker trade-off.
- [RabbitMQ consumers](https://www.rabbitmq.com/docs/consumers):
  acknowledgement timeout must accommodate task duration. The documented default
  is 30 minutes; enforcement depends on RabbitMQ version and queue type, including
  the documented RabbitMQ 4.3 quorum-queue distinction. Pin and test both.
- [Kombu Azure Service Bus transport](https://docs.celeryq.dev/projects/kombu/en/v5.7.0/reference/kombu.transport.azureservicebus.html):
  a transport exists, but several features are marked unreviewed and SDK shutdown
  caveats are documented. Azure-native managed messaging is attractive for a
  beginner, but this combination needs a focused compatibility/recovery spike
  before replacing the broker recommendation.
- [Container Apps lifecycle](https://learn.microsoft.com/en-us/azure/container-apps/application-lifecycle-management):
  documented default termination sends `SIGTERM`, followed by `SIGKILL` after
  30 seconds if still running. Hours-long work cannot rely on graceful shutdown
  alone. Check current configurable behavior, but retain interruption recovery.
- [Container Apps Jobs](https://learn.microsoft.com/en-us/azure/container-apps/jobs):
  continuously running consumers fit apps; finite trigger-driven executions fit
  jobs. Job retry/timeout semantics do not replace the platform's task contract.
- [Container Apps scaling](https://learn.microsoft.com/en-us/azure/container-apps/scale-app):
  custom event scaling is available. Validate RabbitMQ scaler support and
  credentials with the actual deployment; do not assume Celery broker support
  proves platform autoscaling support.
- [Azurite scope and differences](https://learn.microsoft.com/en-us/azure/storage/common/storage-use-azurite):
  useful for local storage API tests, but not complete feature, identity, or
  performance parity with Azure. Keep real-storage integration tests small and
  explicit.
