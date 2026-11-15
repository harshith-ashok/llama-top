import { QueryClient, QueryClientProvider } from "@tanstack/react-query"
import { render, screen } from "@testing-library/react"
import ModelsPage from "./models"

const row = (source: string, digest: string) => ({
  source_id: source, source_name: source, name: "llama3:8b", digest, size_bytes: 4_700_000_000,
  family: "llama", parameter_size: "8B", quantization: "Q4_0", loaded: source === "a", vram_bytes: null,
})

it("lists models and flags same-name models with different digests", async () => {
  vi.stubGlobal("fetch", vi.fn(async () =>
    new Response(JSON.stringify([row("a", "111111111111aaa"), row("b", "222222222222bbb")]), {
      headers: { "Content-Type": "application/json" },
    })))
  render(
    <QueryClientProvider client={new QueryClient()}>
      <ModelsPage />
    </QueryClientProvider>,
  )
  expect(await screen.findAllByText("llama3:8b")).toHaveLength(2)
  expect(screen.getAllByText("differs")).toHaveLength(2)
  expect(screen.getByText("Loaded")).toBeInTheDocument()
})
