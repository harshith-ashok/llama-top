import { useMutation, useQueryClient } from "@tanstack/react-query"
import { Plus, RefreshCw, Server, Trash2 } from "lucide-react"
import { useState } from "react"
import { Link } from "react-router-dom"
import { toast } from "sonner"
import { StatusBadge } from "@/components/status-badge"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import {
  Dialog, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle, DialogTrigger,
} from "@/components/ui/dialog"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select"
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table"
import { useLive } from "@/hooks/use-api"
import { api, type Source, type SourceType } from "@/lib/api"
import { ago, ms } from "@/lib/format"

const PRESETS: Record<SourceType, { label: string; url: string; hint: string }> = {
  ollama: {
    label: "Ollama",
    url: "http://host.docker.internal:11434",
    hint: "Server root. From Docker, host.docker.internal reaches Ollama running on this machine.",
  },
  openai: {
    label: "OpenAI-compatible",
    url: "https://api.openai.com/v1",
    hint: "Base URL including the API path (e.g. …/v1) — vLLM, LM Studio, llama.cpp, OpenRouter, …",
  },
}

export default function SourcesPage() {
  const qc = useQueryClient()
  const sources = useLive(["sources"], api.sources)
  const refresh = () => qc.invalidateQueries({ queryKey: ["sources"] })
  const check = useMutation({
    mutationFn: api.checkSource,
    onSuccess: refresh,
    onError: (e: Error) => toast.error(e.message),
  })
  const remove = useMutation({
    mutationFn: api.deleteSource,
    onSuccess: () => { toast.success("Source removed"); refresh() },
    onError: (e: Error) => toast.error(e.message),
  })
  const toggle = useMutation({
    mutationFn: (s: Source) => api.patchSource(s.id, { enabled: !s.enabled }),
    onSuccess: refresh,
    onError: (e: Error) => toast.error(e.message),
  })

  return (
    <>
      <div className="flex items-center justify-between">
        <p className="text-sm text-muted-foreground">
          Register inference servers. Route client traffic through a source's gateway URL to record requests.
        </p>
        <AddSource onDone={refresh} />
      </div>
      <Table>
        <TableHeader>
          <TableRow>
            <TableHead>Name</TableHead><TableHead>Status</TableHead><TableHead>Endpoint</TableHead>
            <TableHead>Gateway URL</TableHead><TableHead>Latency</TableHead><TableHead>Last seen</TableHead>
            <TableHead className="text-right">Actions</TableHead>
          </TableRow>
        </TableHeader>
        <TableBody>
          {sources.data?.map((s) => (
            <TableRow key={s.id}>
              <TableCell>
                <div className="font-medium">{s.name}</div>
                <div className="flex gap-1 pt-1">
                  <Badge variant="outline">{PRESETS[s.type].label}</Badge>
                  {s.tags.map((t) => <Badge key={t} variant="secondary">{t}</Badge>)}
                </div>
              </TableCell>
              <TableCell>
                <StatusBadge status={s.status} />
                {s.error && <div className="pt-1 text-xs text-red-500">{s.error}</div>}
                {s.agent_url && (
                  <div className="pt-1 text-xs">
                    {s.agent_error ? (
                      <span className="text-red-500">Host agent: {s.agent_error}</span>
                    ) : (
                      <Link to="/host" className="text-muted-foreground underline">Host metrics</Link>
                    )}
                  </div>
                )}
              </TableCell>
              <TableCell className="max-w-56 truncate">{s.base_url}</TableCell>
              <TableCell><code className="text-xs">{location.origin}{s.gateway_path}</code></TableCell>
              <TableCell>{ms(s.latency_ms)}</TableCell>
              <TableCell>{ago(s.last_seen)}</TableCell>
              <TableCell className="space-x-1 text-right">
                <AgentDialog source={s} onDone={refresh} />
                <Button size="icon" variant="ghost" aria-label="Check health" onClick={() => check.mutate(s.id)}>
                  <RefreshCw />
                </Button>
                <Button size="sm" variant="outline" onClick={() => toggle.mutate(s)}>
                  {s.enabled ? "Disable" : "Enable"}
                </Button>
                <Button size="icon" variant="ghost" aria-label="Remove source"
                  onClick={() => confirm(`Remove ${s.name}?`) && remove.mutate(s.id)}>
                  <Trash2 />
                </Button>
              </TableCell>
            </TableRow>
          ))}
          {sources.data?.length === 0 && (
            <TableRow><TableCell colSpan={7} className="text-center text-muted-foreground">No sources registered.</TableCell></TableRow>
          )}
        </TableBody>
      </Table>
    </>
  )
}

