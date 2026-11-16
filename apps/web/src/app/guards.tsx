import { Navigate, Outlet, useLocation } from 'react-router-dom'
import { ShieldAlert } from 'lucide-react'

import { BrandMark } from '@/components/BrandMark'
import { buttonVariants } from '@/components/ui/button'
import { useAuth } from '@/features/auth/AuthProvider'
import { PRODUCT_NAME } from '@/lib/brand'
import type { Role } from '@/lib/types'
import { cn } from 'cn'
import { Link } from 'react-router-dom'

export function RequireAuth() {
  const { user, loading } = useAuth()
  const location = useLocation()
  if (loading) {
    return (
      <main className="flex min-h-svh items-center justify-center bg-oat px-6">
        <div className="flex flex-col items-center gap-4 text-center">
          <BrandMark className="size-10 text-forest" />
          <p className="text-sm text-ink-soft">Checking your session…</p>
          <span className="sr-only">{PRODUCT_NAME}</span>
        </div>
      </main>
    )
  }
  if (!user) {
    return <Navigate to="/login" replace state={{ from: `${location.pathname}${location.search}` }} />
  }
  return <Outlet />
}

export function RequireRole({ roles }: { roles: Role[] }) {
  const { user } = useAuth()
  if (!user || !roles.includes(user.role)) {
    return (
      <section className="mx-auto max-w-xl rounded-[8px] border border-line bg-paper p-8">
        <ShieldAlert aria-hidden="true" className="size-8 text-forest" />
        <h1 className="mt-4 font-heading text-3xl text-charcoal">Not available to your role</h1>
        <p className="mt-2 text-sm leading-6 text-ink-soft">
          This workspace belongs to another role. Your session is still active;
          use the navigation for the records your role can see.
        </p>
        <Link to="/" className={cn(buttonVariants(), 'mt-5 h-9 px-3')}>
          Back to overview
        </Link>
      </section>
    )
  }
  return <Outlet />
}
