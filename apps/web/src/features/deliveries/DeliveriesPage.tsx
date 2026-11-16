import { Link, useSearchParams } from 'react-router-dom'
import { useQuery } from '@tanstack/react-query'
import { Truck } from 'lucide-react'

import { EmptyState } from '@/components/EmptyState'
import { ErrorNotice } from '@/components/ErrorNotice'
import { PageHeader } from '@/components/PageHeader'
import { StatusBadge } from '@/components/StatusBadge'
import { Button, buttonVariants } from '@/components/ui/button'
import { useAuth } from '@/features/auth/AuthProvider'
import { apiGetPaged } from '@/lib/api'
import { formatLocalDateTime } from '@/lib/datetime'
import type { Delivery } from '@/lib/types'
import { cn } from 'cn'

export function DeliveriesPage() {
  const { user } = useAuth()
  const [searchParams, setSearchParams] = useSearchParams()
  const status = searchParams.get('status') ?? ''
  const page = Number(searchParams.get('page') ?? '1') || 1
  const query = useQuery({
    queryKey: ['deliveries', { status, page }],
    queryFn: ({ signal }) =>
      apiGetPaged<Delivery>(
        `/api/deliveries?page=${page}&page_size=25${status ? `&status=${status}` : ''}`,
        signal,
      ),
  })
  const rows = query.data?.data ?? []
  const pagination = query.data?.meta.pagination
  const isDriver = user?.role === 'DRIVER'

  function update(key: string, value: string) {
    const next = new URLSearchParams(searchParams)
    if (value) next.set(key, value)
    else next.delete(key)
    if (key !== 'page') next.delete('page')
    setSearchParams(next)
  }

  return (
    <div className="space-y-7">
      <PageHeader
        eyebrow={isDriver ? 'Driver workflow' : 'Logistics'}
        title={isDriver ? 'My deliveries' : 'Deliveries'}
        description={
          isDriver
            ? 'Only deliveries attributed to you appear here. Start a delivery before marking it delivered.'
            : 'Every delivery allocated from donations in your branch scope.'
        }
      />

      <div className="flex flex-wrap items-center gap-2 rounded-[8px] border border-line bg-paper p-4">
        <label htmlFor="delivery-status" className="text-sm font-medium text-charcoal">
          Status
        </label>
        <select
          id="delivery-status"
          value={status}
          onChange={(event) => update('status', event.target.value)}
          className="h-9 min-w-40 rounded-[4px] border border-input bg-paper px-3 text-sm"
        >
          <option value="">All deliveries</option>
          {['PLANNED', 'IN_TRANSIT', 'DELIVERED', 'FAILED', 'CANCELLED'].map((value) => (
            <option key={value} value={value}>
              {value.replaceAll('_', ' ')}
            </option>
          ))}
        </select>
      </div>

      {query.isError ? (
        <ErrorNotice error={query.error} onRetry={() => void query.refetch()} />
      ) : null}

      {query.isPending ? (
        <div className="rounded-[8px] border border-line bg-paper p-6 text-sm text-ink-soft">
          Loading deliveries…
        </div>
      ) : rows.length === 0 ? (
        <EmptyState
          icon={Truck}
          title="No deliveries found"
          body={
            isDriver
              ? 'A manager will allocate a delivery to your route when food is approved.'
              : 'Approved donations become deliveries once a manager allocates quantities.'
          }
        />
      ) : (
        <div className="grid gap-4 md:grid-cols-2">
          {rows.map((delivery) => (
            <article key={delivery.delivery_id} className="rounded-[8px] border border-line bg-paper p-5">
              <div className="flex items-start justify-between gap-3">
                <div>
                  <p className="text-xs tracking-[0.08em] text-ink-soft uppercase">Delivery</p>
                  <h2 className="mt-1 font-heading text-2xl text-charcoal">#{delivery.delivery_id}</h2>
                </div>
                <StatusBadge status={delivery.status} />
              </div>
              <dl className="mt-4 space-y-2 text-sm">
                <div className="flex justify-between gap-3">
                  <dt className="text-ink-soft">Donation</dt>
                  <dd>
                    <Link to={`/donations/${delivery.donation.donation_id}`} className="font-medium text-forest underline underline-offset-4">
                      #{delivery.donation.donation_id}
                    </Link>
                  </dd>
                </div>
                <div className="flex justify-between gap-3">
                  <dt className="text-ink-soft">Receiving branch</dt>
                  <dd className="text-right text-charcoal">{delivery.recipient_branch.branch_name}</dd>
                </div>
                <div className="flex justify-between gap-3">
                  <dt className="text-ink-soft">Driver</dt>
                  <dd className="text-right text-charcoal">{delivery.driver?.full_name ?? 'Unassigned'}</dd>
                </div>
                <div className="flex justify-between gap-3">
                  <dt className="text-ink-soft">Scheduled</dt>
                  <dd className="text-right text-charcoal">{formatLocalDateTime(delivery.scheduled_for)}</dd>
                </div>
              </dl>
              <Link
                to={`/deliveries/${delivery.delivery_id}`}
                className={cn(buttonVariants({ variant: 'outline' }), 'mt-5 h-9 px-3')}
              >
                Open delivery
              </Link>
            </article>
          ))}
        </div>
      )}

      {pagination && pagination.pages > 1 ? (
        <nav aria-label="Delivery pages" className="flex items-center justify-between gap-3">
          <p className="text-sm text-ink-soft">
            Page {pagination.page} of {pagination.pages} · {pagination.total} deliveries
          </p>
          <div className="flex gap-2">
            <Button type="button" variant="outline" disabled={page <= 1} onClick={() => update('page', String(page - 1))}>
              Previous
            </Button>
            <Button type="button" variant="outline" disabled={page >= pagination.pages} onClick={() => update('page', String(page + 1))}>
              Next
            </Button>
          </div>
        </nav>
      ) : null}
      <span className="sr-only">{user?.role}</span>
    </div>
  )
}
