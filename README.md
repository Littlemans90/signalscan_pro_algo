# SignalScan Pro Algo

SignalScan Pro is a low-latency, production-ready signal scanner for US equities. It continuously ingests market and news data, runs multiple detection and algorithmic channels in parallel, scores and deduplicates candidate signals, enriches them with contextual data, and publishes high-confidence alerts to downstream consumers (webhooks, Slack, dashboards, databases).

This README expands on what the scanner DOES and HOW it WORKS so operators, developers, and integrators can understand behavior, tune rules, and scale the system.

Contents
- What the scanner does
- High-level architecture & data flow
- Channel internals (what runs inside each channel)
- Signal aggregation, scoring and deduplication
- Enrichment, outputs and alert delivery
- Persistence, observability and operational controls
- Scaling, deployment and failure modes
- Configuration & tuning examples
- Testing & validation
- Glossary

What the scanner does (concise)
- Monitors US-listed symbols in real time for actionable events:
  - Price moves (spikes, gaps, breakouts)
  - Volume anomalies (spikes vs VWAP/rolling averages)
  - Volatility/range expansions and pattern-based signals
  - Algorithmic signals (momentum, mean-reversion, custom strategies)
  - Breaking news / sentiment events (NLP + news feed correlation)
  - Trading halts and resume events
- Produces structured signal objects with metadata, score, provenance (which channels fired), and enrichment fields
- Applies scoring, deduplication and suppression rules to avoid alert storms
- Emits alerts via configurable outputs (webhooks, Slack, email, publisher queues) and stores events for audit and backtesting

High-level architecture & data flow
1. Ingestion
   - Market data: trade/quote/tick or aggregated bars (via providers like IEX, Polygon, Tradier, or direct feeds)
   - News: structured feeds, raw RSS, APIs, and social sources
   - Exchange notices: halt/resume messages from exchange APIs or websockets

2. Preprocessing
   - Normalize symbol formats (mapping tickers and exchanges)
   - Time alignment (convert to UTC, align ticks to windows)
   - Lightweight enrichment (market session, previous close, open price)
   - Basic quality checks (bad ticks, stale data)

3. Channel processing (parallel)
   - Each channel receives the normalized stream and either:
     - Operates statelessly on each event (e.g., immediate halt messages); or
     - Maintains short-lived state for rolling windows (e.g., 1m/5m VWAP, moving averages)
   - Channels output candidate signals with channel_id and channel_score

4. Aggregation & scoring
   - Normalizer receives candidate signals and:
     - Normalizes timestamps and symbol representation
     - Applies channel-level weights and rules
     - Deduplicates correlated signals (time-window + symbol + reason heuristics)
     - Computes a final alert score and decision

5. Enrichment & output
   - Enrich alerts with additional context (fundamentals, order book snapshot, short interest, news snippets)
   - Persist signals/events to DB or object store for audit/backtest
   - Emit alert to outputs if final score >= threshold or if priority flag (e.g., halt) is set

Channel internals — what each channel typically does
- Standard detection channels (4)
  1. Price Spike Detector
     - Inputs: trade stream or minute bars
     - State: short-term baseline price (rolling median) and lookback
     - Trigger: price change > configured % over window and confirmed by volume threshold
  2. Volume Spike Detector
     - Inputs: trade sizes or aggregated volume bars
     - State: rolling average volume per interval (VWAP, moving avg)
     - Trigger: short-term volume > k * historical average (k configurable)
  3. Moving-Average / Crossover Detector
     - Inputs: bar/candles
     - State: short and long moving averages; optional smoothing
     - Trigger: crossover with minimum volume and optional confirmation window
  4. Volatility / Range Surge Detector
     - Inputs: high/low/close series
     - State: realized volatility / ATR baseline
     - Trigger: intraday range or volatility exceeds n * historical

- Algorithmic channels (3)
  1. Momentum Channel
     - Uses multi-timescale confirmation, filters on liquidity and trend
     - Assigns higher confidence when multiple windows confirm direction
  2. Mean-Reversion / Statistical Channel
     - Uses z-score, rolling sigma, or pair-deviation checks for reversion opportunities
  3. Pattern / Strategy Channel
     - Pluggable strategy engine for custom ideas (gap up/down, pre-market signals, order-flow heuristics)

- Breaking News Channel
  - Ingests headlines, article text and social snippets
  - Performs entity recognition (symbol mapping), keyword matching, and sentiment scoring
  - Correlates with recent market moves for confidence boosting (e.g., news + price move)

- Halts Channel
  - Listens to exchange stall/halt messages and marks alerts as high-priority
  - Emits immediate alerts when a symbol is halted or resumed

Signal object (recommended schema)
- symbol (string)
- timestamp (ISO8601 UTC)
- channels (list of channel_id that contributed)
- score (numeric 0-100)
- priority (enum low|medium|high|critical)
- reason (human-readable summary)
- raw_details (channel-specific fields)
- enrichments (fundamentals, latest news snippet, order-book snapshot)
- uuid (unique id for dedupe/audit)

