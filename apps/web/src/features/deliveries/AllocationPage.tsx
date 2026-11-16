import { useMemo, useState } from 'react'
import { Link, useNavigate, useSearchParams } from 'react-router-dom'
import { useQuery } from '@tanstack/react-query'
import { ArrowLeft, Truck } from 'lucide-react'

import { EmptyState } from '@/components/EmptyState'
import { ErrorNotice } from '@/components/ErrorNotice'
import { PageHeader } from '@/components/PageHeader'
import { Panel } from '@/components/Panel'
import { StatusBadge } from '@/components/StatusBadge'
import { Button, buttonVariants } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { ApiRequestError, apiGet, apiGetPaged, apiRequest } from '@/lib/api'
import { formatLocalDateTime } from '@/lib/datetime'
import { formatKg } from '@/lib/format'
import type { Delivery, DonationDetail, DonationSummary, RouteRef } from '@/lib/types'
import { cn } from 'cn'

type BranchReport = { branch_id: number; branch_name: string }

function toIst(value: string): string | null {
  if (!value) return null
  return `${value.length === 16 ? `${value}:00` : value}+05:30`
}

export function AllocationPage() {
  const navigate = useNavigate()
  const [searchParams, setSearchParams] = useSearchParams()
  const donationId = Number(searchParams.get('donation') ?? '') || null
  const [routeId, setRouteId] = useState('')
  const [branchId, setBranchId] = useState('')
  const [scheduled, setScheduled] = useState('')
  const [quantities, setQuantities] = useState<Record<number, string>>({})
  const [error, setError] = useState<string | null>(null)
  const [submitting, setSubmitting] = useState(false)

  const listQuery = useQuery({
    queryKey: ['donations', 'allocatable'],
    queryFn: ({ signal }) => apiGetPaged<DonationSummary>('/api/donations?page_size=100', signal),
  })
  const allocatable = (listQuery.data?.data ?? []).filter((row) =>
    ['APPROVED', 'PARTIALLY_DISTRIBUTED'].includes(row.status),
  )
  const donationQuery = useQuery({
    queryKey: ['donation', donationId],
    queryFn: ({ signal }) => apiGet<DonationDetail>(`/api/donations/${donationId}`, signal),
    enabled: Boolean(donationId),
  })
  const routesQuery = useQuery({
    queryKey: ['routes', 'active'],
    queryFn: ({ signal }) => apiGet<RouteRef[]>('/api/routes?route_status=ACTIVE', signal),
  })
  const branchesQuery = useQuery({
    queryKey: ['managed-branches'],
    queryFn: ({ signal }) => apiGet<BranchReport[]>('/api/reports/branches', signal),
  })

  const donation = donationQuery.data
  const managedIds = useMemo(
    () => new Set((branchesQuery.data ?? []).map((branch) => branch.branch_id)),
    [branchesQuery.data],
  )
  const routes = (routesQuery.data ?? []).filter(
    (route) => managedIds.has(route.managing_branch?.branch_id ?? -1) && route.route_type !== 'DISTRIBUTION',
  )
  const branches = branchesQuery.data ?? []
  const effectiveRouteId =
    routeId || (donation?.pickup_route ? String(donation.pickup_route.route_id) : '')
  const selectedRoute = routes.find((route) => route.route_id === Number(effectiveRouteId))
  const effectiveQuantities = useMemo(() => {
    const next: Record<number, string> = {}
    for (const item of donation?.items ?? []) {
      next[item.food_item_id] =
        quantities[item.food_item_id] ?? (Number(item.available_kg) > 0 ? item.available_kg : '')
    }
    return next
  }, [donation, quantities])

  async function submit() {
    setError(null)
    if (!donationId || !effectiveRouteId || !branchId) {
      setError('Choose a donation, route, and receiving branch.')
      return
    }
    const lines = Object.entries(effectiveQuantities)
      .filter(([, value]) => Number(value) > 0)
      .map(([foodItemId, value]) => ({
        food_item_id: Number(foodItemId),
        quantity_delivered_kg: value,
      }))
    if (lines.length === 0) {
      setError('Allocate at least one kilogram.')
      return
    }
    setSubmitting(true)
    try {
      const result = await apiRequest<Delivery>('/api/deliveries', {
        method: 'POST',
        body: {
          donation_id: donationId,
          route_id: Number(effectiveRouteId),
          recipient_branch_id: Number(branchId),
          scheduled_for: toIst(scheduled),
          items: lines,
        },
      })
      navigate(`/deliveries/${result.data.delivery_id}`)
    } catch (caught) {
      setError(caught instanceof ApiRequestError ? caught.message : 'The delivery could not be created.')
    } finally {
      setSubmitting(false)
    }
  }

  return (
    <div className="space-y-7">
      <PageHeader
        eyebrow="Manager workflow"
        title="Allocate a delivery"
        description="Choose approved food, a route in your branch, and a receiving branch. The database rejects any quantity above what is available today."
        action={
          <Link to="/deliveries" className={cn(buttonVariants({ variant: 'outline' }), 'h-10 px-4')}>
            <ArrowLeft aria-hidden="true" className="size-4" />
            Deliveries
          </Link>
        }
      />

      {error ? <ErrorNotice error={error} /> : null}
      {listQuery.isError ? <ErrorNotice error={listQuery.error} onRetry={() => void listQuery.refetch()} /> : null}

      <div className="grid gap-5 lg:grid-cols-[minmax(0,0.8fr)_minmax(0,1.2fr)]">
        <Panel title="1. Choose a donation" description="Only approved or partially distributed donations can be allocated.">
          {listQuery.isPending ? (
            <p className="text-sm text-ink-soft">Loading donations…</p>
          ) : allocatable.length === 0 ? (
            <EmptyState icon={Truck} title="Nothing to allocate" body="An approved donation appears here after its latest inspection passes." />
          ) : (
            <ul className="space-y-2">
              {allocatable.map((row) => (
                <li key={row.donation_id}>
                  <button
                    type="button"
                    onClick={() => {
                      setSearchParams({ donation: String(row.donation_id) })
                      setRouteId('')
                      setQuantities({})
                    }}
                    className={cn(
                      'w-full rounded-[8px] border p-4 text-left transition-colors',
                      donationId === row.donation_id ? 'border-forest bg-oat-deep' : 'border-line bg-paper hover:bg-oat-deep/60',
                    )}
                  >
                    <div className="flex items-start justify-between gap-3">
                      <div>
                        <p className="font-semibold text-charcoal">Donation #{row.donation_id}</p>
                        <p className="mt-1 text-sm text-ink-soft">{row.donor.full_name ?? 'Donor'} · {formatKg(row.total_quantity_kg)}</p>
                      </div>
                      <StatusBadge status={row.status} />
                    </div>
                  </button>
                </li>
              ))}
            </ul>
          )}
        </Panel>

        <Panel title="2. Route and receiving branch" description="Both must be managed by you.">
          <div className="space-y-4">
            <div className="space-y-1.5">
              <Label htmlFor="allocation-route">Route</Label>
              <select id="allocation-route" value={effectiveRouteId} onChange={(event) => setRouteId(event.target.value)} className="h-9 w-full rounded-[4px] border border-input bg-paper px-3 text-sm">
                <option value="">Choose a route</option>
                {routes.map((route) => (
                  <option key={route.route_id} value={route.route_id}>
                    Route #{route.route_id} · {route.coverage_area?.area_name ?? 'Area'}
                  </option>
                ))}
              </select>
            </div>
            <div className="space-y-1.5">
              <Label htmlFor="allocation-branch">Receiving branch</Label>
              <select id="allocation-branch" value={branchId} onChange={(event) => setBranchId(event.target.value)} className="h-9 w-full rounded-[4px] border border-input bg-paper px-3 text-sm">
                <option value="">Choose a branch</option>
                {branches.map((branch) => (
                  <option key={branch.branch_id} value={branch.branch_id}>{branch.branch_name}</option>
                ))}
              </select>
            </div>
            <div className="space-y-1.5">
              <Label htmlFor="allocation-scheduled">Departure time (IST, optional)</Label>
              <Input id="allocation-scheduled" type="datetime-local" value={scheduled} onChange={(event) => setScheduled(event.target.value)} />
            </div>
            <div className="rounded-[8px] border border-line bg-oat-deep p-4 text-sm leading-6 text-ink-soft">
              <p className="font-semibold text-charcoal">Driver</p>
              <p className="mt-1">
                {selectedRoute?.designated_driver
                  ? `${selectedRoute.designated_driver.full_name} is the designated driver for this route.`
                  : 'The selected route has no designated driver; choose another route or ask an operator to assign one.'}
              </p>
            </div>
          </div>
        </Panel>
      </div>

      <Panel title="3. Quantities" description="Available kilograms already subtract every other allocation and spoilage record.">
        {!donationId ? (
          <EmptyState icon={Truck} title="No donation selected" body="Choose an approved donation to see its items." />
        ) : donationQuery.isPending ? (
          <p className="text-sm text-ink-soft">Loading items…</p>
        ) : donationQuery.isError ? (
          <ErrorNotice error={donationQuery.error} onRetry={() => void donationQuery.refetch()} />
        ) : donation ? (
          <>
            <div className="mb-4 flex flex-wrap items-center gap-3">
              <StatusBadge status={donation.status} />
              <span className="text-sm text-ink-soft">
                Pickup {formatLocalDateTime(donation.pickup_datetime)} · {donation.donor.full_name ?? 'Donor'}
              </span>
            </div>
            <div className="overflow-x-auto">
              <table className="w-full min-w-[660px] text-left text-sm">
                <caption className="sr-only">Donation items available for allocation</caption>
                <thead className="bg-oat-deep text-[11px] tracking-[0.08em] text-ink-soft uppercase">
                  <tr>
                    <th scope="col" className="px-3 py-2 font-semibold">Item</th>
                    <th scope="col" className="px-3 py-2 font-semibold">Best before</th>
                    <th scope="col" className="px-3 py-2 font-semibold">Available</th>
                    <th scope="col" className="px-3 py-2 font-semibold">Allocate (kg)</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-line">
                  {donation.items.map((item) => (
                    <tr key={item.food_item_id}>
                      <td className="px-3 py-3">
                        <p className="font-medium text-charcoal">{item.item_name}</p>
                        <p className="text-xs text-ink-soft">{item.category?.category_name ?? 'Uncategorised'}</p>
                      </td>
                      <td className="px-3 py-3">{formatLocalDateTime(item.best_before)}</td>
                      <td className="px-3 py-3 font-medium text-forest">{formatKg(item.available_kg)}</td>
                      <td className="px-3 py-3">
                        <Input
                          aria-label={`Allocate ${item.item_name}`}
                          inputMode="decimal"
                          value={effectiveQuantities[item.food_item_id] ?? ''}
                          onChange={(event) =>
                            setQuantities((current) => ({ ...current, [item.food_item_id]: event.target.value }))
                          }
                          className="h-8 w-32"
                        />
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
            <div className="mt-5 flex justify-end">
              <Button type="button" disabled={submitting} onClick={() => void submit()}>
                <Truck aria-hidden="true" className="size-4" />
                {submitting ? 'Creating…' : 'Create delivery'}
              </Button>
            </div>
          </>
        ) : null}
      </Panel>
    </div>
  )
}
