import { useState } from 'react'
import { Link, useSearchParams } from 'react-router-dom'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { ClipboardCheck, ShieldAlert } from 'lucide-react'

import { EmptyState } from '@/components/EmptyState'
import { ErrorNotice } from '@/components/ErrorNotice'
import { PageHeader } from '@/components/PageHeader'
import { Panel } from '@/components/Panel'
import { StatusBadge } from '@/components/StatusBadge'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { useAuth } from '@/features/auth/AuthProvider'
import { ApiRequestError, apiGet, apiGetPaged, apiRequest } from '@/lib/api'
import { formatLocalDateTime } from '@/lib/datetime'
import { formatKg, titleCase } from '@/lib/format'
import type { DonationDetail, DonationSummary, Inspection } from '@/lib/types'

type QueueRow = DonationSummary & { latest_inspection: Inspection | null }

export function InspectionsPage() {
  const { user } = useAuth()
  const [searchParams, setSearchParams] = useSearchParams()
  const selected = Number(searchParams.get('donation') ?? '') || null
  const queryClient = useQueryClient()
  const [error, setError] = useState<string | null>(null)

  const queueQuery = useQuery({
    queryKey: ['inspection-queue'],
    queryFn: ({ signal }) =>
      apiGetPaged<QueueRow>('/api/inspections/queue?page_size=100', signal),
  })
  const recentQuery = useQuery({
    queryKey: ['inspections', 'recent'],
    queryFn: ({ signal }) =>
      apiGetPaged<Inspection>('/api/inspections?page_size=10', signal),
  })
  const donationQuery = useQuery({
    queryKey: ['donation', selected],
    queryFn: ({ signal }) => apiGet<DonationDetail>(`/api/donations/${selected}`, signal),
    enabled: Boolean(selected),
  })

  const queue = queueQuery.data?.data ?? []
  const canInspect = user?.role === 'SAFETY_INSPECTOR'

  function select(donationId: number | null) {
    const next = new URLSearchParams(searchParams)
    if (donationId) next.set('donation', String(donationId))
    else next.delete('donation')
    setSearchParams(next)
    setError(null)
  }

  async function afterInspect() {
    select(null)
    await queryClient.invalidateQueries({ queryKey: ['inspection-queue'] })
    await queryClient.invalidateQueries({ queryKey: ['inspections'] })
    await queryClient.invalidateQueries({ queryKey: ['overview'] })
  }

  return (
    <div className="space-y-7">
      <PageHeader
        eyebrow="Safety workflow"
        title="Inspections"
        description="Collected food waits here until a safety inspector records a result. The latest inspection decides whether the donation can be approved."
      />

      {queueQuery.isError ? (
        <ErrorNotice error={queueQuery.error} onRetry={() => void queueQuery.refetch()} />
      ) : null}
      {error ? <ErrorNotice error={error} /> : null}

      <div className="grid gap-5 xl:grid-cols-[minmax(0,1fr)_minmax(0,1.1fr)]">
        <Panel
          title="Waiting for inspection"
          description={`${queue.length} donation${queue.length === 1 ? '' : 's'} in your scope.`}
        >
          {queueQuery.isPending ? (
            <p className="text-sm text-ink-soft">Loading queue…</p>
          ) : queue.length === 0 ? (
            <EmptyState
              icon={ClipboardCheck}
              title="Queue is clear"
              body="No collected donation is waiting for a safety decision."
            />
          ) : (
            <ul className="divide-y divide-line">
              {queue.map((row) => (
                <li key={row.donation_id} className="py-4 first:pt-0 last:pb-0">
                  <div className="flex flex-wrap items-start justify-between gap-3">
                    <div>
                      <p className="font-semibold text-charcoal">Donation #{row.donation_id}</p>
                      <p className="mt-1 text-sm text-ink-soft">
                        {row.donor.full_name ?? 'Donor'} · {formatKg(row.total_quantity_kg)} · {row.item_count} item{row.item_count === 1 ? '' : 's'}
                      </p>
                      <p className="mt-1 text-xs text-ink-soft">
                        Collected for pickup {formatLocalDateTime(row.pickup_datetime)}
                      </p>
                    </div>
                    <div className="flex items-center gap-2">
                      <StatusBadge status={row.status} />
                      <Button
                        type="button"
                        size="sm"
                        variant={selected === row.donation_id ? 'default' : 'outline'}
                        onClick={() => select(row.donation_id)}
                        disabled={!canInspect}
                      >
                        {selected === row.donation_id ? 'Selected' : canInspect ? 'Inspect' : 'View only'}
                      </Button>
                    </div>
                  </div>
                  {row.latest_inspection ? (
                    <p className="mt-2 text-xs text-ink-soft">
                      Previous result: {titleCase(row.latest_inspection.safety_status)} on {formatLocalDateTime(row.latest_inspection.inspected_at)}
                    </p>
                  ) : null}
                </li>
              ))}
            </ul>
          )}
        </Panel>

        <Panel
          title={selected ? `Inspection for donation #${selected}` : 'Record a result'}
          description={
            canInspect
              ? 'Temperature and packaging are stored with the inspector and the timestamp.'
              : 'Managers can see the queue and the result but cannot record an inspection.'
          }
        >
          {!selected ? (
            <EmptyState
              icon={ClipboardCheck}
              title="Choose a donation"
              body="Select a collected donation from the queue to record its safety result."
            />
          ) : donationQuery.isPending ? (
            <p className="text-sm text-ink-soft">Loading donation…</p>
          ) : donationQuery.isError ? (
            <ErrorNotice error={donationQuery.error} onRetry={() => void donationQuery.refetch()} />
          ) : donationQuery.data ? (
            <InspectionPanel
              donation={donationQuery.data}
              disabled={!canInspect}
              onSaved={afterInspect}
              onError={setError}
            />
          ) : null}
        </Panel>
      </div>

      <Panel title="Recent inspections" description="Newest first. The log is append-only.">
        {recentQuery.isPending ? (
          <p className="text-sm text-ink-soft">Loading inspections…</p>
        ) : recentQuery.isError ? (
          <ErrorNotice error={recentQuery.error} onRetry={() => void recentQuery.refetch()} />
        ) : (recentQuery.data?.data.length ?? 0) === 0 ? (
          <EmptyState icon={ShieldAlert} title="No inspections yet" body="Results appear here after an inspector records them." />
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full min-w-[620px] text-left text-sm">
              <caption className="sr-only">Recent inspections</caption>
              <thead className="bg-oat-deep text-[11px] tracking-[0.08em] text-ink-soft uppercase">
                <tr>
                  <th scope="col" className="px-3 py-2 font-semibold">Donation</th>
                  <th scope="col" className="px-3 py-2 font-semibold">Result</th>
                  <th scope="col" className="px-3 py-2 font-semibold">Temperature</th>
                  <th scope="col" className="px-3 py-2 font-semibold">Inspector</th>
                  <th scope="col" className="px-3 py-2 font-semibold">When</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-line">
                {recentQuery.data?.data.map((row) => (
                  <tr key={row.inspection_id}>
                    <td className="px-3 py-3">
                      <Link to={`/donations/${row.donation_id}`} className="font-medium text-forest underline underline-offset-4">
                        #{row.donation_id}
                      </Link>
                    </td>
                    <td className="px-3 py-3"><StatusBadge status={row.safety_status} /></td>
                    <td className="px-3 py-3">{row.temperature_c ?? '—'} °C</td>
                    <td className="px-3 py-3">{row.inspector.full_name ?? 'Inspector'}</td>
                    <td className="px-3 py-3 text-ink-soft">{formatLocalDateTime(row.inspected_at)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </Panel>
    </div>
  )
}

function InspectionPanel({
  donation,
  disabled,
  onSaved,
  onError,
}: {
  donation: DonationDetail
  disabled: boolean
  onSaved: () => Promise<void>
  onError: (message: string | null) => void
}) {
  const [temperature, setTemperature] = useState('')
  const [packaging, setPackaging] = useState('INTACT')
  const [status, setStatus] = useState('PASSED')
  const [remarks, setRemarks] = useState('')
  const mutation = useMutation({
    mutationFn: async () => {
      onError(null)
      return apiRequest<Inspection>('/api/inspections', {
        method: 'POST',
        body: {
          donation_id: donation.donation_id,
          temperature_c: temperature || null,
          packaging_integrity: packaging,
          safety_status: status,
          remarks: remarks || null,
        },
      })
    },
    onSuccess: async () => {
      setTemperature('')
      setRemarks('')
      await onSaved()
    },
    onError: (caught: unknown) =>
      onError(caught instanceof ApiRequestError ? caught.message : 'Inspection could not be recorded.'),
  })

  return (
    <div className="space-y-4">
      <div className="rounded-[8px] bg-oat-deep p-4">
        <p className="text-sm font-semibold text-charcoal">
          {donation.donor.full_name ?? 'Donor'} · {formatKg(donation.total_quantity_kg)}
        </p>
        <ul className="mt-2 space-y-1 text-sm text-ink-soft">
          {donation.items.map((item) => (
            <li key={item.food_item_id}>
              {item.item_name} · {formatKg(item.quantity_kg)} · best before {formatLocalDateTime(item.best_before)}
            </li>
          ))}
        </ul>
      </div>
      <form
        className="space-y-4"
        onSubmit={(event) => {
          event.preventDefault()
          mutation.mutate()
        }}
      >
        <div className="grid gap-4 sm:grid-cols-2">
          <div className="space-y-1.5">
            <Label htmlFor="temperature">Temperature (°C)</Label>
            <Input id="temperature" inputMode="decimal" value={temperature} onChange={(event) => setTemperature(event.target.value)} disabled={disabled} />
          </div>
          <div className="space-y-1.5">
            <Label htmlFor="packaging">Packaging</Label>
            <select id="packaging" value={packaging} onChange={(event) => setPackaging(event.target.value)} disabled={disabled} className="h-9 w-full rounded-[4px] border border-input bg-paper px-3 text-sm">
              <option value="INTACT">Intact</option>
              <option value="DAMAGED">Damaged</option>
              <option value="NOT_APPLICABLE">Not applicable</option>
            </select>
          </div>
          <div className="space-y-1.5">
            <Label htmlFor="safety-status">Result</Label>
            <select id="safety-status" value={status} onChange={(event) => setStatus(event.target.value)} disabled={disabled} className="h-9 w-full rounded-[4px] border border-input bg-paper px-3 text-sm">
              <option value="PASSED">Passed</option>
              <option value="FAILED">Failed</option>
              <option value="NEEDS_REVIEW">Needs review</option>
            </select>
          </div>
          <div className="space-y-1.5 sm:col-span-2">
            <Label htmlFor="remarks">Remarks</Label>
            <textarea id="remarks" value={remarks} onChange={(event) => setRemarks(event.target.value)} disabled={disabled} rows={3} maxLength={1000} className="w-full rounded-[4px] border border-input bg-paper px-3 py-2 text-sm text-charcoal" />
          </div>
        </div>
        <Button type="submit" disabled={disabled || mutation.isPending}>
          {mutation.isPending ? 'Recording…' : 'Record inspection'}
        </Button>
        <p className="text-xs leading-5 text-ink-soft">
          A failed result makes rejection the only possible next status. A newer
          passing inspection supersedes it.
        </p>
      </form>
    </div>
  )
}
