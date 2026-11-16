import { useState } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { Building2, Pencil, Plus } from 'lucide-react'

import { EmptyState } from '@/components/EmptyState'
import { ErrorNotice } from '@/components/ErrorNotice'
import { PageHeader } from '@/components/PageHeader'
import { Panel } from '@/components/Panel'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { ApiRequestError, apiGet, apiGetPaged, apiRequest } from '@/lib/api'
import type { BackendBranch } from '@/lib/types'

type BranchForm = {
  branch_name: string
  address: string
  pincode: string
  contact_no: string
  established_date: string
}

const emptyForm: BranchForm = {
  branch_name: '',
  address: '',
  pincode: '',
  contact_no: '',
  established_date: '',
}

export function BranchesPage() {
  const queryClient = useQueryClient()
  const [showCreate, setShowCreate] = useState(false)
  const [editing, setEditing] = useState<number | null>(null)
  const [form, setForm] = useState<BranchForm>(emptyForm)
  const [organizationId, setOrganizationId] = useState('')
  const [error, setError] = useState<string | null>(null)

  const branchesQuery = useQuery({
    queryKey: ['branches'],
    queryFn: ({ signal }) => apiGetPaged<BackendBranch>('/api/branches?page_size=100', signal),
  })
  const orgsQuery = useQuery({
    queryKey: ['organizations'],
    queryFn: ({ signal }) => apiGet<{ organization_id: number; organization_name: string }[]>('/api/organizations', signal),
  })
  const managedQuery = useQuery({
    queryKey: ['managed-branches'],
    queryFn: ({ signal }) => apiGet<{ branch_id: number }[]>('/api/reports/branches', signal),
  })
  const managed = new Set((managedQuery.data ?? []).map((row) => row.branch_id))

  const save = useMutation({
    mutationFn: async () => {
      setError(null)
      if (editing) {
        return apiRequest(`/api/branches/${editing}`, {
          method: 'PATCH',
          body: {
            branch_name: form.branch_name,
            address: form.address,
            pincode: form.pincode,
            contact_no: form.contact_no,
          },
        })
      }
      return apiRequest('/api/branches', {
        method: 'POST',
        body: { ...form, organization_id: Number(organizationId) },
      })
    },
    onSuccess: async () => {
      setForm(emptyForm)
      setEditing(null)
      setShowCreate(false)
      await queryClient.invalidateQueries({ queryKey: ['branches'] })
      await queryClient.invalidateQueries({ queryKey: ['managed-branches'] })
    },
    onError: (caught: unknown) => setError(caught instanceof ApiRequestError ? caught.message : 'The branch could not be saved.'),
  })

  function startEdit(branch: BackendBranch) {
    setEditing(branch.branch_id)
    setShowCreate(false)
    setForm({
      branch_name: branch.branch_name,
      address: branch.address,
      pincode: branch.pincode,
      contact_no: branch.contact_no,
      established_date: branch.established_date,
    })
  }

  return (
    <div className="space-y-7">
      <PageHeader
        eyebrow="Branch administration"
        title="Branches"
        description="You can edit the branches whose regional manager is your account. A new branch is created under your management."
        action={
          <Button
            type="button"
            onClick={() => {
              setShowCreate(true)
              setEditing(null)
              setForm(emptyForm)
            }}
          >
            <Plus aria-hidden="true" className="size-4" />
            New branch
          </Button>
        }
      />
      {error ? <ErrorNotice error={error} /> : null}
      {branchesQuery.isError ? <ErrorNotice error={branchesQuery.error} onRetry={() => void branchesQuery.refetch()} /> : null}

      {showCreate || editing ? (
        <Panel title={editing ? `Edit branch #${editing}` : 'Create a branch'} description="Pincode and contact use the same validation as registration.">
          <form
            className="space-y-4"
            onSubmit={(event) => {
              event.preventDefault()
              save.mutate()
            }}
          >
            <div className="grid gap-4 md:grid-cols-2">
              {!editing ? (
                <div className="space-y-1.5 md:col-span-2">
                  <Label htmlFor="branch-org">Organization</Label>
                  <select id="branch-org" value={organizationId} onChange={(event) => setOrganizationId(event.target.value)} required className="h-9 w-full rounded-[4px] border border-input bg-paper px-3 text-sm">
                    <option value="">Choose an organization</option>
                    {(orgsQuery.data ?? []).map((org) => (
                      <option key={org.organization_id} value={org.organization_id}>{org.organization_name}</option>
                    ))}
                  </select>
                </div>
              ) : null}
              <div className="space-y-1.5 md:col-span-2">
                <Label htmlFor="branch-name">Branch name</Label>
                <Input id="branch-name" value={form.branch_name} onChange={(event) => setForm({ ...form, branch_name: event.target.value })} required />
              </div>
              <div className="space-y-1.5 md:col-span-2">
                <Label htmlFor="branch-address">Address</Label>
                <Input id="branch-address" value={form.address} onChange={(event) => setForm({ ...form, address: event.target.value })} required />
              </div>
              <div className="space-y-1.5">
                <Label htmlFor="branch-pincode">Pincode</Label>
                <Input id="branch-pincode" value={form.pincode} onChange={(event) => setForm({ ...form, pincode: event.target.value })} inputMode="numeric" required />
              </div>
              <div className="space-y-1.5">
                <Label htmlFor="branch-contact">Contact</Label>
                <Input id="branch-contact" value={form.contact_no} onChange={(event) => setForm({ ...form, contact_no: event.target.value })} placeholder="+919876543210" required />
              </div>
              {!editing ? (
                <div className="space-y-1.5">
                  <Label htmlFor="branch-date">Established date</Label>
                  <Input id="branch-date" type="date" value={form.established_date} onChange={(event) => setForm({ ...form, established_date: event.target.value })} required />
                </div>
              ) : null}
            </div>
            <div className="flex flex-wrap gap-2">
              <Button type="submit" disabled={save.isPending}>{save.isPending ? 'Saving…' : 'Save branch'}</Button>
              <Button type="button" variant="outline" onClick={() => { setShowCreate(false); setEditing(null); setForm(emptyForm) }}>Cancel</Button>
            </div>
          </form>
        </Panel>
      ) : null}

      {branchesQuery.isPending ? <p className="text-sm text-ink-soft">Loading branches…</p> : null}
      {branchesQuery.data ? (
        (branchesQuery.data.data ?? []).length === 0 ? (
          <EmptyState icon={Building2} title="No branches" body="Create a branch to begin managing donations and routes." />
        ) : (
          <div className="grid gap-4 md:grid-cols-2">
            {branchesQuery.data.data.map((branch) => (
              <article key={branch.branch_id} className="rounded-[8px] border border-line bg-paper p-5">
                <div className="flex items-start justify-between gap-3">
                  <div>
                    <p className="text-xs tracking-[0.08em] text-ink-soft uppercase">Branch #{branch.branch_id}</p>
                    <h2 className="mt-1 font-heading text-2xl text-charcoal">{branch.branch_name}</h2>
                  </div>
                  {managed.has(branch.branch_id) ? (
                    <Button type="button" variant="outline" size="sm" onClick={() => startEdit(branch)}>
                      <Pencil aria-hidden="true" className="size-4" />
                      Edit
                    </Button>
                  ) : null}
                </div>
                <dl className="mt-4 space-y-2 text-sm">
                  <div className="flex justify-between gap-4"><dt className="text-ink-soft">Organization</dt><dd className="text-right text-charcoal">{branch.organization.organization_name ?? '—'}</dd></div>
                  <div className="flex justify-between gap-4"><dt className="text-ink-soft">Address</dt><dd className="text-right text-charcoal">{branch.address}</dd></div>
                  <div className="flex justify-between gap-4"><dt className="text-ink-soft">Pincode</dt><dd className="text-right text-charcoal">{branch.pincode}</dd></div>
                  <div className="flex justify-between gap-4"><dt className="text-ink-soft">Contact</dt><dd className="text-right text-charcoal">{branch.contact_no}</dd></div>
                  <div className="flex justify-between gap-4"><dt className="text-ink-soft">Manager</dt><dd className="text-right text-charcoal">{branch.regional_manager?.full_name ?? 'Unassigned'}</dd></div>
                </dl>
              </article>
            ))}
          </div>
        )
      ) : null}
    </div>
  )
}
