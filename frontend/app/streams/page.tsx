"use client";

import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Activity, AlertCircle, Clock3, Copy, ExternalLink, KeyRound, Link2, Play, Radio, RotateCcw, Square, Waves } from "lucide-react";
import {
  getLatestStreamEvent,
  getStream,
  getStreamEvents,
  getStreamEventsByType,
  getStreamSseUrl,
  getStreamValidation,
  replayStream,
  startStream,
  stopStream,
} from "@/lib/api";
import type { StreamEvent, StreamPayload, StreamStartResponse, StreamingDomain } from "@/types/api";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Progress } from "@/components/ui/progress";
import { Skeleton } from "@/components/ui/skeleton";
import { cn, formatNumber, titleCase } from "@/lib/utils";

const streamDomains: { id: StreamingDomain; name: string; description: string }[] = [
  { id: "manufacturing", name: "Manufacturing", description: "Machine, quality, maintenance, and downtime events." },
  { id: "telecommunications", name: "Telecommunications", description: "CDR, SMS, data usage, outage, and billing usage events." },
  { id: "ecommerce", name: "E-commerce Marketplace", description: "Product views, carts, orders, payments, shipments, and returns." },
  { id: "logistics", name: "Logistics", description: "Shipments, tracking, GPS, delivery status, and delay alerts." },
  { id: "banking", name: "Banking", description: "Account activity, transactions, transfers, fraud alerts, and ledger events." },
];

const eventTypesByDomain: Record<StreamingDomain, string[]> = {
  manufacturing: ["machine_sensor", "production_event", "quality_event", "maintenance_alert", "downtime_event"],
  telecommunications: ["call_detail_event", "sms_event", "data_session_event", "tower_outage_event", "billing_usage_event"],
  ecommerce: ["product_view_event", "cart_update_event", "order_created_event", "payment_event", "shipment_event", "return_event"],
  logistics: ["shipment_created_event", "tracking_event", "gps_event", "delivery_status_event", "delay_alert_event"],
  banking: ["account_activity_event", "transaction_event", "transfer_event", "fraud_alert_event", "ledger_event"],
};

const failureOptions = [
  "late_events",
  "duplicate_events",
  "out_of_order_events",
  "missing_events",
  "schema_drift",
  "malformed_json",
  "future_timestamp",
  "clock_skew",
  "burst_traffic",
];

