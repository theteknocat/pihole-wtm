/**
 * Replicates Chart.js's nice-max algorithm so a padding dataset can be sized
 * to fill exactly to the axis end rather than stopping at the data maximum.
 */
export function niceMax(dataMax: number, numTicks = 5): number {
  if (dataMax <= 0) return 10
  const roughStep = dataMax / (numTicks - 1)
  const exp = Math.floor(Math.log10(roughStep))
  const magnitude = Math.pow(10, exp)
  const normalized = roughStep / magnitude
  const niceStep = normalized <= 1 ? magnitude
    : normalized <= 2 ? 2 * magnitude
    : normalized <= 5 ? 5 * magnitude
    : 10 * magnitude
  return Math.ceil(dataMax / niceStep) * niceStep
}
