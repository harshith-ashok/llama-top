# AI Infrastructure Observability & Control Dashboard

## Feature and Tool Specification

A unified dashboard for monitoring, managing, and optimizing local and
remote AI inference infrastructure across Ollama, OpenAI-compatible
APIs, and cloud model providers.

The platform is divided into four primary areas:

1.  Host Environment
2.  Ollama & Inference Sources
3.  Multi-Source Control
4.  Analytics & Observability

------------------------------------------------------------------------

# 1. Host Environment

Metrics collected from the machine running an inference server or source
agent.

  -----------------------------------------------------------------------
  Feature                 Metrics / Information   Recommended Tools
  ----------------------- ----------------------- -----------------------
  CPU Monitoring          Usage, per-core usage,  `psutil`, OS utilities
                          core count, frequency,  
                          load average            

  Memory Monitoring       Total, used, available  `psutil`
                          RAM, memory pressure,   
                          swap usage              

  GPU Monitoring          GPU utilization,        NVIDIA NVML / `pynvml`,
                          temperature, power      vendor tools
                          draw, clock speeds      

  VRAM Monitoring         Total, used, free VRAM, NVIDIA NVML / `pynvml`
                          memory utilization      

  GPU Process Monitoring  Processes using GPU,    NVML, `nvidia-smi`
                          per-process VRAM where  
                          supported               

  Disk Monitoring         Capacity, used space,   `psutil`, OS utilities
                          free space, mount       
                          points                  

  Disk I/O                Read/write throughput,  `psutil`, OS utilities
                          IOPS, I/O time          

  Network Monitoring      Upload/download         `psutil`
                          throughput, interface   
                          traffic, packet counts  

  Process Monitoring      Running processes, PID, `psutil`
                          CPU and memory usage    

  System Information      OS, kernel,             `platform`, `psutil`
                          architecture, hostname, 
                          uptime                  

  Hardware Inventory      CPU model, RAM          `psutil`, OS utilities
                          capacity, GPU model,    
                          storage devices         

  Power Monitoring        GPU power draw and      NVML, vendor tools
                          energy consumption      
                          where exposed           

  Temperature Monitoring  CPU, GPU, disk and      NVML, `lm-sensors`
                          system temperatures     
                          where exposed           

  Host Availability       Online status, uptime,  Lightweight host agent
                          heartbeat, last-seen    
                          time                    

  Service Monitoring      Inference service       Agent, systemd, Windows
                          status, process state,  services
                          restart count           

  Docker Monitoring       Container status, CPU,  Docker Engine API /
                          memory, network and     Docker SDK
                          restart count           
  -----------------------------------------------------------------------

## Host Monitoring Tools

-   **psutil** --- CPU, memory, disk, network and process metrics.
-   **NVIDIA NVML / pynvml** --- NVIDIA GPU utilization, VRAM,
    temperature, power and clocks.
-   **nvidia-smi** --- NVIDIA GPU diagnostics and process information.
-   **lm-sensors** --- Linux hardware temperature and voltage sensors.
-   **Docker Engine API / Docker SDK** --- Container status and resource
    metrics.
-   **Prometheus** --- Metrics collection and time-series monitoring.
-   **OpenTelemetry** --- Instrumentation and distributed tracing.
-   **Custom host agent** --- Collects metrics and sends them to the
    central dashboard.

Note: GPU and temperature metrics depend on hardware, drivers, operating
system and permissions. Use capability detection rather than assuming
every metric is available.

------------------------------------------------------------------------

# 2. Ollama & Inference Sources

Information collected from Ollama APIs, compatible provider APIs,
streaming responses and optional proxy instrumentation.

## 2.1 Ollama API Information

  -----------------------------------------------------------------------
  Feature                 Metrics / Information   Source
  ----------------------- ----------------------- -----------------------
  Model Inventory         Installed models, tags, `/api/tags`
                          sizes, digests,         
                          modification times      

  Loaded Models           Currently loaded        `/api/ps`
                          models, memory          
                          allocation where        
                          reported, expiry        
                          information             

  Model Details           Architecture, parameter `/api/show`
                          size, quantization,     
                          template, parameters,   
                          model metadata          

  Ollama Version          Installed server        `/api/version`
                          version                 

  Chat Inference          Chat request and        `/api/chat`
                          response information    

  Text Generation         Generation request and  `/api/generate`
                          response information    

  Embeddings              Embedding requests and  `/api/embed`
                          returned vector         
                          dimensions              

  Model Lifecycle         Model load/unload state `/api/ps` polling and
                          and changes             request events
  -----------------------------------------------------------------------

