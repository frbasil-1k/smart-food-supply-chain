import { useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { Link } from 'react-router-dom'
import { Download, Printer, RefreshCw } from 'lucide-react'

import { EmptyState } from '@/components/EmptyState'
import { ErrorNotice } from '@/components/ErrorNotice'
import { PageHeader } from '@/components/PageHeader'
import { Panel } from '@/components/Panel'
import { Button } from '@/components/ui/button'
import { apiGet } from '@/lib/api'
import { formatKg, formatNumber } from '@/lib/format'
import type { BranchReport, DonorReport, DriverReport } from '@/lib/types'

type Tab = 'branches' | 'donors' | 'drivers'

const tabs: { id: Tab; label: string; path: string; filename: string }[] = [
  { id: 'branches', label: 'Branches', path: '/api/reports/branches', filename: 'branch-report' },
  { id: 'donors', label: 'Donors', path: '/api/reports/donors', filename: 'donor-report' },
  { id: 'drivers', label: 'Drivers', path: '/api/reports/drivers', filename: 'driver-report' },
]

export function ReportsPage() {
  const [tab, setTab] = useState<Tab>('branches')
  const active = tabs.find((item) => item.id === tab) ?? tabs[0]
  const query = useQuery({
    queryKey: ['report', tab],
    queryFn: ({ signal }) => apiGet<unknown[]>(active.path, signal),
  })

  return (
    <div className="space-y-7">
      <PageHeader
        eyebrow="Reporting"
        title="Reports"
        description="Aggregates come from stored deliveries, spoiled rows, and one review per delivery. Nothing here is estimated."
        action={
          <>
            <Button type="button" variant="outline" onClick={() => void query.refetch()} disabled={query.isFetching}>
              <RefreshCw aria-hidden="true" className={query.isFetching ? 'size-4 animate-spin' : 'size-4'} />
              Refresh
            </Button>
            <Link
              to={`/print/reports/${active.id}`}
              className="inline-flex h-9 items-center gap-2 rounded-[4px] border border-line px-3 text-sm font-medium text-charcoal hover:bg-oat-deep"
            >
              <Printer aria-hidden="true" className="size-4" />
              Print view
            </Link>
            <a
              href={`${active.path}?export=csv`}
              className="inline-flex h-9 items-center gap-2 rounded-[4px] bg-forest px-3 text-sm font-medium text-paper hover:bg-forest-deep"
            >
              <Download aria-hidden="true" className="size-4" />
              CSV
            </a>
          </>
        }
      />

      <div role="tablist" aria-label="Report type" className="flex flex-wrap gap-2 border-b border-line pb-2">
        {tabs.map((item) => (
          <button
            key={item.id}
            type="button"
            role="tab"
            aria-selected={tab === item.id}
            onClick={() => setTab(item.id)}
            className={
              tab === item.id
                ? 'rounded-[4px] bg-forest px-3 py-2 text-sm font-medium text-paper'
                : 'rounded-[4px] px-3 py-2 text-sm font-medium text-ink-soft hover:bg-oat-deep'
            }
          >
            {item.label}
          </button>
        ))}
      </div>

      {query.isError ? <ErrorNotice error={query.error} onRetry={() => void query.refetch()} /> : null}
      {query.isPending ? <p className="text-sm text-ink-soft">Loading report…</p> : null}

      {query.data ? (
        tab === 'branches' ? (
          <BranchTable rows={query.data as BranchReport[]} />
        ) : tab === 'donors' ? (
          <DonorTable rows={query.data as DonorReport[]} />
        ) : (
          <DriverTable rows={query.data as DriverReport[]} />
        )
      ) : null}
    </div>
  )
}

function BranchTable({ rows }: { rows: BranchReport[] }) {
  if (rows.length === 0) return <EmptyState icon={RefreshCw} title="No branch data" body="Reports appear once donations are attributed to a branch you manage." />
  return (
    <Panel title="Branch performance" description="Donations are attributed by the pickup route, or by the donor's primary branch when unrouted.">
      <div className="overflow-x-auto">
        <table className="w-full min-w-[720px] text-left text-sm">
          <caption className="sr-only">Branch report</caption>
          <thead className="bg-oat-deep text-[11px] tracking-[0.08em] text-ink-soft uppercase">
            <tr>
              <th scope="col" className="px-3 py-2 font-semibold">Branch</th>
              <th scope="col" className="px-3 py-2 font-semibold">Donations</th>
              <th scope="col" className="px-3 py-2 font-semibold">Donated</th>
              <th scope="col" className="px-3 py-2 font-semibold">Delivered</th>
              <th scope="col" className="px-3 py-2 font-semibold">Spoiled</th>
              <th scope="col" className="px-3 py-2 font-semibold">Balance</th>
              <th scope="col" className="px-3 py-2 font-semibold">Rating</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-line">
            {rows.map((row) => (
              <tr key={row.branch_id}>
                <td className="px-3 py-3 font-medium text-charcoal">{row.branch_name}</td>
                <td className="px-3 py-3">{formatNumber(row.total_donations)}</td>
                <td className="px-3 py-3">{formatKg(row.total_donated_kg)}</td>
                <td className="px-3 py-3">{formatKg(row.delivered_kg)}</td>
                <td className="px-3 py-3">{formatKg(row.spoiled_kg)}</td>
                <td className="px-3 py-3 font-medium text-forest">{formatKg(row.balance_kg)}</td>
                <td className="px-3 py-3">{row.avg_rating} / 5</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </Panel>
  )
}

function DonorTable({ rows }: { rows: DonorReport[] }) {
  if (rows.length === 0) return <EmptyState icon={RefreshCw} title="No donor data" body="Donor totals appear once a donation is registered in your scope." />
  return (
    <Panel title="Donor impact" description="Delivered kilograms are real delivery lines; spoiled kilograms are recorded separately.">
      <div className="overflow-x-auto">
        <table className="w-full min-w-[720px] text-left text-sm">
          <caption className="sr-only">Donor report</caption>
          <thead className="bg-oat-deep text-[11px] tracking-[0.08em] text-ink-soft uppercase">
            <tr>
              <th scope="col" className="px-3 py-2 font-semibold">Donor</th>
              <th scope="col" className="px-3 py-2 font-semibold">Donations</th>
              <th scope="col" className="px-3 py-2 font-semibold">Donated</th>
              <th scope="col" className="px-3 py-2 font-semibold">Delivered</th>
              <th scope="col" className="px-3 py-2 font-semibold">Spoiled</th>
              <th scope="col" className="px-3 py-2 font-semibold">Balance</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-line">
            {rows.map((row) => (
              <tr key={row.donor_id}>
                <td className="px-3 py-3">
                  <p className="font-medium text-charcoal">{row.donor_name}</p>
                  <p className="text-xs text-ink-soft">{row.email ?? 'No email'}</p>
                </td>
                <td className="px-3 py-3">{formatNumber(row.total_donations)}</td>
                <td className="px-3 py-3">{formatKg(row.total_donated_kg)}</td>
                <td className="px-3 py-3">{formatKg(row.delivered_kg)}</td>
                <td className="px-3 py-3">{formatKg(row.spoiled_kg)}</td>
                <td className="px-3 py-3 font-medium text-forest">{formatKg(row.balance_kg ?? row.undistributed_balance_kg)}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </Panel>
  )
}

function DriverTable({ rows }: { rows: DriverReport[] }) {
  if (rows.length === 0) return <EmptyState icon={RefreshCw} title="No driver data" body="Driver totals appear once a delivery is completed on your routes." />
  return (
    <Panel title="Driver performance" description="Completed deliveries count only DELIVERED status; kilograms sum the allocated delivery lines.">
      <div className="overflow-x-auto">
        <table className="w-full min-w-[560px] text-left text-sm">
          <caption className="sr-only">Driver report</caption>
          <thead className="bg-oat-deep text-[11px] tracking-[0.08em] text-ink-soft uppercase">
            <tr>
              <th scope="col" className="px-3 py-2 font-semibold">Driver</th>
              <th scope="col" className="px-3 py-2 font-semibold">Assigned routes</th>
              <th scope="col" className="px-3 py-2 font-semibold">Completed</th>
              <th scope="col" className="px-3 py-2 font-semibold">Delivered kilograms</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-line">
            {rows.map((row) => (
              <tr key={row.driver_id}>
                <td className="px-3 py-3 font-medium text-charcoal">{row.driver_name}</td>
                <td className="px-3 py-3">{formatNumber(row.assigned_routes)}</td>
                <td className="px-3 py-3">{formatNumber(row.completed_deliveries)}</td>
                <td className="px-3 py-3">{formatKg(row.delivered_quantity_kg)}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </Panel>
  )
}
