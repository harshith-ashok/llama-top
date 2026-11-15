import { useState } from "react"
import { Chart } from "@/components/chart"
import { timeAxis } from "@/lib/chart-axes"
import { StatCard } from "@/components/stat-card"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table"
import { Tabs, TabsList, TabsTrigger } from "@/components/ui/tabs"
import { useLive } from "@/hooks/use-api"
import { api, type HistoryPoint } from "@/lib/api"
import { bytes } from "@/lib/format"

const RANGES = { "15": "15m", "60": "1h", "360": "6h", "1440": "24h" }

export default function HostPage() {
  const hosts = useLive(["hosts"], api.hosts)
  const [hostId, setHostId] = useState<string | null>(null)
  const [minutes, setMinutes] = useState("60")
  const host = hosts.data?.find((h) => h.id === hostId) ?? hosts.data?.[0]
  const history = useLive(["history", host?.id, minutes], () => api.history(host!.id, Number(minutes)), 10000)

  if (!host) return <p className="text-sm text-muted-foreground">Waiting for first host sample…</p>
  const c = host.current
  const pts = history.data ?? []
  const line = (name: string, f: (p: HistoryPoint) => number | null | undefined, max?: number) => ({
    xAxis: timeAxis,
    yAxis: { type: "value" as const, max, min: 0 },
    series: [{ name, type: "line" as const, showSymbol: false, areaStyle: { opacity: 0.15 },
      data: pts.map((p) => [p.ts * 1000, f(p) ?? null]) }],
  })
  const gpu0 = (p: HistoryPoint) => p.gpus?.[0]

  return (
    <>
      <div className="flex flex-wrap items-center gap-2">
        <Tabs value={host.id} onValueChange={(v) => setHostId(String(v))}>
          <TabsList>
            {hosts.data!.map((h) => (
              <TabsTrigger key={h.id} value={h.id}>{h.name}</TabsTrigger>
            ))}
          </TabsList>
        </Tabs>
        <Tabs value={minutes} onValueChange={(v) => setMinutes(String(v))} className="ml-auto">
          <TabsList>
            {Object.entries(RANGES).map(([k, v]) => (
              <TabsTrigger key={k} value={k}>{v}</TabsTrigger>
            ))}
          </TabsList>
        </Tabs>
      </div>

      <div className="grid grid-cols-2 gap-3 lg:grid-cols-4">
        <StatCard title="CPU" value={`${c?.cpu.percent.toFixed(0) ?? "—"}%`}
          hint={c?.cpu.load_avg ? `load ${c.cpu.load_avg.map((x) => x.toFixed(2)).join(" ")}` : undefined} />
        <StatCard title="Memory" value={`${c?.memory.percent.toFixed(0) ?? "—"}%`}
          hint={c && `${bytes(c.memory.used)} / ${bytes(c.memory.total)}`} />
        <StatCard title="GPU" value={c?.gpus?.[0] ? `${c.gpus[0].util}%` : "n/a"}
          hint={host.info.gpus?.[0]?.name ?? "No NVIDIA GPU detected"} />
        <StatCard title="VRAM" value={c?.gpus?.[0] ? bytes(c.gpus[0].vram_used) : "n/a"}
          hint={c?.gpus?.[0] && `of ${bytes(c.gpus[0].vram_total)}`} />
      </div>

      <div className="grid gap-3 lg:grid-cols-2">
        <ChartCard title="CPU %"><Chart option={line("CPU", (p) => p.cpu?.percent, 100)} /></ChartCard>
        <ChartCard title="Memory %"><Chart option={line("Memory", (p) => p.memory?.percent, 100)} /></ChartCard>
        {c?.gpus?.length ? (
          <>
            <ChartCard title="GPU utilization %"><Chart option={line("GPU", (p) => gpu0(p)?.util, 100)} /></ChartCard>
            <ChartCard title="VRAM used (GB)">
              <Chart option={line("VRAM", (p) => (gpu0(p) ? gpu0(p)!.vram_used / 1024 ** 3 : null))} />
            </ChartCard>
          </>
        ) : null}
        <ChartCard title="Network (MB/s ↓)">
          <Chart option={line("Download", (p) => (p.network ? p.network.rx_bps / 1e6 : null))} />
        </ChartCard>
      </div>

      <Card size="sm">
        <CardHeader><CardTitle>Top processes</CardTitle></CardHeader>
        <CardContent>
          <Table>
            <TableHeader>
              <TableRow><TableHead>PID</TableHead><TableHead>Name</TableHead>
                <TableHead className="text-right">CPU %</TableHead><TableHead className="text-right">Memory</TableHead></TableRow>
            </TableHeader>
            <TableBody>
              {c?.processes?.map((p) => (
                <TableRow key={p.pid}>
                  <TableCell>{p.pid}</TableCell><TableCell>{p.name}</TableCell>
                  <TableCell className="text-right tabular-nums">{p.cpu.toFixed(1)}</TableCell>
                  <TableCell className="text-right tabular-nums">{bytes(p.rss)}</TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        </CardContent>
      </Card>
      {host.kind === "local" && (
        <p className="text-xs text-muted-foreground">
          Showing metrics as seen from inside Docker. On macOS and Windows, Docker Desktop only exposes its Linux
          VM, not the physical machine; GPU telemetry needs NVIDIA drivers on a Linux host.
        </p>
      )}
    </>
  )
}

function ChartCard({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <Card size="sm">
      <CardHeader><CardTitle>{title}</CardTitle></CardHeader>
      <CardContent>{children}</CardContent>
    </Card>
  )
}
