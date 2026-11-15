import { lazy, Suspense } from "react"
import { Activity, Boxes, Cpu, LayoutDashboard, Moon, Plug, Sun } from "lucide-react"
import { useTheme } from "next-themes"
import { NavLink, Route, Routes, useLocation } from "react-router-dom"
import {
  Sidebar,
  SidebarContent,
  SidebarGroup,
  SidebarGroupContent,
  SidebarGroupLabel,
  SidebarHeader,
  SidebarInset,
  SidebarMenu,
  SidebarMenuButton,
  SidebarMenuItem,
  SidebarProvider,
  SidebarTrigger,
} from "@/components/ui/sidebar"
import { Button } from "@/components/ui/button"
import { Toaster } from "@/components/ui/sonner"

const OverviewPage = lazy(() => import("@/pages/overview"))
const HostPage = lazy(() => import("@/pages/host"))
const RequestsPage = lazy(() => import("@/pages/requests"))
const ModelsPage = lazy(() => import("@/pages/models"))
const SourcesPage = lazy(() => import("@/pages/sources"))

const nav = [
  { to: "/", label: "Overview", icon: LayoutDashboard, group: "Monitor" },
  { to: "/host", label: "Host", icon: Cpu, group: "Monitor" },
  { to: "/requests", label: "Requests", icon: Activity, group: "Inference" },
  { to: "/models", label: "Models", icon: Boxes, group: "Inference" },
  { to: "/sources", label: "Sources", icon: Plug, group: "Control" },
]

function ThemeToggle() {
  const { resolvedTheme, setTheme } = useTheme()
  return (
    <Button
      variant="ghost"
      size="icon"
      aria-label="Toggle theme"
      onClick={() => setTheme(resolvedTheme === "dark" ? "light" : "dark")}
    >
      {resolvedTheme === "dark" ? <Sun /> : <Moon />}
    </Button>
  )
}

export default function App() {
  const { pathname } = useLocation()
  const groups = [...new Set(nav.map((n) => n.group))]
  const title = nav.find((n) => n.to === pathname)?.label ?? ""
  return (
    <SidebarProvider>
      <Sidebar>
        <SidebarHeader className="px-4 py-3 text-base font-semibold">🦙 llama-top</SidebarHeader>
        <SidebarContent>
          {groups.map((g) => (
            <SidebarGroup key={g}>
              <SidebarGroupLabel>{g}</SidebarGroupLabel>
              <SidebarGroupContent>
                <SidebarMenu>
                  {nav
                    .filter((n) => n.group === g)
                    .map((n) => (
                      <SidebarMenuItem key={n.to}>
                        <SidebarMenuButton
                          isActive={pathname === n.to}
                          render={<NavLink to={n.to} />}
                        >
                          <n.icon />
                          <span>{n.label}</span>
                        </SidebarMenuButton>
                      </SidebarMenuItem>
                    ))}
                </SidebarMenu>
              </SidebarGroupContent>
            </SidebarGroup>
          ))}
        </SidebarContent>
      </Sidebar>
      <SidebarInset>
        <header className="flex h-12 items-center gap-2 border-b px-4">
          <SidebarTrigger />
          <h1 className="text-sm font-medium">{title}</h1>
          <div className="ml-auto">
            <ThemeToggle />
          </div>
        </header>
        <main className="flex-1 space-y-6 p-4 md:p-6">
          <Suspense fallback={<p className="text-sm text-muted-foreground">Loading…</p>}>
          <Routes>
            <Route path="/" element={<OverviewPage />} />
            <Route path="/host" element={<HostPage />} />
            <Route path="/requests" element={<RequestsPage />} />
            <Route path="/models" element={<ModelsPage />} />
            <Route path="/sources" element={<SourcesPage />} />
          </Routes>
          </Suspense>
        </main>
      </SidebarInset>
      <Toaster />
    </SidebarProvider>
  )
}
