import { describe, it, expect } from 'vitest'
import { formatCategory } from '@/utils/format'

describe('formatCategory', () => {
  it('capitalises a single word', () => {
    expect(formatCategory('advertising')).toBe('Advertising')
  })

  it('converts underscore-separated slug to title case', () => {
    expect(formatCategory('ad_fraud')).toBe('Ad Fraud')
  })

  it('handles multiple underscores', () => {
    expect(formatCategory('some_long_category_name')).toBe('Some Long Category Name')
  })

  it('leaves already-capitalised input unchanged', () => {
    expect(formatCategory('Analytics')).toBe('Analytics')
  })

  it('handles single character categories', () => {
    expect(formatCategory('a')).toBe('A')
  })
})
