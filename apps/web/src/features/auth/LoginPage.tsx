import { useState, type FormEvent } from 'react'
import { Link, Navigate, useLocation, useNavigate } from 'react-router-dom'
import { AlertCircle, ArrowRight, LockKeyhole } from 'lucide-react'

import { BrandMark } from '@/components/BrandMark'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { PRODUCT_NAME } from '@/lib/brand'
import { ApiRequestError } from '@/lib/api'
import { useAuth } from './AuthProvider'

export function LoginPage() {
  const { login, user } = useAuth()
  const navigate = useNavigate()
  const location = useLocation()
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [error, setError] = useState<string | null>(null)
  const [busy, setBusy] = useState(false)

  if (user) {
    return <Navigate to="/" replace />
  }

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    setError(null)
    setBusy(true)
    try {
      await login(email.trim(), password)
      const from = (location.state as { from?: string } | null)?.from ?? '/'
      navigate(from, { replace: true })
    } catch (caught) {
      setError(
        caught instanceof ApiRequestError
          ? caught.message
          : 'Sign in could not be completed.',
      )
    } finally {
      setBusy(false)
    }
  }

  return (
    <main className="grid min-h-svh bg-oat lg:grid-cols-[minmax(0,1fr)_minmax(380px,0.8fr)]">
      <section className="flex flex-col justify-between bg-forest px-6 py-8 text-oat sm:px-10 lg:px-16 lg:py-12">
        <div className="flex items-center gap-3">
          <BrandMark className="size-9 text-oat" />
          <span className="max-w-[18rem] text-xs leading-5 font-medium">
            {PRODUCT_NAME}
          </span>
        </div>
        <div className="my-12 max-w-xl space-y-5">
          <p className="text-[11px] font-semibold tracking-[0.16em] text-oat/75 uppercase">
            Operations workspace
          </p>
          <h1 className="font-heading text-[36px] leading-[1.05] font-medium tracking-tight sm:text-[52px]">
            Keep good food moving.
          </h1>
          <p className="max-w-lg text-sm leading-6 text-oat/75 sm:text-base sm:leading-7">
            Donations, inspections, route allocations, and deliveries meet in
            one traceable chain. Sign in to work with the records your role
            can see.
          </p>
        </div>
        <p className="text-xs leading-5 text-oat/75">
          Quantities stay explicit. Every transition is attributable.
        </p>
      </section>

      <section className="flex items-center justify-center px-5 py-10 sm:px-8">
        <div className="w-full max-w-md space-y-7 rounded-[8px] border border-line bg-paper p-6 sm:p-8">
          <div className="space-y-2">
            <span className="inline-flex size-10 items-center justify-center rounded-[4px] bg-oat-deep text-forest">
              <LockKeyhole aria-hidden="true" className="size-5" />
            </span>
            <h2 className="font-heading text-[28px] leading-8 font-medium text-charcoal">
              Sign in
            </h2>
            <p className="text-sm leading-6 text-ink-soft">
              Use the email and password provisioned by your manager or
              operator.
            </p>
          </div>

          <form className="space-y-4" onSubmit={submit} noValidate>
            <div className="space-y-1.5">
              <Label htmlFor="email">Email</Label>
              <Input
                id="email"
                name="email"
                type="email"
                autoComplete="username"
                required
                value={email}
                onChange={(event) => setEmail(event.target.value)}
              />
            </div>
            <div className="space-y-1.5">
              <Label htmlFor="password">Password</Label>
              <Input
                id="password"
                name="password"
                type="password"
                autoComplete="current-password"
                required
                value={password}
                onChange={(event) => setPassword(event.target.value)}
              />
            </div>
            {error ? (
              <p
                role="alert"
                className="flex items-start gap-2 rounded-[4px] border-l-[3px] border-l-terracotta bg-oat px-3 py-2 text-sm leading-5 text-charcoal"
              >
                <AlertCircle aria-hidden="true" className="mt-0.5 size-4 shrink-0" />
                {error}
              </p>
            ) : null}
            <Button type="submit" className="h-10 w-full px-4" disabled={busy}>
              {busy ? 'Signing in…' : 'Sign in'}
              {!busy ? <ArrowRight aria-hidden="true" className="size-4" /> : null}
            </Button>
          </form>

          <p className="border-t border-line pt-5 text-sm leading-6 text-ink-soft">
            Have an activation token?{' '}
            <Link
              to="/activate"
              className="font-semibold text-forest underline underline-offset-4"
            >
              Activate your account
            </Link>
          </p>
        </div>
      </section>
    </main>
  )
}
