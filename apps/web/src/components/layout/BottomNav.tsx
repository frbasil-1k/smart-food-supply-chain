import { NavLink } from 'react-router-dom'
import { cn } from 'cn'

import { useAuth } from '@/features/auth/AuthProvider'
import { navigationForRole } from './navigation'

export function BottomNav() {
  const { user } = useAuth()
  const items = navigationForRole(user?.role ?? null).slice(0, 4)

  return (
    <nav
      aria-label="Primary"
      className="fixed inset-x-0 bottom-0 z-30 border-t border-oat/15 bg-forest pb-[env(safe-area-inset-bottom)] text-oat md:hidden"
    >
      <ul className="grid grid-cols-4">
        {items.map((item) => {
          const Icon = item.icon
          return (
            <li key={item.to}>
              <NavLink
                to={item.to}
                end={item.end}
                className={({ isActive }) =>
                  cn(
                    'flex min-h-14 flex-col items-center justify-center gap-1 border-t-[3px] px-1 text-[10px] leading-3 font-semibold tracking-[0.03em] uppercase transition-colors focus-visible:outline-2 focus-visible:outline-offset-[-2px] focus-visible:outline-oat',
                    isActive
                      ? 'border-t-terracotta bg-white/10 text-oat'
                      : 'border-t-transparent text-oat/70',
                  )
                }
              >
                <Icon aria-hidden="true" className="size-5" />
                <span className="truncate">{item.label}</span>
              </NavLink>
            </li>
          )
        })}
      </ul>
    </nav>
  )
}
