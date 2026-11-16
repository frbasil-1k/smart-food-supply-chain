import { useId, type ReactNode } from 'react'
import { cn } from 'cn'

type PanelProps = {
  title: string
  description?: string
  action?: ReactNode
  accent?: boolean
  className?: string
  children: ReactNode
}

export function Panel({
  title,
  description,
  action,
  accent = false,
  className,
  children,
}: PanelProps) {
  const headingId = useId()

  return (
    <section
      aria-labelledby={headingId}
      className={cn(
        'rounded-[8px] border border-line bg-paper p-5 sm:p-6',
        accent && 'border-l-[3px] border-l-terracotta',
        className,
      )}
    >
      <header className="flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
        <div className="space-y-1.5">
          <h2
            id={headingId}
            className="font-heading text-[22px] leading-7 font-medium tracking-tight text-charcoal"
          >
            {title}
          </h2>
          {description ? (
            <p className="max-w-prose text-sm leading-6 text-ink-soft">
              {description}
            </p>
          ) : null}
        </div>
        {action ? <div className="shrink-0">{action}</div> : null}
      </header>
      <div className="mt-5">{children}</div>
    </section>
  )
}
