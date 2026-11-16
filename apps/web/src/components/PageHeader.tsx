import type { ReactNode } from 'react'

type PageHeaderProps = {
  eyebrow: string
  title: string
  description?: string
  action?: ReactNode
}

export function PageHeader({ eyebrow, title, description, action }: PageHeaderProps) {
  return (
    <header className="flex flex-col gap-4 lg:flex-row lg:items-end lg:justify-between">
      <div className="max-w-3xl space-y-2">
        <p className="text-[11px] font-semibold tracking-[0.16em] text-forest uppercase">
          {eyebrow}
        </p>
        <h1 className="font-heading text-[30px] leading-[1.08] font-medium tracking-tight text-charcoal sm:text-[38px]">
          {title}
        </h1>
        {description ? (
          <p className="text-sm leading-6 text-ink-soft sm:text-base sm:leading-7">
            {description}
          </p>
        ) : null}
      </div>
      {action ? <div className="flex shrink-0 flex-wrap gap-2">{action}</div> : null}
    </header>
  )
}
