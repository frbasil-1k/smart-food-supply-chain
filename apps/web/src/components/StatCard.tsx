import type { LucideIcon } from 'lucide-react'

type StatCardProps = {
  label: string
  value: string | number
  detail?: string
  icon: LucideIcon
}

export function StatCard({ label, value, detail, icon: Icon }: StatCardProps) {
  return (
    <div className="rounded-[8px] border border-line bg-paper p-4">
      <div className="flex items-center justify-between gap-3">
        <p className="text-xs font-semibold tracking-[0.08em] text-ink-soft uppercase">
          {label}
        </p>
        <Icon aria-hidden="true" className="size-4 text-forest" />
      </div>
      <p className="mt-3 font-heading text-3xl leading-9 font-medium text-charcoal">
        {value}
      </p>
      {detail ? <p className="mt-1 text-xs leading-5 text-ink-soft">{detail}</p> : null}
    </div>
  )
}
