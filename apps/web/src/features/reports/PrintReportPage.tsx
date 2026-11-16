import { useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { Link, useParams } from 'react-router-dom'
import { ArrowLeft, Printer } from 'lucide-react'

import { ErrorNotice } from '@/components/ErrorNotice'
import { buttonVariants } from '@/components/ui/button'
import { Button } from '@/components/ui/button'
import { useAuth } from '@/features/auth/AuthProvider'
import { apiGet } from '@/lib/api'
import { formatLocalDateTime } from '@/lib/datetime'
import { formatKg, formatNumber } from '@/lib/format'
import { PRODUCT_NAME } from '@/lib/brand'
import type { BranchReport, DonorReport, DriverReport, FreshnessItem } from '@/lib/types'
import { cn } from 'cn'

type Column = { label: string; value: (row: Record<string, unknown>) => string }

const configs: Record<
  string,
  { title: string; path: string; columns: Column[]; note: string }
> = {
  branches: {
    title: 'Branch report',
    path: '/api/reports/branches',
    columns: [
      { label: 'Branch', value: (row) => String(row.branch_name ?? '') },
      { label: 'Donations', value: (row) => formatNumber(Number(row.total_donations ?? 0)) },
      { label: 'Donated', value: (row) => formatKg(String(row.total_donated_kg ?? '0')) },
      { label: 'Delivered', value: (row) => formatKg(String(row.delivered_kg ?? '0')) },
      { label: 'Spoiled', value: (row) => formatKg(String(row.spoiled_kg ?? '0')) },
      { label: 'Balance', value: (row) => formatKg(String(row.balance_kg ?? '0')) },
      { label: 'Average review', value: (row) => `${String(row.avg_rating ?? '0.00')} / 5` },
    ],
    note: 'Donations attributed by pickup route, or by the donor branch when unrouted.',
  },
  donors: {
    title: 'Donor impact report',
    path: '/api/reports/donors',
    columns: [
      { label: 'Donor', value: (row) => String(row.donor_name ?? '') },
      { label: 'Donations', value: (row) => formatNumber(Number(row.total_donations ?? 0)) },
      { label: 'Donated', value: (row) => formatKg(String(row.total_donated_kg ?? '0')) },
      { label: 'Delivered', value: (row) => formatKg(String(row.delivered_kg ?? '0')) },
      { label: 'Spoiled', value: (row) => formatKg(String(row.spoiled_kg ?? '0')) },
      {
        label: 'Balance',
        value: (row) => formatKg(String(row.balance_kg ?? row.undistributed_balance_kg ?? '0')),
      },
    ],
    note: 'Delivered and spoiled kilograms come from their stored rows.',
  },
  drivers: {
    title: 'Driver performance report',
    path: '/api/reports/drivers',
    columns: [
      { label: 'Driver', value: (row) => String(row.driver_name ?? '') },
      { label: 'Assigned routes', value: (row) => formatNumber(Number(row.assigned_routes ?? 0)) },
      { label: 'Completed deliveries', value: (row) => formatNumber(Number(row.completed_deliveries ?? 0)) },
      { label: 'Delivered kilograms', value: (row) => formatKg(String(row.delivered_quantity_kg ?? '0')) },
    ],
    note: 'Completed deliveries count only DELIVERED status.',
  },
  freshness: {
    title: 'Freshness report',
    path: '/api/reports/freshness?within_hours=48',
    columns: [
      { label: 'Item', value: (row) => String(row.item_name ?? '') },
      { label: 'Donation', value: (row) => `#${String(row.donation_id ?? '')}` },
      { label: 'Category', value: (row) => String(row.category ?? 'Uncategorised') },
      { label: 'Quantity', value: (row) => formatKg(String(row.quantity_kg ?? '0')) },
      { label: 'Best before', value: (row) => formatLocalDateTime(row.best_before as string) },
      { label: 'Hours remaining', value: (row) => String(row.hours_remaining ?? '') },
      { label: 'Open allocated', value: (row) => formatKg(String(row.open_allocated_kg ?? '0')) },
    ],
    note: 'Window: best before within 48 hours of generation time.',
  },
}

type ReportRow = BranchReport | DonorReport | DriverReport | FreshnessItem

export function PrintReportPage() {
  const { kind = '' } = useParams()
  const { user } = useAuth()
  const [generatedAt] = useState(() => new Date().toISOString())
  const config = configs[kind]
  const query = useQuery({
    queryKey: ['print-report', kind, user?.user_id],
    queryFn: ({ signal }) => apiGet<ReportRow[]>(config?.path ?? '', signal),
    enabled: Boolean(config && user),
  })

  if (!config) {
    return (
      <main className="mx-auto max-w-2xl p-8">
        <ErrorNotice error="That printed report does not exist." />
      </main>
    )
  }

  return (
    <main className="min-h-svh bg-paper px-5 py-8 text-charcoal sm:px-10 lg:px-16">
      <style>{`
        @page { margin: 18mm; }
        @media print {
          .no-print { display: none !important; }
          main { padding: 0 !important; }
          table { page-break-inside: auto; }
          tr { page-break-inside: avoid; }
          thead { display: table-header-group; }
        }
      `}</style>
      <div className="mx-auto max-w-5xl">
        <div className="no-print mb-6 flex flex-wrap items-center justify-between gap-3">
          <Link to="/reports" className={cn(buttonVariants({ variant: 'outline' }), 'h-9 px-3')}>
            <ArrowLeft aria-hidden="true" className="size-4" />
            Back to reports
          </Link>
          <Button type="button" onClick={() => window.print()}>
            <Printer aria-hidden="true" className="size-4" />
            Print
          </Button>
        </div>

        <header className="border-b-[1.5px] border-forest pb-4">
          <p className="text-[11px] font-semibold tracking-[0.14em] text-forest uppercase">
            {PRODUCT_NAME}
          </p>
          <h1 className="mt-2 font-heading text-[32px] leading-tight text-charcoal">
            {config.title}
          </h1>
          <p className="mt-2 text-sm text-ink-soft">{config.note}</p>
          <p className="mt-2 text-xs text-ink-soft">
            Generated {formatLocalDateTime(generatedAt)} · {user?.full_name} ·{' '}
            {user?.role.replaceAll('_', ' ')}
          </p>
        </header>

        {query.isError ? <div className="mt-6"><ErrorNotice error={query.error} onRetry={() => void query.refetch()} /></div> : null}
        {query.isPending ? <p className="mt-6 text-sm text-ink-soft">Loading report…</p> : null}
        {query.data ? (
          query.data.length === 0 ? (
            <p className="mt-8 text-sm text-ink-soft">No rows in this report.</p>
          ) : (
            <table className="mt-6 w-full border-collapse text-left text-sm">
              <caption className="sr-only">{config.title}</caption>
              <thead className="border-b border-forest bg-oat-deep">
                <tr>
                  {config.columns.map((column) => (
                    <th key={column.label} scope="col" className="px-2 py-2 font-semibold">
                      {column.label}
                    </th>
                  ))}
                </tr>
              </thead>
              <tbody className="divide-y divide-line">
                {query.data.map((row, index) => (
                  <tr key={index}>
                    {config.columns.map((column) => (
                      <td key={column.label} className="px-2 py-2 align-top">
                        {column.value(row as unknown as Record<string, unknown>)}
                      </td>
                    ))}
                  </tr>
                ))}
              </tbody>
            </table>
          )
        ) : null}
      </div>
    </main>
  )
}
