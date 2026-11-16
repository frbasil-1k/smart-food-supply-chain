import { useState } from 'react'
import { Link, useParams } from 'react-router-dom'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { ArrowLeft, Check, MapPin, PackageCheck, Star, Truck, X } from 'lucide-react'

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
import { formatKg } from '@/lib/format'
import type { Delivery, Review } from '@/lib/types'
import { cn } from 'cn'

export function DeliveryDetailPage() {
  const { id } = useParams()
  const deliveryId = Number(id)
  const { user } = useAuth()
  const queryClient = useQueryClient()
  const [error, setError] = useState<string | null>(null)
  const query = useQuery({
    queryKey: ['delivery', deliveryId],
    queryFn: ({ signal }) => apiGet<Delivery>(`/api/deliveries/${deliveryId}`, signal),
    enabled: Number.isFinite(deliveryId),
  })
  const delivery = query.data
  const mutation = useMutation({
    mutationFn: async (target: string) => {
      setError(null)
      return apiRequest(`/api/deliveries/${deliveryId}/status`, {
        method: 'PATCH',
        body: { target_status: target },
      })
    },
    onSuccess: async () => {
      await queryClient.invalidateQueries({ queryKey: ['delivery', deliveryId] })
      await queryClient.invalidateQueries({ queryKey: ['deliveries'] })
      await queryClient.invalidateQueries({ queryKey: ['overview'] })
    },
    onError: (caught: unknown) => setError(caught instanceof ApiRequestError ? caught.message : 'The delivery status could not change.'),
  })

  if (query.isError) {
    return (
      <div className="space-y-6">
        <PageHeader eyebrow="Logistics" title="Delivery detail" />
        <ErrorNotice error={query.error} onRetry={() => void query.refetch()} />
      </div>
    )
  }
  if (query.isPending || !delivery) {
    return <div className="rounded-[8px] border border-line bg-paper p-6 text-sm text-ink-soft">Loading delivery…</div>
  }

  const isDriver = user?.role === 'DRIVER'
  const isManager = user?.role === 'NGO_MANAGER'
  const isMyDelivery = delivery.driver?.user_id === user?.user_id

  return (
    <div className="space-y-7">
      <PageHeader
        eyebrow={`Delivery #${delivery.delivery_id}`}
        title={delivery.recipient_branch.branch_name ?? 'Receiving branch'}
        description={`Donation #${delivery.donation.donation_id} · scheduled ${formatLocalDateTime(delivery.scheduled_for)} (Asia/Kolkata).`}
        action={
          <Link to="/deliveries" className={cn(buttonVariants({ variant: 'outline' }), 'h-10 px-4')}>
            <ArrowLeft aria-hidden="true" className="size-4" />
            Deliveries
          </Link>
        }
      />

      {error ? <ErrorNotice error={error} /> : null}

      <div className="grid gap-5 lg:grid-cols-[minmax(0,1.1fr)_minmax(0,0.9fr)]">
        <Panel title="Progress" description="A failed delivery is terminal in this application." accent>
          <div className="flex flex-wrap items-center gap-3">
            <StatusBadge status={delivery.status} />
          </div>
          <div className="mt-5 flex flex-wrap gap-2">
            {isManager && delivery.status === 'PLANNED' ? (
              <>
                <Button type="button" size="sm" variant="outline" disabled={mutation.isPending} onClick={() => mutation.mutate('CANCELLED')}>
                  <X aria-hidden="true" className="size-4" />
                  Cancel and release stock
                </Button>
                <Button type="button" size="sm" variant="outline" disabled={mutation.isPending} onClick={() => mutation.mutate('FAILED')}>
                  Mark failed
                </Button>
              </>
            ) : null}
            {isManager && delivery.status === 'IN_TRANSIT' ? (
              <Button type="button" size="sm" variant="outline" disabled={mutation.isPending} onClick={() => mutation.mutate('FAILED')}>
                Mark failed
              </Button>
            ) : null}
            {isDriver && isMyDelivery && delivery.status === 'PLANNED' ? (
              <Button type="button" size="sm" disabled={mutation.isPending} onClick={() => mutation.mutate('IN_TRANSIT')}>
                <Truck aria-hidden="true" className="size-4" />
                Start delivery
              </Button>
            ) : null}
            {isDriver && isMyDelivery && delivery.status === 'IN_TRANSIT' ? (
              <>
                <Button type="button" size="sm" disabled={mutation.isPending} onClick={() => mutation.mutate('DELIVERED')}>
                  <Check aria-hidden="true" className="size-4" />
                  Mark delivered
                </Button>
                <Button type="button" size="sm" variant="outline" disabled={mutation.isPending} onClick={() => mutation.mutate('FAILED')}>
                  Mark failed
                </Button>
              </>
            ) : null}
            {!isManager && !isDriver ? (
              <p className="text-sm text-ink-soft">This delivery is read-only for your role.</p>
            ) : null}
          </div>
          <p className="mt-4 border-l-[3px] border-l-terracotta pl-3 text-sm leading-6 text-ink-soft">
            Delivery status has no history table in the frozen schema; the current
            status and its timestamps are the authoritative record.
          </p>
        </Panel>

        <Panel title="Route" description="Driver, route, and receiving branch as stored.">
          <dl className="space-y-3 text-sm">
            <div className="flex justify-between gap-4">
              <dt className="text-ink-soft">Driver</dt>
              <dd className="text-right font-medium text-charcoal">{delivery.driver?.full_name ?? 'Unassigned'}</dd>
            </div>
            <div className="flex justify-between gap-4">
              <dt className="text-ink-soft">Route</dt>
              <dd className="text-right font-medium text-charcoal">#{delivery.route.route_id}</dd>
            </div>
            <div className="flex justify-between gap-4">
              <dt className="text-ink-soft">Receiving branch</dt>
              <dd className="text-right font-medium text-charcoal">{delivery.recipient_branch.branch_name}</dd>
            </div>
            <div className="flex justify-between gap-4">
              <dt className="text-ink-soft">Delivered at</dt>
              <dd className="text-right font-medium text-charcoal">{delivery.delivered_at ? formatLocalDateTime(delivery.delivered_at) : 'Not yet'}</dd>
            </div>
          </dl>
          <Link to={`/donations/${delivery.donation.donation_id}`} className={cn(buttonVariants({ variant: 'outline' }), 'mt-5 h-9 px-3')}>
            <MapPin aria-hidden="true" className="size-4" />
            Open source donation
          </Link>
        </Panel>
      </div>

      <Panel title="Delivery items" description="The allocated quantity is what the driver delivers and what reconciliation counts.">
        {(delivery.items ?? []).length === 0 ? (
          <EmptyState icon={PackageCheck} title="No items" body="This delivery has no item lines." />
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full min-w-[520px] text-left text-sm">
              <caption className="sr-only">Delivery items</caption>
              <thead className="bg-oat-deep text-[11px] tracking-[0.08em] text-ink-soft uppercase">
                <tr>
                  <th scope="col" className="px-3 py-2 font-semibold">Food item</th>
                  <th scope="col" className="px-3 py-2 font-semibold">Quantity delivered</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-line">
                {delivery.items?.map((item) => (
                  <tr key={item.delivery_item_id}>
                    <td className="px-3 py-3 font-medium text-charcoal">{item.item_name ?? `Item #${item.food_item_id}`}</td>
                    <td className="px-3 py-3">{formatKg(item.quantity_delivered_kg)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </Panel>

      <Panel title="Receiving manager review" description="One review per delivered delivery, aggregated separately from kilograms.">
        {delivery.review ? (
          <ReviewSummary review={delivery.review} />
        ) : isManager && delivery.status === 'DELIVERED' ? (
          <ReviewForm deliveryId={delivery.delivery_id} onSaved={() => void queryClient.invalidateQueries({ queryKey: ['delivery', deliveryId] })} />
        ) : (
          <EmptyState icon={Star} title="No review yet" body="The receiving branch manager can review the delivery once it is delivered." />
        )}
      </Panel>

      <Panel title="Spoilage" description="Spoiled kilograms are recorded against a food item and never counted as delivered.">
        <Link to={`/spoilage?delivery=${delivery.delivery_id}`} className={cn(buttonVariants({ variant: 'outline' }), 'h-9 px-3')}>
          Record or view spoilage
        </Link>
      </Panel>
    </div>
  )
}

function ReviewSummary({ review }: { review: Review }) {
  return (
    <div className="space-y-2">
      <div className="flex items-center gap-1" aria-label={`${review.rating} out of 5`}>
        {[1, 2, 3, 4, 5].map((value) => (
          <Star key={value} aria-hidden="true" className={cn('size-4', value <= review.rating ? 'fill-terracotta text-terracotta' : 'text-line')} />
        ))}
        <span className="ml-2 text-sm font-medium text-charcoal">{review.rating} / 5</span>
      </div>
      <p className="text-sm text-charcoal">{review.quality_notes ?? 'No notes supplied.'}</p>
      <p className="text-xs text-ink-soft">
        {review.reviewed_by.full_name ?? 'Manager'} · {review.review_date ? formatLocalDateTime(review.review_date) : 'No date'}
      </p>
    </div>
  )
}

function ReviewForm({ deliveryId, onSaved }: { deliveryId: number; onSaved: () => void }) {
  const [rating, setRating] = useState('5')
  const [notes, setNotes] = useState('')
  const [error, setError] = useState<string | null>(null)
  const mutation = useMutation({
    mutationFn: async () => {
      setError(null)
      return apiRequest<Review>(`/api/deliveries/${deliveryId}/review`, {
        method: 'POST',
        body: { rating: Number(rating), quality_notes: notes || null },
      })
    },
    onSuccess: onSaved,
    onError: (caught: unknown) => setError(caught instanceof ApiRequestError ? caught.message : 'The review could not be saved.'),
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
      <div className="grid gap-4 sm:grid-cols-[140px_minmax(0,1fr)]">
        <div className="space-y-1.5">
          <Label htmlFor="rating">Rating</Label>
          <select id="rating" value={rating} onChange={(event) => setRating(event.target.value)} className="h-9 w-full rounded-[4px] border border-input bg-paper px-3 text-sm">
            {[5, 4, 3, 2, 1].map((value) => <option key={value} value={value}>{value} / 5</option>)}
          </select>
        </div>
        <div className="space-y-1.5">
          <Label htmlFor="quality-notes">Quality notes</Label>
          <Input id="quality-notes" value={notes} onChange={(event) => setNotes(event.target.value)} maxLength={1000} />
        </div>
      </div>
      <Button type="submit" size="sm" disabled={mutation.isPending}>{mutation.isPending ? 'Saving…' : 'Save review'}</Button>
    </form>
  )
}