## 2.2 Request & Token Analytics

  ------------------------------------------------------------------------
  Feature                 Metrics / Information   Source
  ----------------------- ----------------------- ------------------------
  Request Monitoring      Request ID, model,      API interception / proxy
                          endpoint, timestamp,    
                          status                  

  Prompt Tokens           Input token count       `prompt_eval_count` or
                                                  provider usage

  Completion Tokens       Generated token count   `eval_count` or provider
                                                  usage

  Total Tokens            Input plus output       Derived
                          tokens                  

  Cached Tokens           Cached input tokens     Provider usage
                          where provider reports  
                          them                    

  Reasoning Tokens        Reasoning token count   Provider usage
                          where provider reports  
                          them                    

  Generation Speed        Output tokens per       `eval_count`,
                          second                  `eval_duration`

  Prompt Processing Speed Input tokens per second `prompt_eval_count`,
                                                  `prompt_eval_duration`

  Time to First Token     Time until first        Streaming interception
                          streamed output token   

  Prompt Evaluation Time  Time spent processing   `prompt_eval_duration`
                          prompt                  

  Generation Duration     Time spent generating   `eval_duration`
                          output                  

  Model Load Duration     Time spent loading the  `load_duration`
                          model                   

  Total Inference         Total server-reported   `total_duration`
  Duration                request duration        

  End-to-End Latency      Full client-observed    Proxy / SDK
                          request duration        

  Streaming Analytics     Chunks, inter-token     Streaming interception
                          timing, output rate,    
                          completion time         

  Request Parameters      Temperature, top-p,     Request interception
                          seed, output limit and  
                          other parameters        

  Finish Reason           Stop, length, tool call Provider response
                          or provider-specific    
                          reason                  

  Error Analytics         HTTP status, provider   API interception
                          errors, failed requests 
                          and retries             

  Concurrency             Active requests and     Proxy / server metrics
                          concurrent streams      

  Queueing                Waiting requests and    Server instrumentation
                          queue duration where    
                          exposed                 
  ------------------------------------------------------------------------

Ollama response fields commonly useful for timing and token analytics
include:

-   `prompt_eval_count`
-   `eval_count`
-   `prompt_eval_duration`
-   `eval_duration`
-   `load_duration`
-   `total_duration`

For Ollama durations expressed in nanoseconds:

`generation_tokens_per_second = eval_count / (eval_duration / 1_000_000_000)`

`prompt_tokens_per_second = prompt_eval_count / (prompt_eval_duration / 1_000_000_000)`

Do not assume all providers expose equivalent fields. Normalize what is
available and retain the original provider response.

## 2.3 Context Analytics

  -------------------------------------------------------------------------
  Feature                 Metrics / Information   Collection Method
  ----------------------- ----------------------- -------------------------
  Context Window Size     Maximum context length  Model metadata registry
                          supported/configured    and provider metadata
                          for a model             

  Current Prompt Size     Tokens in the submitted Provider usage or
                          prompt                  tokenizer

  Context Utilization     Prompt tokens divided   Derived
                          by configured context   
                          limit                   

  Estimated Remaining     Configured context      Derived
  Context                 limit minus current     
                          prompt tokens           

  Conversation Growth     Prompt token growth     Session tracking
                          across turns            

  Average Context Size    Average prompt tokens   Derived
                          per request/session     

  Context Limit Warnings  Requests approaching    Derived
                          configured limit        

  Context Overflow Events Requests exceeding      Errors and token tracking
                          known context           
                          constraints             

  Truncation Events       History or prompt       Client/proxy
                          truncation where        instrumentation
                          detectable              

  System Prompt Overhead  Tokens attributed to    Optional prompt
                          system instructions     inspection/tokenization

  Tool Definition         Tokens attributed to    Optional request
  Overhead                tool schemas and        inspection
                          definitions             

  Tool Result Overhead    Tokens attributed to    Optional request
                          tool outputs            inspection
  -------------------------------------------------------------------------

Important: Context utilization is an estimate unless the provider
reports authoritative context information. Track the actual serialized
request when possible, including system prompts, conversation history,
tool definitions and tool results. Distinguish model maximum context
from the context limit configured for a particular request.

## 2.4 Model Inventory & Capabilities

Track these fields for every model:

