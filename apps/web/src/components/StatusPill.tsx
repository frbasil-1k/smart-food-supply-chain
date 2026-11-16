import { type ReactNode } from 'react'
import { cn } from 'cn'

type StatusTone = 'success' | 'attention' | 'neutral'

type StatusPillProps = {
  tone?: StatusTone
  live?: boolean
  children: ReactNode
  className?: string
}

const toneClasses: Record<StatusTone, string> = {
  success: 'border-forest/20 bg-forest/10 text-forest',
  attention:
    'border-l-[3px] border-line border-l-terracotta bg-terracotta/10 text-forest',
  neutral: 'border-line bg-oat-deep text-ink-soft',
}

export function StatusPill({
  tone = 'neutral',
  live = false,
  children,
  className,
}: StatusPillProps) {
  return (
    <span
      className={cn(
        'inline-flex min-h-[22px] items-center gap-1.5 rounded-[2px] border px-2 py-0.5 text-[11px] font-semibold tracking-[0.04em] uppercase',
        toneClasses[tone],
        className,
      )}
      role={live ? 'status' : undefined}
      aria-live={live ? 'polite' : undefined}
    >
      <span
        aria-hidden="true"
        className="size-1.5 shrink-0 rounded-full bg-current"
      />
      {children}
    </span>
  )
}
