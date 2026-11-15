import { ago, bytes, compact, ms } from "./format"

describe("format", () => {
  it("formats bytes", () => {
    expect(bytes(null)).toBe("—")
    expect(bytes(512)).toBe("512 B")
    expect(bytes(1536)).toBe("1.5 KB")
    expect(bytes(4_700_000_000)).toBe("4.4 GB")
  })
  it("formats durations", () => {
    expect(ms(250.4)).toBe("250 ms")
    expect(ms(2500)).toBe("2.50 s")
    expect(ms(undefined)).toBe("—")
  })
  it("formats relative time", () => {
    expect(ago(null)).toBe("never")
    expect(ago(90, 100)).toBe("10s ago")
    expect(ago(0, 7200)).toBe("2h ago")
  })
  it("compacts numbers", () => {
    expect(compact(1500)).toBe("1.5K")
  })
})