-   Provider and source
-   Model name, tag and digest/version
-   Model family and architecture
-   Parameter count
-   Quantization level
-   Model format
-   Context length, with source and confidence
-   Model size on disk
-   Embedding dimensions, where applicable
-   Vision capability
-   Tool-calling capability
-   Structured output support
-   Embedding support
-   Currently loaded status
-   Last used timestamp
-   Source-specific capabilities and limitations

------------------------------------------------------------------------

# 3. Multi-Source Control

A central control plane for multiple local machines, remote inference
servers and cloud providers.

## 3.1 Supported Source Types

  -----------------------------------------------------------------------
  Source Type             Examples                Intended Capabilities
  ----------------------- ----------------------- -----------------------
  Local Ollama            macOS, Linux, Windows   Monitor and manage
                                                  models

  Remote Ollama           LAN, Tailscale, VPS     Remote monitoring and
                                                  model management

  OpenAI-Compatible       vLLM, LM Studio, oMLX,  Usage monitoring and
  Servers                 llama.cpp server        supported API
                                                  operations

  Cloud API Providers     OpenAI, OpenRouter and  Usage, latency, cost
                          other providers         and model availability

  Custom Endpoints        Custom                  Configurable
                          OpenAI-compatible APIs  integration and
                                                  monitoring
  -----------------------------------------------------------------------

Support should be adapter-based. An OpenAI-compatible endpoint does not
automatically support model management, server metrics or lifecycle
operations.

## 3.2 Source Registry

  -----------------------------------------------------------------------
  Feature                             Description
  ----------------------------------- -----------------------------------
  Add Source                          Register a local, remote or cloud
                                      source

  Edit Source                         Update name, endpoint and
                                      configuration

  Remove Source                       Remove a source from the dashboard

  Connect / Disconnect                Manage connection state

  Health Check                        Test endpoint availability

  Connection Status                   Online, offline, degraded or
                                      unknown

  Authentication                      Configure API keys or supported
                                      authentication

  Endpoint Configuration              Configure base URL and API path

  Source Metadata                     Hostname, OS, server version and
                                      source type

  Last Seen                           Last successful communication

  Connection Latency                  Time taken to reach the source

  Capability Detection                Identify supported monitoring and
                                      control operations

  Tags and Groups                     Organize sources by machine,
                                      environment or purpose
  -----------------------------------------------------------------------

## 3.3 Remote Source Management

  Feature                    Description
  -------------------------- ---------------------------------------------
  Restart Service            Restart supported inference services
  Stop Service               Stop a supported service
  Start Service              Start a supported service
  View Logs                  Inspect service logs where available
  Update Server              Update supported inference runtimes
  Service Status             View service state and uptime
  Host Diagnostics           View source health and resource information
  Configuration Management   View or change supported server settings
  Remote Agent Updates       Manage the dashboard's host agent

Remote service control should use an authenticated host agent with
explicit permissions. Avoid exposing arbitrary shell execution through
the dashboard.

## 3.4 Cross-Source Model Management

  -----------------------------------------------------------------------
  Feature                             Description
  ----------------------------------- -----------------------------------
  Global Model Inventory              See models installed across all
                                      sources

  Search Models                       Search by name, provider, family or
                                      capability

  Pull / Download Model               Download a model to a selected
                                      compatible source

  Delete Model                        Remove a model from a source

  Load Model                          Load a model into memory where
                                      supported

  Unload Model                        Release model resources where
                                      supported

  Model Details                       Compare metadata and configuration

  Duplicate Detection                 Identify repeated model
                                      installations

  Version Comparison                  Compare tags, digests and
                                      configurations

  Model Placement                     Identify sources with sufficient
                                      resources

  Default Model                       Configure a preferred model per
                                      source or use case

  Model Availability                  Identify where a model is currently
                                      available

  Model Lifecycle History             Track pulls, loads, unloads and
                                      deletions
  -----------------------------------------------------------------------

Use a unified model identity while retaining source-specific tags,
digests, quantizations and configuration. Identically named models on
different machines may not be equivalent.

## 3.5 Unified Inference Routing

