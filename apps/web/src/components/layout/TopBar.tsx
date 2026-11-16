import { useState } from 'react'
import { Link, NavLink, useLocation } from 'react-router-dom'
import { LogOut, Menu, X } from 'lucide-react'
import { cn } from 'cn'

import { BrandMark } from '@/components/BrandMark'
import { Button } from '@/components/ui/button'
import { PRODUCT_NAME } from '@/lib/brand'
import { useAuth } from '@/features/auth/AuthProvider'
import { ROLE_LABELS, navigationForRole, titleForPath } from './navigation'

export function MobileHeader() {
  const { user, logout } = useAuth()
  const { pathname } = useLocation()
  const [open, setOpen] = useState(false)
  const items = navigationForRole(user?.role ?? null)

  return (
    <>
      <header className="flex min-h-14 items-center justify-between gap-3 border-b border-oat/15 bg-forest px-4 py-2 text-oat md:hidden">
        <Link
          to="/"
          className="flex min-w-0 items-center gap-3 rounded-[4px] focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-oat"
        >
          <BrandMark className="size-7 shrink-0 text-oat" />
          <span className="text-[11px] leading-4 font-medium">{PRODUCT_NAME}</span>
        </Link>
        <div className="flex shrink-0 items-center gap-2">
          <span className="max-w-[7rem] truncate text-[11px] leading-4 text-oat/75">
            {user?.full_name}
          </span>
          <button
            type="button"
            aria-expanded={open}
            aria-controls="mobile-menu"
            aria-label={open ? 'Close menu' : 'Open menu'}
            onClick={() => setOpen((value) => !value)}
            className="inline-flex size-9 items-center justify-center rounded-[4px] text-oat hover:bg-white/10 focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-oat"
          >
            {open ? <X aria-hidden="true" className="size-5" /> : <Menu aria-hidden="true" className="size-5" />}
          </button>
        </div>
      </header>
      {open ? (
        <div
          id="mobile-menu"
          className="fixed inset-x-0 top-14 bottom-0 z-40 overflow-y-auto border-t border-oat/15 bg-forest px-4 pt-4 pb-8 text-oat md:hidden"
        >
          <p className="text-[10px] tracking-[0.12em] text-oat/75 uppercase">
            {titleForPath(pathname, user?.role ?? null)}
          </p>
          <p className="mt-1 text-sm font-semibold">{user?.full_name}</p>
          <p className="text-[10px] tracking-[0.08em] text-oat/75 uppercase">
            {user ? ROLE_LABELS[user.role] : ''}
          </p>
          <nav aria-label="Mobile menu" className="mt-5">
            <ul className="space-y-1">
              {items.map((item) => {
                const Icon = item.icon
                return (
                  <li key={item.to}>
                    <NavLink
                      to={item.to}
                      end={item.end}
                      onClick={() => setOpen(false)}
                      className={({ isActive }) =>
                        cn(
                          'flex min-h-12 items-center gap-3 rounded-[4px] border-l-[3px] px-3 text-sm font-medium',
                          isActive
                            ? 'border-l-terracotta bg-white/10 text-oat'
                            : 'border-l-transparent text-oat/75 hover:bg-white/5 hover:text-oat',
                        )
                      }
                    >
                      <Icon aria-hidden="true" className="size-5" />
                      {item.label}
                    </NavLink>
                  </li>
                )
              })}
            </ul>
          </nav>
          <Button
            type="button"
            variant="outline"
            onClick={() => {
              setOpen(false)
              void logout()
            }}
            className="mt-6 h-10 border-oat/30 bg-transparent px-4 text-oat hover:bg-white/10 hover:text-oat"
          >
            <LogOut aria-hidden="true" className="size-4" />
            Sign out
          </Button>
        </div>
      ) : null}
    </>
  )
}

export function TopBar() {
  const { pathname } = useLocation()
  const { user, logout } = useAuth()

  return (
    <header className="sticky top-0 z-20 hidden h-16 items-center justify-between gap-4 border-b border-oat/15 bg-forest px-6 py-2 text-oat md:flex">
      <div className="min-w-0">
        <p className="truncate text-[10px] leading-3 tracking-[0.12em] text-oat/75 uppercase">
          {PRODUCT_NAME}
        </p>
        <p className="mt-1 font-heading text-[15px] leading-5 font-medium">
          Workspace
          <span aria-hidden="true" className="px-1.5 text-oat/40">
            /
          </span>
          {titleForPath(pathname, user?.role ?? null)}
        </p>
      </div>
      <div className="flex shrink-0 items-center gap-3">
        <div className="hidden text-right lg:block">
          <p className="text-xs font-semibold text-oat">{user?.full_name}</p>
          <p className="text-[10px] tracking-[0.08em] text-oat/75 uppercase">
            {user ? ROLE_LABELS[user.role] : ''}
          </p>
        </div>
        <Button
          type="button"
          variant="ghost"
          size="sm"
          onClick={() => void logout()}
          className="text-oat hover:bg-white/10 hover:text-oat"
        >
          <LogOut aria-hidden="true" className="size-4" />
          Sign out
        </Button>
      </div>
    </header>
  )
}
