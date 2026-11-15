import { useState } from "react"
import { Chart } from "@/components/chart"
import { timeAxis } from "@/lib/chart-axes"
import { StatCard } from "@/components/stat-card"
import { Badge } from "@/components/ui/badge"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table"
import { Tabs, TabsList, TabsTrigger } from "@/components/ui/tabs"
import { useLive } from "@/hooks/use-api"
import { api } from "@/lib/api"
import { compact, ms, num } from "@/lib/format"

export default function RequestsPage() {
  const [hours, setHours] = useState("24")
  const h = Number(hours)
  const summary = useLive(["summary", h], () => api.summary(h))
  const series = useLive(["series", h], () => api.timeseries(h), 10000)
  const stats = useLive(["modelstats", h], () => api.modelStats(h), 10000)
  const reqs = useLive(["requests"], () => api.requests(100), 3000)
  const sources = useLive(["sources"], api.sources)
  const names = new Map(sources.data?.map((s) => [s.id, s.name]))
  const s = summary.data
  const pts = series.data ?? []

  return (
    <>
      <Tabs value={hours} onValueChange={(v) => setHours(String(v))}>
        <TabsList>
          {[["1", "1h"], ["24", "24h"], ["168", "7d"]].map(([k, v]) => <TabsTrigger key={k} value={k}>{v}</TabsTrigger>)}
        </TabsList>
      </Tabs>

      <div className="grid grid-cols-2 gap-3 lg:grid-cols-5">
        <StatCard title="Requests" value={num(s?.requests)} />
        <StatCard title="Tokens" value={compact(s?.total_tokens)} hint={`${compact(s?.prompt_tokens)} in · ${compact(s?.completion_tokens)} out`} />
        <StatCard title="Generation" value={s?.avg_gen_tps != null ? `${num(s.avg_gen_tps, 1)} tok/s` : "—"} />
        <StatCard title="Avg TTFT" value={ms(s?.avg_ttft_ms)} />
        <StatCard title="Error rate" value={`${num((s?.error_rate ?? 0) * 100, 1)}%`} hint={`${s?.errors ?? 0} failed`} />
      </div>

      <div className="grid gap-3 lg:grid-cols-2">
        <Card size="sm">
          <CardHeader><CardTitle>Tokens over time</CardTitle></CardHeader>
          <CardContent>
            <Chart option={{
              legend: { top: 0, right: 0 },
              xAxis: timeAxis, yAxis: { type: "value" },
              series: [
                { name: "Input", type: "bar", stack: "t", data: pts.map((p) => [p.ts * 1000, p.prompt_tokens]) },
                { name: "Output", type: "bar", stack: "t", data: pts.map((p) => [p.ts * 1000, p.completion_tokens]) },
              ],
            }} />
          </CardContent>
        </Card>
        <Card size="sm">
          <CardHeader><CardTitle>Generation speed (tok/s)</CardTitle></CardHeader>
          <CardContent>
            <Chart option={{
              xAxis: timeAxis, yAxis: { type: "value" },
              series: [{ name: "tok/s", type: "line", showSymbol: false, connectNulls: true,
                data: pts.map((p) => [p.ts * 1000, p.avg_gen_tps]) }],
            }} />
          </CardContent>
        </Card>
      </div>

      <Card size="sm">
        <CardHeader><CardTitle>Models</CardTitle></CardHeader>
        <CardContent>
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>Model</TableHead><TableHead>Source</TableHead>
                <TableHead className="text-right">Requests</TableHead><TableHead className="text-right">Tokens in/out</TableHead>
                <TableHead className="text-right">tok/s</TableHead><TableHead className="text-right">TTFT</TableHead>
                <TableHead className="text-right">Latency</TableHead><TableHead className="text-right">Errors</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {stats.data?.map((m) => (
                <TableRow key={`${m.source_id}:${m.model}`}>
                  <TableCell className="font-medium">{m.model}</TableCell>
                  <TableCell>{names.get(m.source_id) ?? m.source_id}</TableCell>
                  <TableCell className="text-right tabular-nums">{num(m.requests)}</TableCell>
                  <TableCell className="text-right tabular-nums">{compact(m.prompt_tokens)} / {compact(m.completion_tokens)}</TableCell>
                  <TableCell className="text-right tabular-nums">{num(m.avg_gen_tps, 1)}</TableCell>
                  <TableCell className="text-right tabular-nums">{ms(m.avg_ttft_ms)}</TableCell>
                  <TableCell className="text-right tabular-nums">{ms(m.avg_latency_ms)}</TableCell>
                  <TableCell className="text-right tabular-nums">{m.errors}</TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        </CardContent>
      </Card>

      <Card size="sm">
        <CardHeader><CardTitle>Recent requests</CardTitle></CardHeader>
        <CardContent>
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>Time</TableHead><TableHead>Model</TableHead><TableHead>Source</TableHead>
                <TableHead>Status</TableHead><TableHead className="text-right">In / Out</TableHead>
                <TableHead className="text-right">tok/s</TableHead><TableHead className="text-right">TTFT</TableHead>
                <TableHead className="text-right">Latency</TableHead><TableHead>App</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {reqs.data?.map((r) => (
                <TableRow key={r.id}>
                  <TableCell className="whitespace-nowrap">{new Date(r.ts * 1000).toLocaleTimeString()}</TableCell>
                  <TableCell>{r.model ?? "—"}<div className="text-xs text-muted-foreground">{r.endpoint}</div></TableCell>
                  <TableCell>{names.get(r.source_id) ?? r.source_id}</TableCell>
                  <TableCell>
                    <Badge variant={r.status >= 400 ? "destructive" : "secondary"} title={r.error ?? undefined}>{r.status}</Badge>
                  </TableCell>
                  <TableCell className="text-right tabular-nums">{num(r.prompt_tokens)} / {num(r.completion_tokens)}</TableCell>
                  <TableCell className="text-right tabular-nums">{num(r.gen_tps, 1)}</TableCell>
                  <TableCell className="text-right tabular-nums">{ms(r.ttft_ms)}</TableCell>
                  <TableCell className="text-right tabular-nums">{ms(r.latency_ms)}</TableCell>
                  <TableCell>{r.app ?? "—"}</TableCell>
                </TableRow>
              ))}
              {reqs.data?.length === 0 && (
                <TableRow>
                  <TableCell colSpan={9} className="text-center text-muted-foreground">
                    No requests recorded yet. Point your client at a source's gateway URL (Sources page), e.g.
                    <code className="ml-1">{location.origin}/gateway/&lt;source-id&gt;</code>.
                  </TableCell>
                </TableRow>
              )}
            </TableBody>
          </Table>
        </CardContent>
      </Card>
    </>
  )
}