export default function StreamsPage() {
  const queryClient = useQueryClient();
  const [domain, setDomain] = useState<StreamingDomain>("manufacturing");
  const [eventTypes, setEventTypes] = useState<string[]>(eventTypesByDomain.manufacturing);
  const [eventsPerSecond, setEventsPerSecond] = useState(1);
  const [durationMinutes, setDurationMinutes] = useState(1);
  const [seed, setSeed] = useState(42);
  const [failures, setFailures] = useState<Record<string, boolean>>({});
  const [activeStreamId, setActiveStreamId] = useState<string | null>(null);
  const [streamAccess, setStreamAccess] = useState<StreamStartResponse | null>(null);
  const [webhookEnabled, setWebhookEnabled] = useState(false);
  const [webhookUrl, setWebhookUrl] = useState("");
  const [webhookSecret, setWebhookSecret] = useState("");
  const [eventTypeFilter, setEventTypeFilter] = useState<string>("all");
  const [afterSequence, setAfterSequence] = useState(0);
  const [copiedValue, setCopiedValue] = useState<string | null>(null);

  const statusQuery = useQuery({
    queryKey: ["stream", activeStreamId],
    queryFn: () => getStream(activeStreamId as string),
    enabled: Boolean(activeStreamId),
    refetchInterval: (query) => (["queued", "running"].includes(query.state.data?.status ?? "") ? 1200 : false),
  });

  const eventsQuery = useQuery({
    queryKey: ["stream-events", activeStreamId, eventTypeFilter, afterSequence, streamAccess?.stream_token],
    queryFn: () =>
      eventTypeFilter === "all"
        ? getStreamEvents(activeStreamId as string, 100, 0, streamAccess?.stream_token, afterSequence || null)
        : getStreamEventsByType(activeStreamId as string, eventTypeFilter, 100, 0, streamAccess?.stream_token, afterSequence || null),
    enabled: Boolean(activeStreamId) && ["completed", "stopped", "failed"].includes(statusQuery.data?.status ?? ""),
  });

  const latestEventQuery = useQuery({
    queryKey: ["stream-latest-event", activeStreamId, streamAccess?.stream_token],
    queryFn: () => getLatestStreamEvent(activeStreamId as string, streamAccess?.stream_token),
    enabled: Boolean(activeStreamId) && ["completed", "stopped", "failed"].includes(statusQuery.data?.status ?? ""),
  });

  const validationQuery = useQuery({
    queryKey: ["stream-validation", activeStreamId],
    queryFn: () => getStreamValidation(activeStreamId as string),
    enabled: Boolean(activeStreamId) && ["completed", "stopped", "failed"].includes(statusQuery.data?.status ?? ""),
  });

  const startMutation = useMutation({
    mutationFn: (payload: StreamPayload) => startStream(payload),
    onSuccess: (response) => {
      setActiveStreamId(response.stream_id);
      setStreamAccess(response);
      setEventTypeFilter("all");
      setAfterSequence(0);
      queryClient.invalidateQueries({ queryKey: ["stream", response.stream_id] });
    },
  });

  const stopMutation = useMutation({
    mutationFn: (streamId: string) => stopStream(streamId),
    onSuccess: () => {
      if (activeStreamId) {
        queryClient.invalidateQueries({ queryKey: ["stream", activeStreamId] });
      }
    },
  });

  const replayMutation = useMutation({
    mutationFn: (streamId: string) => replayStream(streamId),
    onSuccess: (_, streamId) => {
      queryClient.invalidateQueries({ queryKey: ["stream-events", streamId] });
    },
  });

  const selectedDomain = streamDomains.find((item) => item.id === domain) ?? streamDomains[0];
  const selectedFailures = Object.fromEntries(Object.entries(failures).filter(([, enabled]) => enabled));
  const estimatedEvents = Math.min(eventsPerSecond * durationMinutes * 60, 10_000);
  const progress = statusQuery.data ? Math.min(100, Math.round((statusQuery.data.events_generated / Math.max(estimatedEvents, 1)) * 100)) : 0;

  function changeDomain(nextDomain: StreamingDomain) {
    setDomain(nextDomain);
    setEventTypes(eventTypesByDomain[nextDomain]);
  }

  function toggleEventType(eventType: string) {
    setEventTypes((current) => (current.includes(eventType) ? current.filter((item) => item !== eventType) : [...current, eventType]));
  }

  function setCleanStream() {
    setFailures({});
  }

  function setFailureInjectedStream() {
    setFailures({
      late_events: true,
      duplicate_events: true,
      out_of_order_events: true,
      schema_drift: true,
      clock_skew: true,
    });
  }

  function start() {
    if (!eventTypes.length) return;
    startMutation.mutate({
      domain,
      event_types: eventTypes,
      events_per_second: eventsPerSecond,
      duration_minutes: durationMinutes,
      format: "json",
      seed,
      failure_injections: selectedFailures,
      webhook_url: webhookEnabled && webhookUrl.trim() ? webhookUrl.trim() : undefined,
      webhook_secret: webhookEnabled && webhookSecret.trim() ? webhookSecret.trim() : undefined,
    });
  }

  async function copyText(label: string, value?: string | null) {
    if (!value) return;
    await navigator.clipboard.writeText(value);
    setCopiedValue(label);
    window.setTimeout(() => setCopiedValue(null), 1600);
  }

  return (
    <div className="min-w-0 space-y-6">
      <header className="min-w-0 overflow-hidden rounded-2xl border border-border bg-white/70 p-5 shadow-sm backdrop-blur">
        <Badge>Phase 2 · Streaming MVP</Badge>
        <div className="mt-3 grid min-w-0 gap-4 xl:grid-cols-[minmax(0,1fr)_auto] xl:items-end">
          <div className="min-w-0">
            <h1 className="text-3xl font-bold tracking-tight">Streaming Simulation APIs</h1>
            <p className="mt-2 max-w-3xl text-sm text-muted-foreground">
              Simulate deterministic JSON event streams, inject streaming failures, validate outcomes, and inspect persisted event samples.
            </p>
          </div>
          <div className="flex min-w-0 flex-wrap gap-2 xl:justify-end">
            {activeStreamId ? (
              <>
                <a
                  href={streamAccess?.sse_url ?? getStreamSseUrl(activeStreamId, streamAccess?.stream_token)}
                  target="_blank"
                  rel="noreferrer"
                  className="inline-flex h-11 items-center justify-center rounded-xl border border-border bg-card px-4 text-sm font-semibold transition hover:bg-muted"
                >
                  Open SSE
                </a>
                <Button variant="secondary" disabled={replayMutation.isPending} onClick={() => replayMutation.mutate(activeStreamId)}>
                  <RotateCcw className="mr-2 h-4 w-4" /> Replay
                </Button>
                <Button variant="danger" disabled={stopMutation.isPending || !["queued", "running"].includes(statusQuery.data?.status ?? "")} onClick={() => stopMutation.mutate(activeStreamId)}>
                  <Square className="mr-2 h-4 w-4" /> Stop
                </Button>
              </>
            ) : null}
          </div>
        </div>
      </header>

      <div className="grid min-w-0 gap-5 xl:grid-cols-[minmax(0,1fr)_minmax(320px,360px)]">
        <div className="min-w-0 space-y-5">
          <Card className="min-w-0 overflow-hidden">
            <CardHeader>
              <CardTitle>1. Stream Setup</CardTitle>
              <CardDescription>Select an MVP streaming domain, rate, duration, and deterministic seed.</CardDescription>
            </CardHeader>
            <CardContent className="grid min-w-0 gap-4 lg:grid-cols-4">
              <label className="grid min-w-0 gap-2 lg:col-span-2">
                <span className="text-xs font-semibold uppercase tracking-[0.18em] text-muted-foreground">Domain</span>
                <select className="h-11 min-w-0 rounded-xl border border-border bg-card px-3 text-sm font-semibold outline-none focus:border-primary" value={domain} onChange={(event) => changeDomain(event.target.value as StreamingDomain)}>
                  {streamDomains.map((item) => (
                    <option key={item.id} value={item.id}>{item.name}</option>
                  ))}
                </select>
                <span className="text-xs text-muted-foreground">{selectedDomain.description}</span>
              </label>
              <NumberField label="Events / Second" value={eventsPerSecond} min={1} max={100} onChange={setEventsPerSecond} />
              <NumberField label="Duration Minutes" value={durationMinutes} min={1} max={240} onChange={setDurationMinutes} />
              <NumberField label="Seed" value={seed} min={1} max={999999} onChange={setSeed} />
              <div className="min-w-0 rounded-xl border border-border bg-muted/30 p-3 lg:col-span-3">
                <p className="text-xs font-semibold uppercase tracking-[0.18em] text-muted-foreground">Estimated Events</p>
                <p className="mt-2 text-2xl font-bold">{formatNumber(estimatedEvents)}</p>
                <p className="mt-1 text-xs text-muted-foreground">Capped at 10,000 events per MVP session.</p>
              </div>
            </CardContent>
          </Card>

          <Card className="min-w-0 overflow-hidden">
            <CardHeader>
              <CardTitle>2. Event Types</CardTitle>
              <CardDescription>Select one or more event types for this stream session.</CardDescription>
            </CardHeader>
            <CardContent className="grid min-w-0 gap-3 md:grid-cols-2 2xl:grid-cols-3">
              {eventTypesByDomain[domain].map((eventType) => {
                const selected = eventTypes.includes(eventType);
                return (
                  <label key={eventType} className={cn("min-w-0 rounded-xl border bg-card p-3 transition hover:shadow-glow", selected ? "border-primary ring-4 ring-primary/10" : "border-border")}>
                    <div className="flex min-w-0 items-center gap-3">
                      <input type="checkbox" checked={selected} onChange={() => toggleEventType(eventType)} className="h-4 w-4 shrink-0 accent-primary" />
                      <div className="min-w-0">
                        <p className="truncate text-sm font-semibold">{titleCase(eventType)}</p>
                        <p className="text-xs text-muted-foreground">JSON event envelope</p>
                      </div>
                    </div>
                  </label>
                );
              })}
            </CardContent>
          </Card>

          <Card className="min-w-0 overflow-hidden">
            <CardHeader>
              <CardTitle>3. Streaming Failure Injection</CardTitle>
              <CardDescription>Toggle realistic streaming issues. Each one produces a validation check.</CardDescription>
            </CardHeader>
            <CardContent className="grid min-w-0 gap-3 md:grid-cols-2 2xl:grid-cols-3">
              <div className="min-w-0 rounded-xl border border-border bg-muted/20 p-3 md:col-span-2 2xl:col-span-3">
                <p className="text-sm font-semibold">Comparison preset</p>
                <p className="mt-1 text-xs text-muted-foreground">Switch quickly between a clean stream and a realistic failure-injected stream.</p>
                <div className="mt-3 flex flex-wrap gap-2">
                  <Button variant="secondary" className="h-9" onClick={setCleanStream}>Clean stream</Button>
                  <Button variant="secondary" className="h-9" onClick={setFailureInjectedStream}>Failure-injected stream</Button>
                </div>
              </div>
              {failureOptions.map((failure) => (
                <label key={failure} className={cn("min-w-0 rounded-xl border bg-card p-3 transition", failures[failure] ? "border-danger/40 bg-danger/5" : "border-border")}>
                  <div className="flex min-w-0 items-center gap-3">
                    <input
                      type="checkbox"
                      checked={Boolean(failures[failure])}
                      onChange={() => setFailures((current) => ({ ...current, [failure]: !current[failure] }))}
                      className="h-4 w-4 shrink-0 accent-primary"
                    />
                    <span className="truncate text-sm font-semibold">{titleCase(failure)}</span>
                  </div>
                </label>
              ))}
            </CardContent>
          </Card>

          <Card className="min-w-0 overflow-hidden">
            <CardHeader>
              <CardTitle>4. Push Integration</CardTitle>
              <CardDescription>Optionally push generated events to an external webhook with signed payloads.</CardDescription>
            </CardHeader>
            <CardContent className="space-y-4">
              <label className="flex min-w-0 items-center gap-3 rounded-xl border border-border bg-card p-3">
                <input type="checkbox" checked={webhookEnabled} onChange={() => setWebhookEnabled((current) => !current)} className="h-4 w-4 shrink-0 accent-primary" />
                <span className="text-sm font-semibold">Enable webhook push mode</span>
              </label>
              {webhookEnabled ? (
                <div className="grid min-w-0 gap-4 md:grid-cols-2">
                  <TextField label="Webhook URL" value={webhookUrl} placeholder="https://example.com/dataforge-webhook" onChange={setWebhookUrl} />
                  <TextField label="Webhook Secret" value={webhookSecret} placeholder="Used for HMAC signature" onChange={setWebhookSecret} type="password" />
                </div>
              ) : null}
            </CardContent>
          </Card>

          <StreamEventsPanel
            isLoading={eventsQuery.isLoading}
            error={eventsQuery.error?.message}
            events={eventsQuery.data?.events ?? []}
            total={eventsQuery.data?.total ?? 0}
            eventTypes={eventTypesByDomain[domain]}
            eventTypeFilter={eventTypeFilter}
            afterSequence={afterSequence}
            latestEventSequence={latestEventQuery.data?.event.sequence_number}
            onEventTypeFilterChange={setEventTypeFilter}
            onAfterSequenceChange={setAfterSequence}
          />
        </div>

        <aside className="min-w-0 space-y-5">
          <Card className="min-w-0 overflow-hidden xl:sticky xl:top-6">
            <CardHeader>
              <CardTitle>Stream Control</CardTitle>
              <CardDescription>Start a session and monitor generated event samples.</CardDescription>
            </CardHeader>
            <CardContent className="space-y-4">
              <SummaryRow label="Domain" value={selectedDomain.name} />
              <SummaryRow label="Event Types" value={`${eventTypes.length} selected`} />
              <SummaryRow label="Rate" value={`${eventsPerSecond}/sec`} />
              <SummaryRow label="Duration" value={`${durationMinutes} min`} />
              <SummaryRow label="Failures" value={Object.keys(selectedFailures).length ? `${Object.keys(selectedFailures).length} enabled` : "Clean stream"} />
              <Button className="w-full" disabled={!eventTypes.length || startMutation.isPending} onClick={start}>
                <Play className="mr-2 h-4 w-4" /> {startMutation.isPending ? "Starting..." : "Start Stream"}
              </Button>
              {startMutation.isError ? <ErrorMessage message={startMutation.error.message} /> : null}
            </CardContent>
          </Card>

          <StreamStatusCard status={statusQuery.data} isLoading={statusQuery.isLoading} progress={progress} />
          <IntegrationCard
            stream={streamAccess}
            eventTypes={eventTypesByDomain[domain]}
            copiedValue={copiedValue}
            onCopy={copyText}
          />
          <ValidationCard isLoading={validationQuery.isLoading} report={validationQuery.data} error={validationQuery.error?.message} />
        </aside>
      </div>
    </div>
  );
}

