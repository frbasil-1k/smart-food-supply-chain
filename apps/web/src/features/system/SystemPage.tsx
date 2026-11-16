import { RefreshCw } from 'lucide-react'
import { cn } from 'cn'

import { Panel } from '@/components/Panel'
import { StatusPill } from '@/components/StatusPill'
import { buttonVariants } from '@/components/ui/button'
import { useHealth } from '@/features/system/useHealth'
import { formatLocalDateTime } from '@/lib/datetime'

export function SystemPage() {
  const healthQuery = useHealth()
  const healthResult = healthQuery.isError ? undefined : healthQuery.data
  const health = healthResult?.data

  const apiLabel = healthQuery.isPending
    ? 'Checking'
    : healthQuery.isError
      ? 'Unreachable'
      : 'Online'
  const apiTone = healthQuery.isPending
    ? 'neutral'
    : healthQuery.isError
      ? 'attention'
      : 'success'

  return (
    <div className="space-y-8">
      <header className="max-w-3xl space-y-3">
        <p className="text-[11px] font-semibold tracking-[0.16em] text-forest uppercase">
          Operations foundation
        </p>
        <h1 className="font-heading text-[32px] leading-[1.08] font-medium tracking-tight text-charcoal sm:text-[40px]">
          System status
        </h1>
        <p className="text-sm leading-6 text-ink-soft sm:text-base sm:leading-7">
          Runtime checks for the application foundation. API values come from
          the live liveness endpoint; nothing here is cached or pre-filled.
        </p>
      </header>

      <div className="grid gap-5 lg:grid-cols-[minmax(0,1.4fr)_minmax(0,1fr)]">
        <Panel
          title="API health"
          description="GET /api/health returns the API envelope and a correlation ID."
          action={
            <button
              type="button"
              onClick={() => void healthQuery.refetch()}
              disabled={healthQuery.isFetching}
              className={cn(
                buttonVariants({ variant: 'outline', size: 'sm' }),
                'h-9 px-3',
              )}
            >
              <RefreshCw
                aria-hidden="true"
                className={cn(
                  'size-4',
                  healthQuery.isFetching && 'animate-spin',
                )}
              />
              Refresh
            </button>
          }
        >
          <dl className="divide-y divide-line">
            <div className="flex flex-col gap-2 py-3 first:pt-0 sm:flex-row sm:items-center sm:justify-between">
              <dt className="text-sm font-medium text-charcoal">Status</dt>
              <dd>
                <StatusPill tone={apiTone} live>
                  {apiLabel}
                </StatusPill>
              </dd>
            </div>
            <div className="flex flex-col gap-2 py-3 sm:flex-row sm:items-baseline sm:justify-between">
              <dt className="text-sm text-ink-soft">Endpoint</dt>
              <dd className="font-mono text-xs text-charcoal">/api/health</dd>
            </div>
            <div className="flex flex-col gap-2 py-3 sm:flex-row sm:items-baseline sm:justify-between">
              <dt className="text-sm text-ink-soft">Service</dt>
              <dd className="text-sm font-medium text-charcoal">
                {health ? `sfc-api ${health.version}` : 'Unavailable'}
              </dd>
            </div>
            <div className="flex flex-col gap-2 py-3 sm:flex-row sm:items-baseline sm:justify-between">
              <dt className="text-sm text-ink-soft">Environment</dt>
              <dd className="text-sm font-medium text-charcoal">
                {health?.environment ?? 'Unavailable'}
              </dd>
            </div>
            <div className="flex flex-col gap-2 py-3 sm:flex-row sm:items-baseline sm:justify-between">
              <dt className="text-sm text-ink-soft">Timezone</dt>
              <dd className="text-sm font-medium text-charcoal">
                {health?.timezone ?? 'Unavailable'}
              </dd>
            </div>
            <div className="flex flex-col gap-2 py-3 sm:flex-row sm:items-baseline sm:justify-between">
              <dt className="text-sm text-ink-soft">Server time</dt>
              <dd className="text-sm font-medium text-charcoal">
                {health ? formatLocalDateTime(health.time) : 'Unavailable'}
              </dd>
            </div>
            <div className="flex flex-col gap-2 py-3 last:pb-0 sm:flex-row sm:items-baseline sm:justify-between">
              <dt className="text-sm text-ink-soft">Request ID</dt>
              <dd className="max-w-full font-mono text-xs break-all text-charcoal">
                {healthResult?.requestId ?? 'Unavailable'}
              </dd>
            </div>
          </dl>

          {healthQuery.isError ? (
            <p className="mt-5 border-t border-line pt-4 text-sm leading-6 text-ink-soft">
              The API did not answer. Check the Flask server in{' '}
              <code className="font-mono text-xs">apps/api</code>, then refresh.
            </p>
          ) : null}
        </Panel>

        <Panel
          title="Data boundary"
          description="What this foundation does and does not touch."
        >
          <ul className="space-y-5">
            <li className="space-y-1 border-l-[3px] border-l-terracotta pl-3">
              <p className="text-sm font-semibold text-charcoal">
                No database connection
              </p>
              <p className="text-sm leading-6 text-ink-soft">
                Stage A never opens a MySQL connection, runs a query, or applies
                a schema change.
              </p>
            </li>
            <li className="space-y-1">
              <p className="text-sm font-semibold text-charcoal">
                Development target
              </p>
              <p className="text-sm leading-6 text-ink-soft">
                The future database of record is{' '}
                <code className="font-mono text-xs break-all">
                  smart_food_supply_chain_dev
                </code>
                . The original database and its test clone remain untouched.
              </p>
            </li>
            <li className="space-y-1">
              <p className="text-sm font-semibold text-charcoal">
                Frontend build
              </p>
              <p className="text-sm leading-6 text-ink-soft">
                Running in{' '}
                <code className="font-mono text-xs">
                  {import.meta.env.MODE}
                </code>{' '}
                mode. API calls use the same-origin{' '}
                <code className="font-mono text-xs">/api</code> path, proxied to
                Flask during development.
              </p>
            </li>
          </ul>
        </Panel>
      </div>
    </div>
  )
}
