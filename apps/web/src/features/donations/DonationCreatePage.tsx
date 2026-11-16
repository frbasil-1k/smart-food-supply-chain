import { useState } from 'react'
import { useFieldArray, useForm } from 'react-hook-form'
import { zodResolver } from '@hookform/resolvers/zod'
import { useNavigate } from 'react-router-dom'
import { useQuery } from '@tanstack/react-query'
import { z } from 'zod'
import { AlertCircle, ArrowLeft, Plus, Trash2 } from 'lucide-react'

import { ErrorNotice } from '@/components/ErrorNotice'
import { PageHeader } from '@/components/PageHeader'
import { Panel } from '@/components/Panel'
import { Button, buttonVariants } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { useAuth } from '@/features/auth/AuthProvider'
import { ApiRequestError, apiGet, apiRequest } from '@/lib/api'
import type { DonationDetail, RouteRef } from '@/lib/types'
import { Link } from 'react-router-dom'
import { cn } from 'cn'

const quantityPattern = /^(?:0|[1-9]\d*)(?:\.\d{1,2})?$/

const schema = z.object({
  pickup_route_id: z.string(),
  pickup_datetime: z.string().min(1, 'Choose a pickup time.'),
  pickup_address: z.string().min(5, 'Enter at least 5 characters.').max(255),
  pickup_pincode: z.string().regex(/^[1-9]\d{5}$/, 'Use a 6-digit Indian pincode.'),
  pickup_contact: z.string().regex(/^\+91[6-9]\d{9}$/, 'Use +91 followed by 10 digits.'),
  urgency_level: z.enum(['LOW', 'NORMAL', 'HIGH']),
  items: z
    .array(
      z.object({
        category_id: z.string().min(1, 'Choose a category.'),
        item_name: z.string().min(1, 'Name the food.').max(150),
        quantity_kg: z
          .string()
          .regex(quantityPattern, 'Use kilograms with up to 2 decimals.')
          .refine((value) => Number(value) > 0, 'Quantity must be greater than zero.'),
        best_before: z.string().min(1, 'Choose a best-before time.'),
      }),
    )
    .min(1),
})

type FormValues = z.infer<typeof schema>

function toIst(value: string): string {
  if (!value) return ''
  return `${value.length === 16 ? `${value}:00` : value}+05:30`
}