function TextField({ label, value, placeholder, type = "text", onChange }: { label: string; value: string; placeholder?: string; type?: string; onChange: (value: string) => void }) {
  return (
    <label className="grid min-w-0 gap-2">
      <span className="text-xs font-semibold uppercase tracking-[0.18em] text-muted-foreground">{label}</span>
      <input
        type={type}
        value={value}
        placeholder={placeholder}
        onChange={(event) => onChange(event.target.value)}
        className="h-11 min-w-0 rounded-xl border border-border bg-card px-3 text-sm font-semibold outline-none focus:border-primary"
      />
    </label>
  );
}

function NumberField({ label, value, min, max, onChange }: { label: string; value: number; min: number; max: number; onChange: (value: number) => void }) {
  return (
    <label className="grid min-w-0 gap-2">
      <span className="text-xs font-semibold uppercase tracking-[0.18em] text-muted-foreground">{label}</span>
      <input
        type="number"
        min={min}
        max={max}
        value={value}
        onChange={(event) => onChange(Math.min(max, Math.max(min, Math.floor(Number(event.target.value) || min))))}
        className="h-11 min-w-0 rounded-xl border border-border bg-card px-3 text-sm font-semibold outline-none focus:border-primary"
      />
    </label>
  );
}

function StreamStatusCard({ status, isLoading, progress }: { status?: { status: string; events_generated: number; events_failed: number; failure_summary: Record<string, number>; webhook_delivery_summary?: Record<string, unknown>; estimated_end_at: string; completed_at: string | null }; isLoading: boolean; progress: number }) {
  return (
    <Card className="min-w-0 overflow-hidden">
      <CardHeader>
        <CardTitle>Status</CardTitle>
        <CardDescription>Current stream session state.</CardDescription>
      </CardHeader>
      <CardContent className="space-y-4">
        {isLoading ? (
          <Skeleton className="h-28" />
        ) : status ? (
          <>
            <div className="grid min-w-0 gap-2 sm:grid-cols-[auto_minmax(0,1fr)] sm:items-center">
              <Badge className={statusBadgeClass(status.status)}>{titleCase(status.status)}</Badge>
              <span className="min-w-0 truncate text-sm text-muted-foreground sm:text-right">{status.completed_at ? `Completed ${formatDateTime(status.completed_at)}` : `ETA ${formatDateTime(status.estimated_end_at)}`}</span>
            </div>
            <Progress value={progress} />
            <div className="grid min-w-0 grid-cols-2 gap-3">
              <MetricTile icon={Activity} label="Generated" value={formatNumber(status.events_generated)} />
              <MetricTile icon={AlertCircle} label="Failed" value={formatNumber(status.events_failed)} />
            </div>
            {Object.keys(status.failure_summary).length ? (
              <div className="rounded-xl border border-danger/20 bg-danger/5 p-3">
                <p className="text-sm font-semibold text-danger">Failure Summary</p>
                <div className="mt-2 space-y-1 text-xs text-muted-foreground">
                  {Object.entries(status.failure_summary).map(([key, value]) => (
                    <div key={key} className="grid min-w-0 grid-cols-[minmax(0,1fr)_auto] gap-3">
                      <span className="truncate">{titleCase(key)}</span>
                      <span className="shrink-0">{formatNumber(value)}</span>
                    </div>
                  ))}
                </div>
              </div>
            ) : null}
            {status.webhook_delivery_summary && Object.keys(status.webhook_delivery_summary).length ? (
              <div className="rounded-xl border border-primary/20 bg-primary/5 p-3">
                <p className="text-sm font-semibold text-primary">Webhook Delivery</p>
                <div className="mt-2 space-y-1 text-xs text-muted-foreground">
                  {Object.entries(status.webhook_delivery_summary).map(([key, value]) => (
                    <div key={key} className="grid min-w-0 grid-cols-[minmax(0,1fr)_auto] gap-3">
                      <span className="truncate">{titleCase(key)}</span>
                      <span className="shrink-0 truncate text-right">{formatSummaryValue(value)}</span>
                    </div>
                  ))}
                </div>
              </div>
            ) : null}
          </>
        ) : (
          <div className="rounded-xl border border-dashed border-border p-4 text-sm text-muted-foreground">Start a stream to see live status.</div>
        )}
      </CardContent>
    </Card>
  );
}

