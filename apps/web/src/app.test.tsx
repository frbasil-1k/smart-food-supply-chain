import { afterEach, describe, expect, it, vi } from 'vitest'
import { screen, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'

import indexHtml from '../index.html?raw'
import { PRODUCT_NAME } from '@/lib/brand'
import type { User } from '@/lib/types'
import { healthEnvelope, jsonResponse, renderApp } from '@/test/renderApp'

const donor: User = {
  user_id: 3,
  full_name: 'Donor A',
  email: 'donor.a@example.test',
  phone: '+919876543210',
  role: 'DONOR',
  account_status: 'ACTIVE',
  primary_branch_id: 1,
  branch_name: 'Branch A',
  primary_branch: { branch_id: 1, branch_name: 'Branch A' },
  supervisor_user_id: null,
}

const manager: User = {
  ...donor,
  user_id: 1,
  full_name: 'Manager A',
  role: 'NGO_MANAGER',
}

const overview = {
  open_donations: 2,
  kg_donated: '10.00',
  kg_delivered: '4.00',
  kg_spoiled: '0.00',
  balance_kg: '6.00',
  donations_by_status: [{ status: 'PENDING', count: 2 }],
  donations_awaiting_review: 2,
  inspections_pending: 1,
  deliveries_in_transit: 0,
  deliveries_today: 0,
  kg_allocated_open: '3.00',
  expiring_within_48h: 1,
  avg_rating: '0.00',
  assigned_today: 0,
  in_transit: 0,
  delivered_this_week: 0,
  kg_delivered_this_week: '0.00',
  next_delivery: null,
  queue_size: 1,
  inspected_today: 0,
  failed_last_7d: 0,
  avg_temperature_7d: '0.00',
}

function envelope(data: unknown) {
  return jsonResponse({ data, meta: {} })
}

function paged<T>(rows: T[]) {
  return jsonResponse({
    data: rows,
    meta: { pagination: { page: 1, page_size: 25, total: rows.length, pages: 1 } },
  })
}

function mockApi({
  authenticated = true,
  user = donor,
  health = true,
}: {
  authenticated?: boolean
  user?: User
  health?: boolean
} = {}) {
  return vi.fn(async (input: RequestInfo | URL) => {
    const url = typeof input === 'string' ? input : input instanceof URL ? input.href : input.url
    if (url.includes('/api/auth/me')) {
      return authenticated
        ? envelope(user)
        : jsonResponse(
            {
              error: { code: 'unauthenticated', message: 'Sign in is required.' },
              request_id: 'auth-request',
            },
            401,
            'auth-request',
          )
    }
    if (url.includes('/api/auth/csrf')) return envelope({ csrf_token: 'test-csrf' })
    if (url.includes('/api/auth/login')) return envelope({ user, csrf_token: 'test-csrf' })
    if (url.includes('/api/auth/logout')) return envelope({})
    if (url.includes('/api/health')) {
      if (!health) throw new TypeError('Network unavailable')
      return healthEnvelope()
    }
    if (url.includes('/api/reports/overview')) return envelope(overview)
    if (url.includes('/api/reports/donors')) return envelope([])
    if (url.includes('/api/reports/drivers')) return envelope([])
    if (url.includes('/api/reports/branches')) return envelope([])
    if (url.includes('/api/reports/freshness')) return envelope([])
    if (url.includes('/api/activity')) return paged([])
    if (url.includes('/api/donations')) return paged([])
    if (url.includes('/api/deliveries')) return paged([])
    if (url.includes('/api/inspections')) return paged([])
    if (url.includes('/api/branches')) return paged([])
    if (url.includes('/api/routes')) return paged([])
    if (url.includes('/api/users')) return paged([])
    if (url.includes('/api/dependents')) return envelope([])
    if (url.includes('/api/organizations') || url.includes('/api/coverage-areas') || url.includes('/api/food-categories')) {
      return envelope([])
    }
    if (url.includes('/api/spoilage')) return paged([])
    return envelope({})
  })
}

describe('application shell', () => {
  afterEach(() => {
    vi.unstubAllGlobals()
  })

  it('redirects a signed-out visitor to the login screen', async () => {
    vi.stubGlobal('fetch', mockApi({ authenticated: false }))
    renderApp()

    expect(
      await screen.findByRole('heading', { level: 1, name: /keep good food moving/i }),
    ).toBeInTheDocument()
    expect(screen.getByRole('heading', { level: 2, name: 'Sign in' })).toBeInTheDocument()
    expect(screen.getAllByText(PRODUCT_NAME).length).toBeGreaterThanOrEqual(1)
    expect(indexHtml).toContain(
      '<title>Smart Food Supply Chain &amp; Surplus Redistribution System</title>',
    )
  })

  it('signs a provisioned user in through the real form flow', async () => {
    const user = userEvent.setup()
    vi.stubGlobal('fetch', mockApi({ authenticated: false }))
    renderApp('/login')

    await user.type(screen.getByLabelText(/email/i), donor.email)
    await user.type(screen.getByLabelText(/password/i), 'TestPass!12345')
    await user.click(screen.getByRole('button', { name: /^sign in$/i }))

    expect(
      await screen.findByRole('heading', { level: 1, name: 'Overview' }),
    ).toBeInTheDocument()
    expect(screen.getAllByText(donor.full_name).length).toBeGreaterThan(0)
  })

  it('renders role navigation and moves to a role screen', async () => {
    const user = userEvent.setup()
    vi.stubGlobal('fetch', mockApi())
    renderApp()

    expect(
      await screen.findByRole('heading', { level: 1, name: 'Overview' }),
    ).toBeInTheDocument()
    const rail = screen.getByTestId('rail-nav')
    expect(within(rail).getByRole('link', { name: 'Donations' })).toHaveAttribute(
      'href',
      '/donations',
    )
    expect(within(rail).queryByRole('link', { name: 'Branches' })).not.toBeInTheDocument()

    await user.click(within(rail).getByRole('link', { name: 'Donations' }))

    expect(
      await screen.findByRole('heading', { level: 1, name: 'Donations' }),
    ).toBeInTheDocument()
    expect(screen.getAllByRole('link', { name: /register donation/i }).length).toBeGreaterThan(0)
  })

  it('shows manager-only navigation for a manager and hides it from a donor', async () => {
    vi.stubGlobal('fetch', mockApi({ user: manager }))
    renderApp()

    await screen.findByRole('heading', { level: 1, name: 'Overview' })
    const rail = screen.getByTestId('rail-nav')
    expect(within(rail).getByRole('link', { name: 'Branches' })).toBeInTheDocument()
    expect(within(rail).getByRole('link', { name: 'Reports' })).toBeInTheDocument()
    expect(within(rail).queryByRole('link', { name: 'Impact' })).not.toBeInTheDocument()
  })

  it('refuses a screen outside the signed-in role', async () => {
    vi.stubGlobal('fetch', mockApi())
    renderApp('/reports')

    expect(
      await screen.findByRole('heading', { level: 1, name: /not available to your role/i }),
    ).toBeInTheDocument()
  })

  it('renders live API health on the system route', async () => {
    const user = userEvent.setup()
    vi.stubGlobal('fetch', mockApi())
    renderApp('/system')

    expect(
      await screen.findByRole('heading', { level: 1, name: 'System status' }),
    ).toBeInTheDocument()
    expect(await screen.findByText('Online')).toBeInTheDocument()
    expect(screen.getByText(/sfc-api 0\.1\.0/)).toBeInTheDocument()

    const systemLink = within(screen.getByTestId('rail-nav')).getByRole('link', {
      name: 'System',
    })
    expect(systemLink).toHaveAttribute('aria-current', 'page')
    await user.click(screen.getByRole('button', { name: /refresh/i }))
    expect(await screen.findByText('Online')).toBeInTheDocument()
  })

  it('keeps responsive navigation and accessibility basics in place', async () => {
    vi.stubGlobal('fetch', mockApi())
    renderApp()

    await screen.findByRole('heading', { level: 1, name: 'Overview' })

    const rail = screen.getByTestId('rail-nav')
    expect(rail).toHaveClass('hidden', 'md:flex')

    const primaryNavs = screen.getAllByRole('navigation', { name: 'Primary' })
    expect(primaryNavs).toHaveLength(2)
    const bottomNav = primaryNavs.find((nav) => nav.className.includes('fixed'))
    expect(bottomNav).toBeDefined()
    expect(bottomNav).toHaveClass('md:hidden')

    const skipLink = screen.getByRole('link', { name: /skip to content/i })
    expect(skipLink).toHaveAttribute('href', '#main')

    const main = screen.getByRole('main')
    expect(main).toHaveAttribute('id', 'main')

    for (const link of screen.getAllByRole('link')) {
      expect(link).toHaveAccessibleName()
    }

    const levels = screen
      .getAllByRole('heading')
      .map((heading) => Number(heading.tagName.slice(1)))
    expect(levels[0]).toBe(1)
    for (let index = 1; index < levels.length; index += 1) {
      expect(levels[index]! - levels[index - 1]!).toBeLessThanOrEqual(1)
    }
  })

  it('renders a real not-found screen for unknown routes', async () => {
    vi.stubGlobal('fetch', mockApi())
    renderApp('/unknown')

    expect(
      await screen.findByRole('heading', {
        level: 1,
        name: /this page is not part of the workspace/i,
      }),
    ).toBeInTheDocument()
    expect(
      screen.getByRole('link', { name: /back to overview/i }),
    ).toHaveAttribute('href', '/')
  })
})
