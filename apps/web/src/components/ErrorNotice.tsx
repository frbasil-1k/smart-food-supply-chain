import { AlertCircle, RefreshCw } from 'lucide-react'

import { Button } from '@/components/ui/button'
import { ApiRequestError } from '@/lib/api'

export function ErrorNotice({
  error,
  onRetry,
}: {
  error: unknown
  onRetry?: () => void
}) {
  const message =
    error instanceof ApiRequestError
      ? error.message
      : 'The request could not be completed.'
  return (
    <div
      role="alert"
      className="flex flex-col gap-3 rounded-[8px] border border-line border-l-[3px] border-l-terracotta bg-paper p-4 sm:flex-row sm:items-center sm:justify-between"
    >
      <p className="flex items-start gap-2 text-sm leading-6 text-charcoal">
        <AlertCircle aria-hidden="true" className="mt-0.5 size-4 shrink-0" />
        {message}
      </p>
      {onRetry ? (
        <Button type="button" variant="outline" size="sm" onClick={onRetry}>
          <RefreshCw aria-hidden="true" className="size-4" />
          Retry
        </Button>
      ) : null}
    </div>
  )
}
