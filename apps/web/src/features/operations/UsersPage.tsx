import { useState } from 'react'
import { useSearchParams } from 'react-router-dom'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { KeyRound, Search, ShieldCheck, Users } from 'lucide-react'

import { EmptyState } from '@/components/EmptyState'
import { ErrorNotice } from '@/components/ErrorNotice'
import { PageHeader } from '@/components/PageHeader'
import { StatusBadge } from '@/components/StatusBadge'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { ApiRequestError, apiGetPaged, apiRequest } from '@/lib/api'
import { formatLocalDateTime } from '@/lib/datetime'
import type { User } from '@/lib/types'

type TokenResponse = {
  activation_token?: string
  reset_token?: string
  expires_at: string | null
  delivery: 'shown_once'
}

export function UsersPage() {
  const [searchParams, setSearchParams] = useSearchParams()
  const role = searchParams.get('role') ?? ''
  const [q, setQ] = useState(searchParams.get('q') ?? '')
  const [error, setError] = useState<string | null>(null)
  const [token, setToken] = useState<{ userId: number; kind: 'activation' | 'reset'; value: string; expires: string | null } | null>(null)
  const queryClient = useQueryClient()
  const query = useQuery({
    queryKey: ['users', { role, q }],
    queryFn: ({ signal }) =>
      apiGetPaged<User>(
        `/api/users?page_size=100${role ? `&role=${role}` : ''}${q ? `&q=${encodeURIComponent(q)}` : ''}`,
        signal,
      ),
  })
  const rows = query.data?.data ?? []

  function update(key: string, value: string) {
    const next = new URLSearchParams(searchParams)
    if (value) next.set(key, value)
    else next.delete(key)
    setSearchParams(next)
  }

  const statusMutation = useMutation({
    mutationFn: async ({ userId, status }: { userId: number; status: string }) => {
      setError(null)
      return apiRequest(`/api/users/${userId}`, { method: 'PATCH', body: { account_status: status } })
    },
    onSuccess: async () => {
      await queryClient.invalidateQueries({ queryKey: ['users'] })
    },
    onError: (caught: unknown) => setError(caught instanceof ApiRequestError ? caught.message : 'The account status could not change.'),
  })

  const tokenMutation = useMutation({
    mutationFn: async ({ userId, kind }: { userId: number; kind: 'activation' | 'reset' }) => {
      setError(null)
      const path = kind === 'activation' ? 'activation-token' : 'password-reset-token'
      return apiRequest<TokenResponse>(`/api/users/${userId}/${path}`, { method: 'POST', body: {} })
    },
    onSuccess: (response, variables) => {
      const value = variables.kind === 'activation' ? response.data.activation_token : response.data.reset_token
      if (value) {
        setToken({ userId: variables.userId, kind: variables.kind, value, expires: response.data.expires_at })
      }
    },
    onError: (caught: unknown) => setError(caught instanceof ApiRequestError ? caught.message : 'The token could not be issued.'),
  })

  return (
    <div className="space-y-7">
      <PageHeader
        eyebrow="People"
        title="Users"
        description="Users in your managed branches. Managers cannot change another manager or their own status."
      />

      {error ? <ErrorNotice error={error} /> : null}

      {token ? (
        <div role="status" className="rounded-[8px] border border-forest bg-oat-deep p-4">
          <div className="flex items-start gap-3">
            <ShieldCheck aria-hidden="true" className="mt-0.5 size-5 shrink-0 text-forest" />
            <div className="min-w-0">
              <p className="font-semibold text-charcoal">
                {token.kind === 'activation' ? 'Activation' : 'Password reset'} token for user #{token.userId}
              </p>
              <p className="mt-1 text-sm text-ink-soft">
                Shown once. Deliver it over a trusted channel; it is not stored in the browser.
              </p>
              <code className="mt-3 block overflow-x-auto rounded-[4px] bg-paper px-3 py-2 font-mono text-sm text-charcoal">
                {token.value}
              </code>
              <p className="mt-2 text-xs text-ink-soft">
                Expires {token.expires ? formatLocalDateTime(token.expires) : 'according to policy'}.
              </p>
              <Button type="button" variant="outline" size="sm" className="mt-3" onClick={() => setToken(null)}>
                I have saved it
              </Button>
            </div>
          </div>
        </div>
      ) : null}

      <div className="flex flex-col gap-3 rounded-[8px] border border-line bg-paper p-4 sm:flex-row sm:items-end">
        <div className="min-w-0 flex-1 space-y-1.5">
          <label htmlFor="user-search" className="text-sm font-medium text-charcoal">Search</label>
          <div className="relative">
            <Search aria-hidden="true" className="pointer-events-none absolute top-1/2 left-3 size-4 -translate-y-1/2 text-ink-soft" />
            <Input id="user-search" value={q} onChange={(event) => setQ(event.target.value)} onKeyDown={(event) => event.key === 'Enter' && update('q', q.trim())} placeholder="Name or email" className="pl-9" />
          </div>
        </div>
        <div className="space-y-1.5">
          <label htmlFor="user-role" className="text-sm font-medium text-charcoal">Role</label>
          <select id="user-role" value={role} onChange={(event) => update('role', event.target.value)} className="h-9 min-w-40 rounded-[4px] border border-input bg-paper px-3 text-sm">
            <option value="">All roles</option>
            <option value="DONOR">Donor</option>
            <option value="DRIVER">Driver</option>
            <option value="SAFETY_INSPECTOR">Safety inspector</option>
            <option value="NGO_MANAGER">NGO manager</option>
          </select>
        </div>
        <Button type="button" variant="outline" onClick={() => update('q', q.trim())}>Search</Button>
      </div>

      {query.isError ? <ErrorNotice error={query.error} onRetry={() => void query.refetch()} /> : null}
      {query.isPending ? <p className="text-sm text-ink-soft">Loading users…</p> : null}
      {query.data ? (
        rows.length === 0 ? (
          <EmptyState icon={Users} title="No users in this view" body="Users appear when they are assigned to a branch you manage." />
        ) : (
          <div className="overflow-hidden rounded-[8px] border border-line bg-paper">
            <div className="overflow-x-auto">
              <table className="w-full min-w-[900px] text-left text-sm">
                <caption className="sr-only">Users in managed branches</caption>
                <thead className="bg-oat-deep text-[11px] tracking-[0.08em] text-ink-soft uppercase">
                  <tr>
                    <th scope="col" className="px-4 py-3 font-semibold">User</th>
                    <th scope="col" className="px-4 py-3 font-semibold">Role</th>
                    <th scope="col" className="px-4 py-3 font-semibold">Branch</th>
                    <th scope="col" className="px-4 py-3 font-semibold">Status</th>
                    <th scope="col" className="px-4 py-3 font-semibold">Last login</th>
                    <th scope="col" className="px-4 py-3 font-semibold">Actions</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-line">
                  {rows.map((row) => (
                    <tr key={row.user_id}>
                      <td className="px-4 py-4">
                        <p className="font-medium text-charcoal">{row.full_name}</p>
                        <p className="text-xs text-ink-soft">{row.email}</p>
                      </td>
                      <td className="px-4 py-4">{row.role.replaceAll('_', ' ')}</td>
                      <td className="px-4 py-4">{row.branch_name ?? '—'}</td>
                      <td className="px-4 py-4">
                        <div className="space-y-2">
                          <StatusBadge status={row.account_status} />
                          {row.role !== 'NGO_MANAGER' ? (
                            <select
                              aria-label={`Account status for ${row.full_name}`}
                              value={row.account_status}
                              onChange={(event) => statusMutation.mutate({ userId: row.user_id, status: event.target.value })}
                              className="h-8 rounded-[4px] border border-input bg-paper px-2 text-xs"
                            >
                              <option value="ACTIVE">Active</option>
                              <option value="INACTIVE">Inactive</option>
                              <option value="SUSPENDED">Suspended</option>
                            </select>
                          ) : null}
                        </div>
                      </td>
                      <td className="px-4 py-4 text-ink-soft">{row.last_login_at ? formatLocalDateTime(row.last_login_at) : 'Never'}</td>
                      <td className="px-4 py-4">
                        {row.role !== 'NGO_MANAGER' ? (
                          <div className="flex flex-wrap gap-2">
                            <Button type="button" variant="outline" size="sm" onClick={() => tokenMutation.mutate({ userId: row.user_id, kind: 'activation' })} disabled={tokenMutation.isPending}>
                              <KeyRound aria-hidden="true" className="size-3.5" />
                              Activate
                            </Button>
                            <Button type="button" variant="outline" size="sm" onClick={() => tokenMutation.mutate({ userId: row.user_id, kind: 'reset' })} disabled={tokenMutation.isPending}>
                              Reset
                            </Button>
                          </div>
                        ) : (
                          <span className="text-xs text-ink-soft">Protected</span>
                        )}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
        )
      ) : null}
    </div>
  )
}
