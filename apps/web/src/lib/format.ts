export function formatKg(value: string | number | null | undefined): string {
  if (value === null || value === undefined || value === '') return '0.00 kg'
  const numeric = typeof value === 'number' ? value : Number(value)
  if (Number.isNaN(numeric)) return '0.00 kg'
  return `${numeric.toFixed(2)} kg`
}

export function titleCase(value: string): string {
  return value
    .toLowerCase()
    .split('_')
    .map((word) => word.charAt(0).toUpperCase() + word.slice(1))
    .join(' ')
}

export function formatNumber(value: number | null | undefined): string {
  return new Intl.NumberFormat('en-IN').format(value ?? 0)
}

export function shortId(value: number): string {
  return `#${String(value).padStart(4, '0')}`
}

export function errorMessage(error: unknown): string {
  if (error instanceof Error) return error.message
  return 'The request could not be completed.'
}
