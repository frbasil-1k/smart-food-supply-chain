import { useQuery } from '@tanstack/react-query'
import { Link } from 'react-router-dom'
import {
  Activity,
  ClipboardCheck,
  ClipboardList,
  Clock3,
  PackageCheck,
  ShieldAlert,
  Truck,
  Users,
} from 'lucide-react'

import { EmptyState } from '@/components/EmptyState'
import { ErrorNotice } from '@/components/ErrorNotice'
import { PageHeader } from '@/components/PageHeader'
import { Panel } from '@/components/Panel'
import { StatCard } from '@/components/StatCard'
import { StatusBadge } from '@/components/StatusBadge'
import { buttonVariants } from '@/components/ui/button'
import { useAuth } from '@/features/auth/AuthProvider'
import { apiGet } from '@/lib/api'
import { formatKg, formatNumber } from '@/lib/format'
import { cn } from 'cn'

type Overview = Record<string, unknown>

function stringValue(data: Overview | undefined, key: string): string {
  const value = data?.[key]
  if (typeof value === 'string') return value
  if (typeof value === 'number') return String(value)
  return '0'
}

function numberValue(data: Overview | undefined, key: string): number {
  const value = data?.[key]
  return typeof value === 'number' ? value : Number(value ?? 0)
}

const roleLabel = {
  DONOR: 'Donor',
  NGO_MANAGER: 'NGO manager',
  DRIVER: 'Driver',
  SAFETY_INSPECTOR: 'Safety inspector',
} as const

export function RoleHomePage() {
  const { user } = useAuth()
  const role = user?.role
  const query = useQuery({
    queryKey: ['overview', role],
    queryFn: ({ signal }) => apiGet<Overview>('/api/reports/overview', signal),
    enabled: Boolean(role),
  })
  const data = query.data

  if (!user) return null

  const title = role === 'DRIVER' ? 'Today' : 'Overview'
  const description =
    role === 'DONOR'
      ? 'Your donations and their real distribution outcomes.'
      : role === 'NGO_MANAGER'
        ? 'The donation, inspection, and delivery work waiting in your branches.'
        : role === 'DRIVER'
          ? 'Your assigned deliveries and last seven days of completed work.'
          : 'The inspections waiting for a safety decision.'

  return (
    <div className="space-y-8">
      <PageHeader
        eyebrow={`${user.full_name} · ${roleLabel[user.role]}`}
        title={title}
        description={description}
        action={
          role === 'DONOR' ? (
            <Link to="/donations/new" className={cn(buttonVariants(), 'h-10 px-4')}>
              <PackageCheck aria-hidden="true" className="size-4" />
              Register donation
            </Link>
          ) : role === 'NGO_MANAGER' ? (
            <Link to="/donations" className={cn(buttonVariants(), 'h-10 px-4')}>
              <ClipboardList aria-hidden="true" className="size-4" />
              Review donations
            </Link>
          ) : role === 'DRIVER' ? (
            <Link to="/deliveries" className={cn(buttonVariants(), 'h-10 px-4')}>
              <Truck aria-hidden="true" className="size-4" />
              Open deliveries
            </Link>
          ) : (
            <Link to="/inspections" className={cn(buttonVariants(), 'h-10 px-4')}>
              <ClipboardCheck aria-hidden="true" className="size-4" />
              Open queue
            </Link>
          )
        }
      />

      {query.isError ? (
        <ErrorNotice error={query.error} onRetry={() => void query.refetch()} />
      ) : null}

      {role === 'DONOR' ? (
        <DonorHome data={data} loading={query.isPending} />
      ) : role === 'NGO_MANAGER' ? (
        <ManagerHome data={data} loading={query.isPending} />
      ) : role === 'DRIVER' ? (
        <DriverHome data={data} loading={query.isPending} />
      ) : (
        <InspectorHome data={data} loading={query.isPending} />
      )}

      <Panel title="How this workspace works" description="The same rules apply to every screen.">
        <div className="grid gap-4 md:grid-cols-3">
          {[
            ['Scope first', 'Your role and branch decide which records are visible.'],
            ['Quantities only', 'Kilograms come from stored rows, never from estimates.'],
            ['Traceable actions', 'Every status change records who made it and when.'],
          ].map(([heading, body]) => (
            <div key={heading} className="border-l-[3px] border-l-terracotta pl-3">
              <p className="text-sm font-semibold text-charcoal">{heading}</p>
              <p className="mt-1 text-sm leading-6 text-ink-soft">{body}</p>
            </div>
          ))}
        </div>
      </Panel>
    </div>
  )
}

