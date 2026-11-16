import { lazy, type ComponentType } from 'react'

/** Create a lazy route component from a module with named page exports. */
export function lazyPage(
  loader: () => Promise<Record<string, ComponentType>>,
  name: string,
) {
  return lazy(async () => {
    const module = await loader()
    return { default: module[name]! }
  })
}

export const RoleHomePage = lazyPage(
  () => import('@/features/overview/RoleHomePage'),
  'RoleHomePage',
)
export const DonationsPage = lazyPage(
  () => import('@/features/donations/DonationsPage'),
  'DonationsPage',
)
export const DonationCreatePage = lazyPage(
  () => import('@/features/donations/DonationCreatePage'),
  'DonationCreatePage',
)
export const DonationDetailPage = lazyPage(
  () => import('@/features/donations/DonationDetailPage'),
  'DonationDetailPage',
)
export const InspectionsPage = lazyPage(
  () => import('@/features/inspections/InspectionsPage'),
  'InspectionsPage',
)
export const DeliveriesPage = lazyPage(
  () => import('@/features/deliveries/DeliveriesPage'),
  'DeliveriesPage',
)
export const DeliveryDetailPage = lazyPage(
  () => import('@/features/deliveries/DeliveryDetailPage'),
  'DeliveryDetailPage',
)
export const AllocationPage = lazyPage(
  () => import('@/features/deliveries/AllocationPage'),
  'AllocationPage',
)
export const SpoilagePage = lazyPage(
  () => import('@/features/deliveries/SpoilagePage'),
  'SpoilagePage',
)
export const ReportsPage = lazyPage(
  () => import('@/features/reports/ReportsPage'),
  'ReportsPage',
)
export const ImpactPage = lazyPage(
  () => import('@/features/reports/ImpactPage'),
  'ImpactPage',
)
export const FreshnessPage = lazyPage(
  () => import('@/features/reports/FreshnessPage'),
  'FreshnessPage',
)
export const ActivityPage = lazyPage(
  () => import('@/features/reports/ActivityPage'),
  'ActivityPage',
)
export const BranchesPage = lazyPage(
  () => import('@/features/operations/BranchesPage'),
  'BranchesPage',
)
export const RoutesPage = lazyPage(
  () => import('@/features/operations/RoutesPage'),
  'RoutesPage',
)
export const UsersPage = lazyPage(
  () => import('@/features/operations/UsersPage'),
  'UsersPage',
)
export const DependentsPage = lazyPage(
  () => import('@/features/operations/DependentsPage'),
  'DependentsPage',
)
export const DriverRoutePage = lazyPage(
  () => import('@/features/operations/DriverRoutePage'),
  'DriverRoutePage',
)
export const DriverHistoryPage = lazyPage(
  () => import('@/features/operations/DriverHistoryPage'),
  'DriverHistoryPage',
)
