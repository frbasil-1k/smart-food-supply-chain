import { Suspense } from 'react'
import { Route, Routes } from 'react-router-dom'

import { RequireAuth, RequireRole } from '@/app/guards'
import {
  ActivityPage,
  AllocationPage,
  BranchesPage,
  DeliveriesPage,
  DeliveryDetailPage,
  DependentsPage,
  DonationCreatePage,
  DonationDetailPage,
  DonationsPage,
  DriverHistoryPage,
  DriverRoutePage,
  FreshnessPage,
  ImpactPage,
  InspectionsPage,
  ReportsPage,
  RoleHomePage,
  RoutesPage,
  SpoilagePage,
  UsersPage,
} from '@/app/pages'
import { AppShell } from '@/components/layout/AppShell'
import { ActivatePage } from '@/features/auth/ActivatePage'
import { LoginPage } from '@/features/auth/LoginPage'
import { PrintReportPage } from '@/features/reports/PrintReportPage'
import { SystemPage } from '@/features/system/SystemPage'
import { NotFoundPage } from '@/pages/NotFoundPage'

export function AppRoutes() {
  return (
    <Suspense
      fallback={
        <div role="status" className="flex min-h-svh items-center justify-center bg-oat px-6 text-sm text-ink-soft">
          Loading workspace…
        </div>
      }
    >
      <Routes>
      <Route path="login" element={<LoginPage />} />
      <Route path="activate" element={<ActivatePage />} />

      <Route element={<RequireAuth />}>
        <Route path="print/reports/:kind" element={<PrintReportPage />} />
        <Route element={<AppShell />}>
          <Route index element={<RoleHomePage />} />
          <Route path="system" element={<SystemPage />} />

          <Route element={<RequireRole roles={['DONOR', 'NGO_MANAGER']} />}>
            <Route path="donations" element={<DonationsPage />} />
          </Route>
          <Route element={<RequireRole roles={['DONOR']} />}>
            <Route path="donations/new" element={<DonationCreatePage />} />
            <Route path="impact" element={<ImpactPage />} />
          </Route>
          <Route path="donations/:id" element={<DonationDetailPage />} />

          <Route element={<RequireRole roles={['NGO_MANAGER', 'SAFETY_INSPECTOR']} />}>
            <Route path="inspections" element={<InspectionsPage />} />
          </Route>

          <Route element={<RequireRole roles={['DONOR', 'NGO_MANAGER', 'DRIVER']} />}>
            <Route path="deliveries" element={<DeliveriesPage />} />
            <Route path="deliveries/:id" element={<DeliveryDetailPage />} />
          </Route>
          <Route element={<RequireRole roles={['NGO_MANAGER']} />}>
            <Route path="allocation" element={<AllocationPage />} />
            <Route path="reports" element={<ReportsPage />} />
            <Route path="branches" element={<BranchesPage />} />
            <Route path="routes" element={<RoutesPage />} />
            <Route path="users" element={<UsersPage />} />
          </Route>
          <Route element={<RequireRole roles={['NGO_MANAGER', 'DRIVER']} />}>
            <Route path="spoilage" element={<SpoilagePage />} />
          </Route>
          <Route element={<RequireRole roles={['DRIVER']} />}>
            <Route path="route" element={<DriverRoutePage />} />
            <Route path="history" element={<DriverHistoryPage />} />
            <Route path="dependents" element={<DependentsPage />} />
          </Route>

          <Route element={<RequireRole roles={['DONOR', 'NGO_MANAGER', 'SAFETY_INSPECTOR']} />}>
            <Route path="freshness" element={<FreshnessPage />} />
          </Route>
          <Route path="activity" element={<ActivityPage />} />

          <Route path="*" element={<NotFoundPage />} />
        </Route>
      </Route>
      </Routes>
    </Suspense>
  )
}
