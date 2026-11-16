import { useQuery } from '@tanstack/react-query'
import { Link } from 'react-router-dom'
import { HeartHandshake, PackageCheck, Printer, Truck } from 'lucide-react'

import { EmptyState } from '@/components/EmptyState'
import { ErrorNotice } from '@/components/ErrorNotice'
import { PageHeader } from '@/components/PageHeader'
import { Panel } from '@/components/Panel'
import { StatCard } from '@/components/StatCard'
import { StatusBadge } from '@/components/StatusBadge'
import { buttonVariants } from '@/components/ui/button'
import { useAuth } from '@/features/auth/AuthProvider'
import { apiGet } from '@/lib/api'
import { formatLocalDateTime } from '@/lib/datetime'
import { formatKg, formatNumber } from '@/lib/format'
import type { DonorReport } from '@/lib/types'
import { cn } from 'cn'

export function ImpactPage() {
  const { user } = useAuth()
  const query = useQuery({
    queryKey: ['impact', user?.user_id],
    queryFn: ({ signal }) => apiGet<DonorReport>(`/api/reports/donors/${user?.user_id}`, signal),
    enabled: Boolean(user?.user_id),
  })
  const data = query.data

  return (
    <div className="space-y-7">
      <PageHeader
        eyebrow="Donor impact"
        title="Your food, in real kilograms"
        description="These totals come from the donation and delivery rows, not from estimates or projected meals."
        action={
          <Link to="/print/reports/donors" className={cn(buttonVariants({ variant: 'outline' }), 'h-10 px-4')}>
            <Printer aria-hidden="true" className="size-4" />
            Print report
          </Link>
        }
      />
      {query.isError ? <ErrorNotice error={query.error} onRetry={() => void query.refetch()} /> : null}
      {query.isPending ? <p className="text-sm text-ink-soft">Loading impact…</p> : null}
      {data ? (
        <>
          <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
            <StatCard label="Donations" value={formatNumber(data.total_donations)} icon={HeartHandshake} />
            <StatCard label="Donated" value={formatKg(data.total_donated_kg)} icon={PackageCheck} />
            <StatCard label="Delivered" value={formatKg(data.delivered_kg)} icon={Truck} />
            <StatCard
              label="Still available"
              value={formatKg(data.balance_kg ?? data.undistributed_balance_kg)}
              detail={`${formatKg(data.spoiled_kg)} recorded as spoiled`}
              icon={PackageCheck}
            />
          </div>
          <Panel title="Your donations" description="Every donation, with the quantities and current status.">
            {(data.items ?? []).length === 0 ? (
              <EmptyState
                icon={PackageCheck}
                title="No donation items yet"
                body="Register a donation to begin tracking its outcome."
                action={<Link to="/donations/new" className={cn(buttonVariants(), 'h-9 px-3')}>Register donation</Link>}
              />
            ) : (
              <div className="overflow-x-auto">
                <table className="w-full min-w-[760px] text-left text-sm">
                  <caption className="sr-only">Your donation items</caption>
                  <thead className="bg-oat-deep text-[11px] tracking-[0.08em] text-ink-soft uppercase">
                    <tr>
                      <th scope="col" className="px-3 py-2 font-semibold">Donation</th>
                      <th scope="col" className="px-3 py-2 font-semibold">Status</th>
                      <th scope="col" className="px-3 py-2 font-semibold">Food</th>
                      <th scope="col" className="px-3 py-2 font-semibold">Best before</th>
                      <th scope="col" className="px-3 py-2 font-semibold">Donated</th>
                      <th scope="col" className="px-3 py-2 font-semibold">Delivered</th>
                      <th scope="col" className="px-3 py-2 font-semibold">Available</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-line">
                    {data.items?.map((row) => (
                      <tr key={row.food_item.food_item_id}>
                        <td className="px-3 py-3">
                          <Link to={`/donations/${row.donation_id}`} className="font-medium text-forest underline underline-offset-4">
                            #{row.donation_id}
                          </Link>
                          <p className="text-xs text-ink-soft">{formatLocalDateTime(row.pickup_datetime)}</p>
                        </td>
                        <td className="px-3 py-3"><StatusBadge status={row.donation_status} /></td>
                        <td className="px-3 py-3 font-medium text-charcoal">{row.food_item.item_name}</td>
                        <td className="px-3 py-3">{formatLocalDateTime(row.food_item.best_before)}</td>
                        <td className="px-3 py-3">{formatKg(row.food_item.quantity_kg)}</td>
                        <td className="px-3 py-3">{formatKg(row.food_item.delivered_kg)}</td>
                        <td className="px-3 py-3 font-medium text-forest">{formatKg(row.food_item.available_kg)}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </Panel>
        </>
      ) : null}
    </div>
  )
}
