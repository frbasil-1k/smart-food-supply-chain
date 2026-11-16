import type { ReactNode } from 'react'
import type { LucideIcon } from 'lucide-react'

type EmptyStateProps = {
  icon: LucideIcon
  title: string
  body: string
  action?: ReactNode
}

export function EmptyState({ icon: Icon, title, body, action }: EmptyStateProps) {
  return (
    <div className="flex flex-col items-start gap-4 rounded-[8px] border border-dashed border-line-strong bg-paper/60 p-6 sm:flex-row sm:items-center">
      <span className="flex size-11 shrink-0 items-center justify-center rounded-[8px] bg-oat-deep text-forest">
        <Icon aria-hidden="true" className="size-5" />
      </span>
      <div className="flex-1 space-y-1">
        <h2 className="font-heading text-xl leading-6 font-medium text-charcoal">{title}</h2>
        <p className="max-w-2xl text-sm leading-6 text-ink-soft">{body}</p>
      </div>
      {action ? <div className="shrink-0">{action}</div> : null}
    </div>
  )
}
