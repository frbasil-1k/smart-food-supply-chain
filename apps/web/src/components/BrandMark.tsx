type BrandMarkProps = {
  className?: string
  title?: string
}

/**
 * Abstract brand glyph: the bowl arc and leaf vein, with no letterform.
 * Decorative by default; pass `title` only when it is the sole label.
 */
export function BrandMark({ className, title }: BrandMarkProps) {
  return (
    <svg
      viewBox="0 0 48 48"
      fill="none"
      className={className}
      role={title ? 'img' : undefined}
      aria-hidden={title ? undefined : true}
      focusable="false"
    >
      {title ? <title>{title}</title> : null}
      <path
        d="M8 25c0 8.6 6.8 15 16 15s16-6.4 16-15"
        stroke="currentColor"
        strokeWidth="3"
        strokeLinecap="round"
      />
      <path
        d="M24 25.5c.4-7.2 4.6-12.2 11.5-14.3-.8 8.2-4.8 12.9-11.5 14.3Z"
        stroke="currentColor"
        strokeWidth="2.4"
        strokeLinejoin="round"
      />
      <path
        d="M24 25.5c-.9-5.2-3.9-8.6-8.9-10.2.6 5.9 3.7 9.4 8.9 10.2Z"
        stroke="currentColor"
        strokeWidth="2.4"
        strokeLinejoin="round"
      />
      <path
        d="M24 26v9"
        stroke="var(--terracotta)"
        strokeWidth="2.4"
        strokeLinecap="round"
      />
    </svg>
  )
}
