import { NavLink } from 'react-router-dom'
import { cn } from 'cn'
import { LogOut } from 'lucide-react'

import { PRODUCT_NAME } from '@/lib/brand'
import { BrandMark } from '@/components/BrandMark'
import { useAuth } from '@/features/auth/AuthProvider'
import { ROLE_LABELS, navigationForRole } from './navigation'

export function RailNav() {
  const { user, logout } = useAuth()
  const items = navigationForRole(user?.role ?? null)

  return (
    <aside
      data-testid="rail-nav"
      className="sticky top-0 hidden h-svh shrink-0 flex-col bg-forest text-oat md:flex md:w-16 xl:w-60"
    >
      <div className="flex min-h-16 items-center gap-3 border-b border-oat/15 px-3 py-3 xl:px-5">
        <NavLink
          to="/"
          aria-label={PRODUCT_NAME}
          className="flex min-w-0 items-center gap-3 rounded-[4px] focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-oat"
        >
          <BrandMark className="size-8 shrink-0 text-oat" />
          <span className="hidden text-[11px] leading-4 font-medium text-oat xl:block">
            {PRODUCT_NAME}
          </span>
        </NavLink>
      </div>

      <nav aria-label="Primary" className="flex-1 overflow-y-auto px-2 py-4">
        <ul className="space-y-1">
          {items.map((item) => {
            const Icon = item.icon
            return (
              <li key={item.to}>
                <NavLink
                  to={item.to}
                  end={item.end}
                  aria-label={item.label}
                  className={({ isActive }) =>
                    cn(
                      'flex min-h-11 items-center gap-3 rounded-r-[4px] border-l-[3px] px-3 text-sm font-medium transition-colors focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-oat',
                      isActive
                        ? 'border-l-terracotta bg-white/10 text-oat'
                        : 'border-l-transparent text-oat/70 hover:bg-white/5 hover:text-oat',
                    )
                  }
                >
                  <Icon aria-hidden="true" className="size-5 shrink-0" />
                  <span className="hidden xl:inline">{item.label}</span>
                </NavLink>
              </li>
            )
          })}
        </ul>
      </nav>

      <div className="hidden border-t border-oat/15 px-4 py-4 xl:block">
        <p className="truncate text-xs font-semibold text-oat">{user?.full_name}</p>
        <p className="mt-1 text-[10px] tracking-[0.08em] text-oat/75 uppercase">
          {user ? ROLE_LABELS[user.role] : ''}
        </p>
        <button
          type="button"
          onClick={() => void logout()}
          className="mt-3 inline-flex min-h-9 items-center gap-2 rounded-[4px] text-xs font-semibold text-oat/75 hover:text-oat focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-oat"
        >
          <LogOut aria-hidden="true" className="size-4" />
          Sign out
        </button>
      </div>
    </aside>
  )
}
