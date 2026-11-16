import { useState } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { Pencil, Plus, Trash2, Users } from 'lucide-react'

import { EmptyState } from '@/components/EmptyState'
import { ErrorNotice } from '@/components/ErrorNotice'
import { PageHeader } from '@/components/PageHeader'
import { Panel } from '@/components/Panel'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { ApiRequestError, apiGet, apiRequest } from '@/lib/api'

type Dependent = {
  dependent_no: number
  full_name: string
  relationship: string
  date_of_birth: string | null
  phone: string | null
}

const empty = { full_name: '', relationship: '', date_of_birth: '', phone: '' }

export function DependentsPage() {
  const queryClient = useQueryClient()
  const [form, setForm] = useState(empty)
  const [editing, setEditing] = useState<number | null>(null)
  const [error, setError] = useState<string | null>(null)
  const query = useQuery({
    queryKey: ['dependents'],
    queryFn: ({ signal }) => apiGet<Dependent[]>('/api/dependents', signal),
  })

  const save = useMutation({
    mutationFn: async () => {
      setError(null)
      const body = {
        full_name: form.full_name,
        relationship: form.relationship,
        date_of_birth: form.date_of_birth || null,
        phone: form.phone || null,
      }
      if (editing) {
        return apiRequest(`/api/dependents/${editing}`, { method: 'PATCH', body })
      }
      return apiRequest('/api/dependents', { method: 'POST', body })
    },
    onSuccess: async () => {
      setForm(empty)
      setEditing(null)
      await queryClient.invalidateQueries({ queryKey: ['dependents'] })
    },
    onError: (caught: unknown) => setError(caught instanceof ApiRequestError ? caught.message : 'The dependent could not be saved.'),
  })
  const remove = useMutation({
    mutationFn: async (dependentNo: number) => {
      setError(null)
      return apiRequest(`/api/dependents/${dependentNo}`, { method: 'DELETE' })
    },
    onSuccess: async () => {
      await queryClient.invalidateQueries({ queryKey: ['dependents'] })
    },
    onError: (caught: unknown) => setError(caught instanceof ApiRequestError ? caught.message : 'The dependent could not be removed.'),
  })

  const rows = query.data ?? []

  return (
    <div className="space-y-7">
      <PageHeader
        eyebrow="Driver profile"
        title="Dependents"
        description="People who rely on your income. The composite key is your driver account plus the dependent number."
      />
      {error ? <ErrorNotice error={error} /> : null}
      {query.isError ? <ErrorNotice error={query.error} onRetry={() => void query.refetch()} /> : null}

      <Panel title={editing ? `Edit dependent #${editing}` : 'Add a dependent'} description="Only your own dependents are visible to you.">
        <form
          className="space-y-4"
          onSubmit={(event) => {
            event.preventDefault()
            save.mutate()
          }}
        >
          <div className="grid gap-4 md:grid-cols-2">
            <div className="space-y-1.5">
              <Label htmlFor="dependent-name">Full name</Label>
              <Input id="dependent-name" value={form.full_name} onChange={(event) => setForm({ ...form, full_name: event.target.value })} required />
            </div>
            <div className="space-y-1.5">
              <Label htmlFor="dependent-relationship">Relationship</Label>
              <Input id="dependent-relationship" value={form.relationship} onChange={(event) => setForm({ ...form, relationship: event.target.value })} required />
            </div>
            <div className="space-y-1.5">
              <Label htmlFor="dependent-dob">Date of birth</Label>
              <Input id="dependent-dob" type="date" value={form.date_of_birth} onChange={(event) => setForm({ ...form, date_of_birth: event.target.value })} />
            </div>
            <div className="space-y-1.5">
              <Label htmlFor="dependent-phone">Phone</Label>
              <Input id="dependent-phone" value={form.phone} onChange={(event) => setForm({ ...form, phone: event.target.value })} placeholder="+919876543210" />
            </div>
          </div>
          <div className="flex flex-wrap gap-2">
            <Button type="submit" disabled={save.isPending}>
              {editing ? <Pencil aria-hidden="true" className="size-4" /> : <Plus aria-hidden="true" className="size-4" />}
              {save.isPending ? 'Saving…' : editing ? 'Save changes' : 'Add dependent'}
            </Button>
            {editing ? <Button type="button" variant="outline" onClick={() => { setEditing(null); setForm(empty) }}>Cancel</Button> : null}
          </div>
        </form>
      </Panel>

      {query.isPending ? <p className="text-sm text-ink-soft">Loading dependents…</p> : null}
      {query.data ? (
        rows.length === 0 ? (
          <EmptyState icon={Users} title="No dependents recorded" body="Add a dependent to keep your driver profile complete." />
        ) : (
          <Panel title="Recorded dependents" description="Dependent numbers are assigned by the service.">
            <ul className="divide-y divide-line">
              {rows.map((row) => (
                <li key={row.dependent_no} className="flex flex-wrap items-start justify-between gap-4 py-4 first:pt-0 last:pb-0">
                  <div>
                    <p className="font-semibold text-charcoal">{row.full_name}</p>
                    <p className="mt-1 text-sm text-ink-soft">{row.relationship} · No. {row.dependent_no}</p>
                    <p className="mt-1 text-xs text-ink-soft">
                      {row.date_of_birth ?? 'No date of birth'} · {row.phone ?? 'No phone'}
                    </p>
                  </div>
                  <div className="flex gap-2">
                    <Button
                      type="button"
                      variant="outline"
                      size="sm"
                      onClick={() => {
                        setEditing(row.dependent_no)
                        setForm({ full_name: row.full_name, relationship: row.relationship, date_of_birth: row.date_of_birth ?? '', phone: row.phone ?? '' })
                      }}
                    >
                      <Pencil aria-hidden="true" className="size-4" />
                      Edit
                    </Button>
                    <Button type="button" variant="outline" size="sm" onClick={() => remove.mutate(row.dependent_no)} disabled={remove.isPending}>
                      <Trash2 aria-hidden="true" className="size-4" />
                      Remove
                    </Button>
                  </div>
                </li>
              ))}
            </ul>
          </Panel>
        )
      ) : null}
    </div>
  )
}
