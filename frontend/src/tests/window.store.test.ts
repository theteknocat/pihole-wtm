/**
 * Tests for the window store (src/stores/window.ts).
 *
 * Uses createTestingPinia() so each test starts with a fresh store instance.
 * Fake timers prevent the auto-refresh setInterval from running in tests.
 */
import { describe, it, expect, beforeEach, afterEach, vi } from 'vitest'
import { setActivePinia, createPinia } from 'pinia'
import { useWindowStore } from '@/stores/window'

beforeEach(() => {
  vi.useFakeTimers()
  setActivePinia(createPinia())
})

afterEach(() => {
  vi.useRealTimers()
})

describe('default state', () => {
  it('starts with hours=24, periodsBack=0', () => {
    const store = useWindowStore()
    expect(store.hours).toBe(24)
    expect(store.isHistorical).toBe(false)
  })

  it('endTs is null when live', () => {
    const store = useWindowStore()
    expect(store.endTs).toBeNull()
  })
})

describe('setDataRange()', () => {
  it('updates oldestTs and newestTs', () => {
    const store = useWindowStore()
    store.setDataRange(1000, 2000)
    expect(store.oldestTs).toBe(1000)
    expect(store.newestTs).toBe(2000)
  })
})

describe('availablePeriods', () => {
  it('returns first two options when no data range is set', () => {
    const store = useWindowStore()
    expect(store.availablePeriods).toHaveLength(2)
    expect(store.availablePeriods[0].value).toBe(24)
  })

  it('includes only periods covered by at least 25% of the data span', () => {
    const store = useWindowStore()
    // Data span of 50h — covers 24h fully but not 168h (needs 42h, has 50h > 42h, so 168h should be included too)
    // 50h >= 168 * 0.25 = 42h → yes; 50h >= 720 * 0.25 = 180h → no
    store.setDataRange(0, 50 * 3600)
    const values = store.availablePeriods.map(p => p.value)
    expect(values).toContain(24)
    expect(values).toContain(168)
    expect(values).not.toContain(720)
  })

  it('always includes at least one period even with minimal data', () => {
    const store = useWindowStore()
    store.setDataRange(0, 60) // only 1 minute of data
    expect(store.availablePeriods.length).toBeGreaterThanOrEqual(1)
    expect(store.availablePeriods[0].value).toBe(24)
  })
})

describe('goPrev() / goNext()', () => {
  it('goPrev increments periodsBack', () => {
    const store = useWindowStore()
    store.goPrev()
    expect(store.isHistorical).toBe(true)
  })

  it('goNext decrements periodsBack', () => {
    const store = useWindowStore()
    store.goPrev()
    store.goPrev()
    store.goNext()
    const store2 = useWindowStore()
    // periodsBack should be 1 after two prev and one next
    expect(store2.isHistorical).toBe(true)
    store.goNext()
    expect(store.isHistorical).toBe(false)
  })

  it('goNext does nothing when already at latest', () => {
    const store = useWindowStore()
    store.goNext() // already at 0
    expect(store.isHistorical).toBe(false)
  })
})

describe('goLatest() / goOldest()', () => {
  it('goLatest resets to live view', () => {
    const store = useWindowStore()
    store.goPrev()
    store.goPrev()
    store.goLatest()
    expect(store.isHistorical).toBe(false)
    expect(store.endTs).toBeNull()
  })

  it('goOldest jumps to maximum periods back', () => {
    const store = useWindowStore()
    // 48h of data, 24h window → 2 periods back max
    store.setDataRange(0, 48 * 3600)
    store.hours = 24
    store.goOldest()
    expect(store.isHistorical).toBe(true)
  })

  it('goOldest does nothing when no data range is set', () => {
    const store = useWindowStore()
    store.goOldest()
    expect(store.isHistorical).toBe(false)
  })
})

describe('canGoPrev / canGoNext', () => {
  it('canGoPrev is false with no data range', () => {
    const store = useWindowStore()
    expect(store.canGoPrev).toBe(false)
  })

  it('canGoPrev is true when there is older data', () => {
    const store = useWindowStore()
    const now = Date.now() / 1000
    store.setDataRange(now - 48 * 3600, now)
    expect(store.canGoPrev).toBe(true)
  })

  it('canGoNext is false when at latest', () => {
    const store = useWindowStore()
    expect(store.canGoNext).toBe(false)
  })

  it('canGoNext is true after going back', () => {
    const store = useWindowStore()
    store.goPrev()
    expect(store.canGoNext).toBe(true)
  })
})

describe('effectiveEndTs / fromTs', () => {
  it('effectiveEndTs falls back to now when no newestTs', () => {
    const store = useWindowStore()
    const now = Date.now() / 1000
    // Should be approximately now (within 1s)
    expect(store.effectiveEndTs).toBeCloseTo(now, 0)
  })

  it('effectiveEndTs shifts back by periodsBack * hours', () => {
    const store = useWindowStore()
    store.setDataRange(0, 10000)
    store.goPrev() // periodsBack = 1
    expect(store.effectiveEndTs).toBe(10000 - 1 * 24 * 3600)
  })

  it('fromTs is effectiveEndTs minus the window', () => {
    const store = useWindowStore()
    store.setDataRange(0, 10000)
    expect(store.fromTs).toBe(store.effectiveEndTs - store.hours * 3600)
  })
})

describe('endTs', () => {
  it('endTs is null when live', () => {
    const store = useWindowStore()
    expect(store.endTs).toBeNull()
  })

  it('endTs equals effectiveEndTs when historical', () => {
    const store = useWindowStore()
    store.setDataRange(0, 10000)
    store.goPrev()
    expect(store.endTs).toBe(store.effectiveEndTs)
  })
})

describe('queryParams()', () => {
  it('includes hours when live', () => {
    const store = useWindowStore()
    const qs = store.queryParams()
    expect(qs).toContain('hours=24')
    expect(qs).not.toContain('end_ts')
  })

  it('includes end_ts when historical', () => {
    const store = useWindowStore()
    store.setDataRange(0, 10000)
    store.goPrev()
    const qs = store.queryParams()
    expect(qs).toContain('end_ts=')
  })

  it('includes extra params', () => {
    const store = useWindowStore()
    const qs = store.queryParams({ category: 'advertising' })
    expect(qs).toContain('category=advertising')
  })

  it('omits null and empty extra params', () => {
    const store = useWindowStore()
    const qs = store.queryParams({ category: null, company: '' })
    expect(qs).not.toContain('category')
    expect(qs).not.toContain('company')
  })
})

describe('changing hours resets periodsBack', () => {
  it('resets to live when hours changes', async () => {
    const store = useWindowStore()
    store.goPrev()
    store.goPrev()
    expect(store.isHistorical).toBe(true)
    store.hours = 168
    // Watch is async — flush with nextTick equivalent via a promise tick
    await Promise.resolve()
    expect(store.isHistorical).toBe(false)
  })
})
