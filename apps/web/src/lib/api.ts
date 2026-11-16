import { z } from 'zod'

const healthDataSchema = z.object({
  status: z.literal('ok'),
  service: z.literal('sfc-api'),
  version: z.string().min(1),
  environment: z.string().min(1),
  timezone: z.string().min(1),
  time: z.string().min(1),
})

const healthEnvelopeSchema = z.object({
  data: healthDataSchema,
  meta: z.record(z.string(), z.unknown()),
})

const errorEnvelopeSchema = z.object({
  error: z.object({
    code: z.string().min(1),
    message: z.string().min(1),
    details: z
      .array(z.object({ field: z.string(), issue: z.string() }))
      .optional(),
  }),
  request_id: z.string().min(1),
})

export type HealthData = z.infer<typeof healthDataSchema>

export type HealthResult = {
  data: HealthData
  requestId: string | null
}

export class ApiRequestError extends Error {
  readonly status: number
  readonly code: string
  readonly requestId: string | null

  constructor(
    status: number,
    code: string,
    message: string,
    requestId: string | null,
  ) {
    super(message)
    this.name = 'ApiRequestError'
    this.status = status
    this.code = code
    this.requestId = requestId
  }
}

async function readJson(response: Response): Promise<unknown> {
  try {
    return await response.json()
  } catch {
    return null
  }
}

export async function fetchHealth(signal?: AbortSignal): Promise<HealthResult> {
  const response = await fetch('/api/health', {
    method: 'GET',
    headers: { Accept: 'application/json' },
    credentials: 'same-origin',
    signal,
  })
  const requestId = response.headers.get('X-Request-ID')
  const payload = await readJson(response)

  if (!response.ok) {
    const parsedError = errorEnvelopeSchema.safeParse(payload)
    if (parsedError.success) {
      throw new ApiRequestError(
        response.status,
        parsedError.data.error.code,
        parsedError.data.error.message,
        requestId,
      )
    }
    throw new ApiRequestError(
      response.status,
      'request_failed',
      'The API could not complete the request.',
      requestId,
    )
  }

  const parsed = healthEnvelopeSchema.safeParse(payload)
  if (!parsed.success) {
    throw new ApiRequestError(
      502,
      'invalid_response',
      'The API returned an unexpected response.',
      requestId,
    )
  }

  return { data: parsed.data.data, requestId }
}


let csrfToken: string | null = null

export function setCsrfToken(token: string | null) {
  csrfToken = token
}

export function getCsrfToken() {
  return csrfToken
}

export async function ensureCsrfToken(): Promise<string> {
  if (csrfToken) return csrfToken
  const response = await fetch('/api/auth/csrf', {
    method: 'GET',
    headers: { Accept: 'application/json' },
    credentials: 'same-origin',
  })
  const payload = await readJson(response)
  const parsed = z
    .object({ data: z.object({ csrf_token: z.string().min(1) }) })
    .safeParse(payload)
  if (!response.ok || !parsed.success) {
    throw new ApiRequestError(
      response.status,
      'csrf_unavailable',
      'The security token could not be loaded.',
      response.headers.get('X-Request-ID'),
    )
  }
  csrfToken = parsed.data.data.csrf_token
  return csrfToken
}

type RequestOptions = {
  method?: 'GET' | 'POST' | 'PATCH' | 'PUT' | 'DELETE'
  body?: unknown
  signal?: AbortSignal
}

const SAFE_METHODS = new Set(['GET', 'HEAD', 'OPTIONS'])

export async function apiRequest<T>(
  path: string,
  options: RequestOptions = {},
): Promise<{ data: T; meta: Record<string, unknown>; requestId: string | null }> {
  const method = options.method ?? 'GET'
  const headers: Record<string, string> = { Accept: 'application/json' }
  if (!SAFE_METHODS.has(method)) {
    headers['X-CSRF-Token'] = await ensureCsrfToken()
  }
  if (options.body !== undefined) headers['Content-Type'] = 'application/json'

  const response = await fetch(path, {
    method,
    headers,
    credentials: 'same-origin',
    body: options.body === undefined ? undefined : JSON.stringify(options.body),
    signal: options.signal,
  })
  const requestId = response.headers.get('X-Request-ID')
  const payload = await readJson(response)
  if (!response.ok) {
    const parsedError = errorEnvelopeSchema.safeParse(payload)
    if (parsedError.success) {
      throw new ApiRequestError(
        response.status,
        parsedError.data.error.code,
        parsedError.data.error.message,
        requestId,
      )
    }
    throw new ApiRequestError(
      response.status,
      'request_failed',
      'The API could not complete the request.',
      requestId,
    )
  }
  if (response.status === 204) {
    return { data: undefined as T, meta: {}, requestId }
  }
  const envelope = z
    .object({ data: z.unknown(), meta: z.record(z.string(), z.unknown()).optional() })
    .safeParse(payload)
  if (!envelope.success) {
    throw new ApiRequestError(
      502,
      'invalid_response',
      'The API returned an unexpected response.',
      requestId,
    )
  }
  return {
    data: envelope.data.data as T,
    meta: envelope.data.meta ?? {},
    requestId,
  }
}

export async function apiGet<T>(path: string, signal?: AbortSignal): Promise<T> {
  return (await apiRequest<T>(path, { signal })).data
}

export async function apiGetPaged<T>(
  path: string,
  signal?: AbortSignal,
): Promise<import('./types').Paged<T>> {
  const result = await apiRequest<T[]>(path, { signal })
  return {
    data: result.data,
    meta: result.meta as import('./types').Paged<T>['meta'],
  }
}

export async function fetchMe(): Promise<User | null> {
  try {
    const { data } = await apiRequest<User>('/api/auth/me')
    return data
  } catch (error) {
    if (error instanceof ApiRequestError && error.status === 401) return null
    throw error
  }
}

export async function loginRequest(email: string, password: string): Promise<User> {
  const token = await ensureCsrfToken()
  const response = await fetch('/api/auth/login', {
    method: 'POST',
    credentials: 'same-origin',
    headers: {
      Accept: 'application/json',
      'Content-Type': 'application/json',
      'X-CSRF-Token': token,
    },
    body: JSON.stringify({ email, password }),
  })
  const requestId = response.headers.get('X-Request-ID')
  const payload = await readJson(response)
  if (!response.ok) {
    const parsed = errorEnvelopeSchema.safeParse(payload)
    throw new ApiRequestError(
      response.status,
      parsed.success ? parsed.data.error.code : 'login_failed',
      parsed.success ? parsed.data.error.message : 'Sign in failed.',
      requestId,
    )
  }
  const parsed = z
    .object({
      data: z.object({
        user: z.custom<User>(),
        csrf_token: z.string().min(1),
      }),
    })
    .safeParse(payload)
  if (!parsed.success) {
    throw new ApiRequestError(502, 'invalid_response', 'Unexpected login response.', requestId)
  }
  csrfToken = parsed.data.data.csrf_token
  return parsed.data.data.user
}

export async function logoutRequest(): Promise<void> {
  try {
    await apiRequest<void>('/api/auth/logout', { method: 'POST' })
  } finally {
    csrfToken = null
  }
}

import type { User } from './types'
