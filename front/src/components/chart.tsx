import type { EChartsOption } from "echarts"
import ReactECharts from "echarts-for-react"
import { useTheme } from "next-themes"

/** Thin ECharts wrapper: transparent background, theme-aware text and compact grid. */
export function Chart({ option, height = 220 }: { option: EChartsOption; height?: number }) {
  const { resolvedTheme } = useTheme()
  const merged: EChartsOption = {
    backgroundColor: "transparent",
    grid: { left: 48, right: 16, top: 24, bottom: 28 },
    tooltip: { trigger: "axis" },
    color: ["#3b82f6", "#10b981", "#f59e0b", "#ef4444", "#8b5cf6"],
    ...option,
  }
  return (
    <ReactECharts
      option={merged}
      theme={resolvedTheme === "dark" ? "dark" : undefined}
      style={{ height }}
      notMerge
    />
  )
}