Optional gateway functionality for routing requests across sources.

  -----------------------------------------------------------------------
  Feature                             Description
  ----------------------------------- -----------------------------------
  Manual Routing                      Choose a provider and model
                                      explicitly

  Priority Routing                    Prefer configured providers in
                                      order

  Failover                            Use another provider when the
                                      primary fails

  Lowest Latency                      Route using observed latency

  Lowest Cost                         Route using configured pricing

  Context-Aware Routing               Select a model with sufficient
                                      context capacity

  Resource-Aware Routing              Consider available memory and
                                      hardware

  Capability-Based Routing            Select models supporting vision,
                                      tools or embeddings

  Round-Robin                         Distribute requests across
                                      configured sources

  Load-Aware Routing                  Consider active requests and source
                                      utilization

  Routing Rules                       Define application, model and
                                      task-based policies

  Routing Analytics                   Track routing decisions, fallback
                                      and provider distribution
  -----------------------------------------------------------------------

Routing requires a gateway or client integration. A monitoring dashboard
alone cannot transparently redirect requests made directly to provider
endpoints.

------------------------------------------------------------------------

# 4. OpenAI-Compatible Provider Analytics

Normalize usage and request information across providers.

  Feature               Information
  --------------------- --------------------------------------------------------
  Provider Inventory    Configured providers and endpoints
  Model Availability    Models exposed by each provider
  Input Usage           Prompt/input tokens
  Output Usage          Completion/output tokens
  Cached Usage          Cached input tokens where reported
  Reasoning Usage       Reasoning tokens where reported
  Request Latency       Client-observed end-to-end latency
  Time to First Token   Streaming response start time
  Throughput            Output tokens per second
  Provider Errors       Failed requests and error categories
  Rate Limits           Rate-limit responses and remaining quota where exposed
  Retry Analytics       Retry counts and retry outcomes
  Provider Health       Availability and response health
  Pricing               Configured input/output/cached token rates
  Cost Analytics        Estimated request and aggregate cost

Potential integrations:

-   Ollama
-   OpenAI
-   OpenRouter
-   vLLM
-   LM Studio
-   llama.cpp server
-   oMLX
-   LiteLLM
-   Other OpenAI-compatible endpoints

------------------------------------------------------------------------

# 5. Analytics & Derived Metrics

These metrics are calculated from collected host, provider and request
telemetry.

## 5.1 Usage Analytics

  Feature                    Information
  -------------------------- ----------------------------------------------
  Total Requests             Requests across all sources
  Requests per Model         Model-level request volume
  Requests per Provider      Provider-level request volume
  Requests per Source        Host/server request volume
  Input Token Trends         Hourly, daily and monthly input usage
  Output Token Trends        Hourly, daily and monthly output usage
  Total Token Trends         Combined token consumption
  Model Usage Distribution   Most-used models
  Provider Distribution      Usage share per provider
  Application Attribution    Usage by connected application
  Session Analytics          Requests, turns and tokens per conversation
  Peak Usage                 Highest request and token throughput periods

## 5.2 Performance Analytics

  Feature                           Information
  --------------------------------- ---------------------------------------------
  Model Comparison                  Compare speed, latency and usage
  Average Generation Speed          Average output tokens/sec
  Average Prompt Processing Speed   Average input tokens/sec
  Average Time to First Token       Streaming responsiveness
  Average Request Latency           End-to-end response time
  Performance Trends                Historical model performance
  Resource Correlation              GPU/VRAM utilization against inference
  Model Efficiency                  Throughput relative to resource consumption
  Model Availability                Loaded and available time
  Error Rate                        Failed requests divided by total requests
  Benchmark History                 Results from repeatable model tests

## 5.3 Cost Analytics

  -----------------------------------------------------------------------
  Feature                             Information
  ----------------------------------- -----------------------------------
  Input Token Cost                    Cost of input tokens

  Output Token Cost                   Cost of generated tokens

  Cached Token Cost                   Cached input pricing where
                                      applicable

  Reasoning Token Cost                Reasoning usage pricing where
                                      applicable

  Cost per Request                    Estimated request cost

  Cost per Model                      Aggregate model cost

  Cost per Provider                   Aggregate provider cost

  Daily / Monthly Spend               Spending trends

  Cost per Million Tokens             Normalized model/provider
                                      comparison

  Local Energy Estimate               Estimated electricity cost for
                                      local inference
  -----------------------------------------------------------------------

Local inference energy estimates should be based on measured power and
configured electricity rates. Keep estimated local operating costs
separate from provider billing.

## 5.4 Session & Application Analytics

  -----------------------------------------------------------------------
  Feature                             Information
  ----------------------------------- -----------------------------------
  Session Length                      Number of requests or turns

  Tokens per Session                  Aggregate session token usage

  Average Conversation Size           Average prompt and output tokens

  Model Switching                     Models used within a session

  Application Usage                   Requests attributed to an
                                      application

  Tool Usage                          Tool calls and tool-related token
                                      overhead where captured

  Failed Tool Calls                   Tool execution failures where
                                      instrumented

  Expensive Sessions                  Sessions with highest token usage
                                      or cost

  Long-Running Requests               Requests exceeding latency
                                      thresholds
  -----------------------------------------------------------------------

