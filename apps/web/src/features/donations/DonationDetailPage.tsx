import { useState } from 'react'
import { Link, useParams } from 'react-router-dom'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import {
  ArrowLeft,
  Check,
  ClipboardCheck,
  PackageCheck,
  Route as RouteIcon,
  Truck,
  X,
} from 'lucide-react'

import { EmptyState } from '@/components/EmptyState'
import { ErrorNotice } from '@/components/ErrorNotice'
import { PageHeader } from '@/components/PageHeader'
import { Panel } from '@/components/Panel'
import { StatusBadge } from '@/components/StatusBadge'
import { Button, buttonVariants } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { useAuth } from '@/features/auth/AuthProvider'
import { ApiRequestError, apiGet, apiRequest } from '@/lib/api'
import { formatLocalDateTime } from '@/lib/datetime'
import { formatKg, titleCase } from '@/lib/format'
import type { DonationDetail, RouteRef } from '@/lib/types'
import { cn } from 'cn'

type BranchReport = { branch_id: number; branch_name: string }

export function DonationDetailPage() {
  const { id } = useParams()
  const donationId = Number(id)
  const { user } = useAuth()
  const queryClient = useQueryClient()
  const [error, setError] = useState<string | null>(null)
  const [routeId, setRouteId] = useState('')

  const query = useQuery({
    queryKey: ['donation', donationId],
    queryFn: ({ signal }) => apiGet<DonationDetail>(`/api/donations/${donationId}`, signal),
    enabled: Number.isFinite(donationId),
  })
  const routesQuery = useQuery({
    queryKey: ['routes', 'active'],
    queryFn: ({ signal }) => apiGet<RouteRef[]>('/api/routes?route_status=ACTIVE', signal),
    enabled: user?.role === 'NGO_MANAGER',
  })
  const branchesQuery = useQuery({
    queryKey: ['managed-branches'],
    queryFn: ({ signal }) => apiGet<BranchReport[]>('/api/reports/branches', signal),
    enabled: user?.role === 'NGO_MANAGER',
  })

  const donation = query.data
  const managedIds = new Set((branchesQuery.data ?? []).map((branch) => branch.branch_id))
  const assignableRoutes = (routesQuery.data ?? []).filter(
    (route) =>
      managedIds.has(route.managing_branch?.branch_id ?? -1) &&
      route.route_status === 'ACTIVE' &&
      route.route_type !== 'DISTRIBUTION',
  )

  const statusMutation = useMutation({
    mutationFn: async (target: string) => {
      setError(null)
      return apiRequest(`/api/donations/${donationId}/status`, {
        method: 'PATCH',
        body: { target_status: target },
      })
    },
    onSuccess: async () => {
      await queryClient.invalidateQueries({ queryKey: ['donation', donationId] })
      await queryClient.invalidateQueries({ queryKey: ['donations'] })
      await queryClient.invalidateQueries({ queryKey: ['overview'] })
    },
    onError: (caught: unknown) => {
      setError(caught instanceof ApiRequestError ? caught.message : 'Status change failed.')
    },
  })

  const routeMutation = useMutation({
    mutationFn: async () => {
      setError(null)
      return apiRequest(`/api/donations/${donationId}/route`, {
        method: 'PATCH',
        body: { pickup_route_id: Number(routeId) },
      })
    },
    onSuccess: async () => {
      setRouteId('')
      await queryClient.invalidateQueries({ queryKey: ['donation', donationId] })
      await queryClient.invalidateQueries({ queryKey: ['donations'] })
    },
    onError: (caught: unknown) => {
      setError(caught instanceof ApiRequestError ? caught.message : 'Route assignment failed.')
    },
  })

  if (query.isError) {
    return (
      <div className="space-y-6">
        <PageHeader eyebrow="Donation chain" title="Donation detail" />
        <ErrorNotice error={query.error} onRetry={() => void query.refetch()} />
      </div>
    )
  }
  if (query.isPending || !donation) {
    return <div className="rounded-[8px] border border-line bg-paper p-6 text-sm text-ink-soft">Loading donation…</div>
  }

  const latest = donation.latest_inspection
  const canManage = user?.role === 'NGO_MANAGER'
  const canCollect =
    user?.role === 'DRIVER' &&
    donation.status === 'SCHEDULED' &&
    donation.pickup_route?.designated_driver_user_id === user.user_id
  const canCancel = user?.role === 'DONOR' && donation.status === 'PENDING'
  const canInspect = user?.role === 'SAFETY_INSPECTOR' && donation.status === 'COLLECTED'

  return (
    <div className="space-y-7">
      <PageHeader
        eyebrow={`Donation #${donation.donation_id}`}
        title={`${donation.item_count} item${donation.item_count === 1 ? '' : 's'} · ${formatKg(donation.total_quantity_kg)}`}
        description={`Registered by ${donation.donor.full_name ?? 'the donor'} for pickup ${formatLocalDateTime(donation.pickup_datetime)} (Asia/Kolkata).`}
        action={
          <>
            <Link to="/donations" className={cn(buttonVariants({ variant: 'outline' }), 'h-10 px-4')}>
              <ArrowLeft aria-hidden="true" className="size-4" />
              Donations
            </Link>
            {canManage && ['APPROVED', 'PARTIALLY_DISTRIBUTED'].includes(donation.status) ? (
              <Link to={`/allocation?donation=${donation.donation_id}`} className={cn(buttonVariants(), 'h-10 px-4')}>
                <Truck aria-hidden="true" className="size-4" />
                Allocate delivery
              </Link>
            ) : null}
            {canInspect ? (
              <Link to={`/inspections?donation=${donation.donation_id}`} className={cn(buttonVariants(), 'h-10 px-4')}>
                <ClipboardCheck aria-hidden="true" className="size-4" />
                Inspect
              </Link>
            ) : null}
          </>
        }
      />

      {error ? <ErrorNotice error={error} /> : null}

      <div className="grid gap-5 lg:grid-cols-[minmax(0,1.3fr)_minmax(0,0.7fr)]">
        <Panel title="Status and actions" description="The service owns every allowed transition." accent>
          <div className="flex flex-wrap items-center gap-3">
            <StatusBadge status={donation.status} />
            <span className="text-sm text-ink-soft">Urgency: {titleCase(donation.urgency)}</span>
          </div>
          <div className="mt-5 flex flex-wrap gap-2">
            {canManage && donation.status === 'PENDING' ? (
              <>
                <Button type="button" size="sm" disabled={!donation.pickup_route || statusMutation.isPending} onClick={() => statusMutation.mutate('SCHEDULED')}>
                  <Check aria-hidden="true" className="size-4" />
                  Schedule
                </Button>
                <Button type="button" variant="outline" size="sm" disabled={statusMutation.isPending} onClick={() => statusMutation.mutate('REJECTED')}>
                  <X aria-hidden="true" className="size-4" />
                  Reject
                </Button>
              </>
            ) : null}
            {canManage && donation.status === 'SCHEDULED' ? (
              <Button type="button" size="sm" disabled={statusMutation.isPending} onClick={() => statusMutation.mutate('COLLECTED')}>
                Mark collected
              </Button>
            ) : null}
            {canManage && donation.status === 'COLLECTED' ? (
              <>
                <Button type="button" size="sm" disabled={latest?.safety_status !== 'PASSED' || statusMutation.isPending} onClick={() => statusMutation.mutate('APPROVED')}>
                  Approve
                </Button>
                <Button type="button" variant="outline" size="sm" disabled={latest?.safety_status !== 'FAILED' || statusMutation.isPending} onClick={() => statusMutation.mutate('REJECTED')}>
                  Reject
                </Button>
              </>
            ) : null}
            {canCollect ? (
              <Button type="button" size="sm" disabled={statusMutation.isPending} onClick={() => statusMutation.mutate('COLLECTED')}>
                Mark collected
              </Button>
            ) : null}
            {canCancel ? (
              <Button type="button" variant="outline" size="sm" disabled={statusMutation.isPending} onClick={() => statusMutation.mutate('CANCELLED')}>
                Cancel donation
              </Button>
            ) : null}
            {!(
              (canManage && ['PENDING', 'SCHEDULED', 'COLLECTED'].includes(donation.status)) ||
              canCollect ||
              canCancel ||
              canInspect
            ) ? (
              <p className="text-sm text-ink-soft">
                No action is available at this status. The stored reconciliation is final
                unless an operator corrects the data.
              </p>
            ) : null}
          </div>
          {donation.status === 'COLLECTED' && latest?.safety_status !== 'PASSED' && latest?.safety_status !== 'FAILED' ? (
            <p className="mt-4 border-l-[3px] border-l-terracotta pl-3 text-sm leading-6 text-ink-soft">
              Approval waits for an inspection result. The latest inspection is {latest ? latest.safety_status.replaceAll('_', ' ').toLowerCase() : 'not recorded'}.
            </p>
          ) : null}
        </Panel>

        <Panel title="Pickup and route" description="An unrouted donation is anchored to the donor's branch.">
          <dl className="space-y-3 text-sm">
            <div>
              <dt className="text-xs tracking-[0.08em] text-ink-soft uppercase">Address</dt>
              <dd className="mt-1 text-charcoal">{donation.pickup_address ?? 'Not provided'}</dd>
            </div>
            <div>
              <dt className="text-xs tracking-[0.08em] text-ink-soft uppercase">Pincode / contact</dt>
              <dd className="mt-1 text-charcoal">{donation.pickup_pincode ?? '—'} · {donation.pickup_contact ?? '—'}</dd>
            </div>
            <div>
              <dt className="text-xs tracking-[0.08em] text-ink-soft uppercase">Pickup route</dt>
              <dd className="mt-1 text-charcoal">
                {donation.pickup_route ? `Route #${donation.pickup_route.route_id}` : 'Unrouted'}
              </dd>
            </div>
          </dl>
          {canManage && ['PENDING', 'SCHEDULED'].includes(donation.status) ? (
            <form
              className="mt-5 space-y-2 border-t border-line pt-4"
              onSubmit={(event) => {
                event.preventDefault()
                if (routeId) routeMutation.mutate()
              }}
            >
              <Label htmlFor="assign-route">Assign a route in your branch</Label>
              <div className="flex flex-col gap-2 sm:flex-row">
                <select
                  id="assign-route"
                  value={routeId}
                  onChange={(event) => setRouteId(event.target.value)}
                  className="h-9 min-w-0 flex-1 rounded-[4px] border border-input bg-paper px-3 text-sm text-charcoal"
                >
                  <option value="">Choose a route</option>
                  {assignableRoutes.map((route) => (
                    <option key={route.route_id} value={route.route_id}>
                      Route #{route.route_id} · {route.coverage_area?.area_name ?? 'Area'}
                    </option>
                  ))}
                </select>
                <Button type="submit" size="sm" disabled={!routeId || routeMutation.isPending}>
                  <RouteIcon aria-hidden="true" className="size-4" />
                  Assign
                </Button>
              </div>
            </form>
          ) : null}
        </Panel>
      </div>

      <Panel title="Food items" description="Available kilograms are donated minus every allocation and every spoiled kilogram.">
        <div className="overflow-x-auto">
          <table className="w-full min-w-[700px] text-left text-sm">
            <caption className="sr-only">Food items in this donation</caption>
            <thead className="bg-oat-deep text-[11px] tracking-[0.08em] text-ink-soft uppercase">
              <tr>
                <th scope="col" className="px-3 py-2 font-semibold">Item</th>
                <th scope="col" className="px-3 py-2 font-semibold">Best before</th>
                <th scope="col" className="px-3 py-2 font-semibold">Donated</th>
                <th scope="col" className="px-3 py-2 font-semibold">Allocated</th>
                <th scope="col" className="px-3 py-2 font-semibold">Delivered</th>
                <th scope="col" className="px-3 py-2 font-semibold">Spoiled</th>
                <th scope="col" className="px-3 py-2 font-semibold">Available</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-line">
              {donation.items.map((item) => (
                <tr key={item.food_item_id}>
                  <td className="px-3 py-3">
                    <p className="font-medium text-charcoal">{item.item_name}</p>
                    <p className="text-xs text-ink-soft">{item.category?.category_name ?? 'Uncategorised'}</p>
                  </td>
                  <td className="px-3 py-3 text-charcoal">{formatLocalDateTime(item.best_before)}</td>
                  <td className="px-3 py-3">{formatKg(item.quantity_kg)}</td>
                  <td className="px-3 py-3">{formatKg(item.allocated_kg)}</td>
                  <td className="px-3 py-3">{formatKg(item.delivered_kg)}</td>
                  <td className="px-3 py-3">{formatKg(item.spoiled_kg)}</td>
                  <td className="px-3 py-3 font-semibold text-forest">{formatKg(item.available_kg)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </Panel>

      <div className="grid gap-5 lg:grid-cols-2">
        <Panel title="Latest inspection" description="The newest inspection is the only one considered for approval.">
          {latest ? (
            <div className="space-y-3">
              <div className="flex flex-wrap items-center gap-3">
                <StatusBadge status={latest.safety_status} />
                <span className="text-sm text-ink-soft">{formatLocalDateTime(latest.inspected_at)}</span>
              </div>
              <dl className="grid grid-cols-2 gap-3 text-sm">
                <div><dt className="text-ink-soft">Temperature</dt><dd className="font-medium text-charcoal">{latest.temperature_c ?? '—'} °C</dd></div>
                <div><dt className="text-ink-soft">Packaging</dt><dd className="font-medium text-charcoal">{titleCase(latest.packaging_integrity)}</dd></div>
                <div className="col-span-2"><dt className="text-ink-soft">Remarks</dt><dd className="font-medium text-charcoal">{latest.remarks ?? 'None'}</dd></div>
              </dl>
            </div>
          ) : (
            <EmptyState icon={ClipboardCheck} title="Not inspected" body="A safety inspector records the result after the donation is collected." />
          )}
        </Panel>

        <Panel title="Deliveries" description="Only delivered lines count as distribution.">
          {donation.deliveries.length === 0 ? (
            <EmptyState icon={Truck} title="No delivery yet" body="Approved donations can be allocated by a manager." />
          ) : (
            <ul className="divide-y divide-line">
              {donation.deliveries.map((delivery) => (
                <li key={delivery.delivery_id} className="flex flex-wrap items-center justify-between gap-3 py-3 first:pt-0 last:pb-0">
                  <div>
                    <Link to={`/deliveries/${delivery.delivery_id}`} className="font-semibold text-forest underline underline-offset-4">
                      Delivery #{delivery.delivery_id}
                    </Link>
                    <p className="mt-1 text-xs text-ink-soft">{delivery.recipient_branch.branch_name}</p>
                  </div>
                  <StatusBadge status={delivery.status} />
                </li>
              ))}
            </ul>
          )}
        </Panel>
      </div>

      <Panel title="Status history" description="Append-only; system reconciliations are labelled separately.">
        {donation.history.length === 0 ? (
          <p className="text-sm text-ink-soft">No history rows.</p>
        ) : (
          <ol className="space-y-4 border-l border-line pl-5">
            {donation.history.map((row) => (
              <li key={row.history_id} className="relative">
                <span aria-hidden="true" className="absolute top-1.5 -left-[26px] size-2.5 rounded-full bg-forest" />
                <div className="flex flex-wrap items-center gap-2">
                  <StatusBadge status={row.to_status} />
                  {row.from_status ? <span className="text-xs text-ink-soft">from {titleCase(row.from_status)}</span> : null}
                  {row.is_reconstructed ? <span className="text-xs text-ink-soft">reconstructed</span> : null}
                </div>
                <p className="mt-1 text-sm text-charcoal">{row.note ?? 'Status transition'}</p>
                <p className="mt-1 text-xs text-ink-soft">
                  {row.changed_by?.full_name ?? 'System'} · {row.changed_at ? formatLocalDateTime(row.changed_at) : 'No timestamp'}
                </p>
              </li>
            ))}
          </ol>
        )}
      </Panel>

      {canManage && ['PENDING', 'SCHEDULED'].includes(donation.status) ? (
        <Panel title="Add another item" description="Only while the donation is pending or scheduled.">
          <AddItemForm donationId={donationId} onSaved={() => void queryClient.invalidateQueries({ queryKey: ['donation', donationId] })} />
        </Panel>
      ) : null}

      <Input type="hidden" value={donationId} readOnly aria-hidden="true" />
    </div>
  )
}

function AddItemForm({ donationId, onSaved }: { donationId: number; onSaved: () => void }) {
  const [name, setName] = useState('')
  const [category, setCategory] = useState('')
  const [quantity, setQuantity] = useState('')
  const [bestBefore, setBestBefore] = useState('')
  const [error, setError] = useState<string | null>(null)
  const query = useQuery({
    queryKey: ['food-categories'],
    queryFn: ({ signal }) => apiGet<{ category_id: number; category_name: string }[]>('/api/food-categories', signal),
  })
  const mutation = useMutation({
    mutationFn: async () =>
      apiRequest(`/api/donations/${donationId}/items`, {
        method: 'POST',
        body: {
          category_id: Number(category),
          item_name: name,
          quantity_kg: quantity,
          best_before: `${bestBefore.length === 16 ? `${bestBefore}:00` : bestBefore}+05:30`,
        },
      }),
    onSuccess: () => {
      setName('')
      setQuantity('')
      setBestBefore('')
      setError(null)
      onSaved()
    },
    onError: (caught: unknown) => setError(caught instanceof ApiRequestError ? caught.message : 'Item could not be added.'),
  })
  return (
    <form
      className="space-y-4"
      onSubmit={(event) => {
        event.preventDefault()
        mutation.mutate()
      }}
    >
      {error ? <ErrorNotice error={error} /> : null}
      <div className="grid gap-4 md:grid-cols-2">
        <div className="space-y-1.5"><Label htmlFor="new-item-name">Food name</Label><Input id="new-item-name" value={name} onChange={(event) => setName(event.target.value)} required /></div>
        <div className="space-y-1.5">
          <Label htmlFor="new-item-category">Category</Label>
          <select id="new-item-category" value={category} onChange={(event) => setCategory(event.target.value)} required className="h-9 w-full rounded-[4px] border border-input bg-paper px-3 text-sm">
            <option value="">Choose a category</option>
            {(query.data ?? []).map((row) => <option key={row.category_id} value={row.category_id}>{row.category_name}</option>)}
          </select>
        </div>
        <div className="space-y-1.5"><Label htmlFor="new-item-quantity">Quantity (kg)</Label><Input id="new-item-quantity" inputMode="decimal" value={quantity} onChange={(event) => setQuantity(event.target.value)} required /></div>
        <div className="space-y-1.5"><Label htmlFor="new-item-best">Best before (IST)</Label><Input id="new-item-best" type="datetime-local" value={bestBefore} onChange={(event) => setBestBefore(event.target.value)} required /></div>
      </div>
      <Button type="submit" size="sm" disabled={mutation.isPending}><PackageCheck aria-hidden="true" className="size-4" />Add item</Button>
    </form>
  )
}