function DonorHome({ data, loading }: { data?: Overview; loading: boolean }) {
  return (
    <>
      <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
        <StatCard
          label="Open donations"
          value={loading ? '—' : formatNumber(numberValue(data, 'open_donations'))}
          icon={ClipboardList}
        />
        <StatCard
          label="Donated"
          value={loading ? '—' : formatKg(stringValue(data, 'kg_donated'))}
          icon={PackageCheck}
        />
        <StatCard
          label="Delivered"
          value={loading ? '—' : formatKg(stringValue(data, 'kg_delivered'))}
          icon={Truck}
        />
        <StatCard
          label="Balance"
          value={loading ? '—' : formatKg(stringValue(data, 'balance_kg'))}
          detail="Donated minus delivered and spoiled"
          icon={Activity}
        />
      </div>
      <div className="grid gap-5 lg:grid-cols-[minmax(0,1.2fr)_minmax(0,0.8fr)]">
        <Panel title="Donations by status" description="Counts from your own donations only.">
          {Array.isArray(data?.donations_by_status) && data.donations_by_status.length > 0 ? (
            <ul className="divide-y divide-line">
              {(data.donations_by_status as { status: string; count: number }[]).map((row) => (
                <li
                  key={row.status}
                  className="flex items-center justify-between gap-3 py-3 first:pt-0 last:pb-0"
                >
                  <StatusBadge status={row.status} />
                  <span className="font-heading text-xl text-charcoal">{row.count}</span>
                </li>
              ))}
            </ul>
          ) : (
            <EmptyState
              icon={PackageCheck}
              title="No donations yet"
              body="Register surplus food to begin the chain."
              action={
                <Link to="/donations/new" className={cn(buttonVariants({ variant: 'outline' }), 'h-9 px-3')}>
                  Register donation
                </Link>
              }
            />
          )}
        </Panel>
        <Panel title="Your next step" accent>
          <p className="text-sm leading-6 text-ink-soft">
            A donation is only distributed when a manager allocates it to a delivery,
            a driver marks that delivery delivered, and every kilogram reconciles.
            Spoilage is recorded separately and never treated as delivered.
          </p>
          <Link to="/impact" className={cn(buttonVariants({ variant: 'outline' }), 'mt-4 h-9 px-3')}>
            View impact report
          </Link>
        </Panel>
      </div>
    </>
  )
}

function ManagerHome({ data, loading }: { data?: Overview; loading: boolean }) {
  return (
    <>
      <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
        <StatCard
          label="Waiting for review"
          value={loading ? '—' : formatNumber(numberValue(data, 'donations_awaiting_review'))}
          icon={ClipboardList}
        />
        <StatCard
          label="Inspections pending"
          value={loading ? '—' : formatNumber(numberValue(data, 'inspections_pending'))}
          icon={ClipboardCheck}
        />
        <StatCard
          label="In transit"
          value={loading ? '—' : formatNumber(numberValue(data, 'deliveries_in_transit'))}
          icon={Truck}
        />
        <StatCard
          label="Today's deliveries"
          value={loading ? '—' : formatNumber(numberValue(data, 'deliveries_today'))}
          icon={Clock3}
        />
      </div>
      <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-3">
        <StatCard
          label="Allocated, open"
          value={loading ? '—' : formatKg(stringValue(data, 'kg_allocated_open'))}
          detail="Planned and in-transit lines"
          icon={PackageCheck}
        />
        <StatCard
          label="Expiring in 48h"
          value={loading ? '—' : formatNumber(numberValue(data, 'expiring_within_48h'))}
          icon={ShieldAlert}
        />
        <StatCard
          label="Average review"
          value={loading ? '—' : `${stringValue(data, 'avg_rating')} / 5`}
          detail="One rating per delivery"
          icon={Users}
        />
      </div>
      <div className="grid gap-5 lg:grid-cols-3">
        <Panel title="Donation review" description="Unrouted and collected donations in your branches.">
          <Link to="/donations" className={cn(buttonVariants({ variant: 'outline' }), 'h-9 px-3')}>
            Open donations
          </Link>
        </Panel>
        <Panel title="Inspection queue" description="Collected food still waiting for a passing decision.">
          <Link to="/inspections" className={cn(buttonVariants({ variant: 'outline' }), 'h-9 px-3')}>
            Open inspections
          </Link>
        </Panel>
        <Panel title="Allocation" description="Create a delivery only from available kilograms.">
          <Link to="/allocation" className={cn(buttonVariants({ variant: 'outline' }), 'h-9 px-3')}>
            Open allocation
          </Link>
        </Panel>
      </div>
    </>
  )
}