function StreamEventsPanel({
  isLoading,
  error,
  events,
  total,
  eventTypes,
  eventTypeFilter,
  afterSequence,
  latestEventSequence,
  onEventTypeFilterChange,
  onAfterSequenceChange,
}: {
  isLoading: boolean;
  error?: string;
  events: StreamEvent[];
  total: number;
  eventTypes: string[];
  eventTypeFilter: string;
  afterSequence: number;
  latestEventSequence?: number;
  onEventTypeFilterChange: (value: string) => void;
  onAfterSequenceChange: (value: number) => void;
}) {
  return (
    <Card className="min-w-0 overflow-hidden">
      <CardHeader>
        <div className="grid min-w-0 gap-3 sm:grid-cols-[minmax(0,1fr)_auto] sm:items-start">
          <div className="min-w-0">
            <CardTitle>Generated Event Samples</CardTitle>
            <CardDescription>Persisted JSON event envelopes from the active stream session.</CardDescription>
          </div>
          <Badge>{formatNumber(total)} total</Badge>
        </div>
      </CardHeader>
      <CardContent className="space-y-4">
        <div className="grid min-w-0 gap-3 rounded-xl border border-border bg-muted/20 p-3 md:grid-cols-[minmax(0,1fr)_160px_auto] md:items-end">
          <label className="grid min-w-0 gap-2">
            <span className="text-xs font-semibold uppercase tracking-[0.18em] text-muted-foreground">Event Type Filter</span>
            <select value={eventTypeFilter} onChange={(event) => onEventTypeFilterChange(event.target.value)} className="h-10 min-w-0 rounded-xl border border-border bg-card px-3 text-sm font-semibold outline-none focus:border-primary">
              <option value="all">All event types</option>
              {eventTypes.map((eventType) => (
                <option key={eventType} value={eventType}>{titleCase(eventType)}</option>
              ))}
            </select>
          </label>
          <NumberField label="After Sequence" value={afterSequence} min={0} max={999999} onChange={onAfterSequenceChange} />
          <Badge className="justify-center">Latest #{latestEventSequence ?? "—"}</Badge>
        </div>
        {isLoading ? (
          <div className="space-y-3">{Array.from({ length: 4 }).map((_, index) => <Skeleton key={index} className="h-24" />)}</div>
        ) : error ? (
          <ErrorMessage message={error} />
        ) : events.length ? (
          <div className="max-h-[560px] min-w-0 space-y-3 overflow-auto pr-1">
            {events.map((event) => (
              <div key={`${event.event_id}-${event.sequence_number}`} className="min-w-0 overflow-hidden rounded-xl border border-border bg-muted/20 p-3">
                <div className="grid min-w-0 gap-2 sm:grid-cols-[minmax(0,1fr)_auto] sm:items-start">
                  <div className="min-w-0">
                    <p className="truncate text-sm font-semibold">{titleCase(event.event_type)}</p>
                    <p className="truncate text-xs text-muted-foreground">#{event.sequence_number} · {event.event_id}</p>
                  </div>
                  {event.injected_issues.length ? <Badge className="border-danger/30 bg-danger/10 text-danger">{event.injected_issues.length} issues</Badge> : <Badge className="border-success/30 bg-success/10 text-success">Clean</Badge>}
                </div>
                <div className="mt-3 grid min-w-0 gap-2 text-xs text-muted-foreground md:grid-cols-3">
                  <span className="truncate"><Clock3 className="mr-1 inline h-3 w-3" />{formatDateTime(event.event_time)}</span>
                  <span className="truncate"><Radio className="mr-1 inline h-3 w-3" />{event.correlation_id}</span>
                  <span className="truncate"><Waves className="mr-1 inline h-3 w-3" />{titleCase(event.domain)}</span>
                </div>
                <pre className="mt-3 max-h-28 max-w-full overflow-auto whitespace-pre-wrap break-words rounded-lg bg-white/70 p-3 text-xs">{JSON.stringify(event.payload, null, 2)}</pre>
              </div>
            ))}
          </div>
        ) : (
          <div className="rounded-xl border border-dashed border-border p-8 text-center text-sm text-muted-foreground">Start a stream to inspect generated events.</div>
        )}
      </CardContent>
    </Card>
  );
}

