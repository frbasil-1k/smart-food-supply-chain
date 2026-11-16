const dateTimeFormatter = new Intl.DateTimeFormat('en-IN', {
  timeZone: 'Asia/Kolkata',
  dateStyle: 'medium',
  timeStyle: 'short',
})

export function formatLocalDateTime(value: string | null | undefined): string {
  if (!value) return 'Not set'
  const parsed = new Date(value)
  if (Number.isNaN(parsed.getTime())) {
    return 'Unavailable'
  }
  return dateTimeFormatter.format(parsed)
}

const dateFormatter = new Intl.DateTimeFormat('en-IN', {
  timeZone: 'Asia/Kolkata',
  dateStyle: 'medium',
})

export function formatLocalDate(value: string | null | undefined): string {
  if (!value) return 'Not set'
  const parsed = new Date(value)
  if (Number.isNaN(parsed.getTime())) return 'Unavailable'
  return dateFormatter.format(parsed)
}

export function formatRelative(value: string | null | undefined): string {
  if (!value) return 'No timestamp'
  const parsed = new Date(value)
  if (Number.isNaN(parsed.getTime())) return 'Unavailable'
  const minutes = Math.round((parsed.getTime() - Date.now()) / 60_000)
  if (Math.abs(minutes) < 60) {
    return new Intl.RelativeTimeFormat('en', { numeric: 'auto' }).format(minutes, 'minute')
  }
  const hours = Math.round(minutes / 60)
  if (Math.abs(hours) < 48) {
    return new Intl.RelativeTimeFormat('en', { numeric: 'auto' }).format(hours, 'hour')
  }
  const days = Math.round(hours / 24)
  return new Intl.RelativeTimeFormat('en', { numeric: 'auto' }).format(days, 'day')
}