Application attribution requires request metadata from a proxy, SDK,
client integration or explicit application identifier. It cannot
reliably be inferred from a provider API response alone.

------------------------------------------------------------------------

# 6. Request Inspection & Debugging

  -----------------------------------------------------------------------
  Feature                             Information
  ----------------------------------- -----------------------------------
  Request Explorer                    Search and filter individual
                                      requests

  Request ID                          Unique request identifier

  Trace ID                            Distributed trace identifier

  Session ID                          Conversation identifier

  Provider and Model                  Source and model used

  Endpoint                            API endpoint called

  Timestamp                           Request start and completion

  Request Parameters                  Sampling and generation
                                      configuration

  Input / Output Tokens               Token usage

  Finish Reason                       Completion reason

  HTTP Status                         Request result

  Error Details                       Provider error information

  Retry History                       Retry attempts and outcomes

  Streaming Timeline                  First token, chunks and completion
                                      timing

  Prompt Inspection                   Optional inspection of submitted
                                      prompts

  Response Inspection                 Optional inspection of generated
                                      responses

  Tool Call Inspection                Tool names, arguments and results
                                      where captured
  -----------------------------------------------------------------------

Content capture should be opt-in, with redaction, access controls and
configurable retention. Metadata-only collection should be the default.

------------------------------------------------------------------------

# 7. Alerts & Automation

  Feature                   Trigger
  ------------------------- -------------------------------------------------
  Host Offline              Host agent stops reporting
  Provider Offline          Endpoint health check fails
  GPU Memory Warning        VRAM exceeds configured threshold
  RAM Warning               Memory usage exceeds threshold
  GPU Temperature Warning   Temperature exceeds threshold
  High Latency              Request latency exceeds threshold
  Low Generation Speed      Throughput falls below threshold
  Context Warning           Context utilization approaches configured limit
  Context Overflow          Known context limit is exceeded
  API Spending Warning      Cost exceeds configured budget
  Error Rate Warning        Provider or model failures increase
  Model Unloaded            Expected model is no longer loaded
  Disk Space Warning        Model storage approaches capacity
  Rate Limit Warning        Provider rate limit is reached

Possible delivery methods: dashboard notifications, email, webhooks,
Discord or other integrations.

------------------------------------------------------------------------

# 8. Suggested Dashboard Navigation

``` text
Overview

HOST ENVIRONMENT
├── CPU & Memory
├── GPU & VRAM
├── Storage & Network
├── Processes
├── System Information
└── Containers & Services

SOURCES
├── All Sources
├── Local Sources
├── Remote Sources
├── Cloud Providers
├── Source Details
└── Connection Health

OLLAMA & MODELS
├── Model Inventory
├── Loaded Models
├── Model Details
├── Model Lifecycle
└── Model Management

INFERENCE
├── Live Requests
├── Request Explorer
├── Streaming Monitor
├── Context & Tokens
└── Sessions

CONTROL PLANE
├── Source Management
├── Model Management
├── Service Control
├── Routing Rules
└── Provider Configuration

ANALYTICS
├── Usage Analytics
├── Model Comparison
├── Provider Comparison
├── Performance Trends
├── Cost Analytics
└── Benchmarks

SYSTEM
├── Alerts
├── Notifications
├── Agent Management
├── API Keys & Security
└── Settings
```

------------------------------------------------------------------------

# 9. Recommended Technology Stack

  Component               Recommended Technology            Purpose
  ----------------------- --------------------------------- ---------------------------------------------
  Backend                 FastAPI                           API and orchestration
  Frontend                React + TypeScript                Dashboard
  Styling                 Tailwind CSS v4                   UI
  Charts                  Apache ECharts                    Analytics and time-series charts
  Database                PostgreSQL                        Sources, models, requests and configuration
  Time-Series             TimescaleDB                       Historical metrics
  Cache / Live State      Redis                             Caching and live status
  Host Agent              Python                            Host metrics and remote control
  GPU Monitoring          NVML / pynvml                     NVIDIA telemetry
  System Monitoring       psutil                            Host telemetry
  Metrics Collection      Prometheus                        Infrastructure metrics
  Request Tracing         OpenTelemetry                     Distributed tracing
  Live Updates            WebSockets / Server-Sent Events   Dashboard updates
  Container Integration   Docker SDK                        Container management

