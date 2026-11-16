import { Outlet } from 'react-router-dom'

import { BottomNav } from './BottomNav'
import { MobileHeader, TopBar } from './TopBar'
import { RailNav } from './RailNav'

export function AppShell() {
  return (
    <div className="min-h-svh bg-oat">
      <a
        href="#main"
        className="sr-only focus:not-sr-only focus:fixed focus:top-4 focus:left-4 focus:z-50 focus:rounded-[4px] focus:bg-forest focus:px-4 focus:py-2 focus:text-sm focus:font-semibold focus:text-oat"
      >
        Skip to content
      </a>

      <div className="md:grid md:min-h-svh md:grid-cols-[64px_minmax(0,1fr)] xl:grid-cols-[240px_minmax(0,1fr)]">
        <RailNav />
        <div className="flex min-h-svh min-w-0 flex-col">
          <MobileHeader />
          <TopBar />
          <main
            id="main"
            tabIndex={-1}
            className="flex-1 px-4 py-6 pb-28 sm:px-6 sm:py-8 md:pb-10 lg:px-8 lg:py-10"
          >
            <div className="mx-auto w-full max-w-[1440px]">
              <Outlet />
            </div>
          </main>
          <BottomNav />
        </div>
      </div>
    </div>
  )
}