function IntegrationCard({ stream, eventTypes, copiedValue, onCopy }: { stream: StreamStartResponse | null; eventTypes: string[]; copiedValue: string | null; onCopy: (label: string, value?: string | null) => void }) {
  const primaryEventType = eventTypes[0];
  return (
    <Card className="min-w-0 overflow-hidden">
      <CardHeader>
        <CardTitle>Integration Access</CardTitle>
        <CardDescription>Use these URLs from external tools. The stream token is scoped to this stream.</CardDescription>
      </CardHeader>
      <CardContent className="space-y-4">
        {stream ? (
          <>
            <div className="rounded-xl border border-warning/30 bg-warning/5 p-3">
              <div className="flex min-w-0 items-center gap-2 text-sm font-semibold">
                <KeyRound className="h-4 w-4 shrink-0" />
                <span>Stream Token</span>
              </div>
              <p className="mt-2 break-all rounded-lg bg-white/70 p-2 font-mono text-xs">{stream.stream_token}</p>
              <p className="mt-2 text-xs text-muted-foreground">Expires {stream.stream_token_expires_at ? formatDateTime(stream.stream_token_expires_at) : "soon"}. Use this as an Authorization bearer token; avoid putting it in URLs.</p>
              <Button variant="secondary" className="mt-3 h-9 w-full" onClick={() => onCopy("token", stream.stream_token)}>
                <Copy className="mr-2 h-4 w-4" /> {copiedValue === "token" ? "Copied" : "Copy Token"}
              </Button>
            </div>
            <div className="space-y-2">
              <UrlRow label="Pull" value={stream.pull_url} copied={copiedValue === "pull"} onCopy={() => onCopy("pull", stream.pull_url)} />
              <UrlRow label="Latest" value={stream.latest_url} copied={copiedValue === "latest"} onCopy={() => onCopy("latest", stream.latest_url)} />
              <UrlRow label="SSE" value={stream.sse_url} copied={copiedValue === "sse"} onCopy={() => onCopy("sse", stream.sse_url)} />
            </div>
            <div className="rounded-xl border border-border bg-muted/20 p-3">
              <p className="text-sm font-semibold">Copy integration examples</p>
              <div className="mt-3 grid gap-2 sm:grid-cols-2">
                <SnippetButton label="cURL" copied={copiedValue === "curl"} onCopy={() => onCopy("curl", curlSnippet(stream))} />
                <SnippetButton label="Python" copied={copiedValue === "python"} onCopy={() => onCopy("python", pythonSnippet(stream))} />
                <SnippetButton label="Spark" copied={copiedValue === "spark"} onCopy={() => onCopy("spark", sparkSnippet(stream))} />
                <SnippetButton label="Postman" copied={copiedValue === "postman"} onCopy={() => onCopy("postman", postmanSnippet(stream))} />
              </div>
              {primaryEventType ? (
                <Button variant="secondary" className="mt-2 h-9 w-full" onClick={() => onCopy("curl-event-type", curlSnippet(stream, primaryEventType))}>
                  <Copy className="mr-2 h-4 w-4" /> {copiedValue === "curl-event-type" ? "Copied" : `Copy ${titleCase(primaryEventType)} cURL`}
                </Button>
              ) : null}
            </div>
            <div className="rounded-xl border border-border bg-muted/20 p-3">
              <p className="text-sm font-semibold">Event Type URLs</p>
              <div className="mt-2 max-h-48 space-y-2 overflow-auto">
                {eventTypes.map((eventType) => (
                  <UrlRow
                    key={eventType}
                    label={titleCase(eventType)}
                    value={stream.event_type_urls[eventType]}
                    copied={copiedValue === eventType}
                    onCopy={() => onCopy(eventType, stream.event_type_urls[eventType])}
                  />
                ))}
              </div>
            </div>
          </>
        ) : (
          <div className="rounded-xl border border-dashed border-border p-4 text-sm text-muted-foreground">Start a stream to receive pull URLs, SSE URLs, and a scoped token.</div>
        )}
      </CardContent>
    </Card>
  );
}

