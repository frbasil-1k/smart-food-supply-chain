import { useState, type FormEvent } from 'react'
import { Link, useNavigate, useSearchParams } from 'react-router-dom'
import { AlertCircle, CheckCircle2, KeyRound } from 'lucide-react'

import { BrandMark } from '@/components/BrandMark'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { PRODUCT_NAME } from '@/lib/brand'
import { ApiRequestError, apiRequest } from '@/lib/api'
import { useAuth } from './AuthProvider'

type ActivationResponse = {
  user: {
    user_id: number
    full_name: string
    email: string
    role: string
    account_status: string
  }
  csrf_token: string
}

export function ActivatePage() {
  const [searchParams] = useSearchParams()
  const navigate = useNavigate()
  const { refresh } = useAuth()
  const [token, setToken] = useState(searchParams.get('token') ?? '')
  const [password, setPassword] = useState('')
  const [confirm, setConfirm] = useState('')
  const [error, setError] = useState<string | null>(null)
  const [done, setDone] = useState(false)
  const [busy, setBusy] = useState(false)

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    setError(null)
    if (password !== confirm) {
      setError('The passwords do not match.')
      return
    }
    setBusy(true)
    try {
      await apiRequest<ActivationResponse>('/api/auth/activate', {
        method: 'POST',
        body: { token: token.trim(), new_password: password },
      })
      setDone(true)
      await refresh()
      window.setTimeout(() => navigate('/', { replace: true }), 700)
    } catch (caught) {
      setError(
        caught instanceof ApiRequestError
          ? caught.message
          : 'Account activation could not be completed.',
      )
    } finally {
      setBusy(false)
    }
  }

  return (
    <main className="flex min-h-svh items-center justify-center bg-oat px-5 py-10">
      <div className="w-full max-w-lg space-y-7 rounded-[8px] border border-line bg-paper p-6 sm:p-8">
        <div className="flex items-center gap-3 border-b border-line pb-5">
          <BrandMark className="size-8 text-forest" />
          <span className="text-xs leading-5 font-medium text-charcoal">{PRODUCT_NAME}</span>
        </div>
        <div className="space-y-2">
          <span className="inline-flex size-10 items-center justify-center rounded-[4px] bg-oat-deep text-forest">
            <KeyRound aria-hidden="true" className="size-5" />
          </span>
          <h1 className="font-heading text-[28px] leading-8 font-medium text-charcoal">
            Activate your account
          </h1>
          <p className="text-sm leading-6 text-ink-soft">
            Use the token your manager or operator shared with you. Choose a
            password of at least 12 characters that is not a common password.
          </p>
        </div>

        {done ? (
          <p className="flex items-center gap-2 rounded-[4px] bg-forest/10 px-3 py-3 text-sm font-medium text-forest">
            <CheckCircle2 aria-hidden="true" className="size-4" />
            Activated. Opening your workspace…
          </p>
        ) : (
          <form className="space-y-4" onSubmit={submit} noValidate>
            <div className="space-y-1.5">
              <Label htmlFor="token">Activation token</Label>
              <Input
                id="token"
                required
                value={token}
                onChange={(event) => setToken(event.target.value)}
                autoComplete="one-time-code"
              />
            </div>
            <div className="space-y-1.5">
              <Label htmlFor="new-password">New password</Label>
              <Input
                id="new-password"
                type="password"
                required
                minLength={12}
                autoComplete="new-password"
                value={password}
                onChange={(event) => setPassword(event.target.value)}
              />
            </div>
            <div className="space-y-1.5">
              <Label htmlFor="confirm-password">Confirm password</Label>
              <Input
                id="confirm-password"
                type="password"
                required
                minLength={12}
                autoComplete="new-password"
                value={confirm}
                onChange={(event) => setConfirm(event.target.value)}
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
              {busy ? 'Activating…' : 'Activate account'}
            </Button>
          </form>
        )}

        <p className="border-t border-line pt-5 text-sm leading-6 text-ink-soft">
          Already activated?{' '}
          <Link
            to="/login"
            className="font-semibold text-forest underline underline-offset-4"
          >
            Sign in
          </Link>
        </p>
      </div>
    </main>
  )
}
