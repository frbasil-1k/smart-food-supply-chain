import { useState } from 'react'
import { Link, useSearchParams } from 'react-router-dom'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { PackageX } from 'lucide-react'

import { EmptyState } from '@/components/EmptyState'
import { ErrorNotice } from '@/components/ErrorNotice'
import { PageHeader } from '@/components/PageHeader'
import { Panel } from '@/components/Panel'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { useAuth } from '@/features/auth/AuthProvider'
import { ApiRequestError, apiGet, apiGetPaged, apiRequest } from '@/lib/api'
import { formatLocalDateTime } from '@/lib/datetime'
import { formatKg } from '@/lib/format'
import type { Delivery, DonationDetail, DonationSummary } from '@/lib/types'

type Spoilage = {
  spoilage_id: number
  food_item_id: number
  item_name: string | null
  donation_id: number | null
  reported_by: { user_id: number; full_name: string | null }
  quantity_spoiled_kg: string
  reason: string
  reported_at: string
}

export function SpoilagePage() {
  const { user } = useAuth()
  const queryClient = useQueryClient()
  const [searchParams] = useSearchParams()
  const deliveryId = Number(searchParams.get('delivery') ?? '') || null
  const [donationId, setDonationId] = useState('')
  const [itemId, setItemId] = useState('')
  const [quantity, setQuantity] = useState('')
  const [reason, setReason] = useState('')
  const [error, setError] = useState<string | null>(null)
  const [success, setSuccess] = useState<string | null>(null)

  const deliveryQuery = useQuery({
    queryKey: ['delivery', deliveryId],
    queryFn: ({ signal }) => apiGet<Delivery>(`/api/deliveries/${deliveryId}`, signal),
    enabled: Boolean(deliveryId),
  })
  const donationsQuery = useQuery({
    queryKey: ['donations', 'spoilage'],
    queryFn: ({ signal }) => apiGetPaged<DonationSummary>('/api/donations?page_size=100', signal),
    enabled: !deliveryId,
  })
  const allocatable = (donationsQuery.data?.data ?? []).filter((row) =>
    ['APPROVED', 'PARTIALLY_DISTRIBUTED'].includes(row.status),
  )
  const effectiveDonationId =
    donationId || (deliveryQuery.data ? String(deliveryQuery.data.donation.donation_id) : '')
  const effectiveItemId =
    itemId || (deliveryQuery.data?.items?.[0] ? String(deliveryQuery.data.items[0].food_item_id) : '')

  const donationQuery = useQuery({
    queryKey: ['donation', effectiveDonationId],
    queryFn: ({ signal }) => apiGet<DonationDetail>(`/api/donations/${effectiveDonationId}`, signal),
    enabled: Boolean(effectiveDonationId),
  })
  const listQuery = useQuery({
    queryKey: ['spoilage', effectiveDonationId],
    queryFn: ({ signal }) =>
      apiGetPaged<Spoilage>(
        `/api/spoilage?page_size=50${effectiveDonationId ? `&donation_id=${effectiveDonationId}` : ''}`,
        signal,
      ),
  })


  const availableItems = donationQuery.data?.items.filter((item) => Number(item.available_kg) > 0) ?? []

  const mutation = useMutation({
    mutationFn: async () => {
      setError(null)
      setSuccess(null)
      return apiRequest<Spoilage>('/api/spoilage', {
        method: 'POST',
        body: {
          food_item_id: Number(effectiveItemId),
          quantity_spoiled_kg: quantity,
          reason: reason.trim(),
        },
      })
    },
    onSuccess: async (result) => {
      setQuantity('')
      setReason('')
      setSuccess(`Recorded ${result.data.quantity_spoiled_kg} kg of spoilage.`)
      await queryClient.invalidateQueries({ queryKey: ['spoilage'] })
      await queryClient.invalidateQueries({ queryKey: ['donation'] })
      await queryClient.invalidateQueries({ queryKey: ['overview'] })
    },
    onError: (caught: unknown) =>
      setError(caught instanceof ApiRequestError ? caught.message : 'Spoilage could not be recorded.'),
  })

  const canRecord = user?.role === 'NGO_MANAGER' || user?.role === 'DRIVER'
  const rows = listQuery.data?.data ?? []

  return (
    <div className="space-y-7">
      <PageHeader
        eyebrow="Exception handling"
        title="Spoilage"
        description="Spoiled kilograms reduce the available quantity and move the donation toward a reconciled balance. They are never counted as delivered."
      />

      {error ? <ErrorNotice error={error} /> : null}
      {success ? (
        <div role="status" className="rounded-[8px] border border-line bg-oat-deep px-4 py-3 text-sm text-charcoal">
          {success}
        </div>
      ) : null}

      {canRecord ? (
        <Panel title="Record spoilage" description="The database refuses any quantity above the item's available kilograms.">
          <form
            className="space-y-4"
            onSubmit={(event) => {
              event.preventDefault()
              mutation.mutate()
            }}
          >
            <div className="grid gap-4 md:grid-cols-2">
              <div className="space-y-1.5">
                <Label htmlFor="spoilage-donation">Donation</Label>
                {deliveryId ? (
                  <p className="rounded-[4px] border border-line bg-oat-deep px-3 py-2 text-sm text-charcoal">
                    Delivery #{deliveryId} · donation #{deliveryQuery.data?.donation.donation_id ?? '…'}
                  </p>
                ) : (
                  <select
                    id="spoilage-donation"
                    value={effectiveDonationId}
                    onChange={(event) => {
                      setDonationId(event.target.value)
                      setItemId('')
                    }}
                    className="h-9 w-full rounded-[4px] border border-input bg-paper px-3 text-sm"
                  >
                    <option value="">Choose an approved donation</option>
                    {allocatable.map((row) => (
                      <option key={row.donation_id} value={row.donation_id}>
                        #{row.donation_id} · {row.donor.full_name ?? 'Donor'} · {formatKg(row.total_quantity_kg)}
                      </option>
                    ))}
                  </select>
                )}
              </div>
              <div className="space-y-1.5">
                <Label htmlFor="spoilage-item">Food item</Label>
                <select
                  id="spoilage-item"
                  value={effectiveItemId}
                  onChange={(event) => setItemId(event.target.value)}
                  className="h-9 w-full rounded-[4px] border border-input bg-paper px-3 text-sm"
                  disabled={!effectiveDonationId}
                >
                  <option value="">Choose an item</option>
                  {availableItems.map((item) => (
                    <option key={item.food_item_id} value={item.food_item_id}>
                      {item.item_name} · {formatKg(item.available_kg)} available
                    </option>
                  ))}
                  {availableItems.length === 0 && donationQuery.data
                    ? donationQuery.data.items.map((item) => (
                        <option key={item.food_item_id} value={item.food_item_id} disabled>
                          {item.item_name} · no available quantity
                        </option>
                      ))
                    : null}
                </select>
              </div>
              <div className="space-y-1.5">
                <Label htmlFor="spoilage-quantity">Spoiled quantity (kg)</Label>
                <Input id="spoilage-quantity" inputMode="decimal" value={quantity} onChange={(event) => setQuantity(event.target.value)} required />
              </div>
              <div className="space-y-1.5">
                <Label htmlFor="spoilage-reason">Reason</Label>
                <Input id="spoilage-reason" value={reason} onChange={(event) => setReason(event.target.value)} minLength={3} maxLength={255} required />
              </div>
            </div>
            <Button type="submit" disabled={!effectiveItemId || mutation.isPending}>
              <PackageX aria-hidden="true" className="size-4" />
              {mutation.isPending ? 'Recording…' : 'Record spoilage'}
            </Button>
          </form>
        </Panel>
      ) : (
        <Panel title="Read-only" description="Only managers and drivers can record spoilage.">
          <p className="text-sm text-ink-soft">You can read spoilage records in your scope but cannot create one.</p>
        </Panel>
      )}

      <Panel title="Spoilage records" description="Newest first.">
        {listQuery.isError ? <ErrorNotice error={listQuery.error} onRetry={() => void listQuery.refetch()} /> : null}
        {listQuery.isPending ? <p className="text-sm text-ink-soft">Loading records…</p> : null}
        {listQuery.data ? (
          rows.length === 0 ? (
            <EmptyState icon={PackageX} title="No spoilage recorded" body="Spoiled food will appear here with its reporter and reason." />
          ) : (
            <div className="overflow-x-auto">
              <table className="w-full min-w-[700px] text-left text-sm">
                <caption className="sr-only">Spoilage records</caption>
                <thead className="bg-oat-deep text-[11px] tracking-[0.08em] text-ink-soft uppercase">
                  <tr>
                    <th scope="col" className="px-3 py-2 font-semibold">Item</th>
                    <th scope="col" className="px-3 py-2 font-semibold">Quantity</th>
                    <th scope="col" className="px-3 py-2 font-semibold">Reason</th>
                    <th scope="col" className="px-3 py-2 font-semibold">Reported by</th>
                    <th scope="col" className="px-3 py-2 font-semibold">When</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-line">
                  {rows.map((row) => (
                    <tr key={row.spoilage_id}>
                      <td className="px-3 py-3">
                        {row.donation_id ? (
                          <Link to={`/donations/${row.donation_id}`} className="font-medium text-forest underline underline-offset-4">
                            {row.item_name ?? `Item #${row.food_item_id}`}
                          </Link>
                        ) : (
                          row.item_name ?? `Item #${row.food_item_id}`
                        )}
                      </td>
                      <td className="px-3 py-3">{formatKg(row.quantity_spoiled_kg)}</td>
                      <td className="px-3 py-3">{row.reason}</td>
                      <td className="px-3 py-3">{row.reported_by.full_name ?? 'User'}</td>
                      <td className="px-3 py-3 text-ink-soft">{formatLocalDateTime(row.reported_at)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )
        ) : null}
      </Panel>
    </div>
  )
}