Suggested reference projects:

-   [Ollama API
    documentation](https://github.com/ollama/ollama/blob/main/docs/api.md)
-   [LiteLLM](https://github.com/BerriAI/litellm)
-   [Langfuse](https://github.com/langfuse/langfuse)
-   [Prometheus](https://prometheus.io/)
-   [OpenTelemetry](https://opentelemetry.io/)
-   [Grafana](https://grafana.com/)

------------------------------------------------------------------------

# 10. Implementation Priorities

## Phase 1 --- Core Monitoring

-   [x] Multi-source registry
-   [x] Ollama integration
-   [x] OpenAI-compatible provider integration
-   [x] Host monitoring agent
-   [x] CPU and RAM metrics
-   [ ] GPU and VRAM metrics (implemented via NVML, not yet verified on real hardware)
-   [x] Model inventory
-   [x] Request tracking
-   [x] Input/output token analytics
-   [x] Latency and generation speed
-   [x] Historical metrics

## Phase 2 --- Control Plane

-   [ ] Remote source health checks
-   [ ] Cross-source model inventory
-   [ ] Pull and delete models
-   [ ] Load and unload models
-   [ ] Service status and logs
-   [ ] Source capability detection
-   [ ] Remote agent management
-   [ ] Model lifecycle history

## Phase 3 --- Advanced Observability

-   [ ] Context utilization
-   [ ] Session analytics
-   [ ] Application-level attribution
-   [ ] Streaming metrics
-   [ ] Request inspection
-   [ ] Model comparison
-   [ ] Provider comparison
-   [ ] Cost analytics
-   [ ] Alerts and notifications

## Phase 4 --- Intelligent Control

-   [ ] Unified inference gateway
-   [ ] Provider routing
-   [ ] Automatic failover
-   [ ] Resource-aware routing
-   [ ] Context-aware routing
-   [ ] Cost-aware routing
-   [ ] Model placement recommendations
-   [ ] Automated model management

------------------------------------------------------------------------

# 11. Important Architecture Decisions

1.  **Use provider adapters.** Each provider should implement a common
    interface for health, model listing, inference usage and supported
    control operations.

2.  **Use capability-based controls.** A provider should declare whether
    it supports model listing, loading, unloading, service control,
    usage reporting and hardware telemetry. Do not assume
    OpenAI-compatible means full administrative control.

3.  **Separate monitoring from control.** Monitoring can be read-only.
    Destructive or privileged operations should require explicit
    authorization.

4.  **Use a lightweight host agent.** Run one agent per machine to
    collect system metrics and perform explicitly permitted local
    operations. The central dashboard should not need unrestricted SSH
    or shell access.

5.  **Normalize but preserve raw data.** Store normalized metrics for
    cross-provider comparisons and retain raw provider usage/response
    metadata for future compatibility.

6.  **Distinguish observed and estimated metrics.** Label
    provider-reported values, locally measured values and derived
    estimates separately.

7.  **Make telemetry privacy-conscious.** Collect metadata by default.
    Make prompt/response capture optional and support redaction and
    retention policies.

8.  **Support remote connectivity securely.** Use authenticated
    connections, TLS, scoped credentials and network controls. Avoid
    exposing inference servers or privileged agents directly to the
    public internet.

9.  **Avoid double-counting.** If a request is observed by both a
    gateway and a provider adapter, correlate it using request/trace IDs
    and count it once in aggregate usage.

10. **Keep the core useful without routing.** Users should be able to
    monitor and manage sources without adopting the platform as their
    inference gateway.

------------------------------------------------------------------------

# 12. Product Positioning

**An open-source control plane for AI inference infrastructure.**

A unified place to monitor, manage, compare and optimize local and
remote inference servers, models and API providers.

The core differentiators to pursue:

-   Multi-host inference management
-   Multi-provider observability
-   Cross-source model lifecycle management
-   Context and token analytics
-   GPU-aware performance monitoring
-   Application-level usage attribution
-   Infrastructure-aware inference routing

The initial target audience should be developers, local AI enthusiasts,
homelab operators and small teams operating multiple inference sources.

**Recommended MVP:** Multi-source registry + host agent +
Ollama/OpenAI-compatible adapters + model inventory + request/token
analytics + GPU monitoring + historical dashboard. Add remote model
control and routing after the monitoring foundation is reliable.
