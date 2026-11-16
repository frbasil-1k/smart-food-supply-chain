import { useState } from 'react'
import { Link, useSearchParams } from 'react-router-dom'
import { useQuery } from '@tanstack/react-query'
import { PackageOpen, Plus, Search } from 'lucide-react'

import { EmptyState } from '@/components/EmptyState'
import { ErrorNotice } from '@/components/ErrorNotice'
import { PageHeader } from '@/components/PageHeader'
import { StatusBadge } from '@/components/StatusBadge'
import { Button, buttonVariants } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { useAuth } from '@/features/auth/AuthProvider'
import { apiGetPaged } from '@/lib/api'
import { formatLocalDateTime } from '@/lib/datetime'
import { formatKg } from '@/lib/format'
import type { DonationSummary } from '@/lib/types'
import { cn } from 'cn'

export function DonationsPage() {
  const { user } = useAuth()
  const [searchParams, setSearchParams] = useSearchParams()
  const status = searchParams.get('status') ?? ''
  const [q, setQ] = useState(searchParams.get('q') ?? '')
  const page = Number(searchParams.get('page') ?? '1') || 1
  const query = useQuery({
    queryKey: ['donations', { status, q, page }],
    queryFn: ({ signal }) =>
      apiGetPaged<DonationSummary>(
        `/api/donations?page=${page}&page_size=25${status ? `&status=${status}` : ''}${q ? `&q=${encodeURIComponent(q)}` : ''}`,
        signal,
      ),
  })

  const rows = query.data?.data ?? []
  const pagination = query.data?.meta.pagination

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
        eyebrow="Donation chain"
        title="Donations"
        description={
          user?.role === 'DONOR'
            ? 'Everything you have registered, with the kilograms actually delivered and spoiled.'
            : 'Donations in your branch scope, including unrouted donations anchored to your donors.'
        }
        action={
          user?.role === 'DONOR' ? (
            <Link to="/donations/new" className={cn(buttonVariants(), 'h-10 px-4')}>
              <Plus aria-hidden="true" className="size-4" />
              Register donation
            </Link>
          ) : null
        }
      />

      <div className="flex flex-col gap-3 rounded-[8px] border border-line bg-paper p-4 sm:flex-row sm:items-center">
        <label htmlFor="donation-search" className="sr-only">
          Search donations
        </label>
        <div className="relative min-w-0 flex-1">
          <Search
            aria-hidden="true"
            className="pointer-events-none absolute top-1/2 left-3 size-4 -translate-y-1/2 text-ink-soft"
          />
          <Input
            id="donation-search"
            value={q}
            onChange={(event) => setQ(event.target.value)}
            onKeyDown={(event) => {
              if (event.key === 'Enter') update('q', q.trim())
            }}
            placeholder="Search by item or pickup address"
            className="pl-9"
          />
        </div>
        <label htmlFor="status-filter" className="sr-only">
          Filter by status
        </label>
        <select
          id="status-filter"
          value={status}
          onChange={(event) => update('status', event.target.value)}
          className="h-9 min-w-40 rounded-[4px] border border-input bg-paper px-3 text-sm text-charcoal"
        >
          <option value="">All statuses</option>
          {[
            'PENDING',
            'SCHEDULED',
            'COLLECTED',
            'APPROVED',
            'PARTIALLY_DISTRIBUTED',
            'COMPLETED',
            'REJECTED',
            'CANCELLED',
          ].map((value) => (
            <option key={value} value={value}>
              {value.replaceAll('_', ' ')}
            </option>
          ))}
        </select>
        <Button type="button" variant="outline" onClick={() => update('q', q.trim())}>
          Search
        </Button>
      </div>

      {query.isError ? (
        <ErrorNotice error={query.error} onRetry={() => void query.refetch()} />
      ) : null}

      {query.isPending ? (
        <div className="rounded-[8px] border border-line bg-paper p-6 text-sm text-ink-soft">
          Loading donations…
        </div>
      ) : rows.length === 0 ? (
        <EmptyState
          icon={PackageOpen}
          title="No donations in this view"
          body={
            user?.role === 'DONOR'
              ? 'Register a donation to start the workflow.'
              : 'There are no donations in your branch scope for this filter.'
          }
          action={
            user?.role === 'DONOR' ? (
              <Link to="/donations/new" className={cn(buttonVariants(), 'h-9 px-3')}>
                Register donation
              </Link>
            ) : undefined
          }
        />
      ) : (
        <div className="overflow-hidden rounded-[8px] border border-line bg-paper">
          <div className="overflow-x-auto">
            <table className="w-full min-w-[760px] border-collapse text-left text-sm">
              <caption className="sr-only">Donations in your scope</caption>
              <thead className="bg-oat-deep text-[11px] tracking-[0.08em] text-ink-soft uppercase">
                <tr>
                  <th scope="col" className="px-4 py-3 font-semibold">
                    Donation
                  </th>
                  <th scope="col" className="px-4 py-3 font-semibold">
                    Donor
                  </th>
                  <th scope="col" className="px-4 py-3 font-semibold">
                    Pickup
                  </th>
                  <th scope="col" className="px-4 py-3 font-semibold">
                    Quantity
                  </th>
                  <th scope="col" className="px-4 py-3 font-semibold">
                    Status
                  </th>
                  <th scope="col" className="px-4 py-3 font-semibold">
                    Action
                  </th>
                </tr>
              </thead>
              <tbody className="divide-y divide-line">
                {rows.map((row) => (
                  <tr key={row.donation_id} className="align-top">
                    <td className="px-4 py-4">
                      <p className="font-semibold text-charcoal">#{row.donation_id}</p>
                      <p className="mt-1 text-xs text-ink-soft">
                        {row.item_count} item{row.item_count === 1 ? '' : 's'}
                      </p>
                    </td>
                    <td className="px-4 py-4">
                      <p className="font-medium text-charcoal">
                        {row.donor.full_name ?? 'Donor'}
                      </p>
                      <p className="mt-1 text-xs text-ink-soft">
                        {row.pickup_address ?? 'Pickup address not set'}
                      </p>
                    </td>
                    <td className="px-4 py-4">
                      <p className="text-charcoal">{formatLocalDateTime(row.pickup_datetime)}</p>
                      <p className="mt-1 text-xs text-ink-soft">
                        {row.pickup_route ? `Route #${row.pickup_route.route_id}` : 'Unrouted'}
                      </p>
                    </td>
                    <td className="px-4 py-4 font-medium text-charcoal">
                      {formatKg(row.total_quantity_kg)}
                    </td>
                    <td className="px-4 py-4">
                      <StatusBadge status={row.status} />
                    </td>
                    <td className="px-4 py-4">
                      <Link
                        to={`/donations/${row.donation_id}`}
                        className={cn(
                          buttonVariants({ variant: 'outline', size: 'sm' }),
                          'h-8 px-3',
                        )}
                      >
                        Open
                      </Link>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {pagination && pagination.pages > 1 ? (
        <nav aria-label="Donation pages" className="flex items-center justify-between gap-3">
          <p className="text-sm text-ink-soft">
            Page {pagination.page} of {pagination.pages} · {pagination.total} donations
          </p>
          <div className="flex gap-2">
            <Button
              type="button"
              variant="outline"
              disabled={page <= 1}
              onClick={() => update('page', String(page - 1))}
            >
              Previous
            </Button>
            <Button
              type="button"
              variant="outline"
              disabled={page >= pagination.pages}
              onClick={() => update('page', String(page + 1))}
            >
              Next
            </Button>
          </div>
        </nav>
      ) : null}
    </div>
  )
}
