/**
 * Convert a raw category slug (e.g. "fingerprinting", "ad_fraud") to a
 * human-friendly label ("Fingerprinting", "Ad Fraud").
 */
export function formatCategory(cat: string): string {
  return cat.replace(/_/g, ' ').replace(/\b\w/g, c => c.toUpperCase())
}
