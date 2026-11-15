import { useState } from "react"
import { Badge } from "@/components/ui/badge"
import { Input } from "@/components/ui/input"
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table"
import { useLive } from "@/hooks/use-api"
import { api } from "@/lib/api"
import { bytes } from "@/lib/format"

export default function ModelsPage() {
  const [q, setQ] = useState("")
  const models = useLive(["models", q], () => api.models(q), 10000)
  const rows = models.data ?? []
  // Same name on different sources is not necessarily the same model: flag differing digests.
  const digests = new Map<string, Set<string | null>>()
  rows.forEach((m) => digests.set(m.name, (digests.get(m.name) ?? new Set()).add(m.digest)))

  return (
    <>
      <Input className="max-w-sm" placeholder="Search models…" value={q} onChange={(e) => setQ(e.target.value)} />
      <Table>
        <TableHeader>
          <TableRow>
            <TableHead>Model</TableHead><TableHead>Source</TableHead><TableHead>Family</TableHead>
            <TableHead>Params</TableHead><TableHead>Quant</TableHead>
            <TableHead className="text-right">Size</TableHead><TableHead>State</TableHead>
          </TableRow>
        </TableHeader>
        <TableBody>
          {rows.map((m) => (
            <TableRow key={`${m.source_id}:${m.name}`}>
              <TableCell className="font-medium">
                {m.name}
                {(digests.get(m.name)?.size ?? 0) > 1 && (
                  <Badge variant="outline" className="ml-2" title="Different digests across sources">differs</Badge>
                )}
                {m.digest && <div className="font-mono text-xs text-muted-foreground">{m.digest.slice(0, 12)}</div>}
              </TableCell>
              <TableCell>{m.source_name}</TableCell>
              <TableCell>{m.family ?? "—"}</TableCell>
              <TableCell>{m.parameter_size ?? "—"}</TableCell>
              <TableCell>{m.quantization ?? "—"}</TableCell>
              <TableCell className="text-right tabular-nums">{bytes(m.size_bytes)}</TableCell>
              <TableCell>
                {m.loaded ? <Badge>Loaded{m.vram_bytes ? ` · ${bytes(m.vram_bytes)} VRAM` : ""}</Badge> : <Badge variant="secondary">Idle</Badge>}
              </TableCell>
            </TableRow>
          ))}
          {rows.length === 0 && (
            <TableRow><TableCell colSpan={7} className="text-center text-muted-foreground">No models found.</TableCell></TableRow>
          )}
        </TableBody>
      </Table>
    </>
  )
}
