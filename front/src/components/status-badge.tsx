import { Badge } from "@/components/ui/badge"
import type { Status } from "@/lib/api"
import { cn } from "@/lib/utils"

const styles: Record<Status, string> = {
  online: "bg-emerald-500/15 text-emerald-600 dark:text-emerald-400",
  degraded: "bg-amber-500/15 text-amber-600 dark:text-amber-400",
  offline: "bg-red-500/15 text-red-600 dark:text-red-400",
  unknown: "bg-muted text-muted-foreground",
  disabled: "bg-muted text-muted-foreground",
}

export function StatusBadge({ status }: { status: Status }) {
  return (
    <Badge variant="secondary" className={cn("capitalize", styles[status])}>
      <span className="mr-1 inline-block size-1.5 rounded-full bg-current" />
      {status}
    </Badge>
  )
}