Scoring, deduplication and decision rules
- Channel scores are normalized into a common scale (e.g., 0–100)
- Final score = weighted combination of contributing channel scores + enrichment boosts
- Deduplication strategy:
  - Time window dedupe: collapse signals for same symbol within X seconds/minutes
  - Reason hashing: hash of normalized reason + symbol to combine identical alerts
  - Channel precedence: halts or breaking-news flagged as higher priority and bypass certain suppression
- Suppression rules:
  - Configurable cool-down per symbol and per channel
  - Maximum alerts per minute/hour to avoid downstream saturation

Enrichment & outputs
- Enrichment sources (optional, best-effort):
  - Latest fundamentals, pre-market gap, short interest, sector, earnings calendar
  - Small order-book snapshot (top N levels) or liquidity metrics
- Outputs:
  - Webhook with JSON payload
  - Messaging integrations (Slack, Microsoft Teams)
  - Database / event store (Postgres, ClickHouse, or object storage)
  - Stream or queue (Kafka, RabbitMQ, SQS) for downstream consumers

Persistence & auditability
- Persist all candidate signals and final alerts with full provenance for:
  - Backtesting and model evaluation
  - Post-mortem and regulatory audits
  - Retracing missed signals or false positives

Observability & operational controls
- Metrics (expose via Prometheus):
  - Messages ingested/sec, per-channel candidate rate
  - Alerts emitted/sec, final score histogram
  - Queue lag, processing latency percentiles (p50/p95/p99)
  - Errors/exceptions per component
- Tracing:
  - Attach trace ids to messages for cross-component tracing (Jaeger/OpenTelemetry)
- Logging:
  - Structured logs with symbol, channel, score, and UUID
- Alarms:
  - High error rate, long queue lag, persistent stale input sources
- Runtime controls:
  - Dynamic thresholds and channel toggles via a control API or config store (Consul/Redis)

Scaling, latency & deployment
- Latency profile:
  - Target end-to-end latency depends on data source and location — aim for ms–100s ms for exchange feeds, seconds for API-based feeds
- Scaling strategies:
  - Shard by symbol range (partition by symbol hash), by exchange, or by channel type
  - Use worker pools per channel with bounded queues to control memory
  - Horizontal scale ingestion, channel workers, and aggregators independently
- Deployment:
  - Containerized microservices (Docker + Kubernetes suggested)
  - Use node affinites or regional placement near data providers for lower latency
  - Separate critical path (halts, breaking news) into higher-priority, low-latency lanes

Failure modes and mitigations
- Data feed outage: failover to alternate provider and emit degraded-health alerts
- High-frequency alert storm: implement circuit-breakers and rate-limiting
- Misconfigured thresholds: safe defaults and a “dry-run” mode that logs but does not emit
- Incorrect symbol mapping: maintain authoritative mapping table and alert on unknown symbols
- State corruption on restart: persist minimal channel state or accept cold-start behavior with warm-up

Configuration & tuning examples
- Example ENV (do NOT commit secrets)
  DATA_API_PROVIDER=iex
  DATA_API_KEY=xxx
  NEWS_API_PROVIDER=newsapi
  NEWS_API_KEY=yyy
  ALERT_WEBHOOK=https://hooks.example.com/signals
  ALERT_THRESHOLD=60
  MAX_ALERTS_PER_MIN=50
  PRICE_SPIKE_PCT=3.0
  VOLUME_SPIKE_MULTIPLIER=4.0

- Tuning guidance
  - Start with conservative thresholds (higher trigger levels) to reduce false positives
  - Enable one channel at a time in production to establish baseline behavior
  - Use historical replay to calibrate thresholds and scoring weights

Testing & validation
- Unit tests for each channel with synthetic inputs
- Integration tests using historical tick/bar replays across multiple market days
- Backtest suite to evaluate hit rate, precision, recall over a labeled dataset
- Canary deploys and gradual rollouts (shadow mode) for new strategies

Operational playbook (short)
- Before public alerts: run scanner in “audit-only” / dry-run for several trading days
- On secret/key exposure: rotate keys and ensure no secrets commit history remains
- On alert storm: flip global rate-limiter or pause non-critical channels
- On data feed failure: switch to backup provider and notify ops channel

Glossary
- Candidate signal: any channel-generated event that may become an alert
- Alert: a candidate that passed scoring/thresholds and was emitted
- Enrichment: additional context appended to an alert
- Dedupe window: time window used to collapse similar alerts
- Cold-start: the initial period after service start where rolling baselines are not yet established

Contributing, security & license
- See CONTRIBUTING.md and SECURITY.md for contribution and vulnerability-reporting guidelines.
- This project uses the LICENSE file in the repository root for licensing terms.

Contact & next steps
If you want I can:
- Tailor the configuration and run commands to the repo's actual language/runtime (show me file structure or tell me runtime),
- Generate example config files (config.yml / .env.sample),
- Add a diagram or quickstart Docker Compose for one-click runs.
