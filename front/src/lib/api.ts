export type SourceType = "ollama" | "openai"
export type Status = "online" | "degraded" | "offline" | "unknown" | "disabled"

export interface Source {
  id: string
  name: string
  type: SourceType
  base_url: string
  has_api_key: boolean
  tags: string[]
  enabled: boolean
  status: Status
  last_seen: number | null
  latency_ms: number | null
  version: string | null
  error: string | null
  capabilities: string[]
  model_count: number
  gateway_path: string
  agent_url: string | null
  agent_error: string | null
  host_id: string | null
}

export interface SourceInput {
  name: string
  type: SourceType
  base_url: string
  api_key?: string
  tags: string[]
  agent_url?: string
  agent_token?: string
}

export interface ModelRow {
  source_id: string
  source_name: string
  name: string
  digest: string | null
  size_bytes: number | null
  family: string | null
  parameter_size: string | null
  quantization: string | null
  loaded: boolean
  vram_bytes: number | null
}

export interface GpuSample {
  index: number
  util: number
  vram_used: number
  vram_total: number
  temp_c: number | null
  power_w: number | null
}

export interface HostSample {
  ts: number
  cpu: { percent: number; per_core: number[]; freq_mhz: number | null; load_avg: number[] | null }
  memory: { total: number; used: number; percent: number; swap_used: number; swap_total: number }
  disks?: { mount: string; total: number; used: number; percent: number }[]
  network?: { rx_bps: number; tx_bps: number } | null
  gpus: GpuSample[]
  processes?: { pid: number; name: string; cpu: number; rss: number }[]
}

export interface Host {
  id: string
  name: string
  kind: "local" | "agent"
  last_seen: number | null
  online: boolean
  info: {
    hostname?: string
    os?: string
    arch?: string
    cpu_cores_logical?: number
    ram_total?: number
    gpus?: { index: number; name: string }[]
  }
  current: HostSample | null
}

export type HistoryPoint = Pick<HostSample, "ts" | "cpu" | "memory" | "gpus" | "network">

export interface RequestRow {
  id: string
  source_id: string
  ts: number
  model: string | null
  endpoint: string
  status: number
  stream: boolean
  prompt_tokens: number | null
  completion_tokens: number | null
  ttft_ms: number | null
  latency_ms: number | null
  gen_tps: number | null
  finish_reason: string | null
  error: string | null
  app: string | null
}

export interface Summary {
  requests: number
  prompt_tokens: number
  completion_tokens: number
  total_tokens: number
  avg_gen_tps: number | null
  avg_prompt_tps: number | null
  avg_ttft_ms: number | null
  avg_latency_ms: number | null
  errors: number
  error_rate: number
}

export interface TimePoint {
  ts: number
  requests: number
  prompt_tokens: number
  completion_tokens: number
  avg_gen_tps: number | null
}

export interface ModelStat {
  model: string
  source_id: string
  requests: number
  prompt_tokens: number
  completion_tokens: number
  avg_gen_tps: number | null
  avg_ttft_ms: number | null
  avg_latency_ms: number | null
  errors: number
}

async function req<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(`/api${path}`, {
    ...init,
    headers: { "Content-Type": "application/json", ...init?.headers },
  })
  if (!res.ok) {
    let detail = res.statusText
    try {
      const body = await res.json()
      detail = typeof body.detail === "string" ? body.detail : JSON.stringify(body.detail)
    } catch {
      /* non-JSON error body */
    }
    throw new Error(detail)
  }
  return res.status === 204 ? (undefined as T) : res.json()
}

export const api = {
  sources: () => req<Source[]>("/sources"),
  addSource: (b: SourceInput) => req<Source>("/sources", { method: "POST", body: JSON.stringify(b) }),
  patchSource: (id: string, b: Partial<SourceInput> & { enabled?: boolean; clear_agent?: boolean }) =>
    req<Source>(`/sources/${id}`, { method: "PATCH", body: JSON.stringify(b) }),
  deleteSource: (id: string) => req<void>(`/sources/${id}`, { method: "DELETE" }),
  checkSource: (id: string) => req<Source>(`/sources/${id}/check`, { method: "POST" }),
  models: (q?: string) => req<ModelRow[]>(`/models${q ? `?q=${encodeURIComponent(q)}` : ""}`),
  hosts: () => req<Host[]>("/hosts"),
  history: (id: string, minutes: number) => req<HistoryPoint[]>(`/hosts/${id}/history?minutes=${minutes}`),
  requests: (limit = 100) => req<RequestRow[]>(`/requests?limit=${limit}`),
  summary: (hours: number) => req<Summary>(`/analytics/summary?hours=${hours}`),
  timeseries: (hours: number) => req<TimePoint[]>(`/analytics/timeseries?hours=${hours}`),
  modelStats: (hours: number) => req<ModelStat[]>(`/analytics/models?hours=${hours}`),
}
