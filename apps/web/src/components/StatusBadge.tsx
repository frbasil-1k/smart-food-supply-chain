import { cn } from 'cn'

const TONE: Record<string, string> = {
  PENDING: 'border-line bg-oat-deep text-charcoal',
  SCHEDULED: 'border-forest/25 bg-forest/10 text-forest',
  COLLECTED: 'border-forest/25 bg-forest/10 text-forest',
  APPROVED: 'border-forest/25 bg-forest/10 text-forest',
  REJECTED: 'border-charcoal/25 bg-charcoal/10 text-charcoal',
  CANCELLED: 'border-line bg-oat-deep text-ink-soft',
  COMPLETED: 'border-forest/25 bg-forest/15 text-forest',
  PARTIALLY_DISTRIBUTED: 'border-terracotta/40 bg-terracotta/10 text-charcoal',
  PLANNED: 'border-line bg-oat-deep text-charcoal',
  IN_TRANSIT: 'border-forest/25 bg-forest/10 text-forest',
  DELIVERED: 'border-forest/25 bg-forest/15 text-forest',
  FAILED: 'border-terracotta/50 bg-terracotta/10 text-charcoal',
  PASSED: 'border-forest/25 bg-forest/10 text-forest',
  FAILED_INSPECTION: 'border-terracotta/50 bg-terracotta/10 text-charcoal',
  NEEDS_REVIEW: 'border-terracotta/40 bg-terracotta/10 text-charcoal',
  ACTIVE: 'border-forest/25 bg-forest/10 text-forest',
  INACTIVE: 'border-line bg-oat-deep text-ink-soft',
  SUSPENDED: 'border-charcoal/25 bg-charcoal/10 text-charcoal',
}

export function StatusBadge({ status }: { status: string | null | undefined }) {
  const value = status ?? 'UNKNOWN'
  return (
    <span
      className={cn(
        'inline-flex items-center rounded-[2px] border px-2 py-1 text-[10px] font-semibold tracking-[0.06em] uppercase',
        TONE[value] ?? 'border-line bg-oat-deep text-ink-soft',
      )}
    >
      {value.replaceAll('_', ' ')}
    </span>
  )
}
