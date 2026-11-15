export function bytes(n: number | null | undefined): string {
  if (n == null) return "—"
  const units = ["B", "KB", "MB", "GB", "TB"]
  let i = 0
  let v = n
  while (v >= 1024 && i < units.length - 1) {
    v /= 1024
    i++
  }
  return `${v.toFixed(v >= 100 || i === 0 ? 0 : 1)} ${units[i]}`
}

export function num(n: number | null | undefined, digits = 0): string {
  if (n == null) return "—"
  return n.toLocaleString(undefined, { maximumFractionDigits: digits })
}

export function compact(n: number | null | undefined): string {
  if (n == null) return "—"
  return Intl.NumberFormat(undefined, { notation: "compact", maximumFractionDigits: 1 }).format(n)
}

export function ms(n: number | null | undefined): string {
  if (n == null) return "—"
  return n >= 1000 ? `${(n / 1000).toFixed(2)} s` : `${Math.round(n)} ms`
}

export function ago(ts: number | null | undefined, now = Date.now() / 1000): string {
  if (ts == null) return "never"
  const s = Math.max(0, Math.round(now - ts))
  if (s < 60) return `${s}s ago`
  if (s < 3600) return `${Math.floor(s / 60)}m ago`
  if (s < 86400) return `${Math.floor(s / 3600)}h ago`
  return `${Math.floor(s / 86400)}d ago`
}
