import { useQuery } from '@tanstack/react-query'
import { Link } from 'react-router-dom'
import { History, PackageCheck } from 'lucide-react'

import { EmptyState } from '@/components/EmptyState'
import { ErrorNotice } from '@/components/ErrorNotice'
import { PageHeader } from '@/components/PageHeader'
import { Panel } from '@/components/Panel'
import { StatCard } from '@/components/StatCard'
import { StatusBadge } from '@/components/StatusBadge'
import { buttonVariants } from '@/components/ui/button'
import { useAuth } from '@/features/auth/AuthProvider'
import { apiGet, apiGetPaged } from '@/lib/api'
import { formatLocalDateTime } from '@/lib/datetime'
import { formatKg, formatNumber } from '@/lib/format'
import type { Delivery, DriverReport } from '@/lib/types'
import { cn } from 'cn'

export function DriverHistoryPage() {
  const { user } = useAuth()
  const deliveriesQuery = useQuery({
    queryKey: ['driver-history'],
    queryFn: ({ signal }) => apiGetPaged<Delivery>('/api/deliveries?page_size=100', signal),
  })
  const performanceQuery = useQuery({
    queryKey: ['driver-performance'],
    queryFn: ({ signal }) => apiGet<DriverReport[]>('/api/reports/drivers', signal),
  })
  const rows = (deliveriesQuery.data?.data ?? []).filter((row) =>
    ['DELIVERED', 'FAILED', 'CANCELLED'].includes(row.status),
  )
  const performance = performanceQuery.data?.[0]

  return (
    <div className="space-y-7">
      <PageHeader
        eyebrow="Driver workflow"
        title="Delivery history"
        description="Completed, failed, and cancelled deliveries attributed to you."
      />
      {deliveriesQuery.isError ? <ErrorNotice error={deliveriesQuery.error} onRetry={() => void deliveriesQuery.refetch()} /> : null}
      {performanceQuery.isError ? <ErrorNotice error={performanceQuery.error} onRetry={() => void performanceQuery.refetch()} /> : null}

      <div className="grid gap-4 sm:grid-cols-3">
        <StatCard label="Completed deliveries" value={performance ? formatNumber(performance.completed_deliveries) : '—'} icon={PackageCheck} />
        <StatCard label="Completed kilograms" value={performance ? formatKg(performance.delivered_quantity_kg) : '—'} icon={History} />
        <StatCard label="Assigned routes" value={performance ? formatNumber(performance.assigned_routes) : '—'} icon={History} />
      </div>

      <Panel title="Past deliveries" description="A failed delivery is terminal in this application.">
        {deliveriesQuery.isPending ? <p className="text-sm text-ink-soft">Loading history…</p> : null}
        {deliveriesQuery.data ? (
          rows.length === 0 ? (
            <EmptyState icon={History} title="No completed deliveries" body="Finished deliveries appear here with their terminal status." />
          ) : (
            <ul className="divide-y divide-line">
              {rows.map((delivery) => (
                <li key={delivery.delivery_id} className="flex flex-wrap items-center justify-between gap-3 py-4 first:pt-0 last:pb-0">
                  <div>
                    <p className="font-semibold text-charcoal">Delivery #{delivery.delivery_id}</p>
                    <p className="mt-1 text-sm text-ink-soft">{delivery.recipient_branch.branch_name} · {formatLocalDateTime(delivery.delivered_at ?? delivery.scheduled_for)}</p>
                  </div>
                  <div className="flex items-center gap-2">
                    <StatusBadge status={delivery.status} />
                    <Link to={`/deliveries/${delivery.delivery_id}`} className={cn(buttonVariants({ variant: 'outline' }), 'h-8 px-3')}>Open</Link>
                  </div>
                </li>
              ))}
            </ul>
          )
        ) : null}
        <span className="sr-only">{user?.full_name}</span>
      </Panel>
    </div>
  )
}