export function DonationCreatePage() {
  const { user } = useAuth()
  const navigate = useNavigate()
  const [error, setError] = useState<string | null>(null)
  const form = useForm<FormValues>({
    resolver: zodResolver(schema),
    defaultValues: {
      pickup_route_id: '',
      pickup_datetime: '',
      pickup_address: '',
      pickup_pincode: '',
      pickup_contact: '',
      urgency_level: 'NORMAL',
      items: [
        {
          category_id: '',
          item_name: '',
          quantity_kg: '',
          best_before: '',
        },
      ],
    },
  })
  const { fields, append, remove } = useFieldArray({ control: form.control, name: 'items' })

  const routesQuery = useQuery({
    queryKey: ['routes', 'active'],
    queryFn: ({ signal }) => apiGet<RouteRef[]>('/api/routes?route_status=ACTIVE', signal),
  })
  const categoriesQuery = useQuery({
    queryKey: ['food-categories'],
    queryFn: ({ signal }) =>
      apiGet<{ category_id: number; category_name: string }[]>('/api/food-categories', signal),
  })
  const routes = (routesQuery.data ?? []).filter((route) => {
    if (!user?.primary_branch_id) return false
    return route.managing_branch?.branch_id === user.primary_branch_id && route.route_type !== 'DISTRIBUTION'
  })

  async function submit(values: FormValues) {
    setError(null)
    try {
      const data = await apiRequest<DonationDetail>('/api/donations', {
        method: 'POST',
        body: {
          pickup_route_id: values.pickup_route_id ? Number(values.pickup_route_id) : null,
          pickup_datetime: toIst(values.pickup_datetime),
          pickup_address: values.pickup_address.trim(),
          pickup_pincode: values.pickup_pincode.trim(),
          pickup_contact: values.pickup_contact.trim(),
          urgency_level: values.urgency_level,
          items: values.items.map((item) => ({
            category_id: Number(item.category_id),
            item_name: item.item_name.trim(),
            quantity_kg: item.quantity_kg,
            best_before: toIst(item.best_before),
          })),
        },
      })
      navigate(`/donations/${data.data.donation_id}`, { replace: true })
    } catch (caught) {
      setError(
        caught instanceof ApiRequestError
          ? caught.message
          : 'The donation could not be registered.',
      )
    }
  }

  const errors = form.formState.errors

  return (
    <div className="space-y-7">
      <PageHeader
        eyebrow="Donor workflow"
        title="Register a donation"
        description="Record the food, its quantity, and a real pickup window. A manager can route an unassigned donation later."
        action={
          <Link to="/donations" className={cn(buttonVariants({ variant: 'outline' }), 'h-10 px-4')}>
            <ArrowLeft aria-hidden="true" className="size-4" />
            Back to donations
          </Link>
        }
      />

      {error ? <ErrorNotice error={error} /> : null}
      {routesQuery.isError ? (
        <ErrorNotice error={routesQuery.error} onRetry={() => void routesQuery.refetch()} />
      ) : null}

      <form onSubmit={form.handleSubmit(submit)} className="space-y-6" noValidate>
        <Panel title="Pickup" description="The donor's branch anchors an unrouted donation for its manager.">
          <div className="grid gap-5 md:grid-cols-2">
            <div className="space-y-1.5 md:col-span-2">
              <Label htmlFor="pickup_route_id">Pickup route (optional)</Label>
              <select
                id="pickup_route_id"
                {...form.register('pickup_route_id')}
                className="h-9 w-full rounded-[4px] border border-input bg-paper px-3 text-sm text-charcoal"
              >
                <option value="">Leave unrouted for my branch manager</option>
                {routes.map((route) => (
                  <option key={route.route_id} value={route.route_id}>
                    Route #{route.route_id} · {route.coverage_area?.area_name ?? 'Coverage area'}
                  </option>
                ))}
              </select>
              {!user?.primary_branch_id ? (
                <p className="text-xs leading-5 text-ink-soft">
                  Your account has no branch anchor, so this donation will stay operator-only
                  until a branch is assigned.
                </p>
              ) : null}
            </div>
            <div className="space-y-1.5">
              <Label htmlFor="pickup_datetime">Pickup date and time (IST)</Label>
              <Input id="pickup_datetime" type="datetime-local" {...form.register('pickup_datetime')} />
              {errors.pickup_datetime ? <p className="text-xs text-charcoal">{errors.pickup_datetime.message}</p> : null}
            </div>
            <div className="space-y-1.5">
              <Label htmlFor="urgency_level">Urgency</Label>
              <select
                id="urgency_level"
                {...form.register('urgency_level')}
                className="h-9 w-full rounded-[4px] border border-input bg-paper px-3 text-sm text-charcoal"
              >
                <option value="LOW">Low</option>
                <option value="NORMAL">Normal</option>
                <option value="HIGH">High</option>
              </select>
            </div>
            <div className="space-y-1.5 md:col-span-2">
              <Label htmlFor="pickup_address">Pickup address</Label>
              <Input id="pickup_address" {...form.register('pickup_address')} />
              {errors.pickup_address ? <p className="text-xs text-charcoal">{errors.pickup_address.message}</p> : null}
            </div>
            <div className="space-y-1.5">
              <Label htmlFor="pickup_pincode">Pincode</Label>
              <Input id="pickup_pincode" inputMode="numeric" {...form.register('pickup_pincode')} />
              {errors.pickup_pincode ? <p className="text-xs text-charcoal">{errors.pickup_pincode.message}</p> : null}
            </div>
            <div className="space-y-1.5">
              <Label htmlFor="pickup_contact">Contact</Label>
              <Input id="pickup_contact" inputMode="tel" placeholder="+919876543210" {...form.register('pickup_contact')} />
              {errors.pickup_contact ? <p className="text-xs text-charcoal">{errors.pickup_contact.message}</p> : null}
            </div>
          </div>
        </Panel>

        <Panel
          title="Food items"
          description="Each item carries its own best-before time; quantities are strings with two decimals."
          action={
            <Button type="button" variant="outline" size="sm" onClick={() => append({ category_id: '', item_name: '', quantity_kg: '', best_before: '' })}>
              <Plus aria-hidden="true" className="size-4" />
              Add item
            </Button>
          }
        >
          <div className="space-y-5">
            {fields.map((field, index) => (
              <fieldset key={field.id} className="rounded-[8px] border border-line p-4">
                <legend className="px-1 text-xs font-semibold tracking-[0.08em] text-ink-soft uppercase">
                  Item {index + 1}
                </legend>
                <div className="grid gap-4 md:grid-cols-2">
                  <div className="space-y-1.5">
                    <Label htmlFor={`item-name-${index}`}>Food name</Label>
                    <Input id={`item-name-${index}`} {...form.register(`items.${index}.item_name`)} />
                    {errors.items?.[index]?.item_name ? <p className="text-xs text-charcoal">{errors.items[index]?.item_name?.message}</p> : null}
                  </div>
                  <div className="space-y-1.5">
                    <Label htmlFor={`item-category-${index}`}>Category</Label>
                    <select
                      id={`item-category-${index}`}
                      {...form.register(`items.${index}.category_id`)}
                      className="h-9 w-full rounded-[4px] border border-input bg-paper px-3 text-sm text-charcoal"
                    >
                      <option value="">Choose a category</option>
                      {(categoriesQuery.data ?? []).map((category) => (
                        <option key={category.category_id} value={category.category_id}>
                          {category.category_name}
                        </option>
                      ))}
                    </select>
                    {errors.items?.[index]?.category_id ? <p className="text-xs text-charcoal">{errors.items[index]?.category_id?.message}</p> : null}
                  </div>
                  <div className="space-y-1.5">
                    <Label htmlFor={`item-quantity-${index}`}>Quantity (kg)</Label>
                    <Input id={`item-quantity-${index}`} inputMode="decimal" {...form.register(`items.${index}.quantity_kg`)} />
                    {errors.items?.[index]?.quantity_kg ? <p className="text-xs text-charcoal">{errors.items[index]?.quantity_kg?.message}</p> : null}
                  </div>
                  <div className="space-y-1.5">
                    <Label htmlFor={`item-best-${index}`}>Best before (IST)</Label>
                    <Input id={`item-best-${index}`} type="datetime-local" {...form.register(`items.${index}.best_before`)} />
                    {errors.items?.[index]?.best_before ? <p className="text-xs text-charcoal">{errors.items[index]?.best_before?.message}</p> : null}
                  </div>
                </div>
                {fields.length > 1 ? (
                  <Button type="button" variant="ghost" size="sm" className="mt-3" onClick={() => remove(index)}>
                    <Trash2 aria-hidden="true" className="size-4" />
                    Remove item
                  </Button>
                ) : null}
              </fieldset>
            ))}
          </div>
          {errors.items?.message ? <p className="mt-3 text-xs text-charcoal">{errors.items.message}</p> : null}
        </Panel>

        <div className="flex flex-col-reverse gap-3 sm:flex-row sm:justify-end">
          <Link to="/donations" className={cn(buttonVariants({ variant: 'outline' }), 'h-10 px-4')}>
            Cancel
          </Link>
          <Button type="submit" className="h-10 px-5" disabled={form.formState.isSubmitting}>
            {form.formState.isSubmitting ? 'Registering…' : 'Register donation'}
          </Button>
        </div>
        {Object.keys(errors).length > 0 ? (
          <p role="alert" className="flex items-center justify-end gap-2 text-xs text-charcoal">
            <AlertCircle aria-hidden="true" className="size-3.5" />
            Check the highlighted fields.
          </p>
        ) : null}
      </form>
    </div>
  )
}
