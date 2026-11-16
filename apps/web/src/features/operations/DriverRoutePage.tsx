import { useQuery } from '@tanstack/react-query'
import { Link } from 'react-router-dom'
import { MapPinned, Truck } from 'lucide-react'

import { EmptyState } from '@/components/EmptyState'
import { ErrorNotice } from '@/components/ErrorNotice'
import { PageHeader } from '@/components/PageHeader'
import { Panel } from '@/components/Panel'
import { StatusBadge } from '@/components/StatusBadge'
import { buttonVariants } from '@/components/ui/button'
import { useAuth } from '@/features/auth/AuthProvider'
import { apiGet, apiGetPaged } from '@/lib/api'
import { formatLocalDateTime } from '@/lib/datetime'
import type { Delivery, RouteRef } from '@/lib/types'
import { cn } from 'cn'

export function DriverRoutePage() {
  const { user } = useAuth()
  const routesQuery = useQuery({
    queryKey: ['driver-routes', user?.user_id],
    queryFn: ({ signal }) =>
      apiGetPaged<RouteRef>(`/api/routes?driver_id=${user?.user_id}&page_size=100`, signal),
    enabled: Boolean(user?.user_id),
  })
  const upcomingQuery = useQuery({
    queryKey: ['driver-upcoming'],
    queryFn: ({ signal }) => apiGet<Delivery[]>('/api/driver/assignments?scope=upcoming', signal),
  })
  const routes = routesQuery.data?.data ?? []
  const upcoming = upcomingQuery.data ?? []

  return (
    <div className="space-y-7">
      <PageHeader
        eyebrow="Driver workflow"
        title="My routes"
        description="Routes where you are the designated driver, and every upcoming delivery attributed to you."
      />
      {routesQuery.isError ? <ErrorNotice error={routesQuery.error} onRetry={() => void routesQuery.refetch()} /> : null}
      {upcomingQuery.isError ? <ErrorNotice error={upcomingQuery.error} onRetry={() => void upcomingQuery.refetch()} /> : null}

      <Panel title="Designated routes" description="Assigned by a branch manager.">
        {routesQuery.isPending ? <p className="text-sm text-ink-soft">Loading routes…</p> : null}
        {routesQuery.data ? (
          routes.length === 0 ? (
            <EmptyState icon={MapPinned} title="No designated route" body="A branch manager will assign a route when one is available." />
          ) : (
            <div className="grid gap-4 md:grid-cols-2">
              {routes.map((route) => (
                <div key={route.route_id} className="rounded-[8px] border border-line p-4">
                  <p className="text-xs tracking-[0.08em] text-ink-soft uppercase">Route #{route.route_id}</p>
                  <p className="mt-1 font-heading text-2xl text-charcoal">{route.coverage_area?.area_name ?? 'Coverage area'}</p>
                  <p className="mt-1 text-sm text-ink-soft">{route.coverage_area?.city ?? 'City'} · {route.managing_branch?.branch_name ?? 'Branch'}</p>
                  <div className="mt-3 flex items-center gap-2">
                    <StatusBadge status={route.route_status ?? 'ACTIVE'} />
                    <span className="text-xs text-ink-soft">{route.route_type}</span>
                  </div>
                </div>
              ))}
            </div>
          )
        ) : null}
      </Panel>

      <Panel title="Upcoming deliveries" description="Planned and in-transit deliveries ordered by scheduled time.">
        {upcomingQuery.isPending ? <p className="text-sm text-ink-soft">Loading deliveries…</p> : null}
        {upcomingQuery.data ? (
          upcoming.length === 0 ? (
            <EmptyState icon={Truck} title="Nothing upcoming" body="New deliveries appear here after a manager allocates them to your route." />
          ) : (
            <ul className="divide-y divide-line">
              {upcoming.map((delivery) => (
                <li key={delivery.delivery_id} className="flex flex-wrap items-center justify-between gap-3 py-4 first:pt-0 last:pb-0">
                  <div>
                    <p className="font-semibold text-charcoal">Delivery #{delivery.delivery_id}</p>
                    <p className="mt-1 text-sm text-ink-soft">{delivery.recipient_branch.branch_name} · {formatLocalDateTime(delivery.scheduled_for)}</p>
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
      </Panel>
    </div>
  )
}
