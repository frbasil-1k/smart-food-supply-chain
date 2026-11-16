import { useState } from 'react'
import { Link } from 'react-router-dom'
import { useQuery } from '@tanstack/react-query'
import { Clock3, Printer, ShieldAlert } from 'lucide-react'

import { EmptyState } from '@/components/EmptyState'
import { ErrorNotice } from '@/components/ErrorNotice'
import { PageHeader } from '@/components/PageHeader'
import { Panel } from '@/components/Panel'
import { Button, buttonVariants } from '@/components/ui/button'
import { apiGet } from '@/lib/api'
import { formatLocalDateTime } from '@/lib/datetime'
import { formatKg } from '@/lib/format'
import type { FreshnessItem } from '@/lib/types'
import { cn } from 'cn'

export function FreshnessPage() {
  const [hours, setHours] = useState('48')
  const query = useQuery({
    queryKey: ['freshness', hours],
    queryFn: ({ signal }) => apiGet<FreshnessItem[]>(`/api/reports/freshness?within_hours=${hours}`, signal),
  })
  const rows = query.data ?? []

  return (
    <div className="space-y-7">
      <PageHeader
        eyebrow="Operational risk"
        title="Freshness"
        description="Food whose best-before time falls inside the selected window. Expired rows are shown, never hidden."
        action={
          <Link to="/print/reports/freshness" className={cn(buttonVariants({ variant: 'outline' }), 'h-10 px-4')}>
            <Printer aria-hidden="true" className="size-4" />
            Print view
          </Link>
        }
      />
      <div className="flex flex-wrap items-center gap-2 rounded-[8px] border border-line bg-paper p-4">
        <label htmlFor="freshness-window" className="text-sm font-medium text-charcoal">Window</label>
        <select
          id="freshness-window"
          value={hours}
          onChange={(event) => setHours(event.target.value)}
          className="h-9 rounded-[4px] border border-input bg-paper px-3 text-sm"
        >
          <option value="24">Next 24 hours</option>
          <option value="48">Next 48 hours</option>
          <option value="72">Next 3 days</option>
          <option value="168">Next 7 days</option>
        </select>
        <Button type="button" variant="outline" onClick={() => void query.refetch()} disabled={query.isFetching}>
          Refresh
        </Button>
      </div>
      {query.isError ? <ErrorNotice error={query.error} onRetry={() => void query.refetch()} /> : null}
      {query.isPending ? <p className="text-sm text-ink-soft">Loading freshness…</p> : null}
      {query.data ? (
        rows.length === 0 ? (
          <EmptyState icon={Clock3} title="Nothing in this window" body="No food item has a best-before time inside the selected window." />
        ) : (
          <Panel title="Items by best-before" description="Open allocation shows kilograms already planned or in transit.">
            <ul className="divide-y divide-line">
              {rows.map((row) => (
                <li key={row.food_item_id} className="flex flex-wrap items-start justify-between gap-4 py-4 first:pt-0 last:pb-0">
                  <div>
                    <div className="flex flex-wrap items-center gap-2">
                      <Link to={`/donations/${row.donation_id}`} className="font-semibold text-forest underline underline-offset-4">
                        {row.item_name}
                      </Link>
                      {row.is_expired ? (
                        <span className="inline-flex items-center gap-1 rounded-[3px] bg-oat-deep px-2 py-0.5 text-xs font-semibold text-charcoal">
                          <ShieldAlert aria-hidden="true" className="size-3.5" />
                          Expired
                        </span>
                      ) : null}
                    </div>
                    <p className="mt-1 text-sm text-ink-soft">
                      Donation #{row.donation_id} · {row.category ?? 'Uncategorised'} · {formatKg(row.quantity_kg)}
                    </p>
                    <p className="mt-1 text-xs text-ink-soft">Best before {formatLocalDateTime(row.best_before)}</p>
                  </div>
                  <div className="text-right">
                    <p className={row.is_expired ? 'font-heading text-2xl text-charcoal' : 'font-heading text-2xl text-forest'}>
                      {row.hours_remaining} h
                    </p>
                    <p className="text-xs text-ink-soft">{formatKg(row.open_allocated_kg)} open allocated</p>
                  </div>
                </li>
              ))}
            </ul>
          </Panel>
        )
      ) : null}
    </div>
  )
}
