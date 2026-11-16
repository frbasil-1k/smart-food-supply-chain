import { useState } from 'react'
import { Link } from 'react-router-dom'
import { useQuery } from '@tanstack/react-query'
import { Activity } from 'lucide-react'

import { EmptyState } from '@/components/EmptyState'
import { ErrorNotice } from '@/components/ErrorNotice'
import { PageHeader } from '@/components/PageHeader'
import { Panel } from '@/components/Panel'
import { Button } from '@/components/ui/button'
import { apiGetPaged } from '@/lib/api'
import { formatLocalDateTime } from '@/lib/datetime'
import { titleCase } from '@/lib/format'
import type { ActivityEvent } from '@/lib/types'

export function ActivityPage() {
  const [page, setPage] = useState(1)
  const query = useQuery({
    queryKey: ['activity', page],
    queryFn: ({ signal }) =>
      apiGetPaged<ActivityEvent>(`/api/activity?page=${page}&page_size=25`, signal),
  })
  const rows = query.data?.data ?? []
  const pagination = query.data?.meta.pagination

  return (
    <div className="space-y-7">
      <PageHeader
        eyebrow="Audit trail"
        title="Activity"
        description="Only events that exist as stored rows: donation status history and delivery outcomes in your scope."
      />
      {query.isError ? <ErrorNotice error={query.error} onRetry={() => void query.refetch()} /> : null}
      {query.isPending ? <p className="text-sm text-ink-soft">Loading activity…</p> : null}
      {query.data ? (
        rows.length === 0 ? (
          <EmptyState icon={Activity} title="No activity yet" body="Status changes and delivered deliveries appear here." />
        ) : (
          <Panel title="Recent events" description="Newest first, scoped to your role and branch.">
            <ol className="divide-y divide-line">
              {rows.map((row, index) => (
                <li key={`${row.event_type}-${row.donation_id}-${row.timestamp}-${index}`} className="flex flex-wrap items-start justify-between gap-4 py-4 first:pt-0 last:pb-0">
                  <div>
                    <p className="text-xs font-semibold tracking-[0.08em] text-ink-soft uppercase">
                      {titleCase(row.event_type)}
                    </p>
                    <p className="mt-1 text-sm text-charcoal">{row.description}</p>
                    <p className="mt-1 text-xs text-ink-soft">
                      Donation{' '}
                      <Link to={`/donations/${row.donation_id}`} className="font-medium text-forest underline underline-offset-4">
                        #{row.donation_id}
                      </Link>
                      {row.actor ? ` · ${row.actor}` : ''}
                    </p>
                  </div>
                  <time className="text-xs text-ink-soft" dateTime={row.timestamp ?? undefined}>
                    {row.timestamp ? formatLocalDateTime(row.timestamp) : 'No timestamp'}
                  </time>
                </li>
              ))}
            </ol>
          </Panel>
        )
      ) : null}
      {pagination && pagination.pages > 1 ? (
        <nav aria-label="Activity pages" className="flex items-center justify-between gap-3">
          <p className="text-sm text-ink-soft">Page {pagination.page} of {pagination.pages}</p>
          <div className="flex gap-2">
            <Button variant="outline" disabled={page <= 1} onClick={() => setPage((value) => value - 1)}>Previous</Button>
            <Button variant="outline" disabled={page >= pagination.pages} onClick={() => setPage((value) => value + 1)}>Next</Button>
          </div>
        </nav>
      ) : null}
    </div>
  )
}