function DriverHome({ data, loading }: { data?: Overview; loading: boolean }) {
  const next = data?.next_delivery as
    | { delivery_id: number; scheduled_for: string | null; recipient_branch: string | null }
    | null
    | undefined
  return (
    <>
      <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
        <StatCard
          label="Assigned today"
          value={loading ? '—' : formatNumber(numberValue(data, 'assigned_today'))}
          icon={ClipboardList}
        />
        <StatCard
          label="In transit"
          value={loading ? '—' : formatNumber(numberValue(data, 'in_transit'))}
          icon={Truck}
        />
        <StatCard
          label="Delivered this week"
          value={loading ? '—' : formatNumber(numberValue(data, 'delivered_this_week'))}
          icon={PackageCheck}
        />
        <StatCard
          label="Kilograms this week"
          value={loading ? '—' : formatKg(stringValue(data, 'kg_delivered_this_week'))}
          icon={Activity}
        />
      </div>
      <Panel title="Next delivery" description="Ordered by the scheduled time on the record.">
        {next ? (
          <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
            <div>
              <p className="font-heading text-xl text-charcoal">Delivery #{next.delivery_id}</p>
              <p className="mt-1 text-sm text-ink-soft">
                {next.recipient_branch ?? 'Receiving branch'} · {next.scheduled_for ?? 'No scheduled time'}
              </p>
            </div>
            <Link
              to={`/deliveries/${next.delivery_id}`}
              className={cn(buttonVariants(), 'h-9 px-3')}
            >
              Open delivery
            </Link>
          </div>
        ) : (
          <EmptyState
            icon={Truck}
            title="No delivery assigned"
            body="A manager will allocate a delivery to your route when food is ready."
          />
        )}
      </Panel>
    </>
  )
}

function InspectorHome({ data, loading }: { data?: Overview; loading: boolean }) {
  return (
    <>
      <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
        <StatCard
          label="Queue size"
          value={loading ? '—' : formatNumber(numberValue(data, 'queue_size'))}
          icon={ClipboardCheck}
        />
        <StatCard
          label="Inspected today"
          value={loading ? '—' : formatNumber(numberValue(data, 'inspected_today'))}
          icon={Activity}
        />
        <StatCard
          label="Failed, 7 days"
          value={loading ? '—' : formatNumber(numberValue(data, 'failed_last_7d'))}
          icon={ShieldAlert}
        />
        <StatCard
          label="Average temperature"
          value={loading ? '—' : `${stringValue(data, 'avg_temperature_7d')} °C`}
          detail="Across your last seven days"
          icon={Activity}
        />
      </div>
      <Panel title="Decision rules" description="The inspection log is append-only.">
        <p className="text-sm leading-6 text-ink-soft">
          A collected donation can be approved only when its latest inspection
          passed. A failed latest inspection can only lead to rejection; a newer
          passing inspection supersedes an older failure.
        </p>
        <Link to="/inspections" className={cn(buttonVariants({ variant: 'outline' }), 'mt-4 h-9 px-3')}>
          Open inspection queue
        </Link>
      </Panel>
    </>
  )
}