function UrlRow({ label, value, copied, onCopy }: { label: string; value?: string | null; copied: boolean; onCopy: () => void }) {
  return (
    <div className="grid min-w-0 gap-2 rounded-lg border border-border bg-card p-2">
      <div className="flex min-w-0 items-center justify-between gap-2">
        <span className="truncate text-xs font-semibold text-muted-foreground">{label}</span>
        <div className="flex shrink-0 items-center gap-1">
          {value ? (
            <a href={value} target="_blank" rel="noreferrer" className="rounded-md p-1 hover:bg-muted" title="Open URL">
              <ExternalLink className="h-3.5 w-3.5" />
            </a>
          ) : null}
          <button type="button" onClick={onCopy} disabled={!value} className="rounded-md p-1 hover:bg-muted disabled:opacity-40" title="Copy URL">
            {copied ? <Link2 className="h-3.5 w-3.5 text-success" /> : <Copy className="h-3.5 w-3.5" />}
          </button>
        </div>
      </div>
      <p className="break-all font-mono text-[11px] text-muted-foreground">{value ?? "Unavailable"}</p>
    </div>
  );
}

function SnippetButton({ label, copied, onCopy }: { label: string; copied: boolean; onCopy: () => void }) {
  return (
    <Button variant="secondary" className="h-9" onClick={onCopy}>
      <Copy className="mr-2 h-4 w-4" /> {copied ? "Copied" : `Copy ${label}`}
    </Button>
  );
}