function AddSource({ onDone }: { onDone: () => void }) {
  const [open, setOpen] = useState(false)
  const [type, setType] = useState<SourceType>("ollama")
  const [name, setName] = useState("")
  const [url, setUrl] = useState(PRESETS.ollama.url)
  const [key, setKey] = useState("")
  const [tags, setTags] = useState("")
  const [agentUrl, setAgentUrl] = useState("")
  const [agentToken, setAgentToken] = useState("")

  const add = useMutation({
    mutationFn: api.addSource,
    onSuccess: (s) => {
      toast[s.status === "online" ? "success" : "warning"](`${s.name}: ${s.status}${s.error ? ` (${s.error})` : ""}`)
      setOpen(false)
      setName(""); setKey(""); setTags(""); setAgentUrl(""); setAgentToken("")
      onDone()
    },
    onError: (e: Error) => toast.error(e.message),
  })

  return (
    <Dialog open={open} onOpenChange={setOpen}>
      <DialogTrigger render={<Button />}><Plus /> Add source</DialogTrigger>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>Add source</DialogTitle>
          <DialogDescription>{PRESETS[type].hint}</DialogDescription>
        </DialogHeader>
        <form
          className="space-y-3"
          onSubmit={(e) => {
            e.preventDefault()
            add.mutate({
              name, type, base_url: url, api_key: key || undefined,
              tags: tags.split(",").map((t) => t.trim()).filter(Boolean),
              agent_url: agentUrl || undefined,
              agent_token: agentToken || undefined,
            })
          }}
        >
          <div className="space-y-1">
            <Label htmlFor="type">Type</Label>
            <Select value={type} onValueChange={(v) => { const t = v as SourceType; setType(t); setUrl(PRESETS[t].url) }}>
              <SelectTrigger id="type" className="w-full">
                <SelectValue>{PRESETS[type].label}</SelectValue>
              </SelectTrigger>
              <SelectContent>
                {(Object.keys(PRESETS) as SourceType[]).map((t) => (
                  <SelectItem key={t} value={t}>{PRESETS[t].label}</SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>
          <div className="space-y-1">
            <Label htmlFor="name">Name</Label>
            <Input id="name" required value={name} onChange={(e) => setName(e.target.value)} placeholder="Workstation Ollama" />
          </div>
          <div className="space-y-1">
            <Label htmlFor="url">Base URL</Label>
            <Input id="url" required type="url" value={url} onChange={(e) => setUrl(e.target.value)} />
          </div>
          <div className="space-y-1">
            <Label htmlFor="key">API key (optional)</Label>
            <Input id="key" type="password" autoComplete="off" value={key} onChange={(e) => setKey(e.target.value)} />
          </div>
          <div className="space-y-1">
            <Label htmlFor="tags">Tags (comma separated)</Label>
            <Input id="tags" value={tags} onChange={(e) => setTags(e.target.value)} placeholder="local, gpu" />
          </div>
          <div className="space-y-2 rounded-md border p-3">
            <p className="text-xs text-muted-foreground">
              Optional: show CPU / RAM / GPU for the machine this source runs on. Run the host agent there
              (see README) and enter its address, e.g. http://100.74.98.40:9100
            </p>
            <div className="space-y-1">
              <Label htmlFor="agent-url">Host agent URL</Label>
              <Input id="agent-url" type="url" value={agentUrl} onChange={(e) => setAgentUrl(e.target.value)} />
            </div>
            <div className="space-y-1">
              <Label htmlFor="agent-token">Host agent token</Label>
              <Input id="agent-token" type="password" autoComplete="off" required={!!agentUrl}
                value={agentToken} onChange={(e) => setAgentToken(e.target.value)} />
            </div>
          </div>
          <DialogFooter>
            <Button type="submit" disabled={add.isPending}>{add.isPending ? "Connecting…" : "Add source"}</Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  )
}

function AgentDialog({ source, onDone }: { source: Source; onDone: () => void }) {
  const [open, setOpen] = useState(false)
  const [url, setUrl] = useState(source.agent_url ?? "")
  const [token, setToken] = useState("")
  const save = useMutation({
    mutationFn: () => api.patchSource(source.id, { agent_url: url, agent_token: token || undefined }),
    onSuccess: (s) => {
      toast[s.agent_error ? "warning" : "success"](s.agent_error ? `Host agent: ${s.agent_error}` : "Host agent connected")
      setOpen(false)
      setToken("")
      onDone()
    },
    onError: (e: Error) => toast.error(e.message),
  })
  const detach = useMutation({
    mutationFn: () => api.patchSource(source.id, { clear_agent: true }),
    onSuccess: () => { setOpen(false); setUrl(""); onDone() },
    onError: (e: Error) => toast.error(e.message),
  })
  return (
    <Dialog open={open} onOpenChange={setOpen}>
      <DialogTrigger render={<Button size="icon" variant="ghost" aria-label="Host agent" />}>
        <Server />
      </DialogTrigger>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>Host agent for {source.name}</DialogTitle>
          <DialogDescription>
            Pulls CPU / RAM / GPU metrics from the agent running on this source's machine.
          </DialogDescription>
        </DialogHeader>
        <form className="space-y-3" onSubmit={(e) => { e.preventDefault(); save.mutate() }}>
          <div className="space-y-1">
            <Label htmlFor={`au-${source.id}`}>Agent URL</Label>
            <Input id={`au-${source.id}`} required type="url" value={url} placeholder="http://100.74.98.40:9100"
              onChange={(e) => setUrl(e.target.value)} />
          </div>
          <div className="space-y-1">
            <Label htmlFor={`at-${source.id}`}>Token{source.agent_url ? " (leave blank to keep)" : ""}</Label>
            <Input id={`at-${source.id}`} type="password" autoComplete="off" required={!source.agent_url}
              value={token} onChange={(e) => setToken(e.target.value)} />
          </div>
          <DialogFooter>
            {source.agent_url && (
              <Button type="button" variant="outline" onClick={() => detach.mutate()}>Detach</Button>
            )}
            <Button type="submit" disabled={save.isPending}>{save.isPending ? "Connecting…" : "Save"}</Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  )
}
