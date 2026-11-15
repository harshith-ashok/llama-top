import { Link } from "react-router-dom"
import { StatCard } from "@/components/stat-card"
import { StatusBadge } from "@/components/status-badge"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { Progress } from "@/components/ui/progress"
import { useLive } from "@/hooks/use-api"
import { api } from "@/lib/api"
import { bytes, compact, ms, num } from "@/lib/format"

export default function OverviewPage() {
  const sources = useLive(["sources"], api.sources)
  const hosts = useLive(["hosts"], api.hosts)
  const summary = useLive(["summary", 24], () => api.summary(24), 10000)

  const s = summary.data
  const online = sources.data?.filter((x) => x.status === "online").length ?? 0
  return (
    <>
      <div className="grid grid-cols-2 gap-3 lg:grid-cols-4">
        <StatCard
          title="Sources online"
          value={`${online} / ${sources.data?.length ?? 0}`}
          hint={<Link to="/sources" className="underline">Manage sources</Link>}
        />
        <StatCard title="Requests (24h)" value={num(s?.requests)} hint={`${num((s?.error_rate ?? 0) * 100, 1)}% errors`} />
        <StatCard
          title="Tokens (24h)"
          value={compact(s?.total_tokens)}
          hint={`${compact(s?.prompt_tokens)} in · ${compact(s?.completion_tokens)} out`}
        />
        <StatCard
          title="Avg generation"
          value={s?.avg_gen_tps != null ? `${num(s.avg_gen_tps, 1)} tok/s` : "—"}
          hint={`TTFT ${ms(s?.avg_ttft_ms)}`}
        />
      </div>

      <section className="space-y-2">
        <h2 className="text-sm font-medium">Hosts</h2>
        <div className="grid gap-3 md:grid-cols-2 xl:grid-cols-3">
          {hosts.data?.map((h) => {
            const c = h.current
            const gpu = c?.gpus?.[0]
            return (
              <Card key={h.id} size="sm">
                <CardHeader>
                  <CardTitle className="flex items-center justify-between">
                    {h.name}
                    <StatusBadge status={h.online ? "online" : "offline"} />
                  </CardTitle>
                  <p className="text-xs text-muted-foreground">
                    {h.info.os} · {h.info.cpu_cores_logical} cores · {bytes(h.info.ram_total)} RAM
                  </p>
                </CardHeader>
                <CardContent className="space-y-3 text-xs">
                  <Meter label="CPU" value={c?.cpu.percent} />
                  <Meter label="Memory" value={c?.memory.percent} />
                  {gpu ? (
                    <>
                      <Meter label="GPU" value={gpu.util} />
                      <Meter label="VRAM" value={(gpu.vram_used / gpu.vram_total) * 100} />
                    </>
                  ) : (
                    <p className="text-muted-foreground">No NVIDIA GPU telemetry available.</p>
                  )}
                </CardContent>
              </Card>
            )
          })}
          {hosts.data?.length === 0 && <p className="text-sm text-muted-foreground">Waiting for first host sample…</p>}
        </div>
      </section>

      <section className="space-y-2">
        <h2 className="text-sm font-medium">Sources</h2>
        <div className="grid gap-3 md:grid-cols-2 xl:grid-cols-3">
          {sources.data?.map((x) => (
            <Card key={x.id} size="sm">
              <CardHeader>
                <CardTitle className="flex items-center justify-between">
                  {x.name}
                  <StatusBadge status={x.status} />
                </CardTitle>
                <p className="truncate text-xs text-muted-foreground">{x.base_url}</p>
              </CardHeader>
              <CardContent className="text-xs text-muted-foreground">
                {x.model_count} models · {ms(x.latency_ms)}
                {x.version && ` · v${x.version}`}
              </CardContent>
            </Card>
          ))}
          {sources.data?.length === 0 && (
            <p className="text-sm text-muted-foreground">
              No sources yet. <Link to="/sources" className="underline">Add one</Link> to start monitoring.
            </p>
          )}
        </div>
      </section>
    </>
  )
}

function Meter({ label, value }: { label: string; value: number | undefined }) {
  return (
    <div className="space-y-1">
      <div className="flex justify-between">
        <span>{label}</span>
        <span className="tabular-nums">{value == null ? "—" : `${value.toFixed(0)}%`}</span>
      </div>
      <Progress value={value ?? 0} />
    </div>
  )
}