function ValidationCard({ isLoading, report, error }: { isLoading: boolean; report?: { quality_score: number; status: string; summary: { passed: number; failed: number; total_checks: number }; checks: { name: string; status: string; actual: string }[] }; error?: string }) {
  return (
    <Card className="min-w-0 overflow-hidden">
      <CardHeader>
        <CardTitle>Validation</CardTitle>
        <CardDescription>Streaming failure detection report.</CardDescription>
      </CardHeader>
      <CardContent>
        {isLoading ? (
          <Skeleton className="h-32" />
        ) : error ? (
          <ErrorMessage message={error} />
        ) : report ? (
          <div className="space-y-4">
            <div className="flex min-w-0 items-center justify-between gap-3">
              <Badge className={report.status === "PASS" ? "border-success/30 bg-success/10 text-success" : "border-danger/30 bg-danger/10 text-danger"}>{report.status}</Badge>
              <p className="shrink-0 text-2xl font-bold">{report.quality_score}</p>
            </div>
            <Progress value={report.quality_score} />
            <p className="text-sm text-muted-foreground">{report.summary.passed}/{report.summary.total_checks} checks passed · {report.summary.failed} failed</p>
            <div className="space-y-2">
              {report.checks.map((check) => (
                <div key={check.name} className="grid min-w-0 grid-cols-[minmax(0,1fr)_auto] items-center gap-3 rounded-xl border border-border bg-muted/20 p-2 text-xs">
                  <span className="truncate">{check.name}</span>
                  <Badge className={check.status === "PASS" ? "border-success/30 bg-success/10 text-success" : "border-danger/30 bg-danger/10 text-danger"}>{check.actual}</Badge>
                </div>
              ))}
            </div>
          </div>
        ) : (
          <div className="rounded-xl border border-dashed border-border p-4 text-sm text-muted-foreground">Validation appears after a stream completes.</div>
        )}
      </CardContent>
    </Card>
  );
}

