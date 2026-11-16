import { Link } from 'react-router-dom'
import { ArrowLeft } from 'lucide-react'
import { cn } from 'cn'

import { buttonVariants } from '@/components/ui/button'

export function NotFoundPage() {
  return (
    <div className="max-w-2xl space-y-5 py-8 sm:py-16">
      <p className="text-[11px] font-semibold tracking-[0.16em] text-forest uppercase">
        404 · Not found
      </p>
      <h1 className="font-heading text-[32px] leading-[1.08] font-medium tracking-tight text-charcoal sm:text-[40px]">
        This page is not part of the workspace
      </h1>
      <p className="max-w-xl text-sm leading-6 text-ink-soft sm:text-base sm:leading-7">
        The address may be mistyped, or the screen may not have been built yet.
        Return to the overview to continue.
      </p>
      <Link
        to="/"
        className={cn(buttonVariants({ variant: 'outline' }), 'h-10 px-4')}
      >
        <ArrowLeft aria-hidden="true" className="size-4" />
        Back to overview
      </Link>
    </div>
  )
}
