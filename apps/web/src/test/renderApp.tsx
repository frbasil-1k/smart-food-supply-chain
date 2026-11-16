import { render } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'

import App from '@/App'
import type { HealthData } from '@/lib/api'

export const healthFixture: HealthData = {
  status: 'ok',
  service: 'sfc-api',
  version: '0.1.0',
  environment: 'testing',
  timezone: 'Asia/Kolkata',
  time: '2026-11-16T23:45:00+05:30',
}

export function jsonResponse(
  payload: unknown,
  status = 200,
  requestId = 'test-request-id',
): Response {
  return {
    ok: status >= 200 && status < 300,
    status,
    headers: new Headers({ 'X-Request-ID': requestId }),
    json: async () => payload,
  } as Response
}

export function healthEnvelope() {
  return jsonResponse({ data: healthFixture, meta: {} }, 200, 'health-request')
}

export function renderApp(initialPath = '/') {
  return render(
    <MemoryRouter initialEntries={[initialPath]}>
      <App />
    </MemoryRouter>,
  )
}