function curlSnippet(stream: StreamStartResponse, eventType?: string) {
  const url = eventType ? stream.event_type_urls[eventType] : stream.pull_url;
  return `curl -H "Authorization: Bearer ${stream.stream_token}" "${url}"`;
}

function pythonSnippet(stream: StreamStartResponse) {
  return `import requests

url = "${stream.pull_url}"
headers = {"Authorization": "Bearer ${stream.stream_token}"}
response = requests.get(url, headers=headers, params={"after_sequence": 0})
response.raise_for_status()
events = response.json()["events"]
print(events[:3])`;
}

function sparkSnippet(stream: StreamStartResponse) {
  return `import requests

url = "${stream.pull_url}"
headers = {"Authorization": "Bearer ${stream.stream_token}"}
events = requests.get(url, headers=headers).json()["events"]
df = spark.createDataFrame(events)
display(df)`;
}

function postmanSnippet(stream: StreamStartResponse) {
  return `GET ${stream.pull_url}
Authorization: Bearer ${stream.stream_token}

In Postman:
1. Method: GET
2. URL: ${stream.pull_url}
3. Authorization tab: Bearer Token
4. Token: ${stream.stream_token}`;
}

function SummaryRow({ label, value }: { label: string; value: string }) {
  return (
    <div className="grid min-w-0 grid-cols-[minmax(0,1fr)_auto] items-center gap-4 text-sm">
      <span className="truncate text-muted-foreground">{label}</span>
      <span className="min-w-0 truncate text-right font-semibold">{value}</span>
    </div>
  );
}

function MetricTile({ icon: Icon, label, value }: { icon: React.ComponentType<{ className?: string }>; label: string; value: string }) {
  return (
    <div className="min-w-0 rounded-xl border border-border bg-muted/30 p-3">
      <Icon className="h-4 w-4 text-primary" />
      <p className="mt-2 text-xs text-muted-foreground">{label}</p>
      <p className="truncate font-bold">{value}</p>
    </div>
  );
}

function ErrorMessage({ message }: { message: string }) {
  return <div className="rounded-xl border border-danger/30 bg-danger/5 p-3 text-sm text-danger">{message}</div>;
}

function formatSummaryValue(value: unknown) {
  if (value === null || value === undefined || value === "") return "—";
  if (typeof value === "number") return formatNumber(value);
  if (typeof value === "string") return value;
  if (typeof value === "boolean") return value ? "Yes" : "No";
  return "Available";
}

function statusBadgeClass(status: string) {
  if (status === "completed") return "border-success/30 bg-success/10 text-success";
  if (status === "failed") return "border-danger/30 bg-danger/10 text-danger";
  if (status === "stopped") return "border-warning/30 bg-warning/10 text-warning";
  return "border-primary/30 bg-primary/10 text-primary";
}

function formatDateTime(value: string) {
  return new Intl.DateTimeFormat(undefined, {
    month: "short",
    day: "numeric",
    hour: "numeric",
    minute: "2-digit",
  }).format(new Date(value));
}
