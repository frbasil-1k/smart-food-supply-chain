import { useState } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { Plus, Route as RouteIcon, Trash2 } from 'lucide-react'

import { EmptyState } from '@/components/EmptyState'
import { ErrorNotice } from '@/components/ErrorNotice'
import { PageHeader } from '@/components/PageHeader'
import { Panel } from '@/components/Panel'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { ApiRequestError, apiGet, apiGetPaged, apiRequest } from '@/lib/api'
import type { RouteRef, User } from '@/lib/types'

type Area = { coverage_area_id: number; area_name: string; city: string }
type ManagedBranch = { branch_id: number; branch_name: string }
type Assignment = {
  user_id: number
  route_id: number
  user: { user_id: number; full_name: string } | null
  hours_per_week: string
  assigned_date: string
}

export function RoutesPage() {
  const queryClient = useQueryClient()
  const [showCreate, setShowCreate] = useState(false)
  const [selected, setSelected] = useState<number | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [form, setForm] = useState({
    branchId: '',
    driverId: '',
    areaId: '',
    type: 'PICKUP',
  })
  const [assignment, setAssignment] = useState({ userId: '', hours: '8', date: '' })

  const routesQuery = useQuery({
    queryKey: ['routes'],
    queryFn: ({ signal }) => apiGetPaged<RouteRef>('/api/routes?page_size=100', signal),
  })
  const areasQuery = useQuery({
    queryKey: ['coverage-areas'],
    queryFn: ({ signal }) => apiGet<Area[]>('/api/coverage-areas', signal),
  })
  const branchesQuery = useQuery({
    queryKey: ['managed-branches'],
    queryFn: ({ signal }) => apiGet<ManagedBranch[]>('/api/reports/branches', signal),
  })
  const driversQuery = useQuery({
    queryKey: ['drivers'],
    queryFn: ({ signal }) => apiGetPaged<User>('/api/users?role=DRIVER&page_size=100', signal),
  })
  const assignmentsQuery = useQuery({
    queryKey: ['route-assignments', selected],
    queryFn: ({ signal }) => apiGet<Assignment[]>(`/api/routes/${selected}/assignments`, signal),
    enabled: Boolean(selected),
  })

  const managed = new Set((branchesQuery.data ?? []).map((branch) => branch.branch_id))
  const drivers = driversQuery.data?.data ?? []

  const createMutation = useMutation({
    mutationFn: async () => {
      setError(null)
      return apiRequest<RouteRef>('/api/routes', {
        method: 'POST',
        body: {
          managing_branch_id: Number(form.branchId),
          designated_driver_user_id: Number(form.driverId),
          coverage_area_id: Number(form.areaId),
          route_type: form.type,
          route_status: 'ACTIVE',
        },
      })
    },
    onSuccess: async () => {
      setShowCreate(false)
      setForm({ branchId: '', driverId: '', areaId: '', type: 'PICKUP' })
      await queryClient.invalidateQueries({ queryKey: ['routes'] })
    },
    onError: (caught: unknown) => setError(caught instanceof ApiRequestError ? caught.message : 'The route could not be created.'),
  })
  const statusMutation = useMutation({
    mutationFn: async ({ routeId, status }: { routeId: number; status: string }) => {
      setError(null)
      return apiRequest(`/api/routes/${routeId}`, {
        method: 'PATCH',
        body: { route_status: status },
      })
    },
    onSuccess: async () => {
      await queryClient.invalidateQueries({ queryKey: ['routes'] })
      await queryClient.invalidateQueries({ queryKey: ['route-assignments'] })
    },
    onError: (caught: unknown) => setError(caught instanceof ApiRequestError ? caught.message : 'The route status could not change.'),
  })
  const addAssignment = useMutation({
    mutationFn: async () => {
      setError(null)
      return apiRequest(`/api/routes/${selected}/assignments`, {
        method: 'POST',
        body: {
          user_id: Number(assignment.userId),
          hours_per_week: assignment.hours,
          assigned_date: assignment.date,
        },
      })
    },
    onSuccess: async () => {
      setAssignment({ userId: '', hours: '8', date: '' })
      await queryClient.invalidateQueries({ queryKey: ['route-assignments', selected] })
    },
    onError: (caught: unknown) => setError(caught instanceof ApiRequestError ? caught.message : 'The assignment could not be saved.'),
  })
  const removeAssignment = useMutation({
    mutationFn: async (userId: number) => {
      setError(null)
      return apiRequest(`/api/routes/${selected}/assignments/${userId}`, { method: 'DELETE' })
    },
    onSuccess: async () => {
      await queryClient.invalidateQueries({ queryKey: ['route-assignments', selected] })
    },
    onError: (caught: unknown) => setError(caught instanceof ApiRequestError ? caught.message : 'The assignment could not be removed.'),
  })

  const routes = routesQuery.data?.data ?? []

  return (
    <div className="space-y-7">
      <PageHeader
        eyebrow="Logistics configuration"
        title="Routes"
        description="Routes connect a managing branch, a designated driver, and a coverage area. Only routes in your branches can be changed."
        action={
          <Button type="button" onClick={() => setShowCreate((value) => !value)}>
            <Plus aria-hidden="true" className="size-4" />
            New route
          </Button>
        }
      />
      {error ? <ErrorNotice error={error} /> : null}
      {routesQuery.isError ? <ErrorNotice error={routesQuery.error} onRetry={() => void routesQuery.refetch()} /> : null}

      {showCreate ? (
        <Panel title="Create a route" description="The designated driver must be an active driver in your branch.">
          <form
            className="space-y-4"
            onSubmit={(event) => {
              event.preventDefault()
              createMutation.mutate()
            }}
          >
            <div className="grid gap-4 md:grid-cols-2">
              <div className="space-y-1.5">
                <Label htmlFor="route-branch">Managing branch</Label>
                <select id="route-branch" value={form.branchId} onChange={(event) => setForm({ ...form, branchId: event.target.value })} required className="h-9 w-full rounded-[4px] border border-input bg-paper px-3 text-sm">
                  <option value="">Choose a branch</option>
                  {(branchesQuery.data ?? []).map((branch) => <option key={branch.branch_id} value={branch.branch_id}>{branch.branch_name}</option>)}
                </select>
              </div>
              <div className="space-y-1.5">
                <Label htmlFor="route-driver">Designated driver</Label>
                <select id="route-driver" value={form.driverId} onChange={(event) => setForm({ ...form, driverId: event.target.value })} required className="h-9 w-full rounded-[4px] border border-input bg-paper px-3 text-sm">
                  <option value="">Choose a driver</option>
                  {drivers.map((driver) => <option key={driver.user_id} value={driver.user_id}>{driver.full_name}</option>)}
                </select>
              </div>
              <div className="space-y-1.5">
                <Label htmlFor="route-area">Coverage area</Label>
                <select id="route-area" value={form.areaId} onChange={(event) => setForm({ ...form, areaId: event.target.value })} required className="h-9 w-full rounded-[4px] border border-input bg-paper px-3 text-sm">
                  <option value="">Choose an area</option>
                  {(areasQuery.data ?? []).map((area) => <option key={area.coverage_area_id} value={area.coverage_area_id}>{area.area_name} · {area.city}</option>)}
                </select>
              </div>
              <div className="space-y-1.5">
                <Label htmlFor="route-type">Type</Label>
                <select id="route-type" value={form.type} onChange={(event) => setForm({ ...form, type: event.target.value })} className="h-9 w-full rounded-[4px] border border-input bg-paper px-3 text-sm">
                  <option value="PICKUP">Pickup</option>
                  <option value="DISTRIBUTION">Distribution</option>
                  <option value="MIXED">Mixed</option>
                </select>
              </div>
            </div>
            <div className="flex gap-2">
              <Button type="submit" disabled={createMutation.isPending}>{createMutation.isPending ? 'Creating…' : 'Create route'}</Button>
              <Button type="button" variant="outline" onClick={() => setShowCreate(false)}>Cancel</Button>
            </div>
          </form>
        </Panel>
      ) : null}

      {routesQuery.isPending ? <p className="text-sm text-ink-soft">Loading routes…</p> : null}
      {routesQuery.data ? (
        routes.length === 0 ? (
          <EmptyState icon={RouteIcon} title="No routes" body="Create a route so donors and managers can schedule pickups." />
        ) : (
          <div className="grid gap-4 md:grid-cols-2">
            {routes.map((route) => (
              <article key={route.route_id} className="rounded-[8px] border border-line bg-paper p-5">
                <div className="flex items-start justify-between gap-3">
                  <div>
                    <p className="text-xs tracking-[0.08em] text-ink-soft uppercase">Route #{route.route_id}</p>
                    <h2 className="mt-1 font-heading text-2xl text-charcoal">{route.coverage_area?.area_name ?? 'Coverage area'}</h2>
                    <p className="mt-1 text-sm text-ink-soft">{route.coverage_area?.city ?? 'City not set'} · {route.managing_branch?.branch_name ?? 'Branch'}</p>
                  </div>
                  <span className={route.route_status === 'ACTIVE' ? 'rounded-[3px] bg-oat-deep px-2 py-1 text-xs font-semibold text-forest' : 'rounded-[3px] bg-oat-deep px-2 py-1 text-xs font-semibold text-ink-soft'}>
                    {route.route_status ?? 'ACTIVE'}
                  </span>
                </div>
                <dl className="mt-4 space-y-2 text-sm">
                  <div className="flex justify-between gap-4"><dt className="text-ink-soft">Driver</dt><dd className="text-right text-charcoal">{route.designated_driver?.full_name ?? 'Unassigned'}</dd></div>
                  <div className="flex justify-between gap-4"><dt className="text-ink-soft">Type</dt><dd className="text-right text-charcoal">{route.route_type}</dd></div>
                </dl>
                <div className="mt-5 flex flex-wrap gap-2">
                  <Button
                    type="button"
                    variant="outline"
                    size="sm"
                    disabled={!managed.has(route.managing_branch?.branch_id ?? -1) || statusMutation.isPending}
                    onClick={() => statusMutation.mutate({ routeId: route.route_id, status: route.route_status === 'ACTIVE' ? 'INACTIVE' : 'ACTIVE' })}
                  >
                    {route.route_status === 'ACTIVE' ? 'Deactivate' : 'Activate'}
                  </Button>
                  <Button
                    type="button"
                    variant="outline"
                    size="sm"
                    disabled={!managed.has(route.managing_branch?.branch_id ?? -1)}
                    onClick={() => setSelected(route.route_id === selected ? null : route.route_id)}
                  >
                    {selected === route.route_id ? 'Hide assignments' : 'Assignments'}
                  </Button>
                </div>
                {selected === route.route_id ? (
                  <div className="mt-5 border-t border-line pt-4">
                    <h3 className="text-sm font-semibold text-charcoal">Assigned drivers</h3>
                    {assignmentsQuery.isPending ? (
                      <p className="mt-2 text-sm text-ink-soft">Loading…</p>
                    ) : (assignmentsQuery.data ?? []).length === 0 ? (
                      <p className="mt-2 text-sm text-ink-soft">No additional drivers assigned.</p>
                    ) : (
                      <ul className="mt-2 divide-y divide-line">
                        {assignmentsQuery.data?.map((row) => (
                          <li key={row.user_id} className="flex items-center justify-between gap-3 py-2 text-sm">
                            <span className="text-charcoal">{row.user?.full_name ?? `User #${row.user_id}`} · {row.hours_per_week} h/week</span>
                            <Button type="button" variant="ghost" size="sm" onClick={() => removeAssignment.mutate(row.user_id)} aria-label={`Remove ${row.user?.full_name ?? 'driver'}`}>
                              <Trash2 aria-hidden="true" className="size-4" />
                            </Button>
                          </li>
                        ))}
                      </ul>
                    )}
                    <form
                      className="mt-4 grid gap-2 sm:grid-cols-2"
                      onSubmit={(event) => {
                        event.preventDefault()
                        addAssignment.mutate()
                      }}
                    >
                      <div className="space-y-1">
                        <Label htmlFor={`assignment-driver-${route.route_id}`}>Driver</Label>
                        <select id={`assignment-driver-${route.route_id}`} value={assignment.userId} onChange={(event) => setAssignment({ ...assignment, userId: event.target.value })} required className="h-9 w-full rounded-[4px] border border-input bg-paper px-3 text-sm">
                          <option value="">Choose</option>
                          {drivers.map((driver) => <option key={driver.user_id} value={driver.user_id}>{driver.full_name}</option>)}
                        </select>
                      </div>
                      <div className="space-y-1">
                        <Label htmlFor={`assignment-hours-${route.route_id}`}>Hours/week</Label>
                        <Input id={`assignment-hours-${route.route_id}`} value={assignment.hours} onChange={(event) => setAssignment({ ...assignment, hours: event.target.value })} inputMode="decimal" required />
                      </div>
                      <div className="space-y-1 sm:col-span-2">
                        <Label htmlFor={`assignment-date-${route.route_id}`}>Assigned date</Label>
                        <Input id={`assignment-date-${route.route_id}`} type="date" value={assignment.date} onChange={(event) => setAssignment({ ...assignment, date: event.target.value })} required />
                      </div>
                      <div className="sm:col-span-2">
                        <Button type="submit" size="sm" disabled={addAssignment.isPending}>Assign driver</Button>
                      </div>
                    </form>
                  </div>
                ) : null}
              </article>
            ))}
          </div>
        )
      ) : null}
    </div>
  )
}
