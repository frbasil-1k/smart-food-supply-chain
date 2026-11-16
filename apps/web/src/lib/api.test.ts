import { afterEach, describe, expect, it, vi } from 'vitest'

import { ApiRequestError, apiGetPaged, apiRequest, fetchHealth, setCsrfToken } from './api'
import { healthEnvelope, healthFixture, jsonResponse } from '@/test/renderApp'

afterEach(() => {
  vi.unstubAllGlobals()
})

describe('fetchHealth', () => {
  it('returns validated data and the request id', async () => {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue(healthEnvelope()))

    const result = await fetchHealth()

    expect(result.data).toEqual(healthFixture)
    expect(result.requestId).toBe('health-request')
    expect(fetch).toHaveBeenCalledWith(
      '/api/health',
      expect.objectContaining({ method: 'GET' }),
    )
  })

  it('raises a typed error for the API error envelope', async () => {
    vi.stubGlobal(
      'fetch',
      vi.fn().mockResolvedValue(
        jsonResponse(
          {
            error: {
              code: 'invalid_transition',
              message: 'This delivery cannot move to that state.',
            },
            request_id: 'error-request',
          },
          409,
          'error-request',
        ),
      ),
    )

    await expect(fetchHealth()).rejects.toMatchObject({
      status: 409,
      code: 'invalid_transition',
      requestId: 'error-request',
    })
    await expect(fetchHealth()).rejects.toBeInstanceOf(ApiRequestError)
  })

  it('rejects an unexpected success payload', async () => {
    vi.stubGlobal(
      'fetch',
      vi.fn().mockResolvedValue(jsonResponse({ data: null }, 200)),
    )

    await expect(fetchHealth()).rejects.toMatchObject({
      status: 502,
      code: 'invalid_response',
    })
  })
})

describe('authenticated request helpers', () => {
  afterEach(() => {
    vi.unstubAllGlobals()
  })

  it('returns an empty payload for a 204 response instead of failing envelope parsing', async () => {
    setCsrfToken('test-csrf')
    vi.stubGlobal(
      'fetch',
      vi.fn().mockResolvedValue(new Response(null, { status: 204 })),
    )

    const result = await apiRequest<void>('/api/auth/logout', { method: 'POST' })

    expect(result.data).toBeUndefined()
    expect(result.requestId).toBeNull()
    setCsrfToken(null)
  })

  it('rebuilds a paged result with the response pagination metadata', async () => {
    vi.stubGlobal(
      'fetch',
      vi.fn().mockResolvedValue(
        jsonResponse({
          data: [{ donation_id: 1 }],
          meta: { pagination: { page: 2, page_size: 25, total: 26, pages: 2 } },
        }),
      ),
    )

    const result = await apiGetPaged<{ donation_id: number }>('/api/donations?page=2')

    expect(result.data).toEqual([{ donation_id: 1 }])
    expect(result.meta.pagination).toMatchObject({ page: 2, total: 26, pages: 2 })
  })
})
