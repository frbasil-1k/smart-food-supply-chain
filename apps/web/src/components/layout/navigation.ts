import {
  Activity,
  Archive,
  BadgeCheck,
  Building2,
  ClipboardCheck,
  ClipboardList,
  Clock3,
  FileBarChart,
  LayoutDashboard,
  Map,
  PackageCheck,
  PackageX,
  Route,
  ShieldAlert,
  Truck,
  UserRound,
  Users,
  type LucideIcon,
} from 'lucide-react'

import type { Role } from '@/lib/types'

export type NavigationItem = {
  to: string
  label: string
  title: string
  icon: LucideIcon
  end?: boolean
}

const SYSTEM_ITEM: NavigationItem = {
  to: '/system',
  label: 'System',
  title: 'System status',
  icon: Activity,
}

export const NAVIGATION: NavigationItem[] = [
  { to: '/', label: 'Overview', title: 'Overview', icon: LayoutDashboard, end: true },
  { to: '/donations', label: 'Donations', title: 'Donations', icon: PackageCheck },
  { to: '/impact', label: 'Impact', title: 'Donor impact', icon: FileBarChart },
  { to: '/freshness', label: 'Freshness', title: 'Freshness watch', icon: Clock3 },
  { to: '/activity', label: 'Activity', title: 'Activity', icon: Clock3 },
  SYSTEM_ITEM,
]

const ROLE_NAVIGATION: Record<Role, NavigationItem[]> = {
  DONOR: NAVIGATION,
  NGO_MANAGER: [
    { to: '/', label: 'Overview', title: 'Overview', icon: LayoutDashboard, end: true },
    { to: '/donations', label: 'Donations', title: 'Donations', icon: ClipboardList },
    { to: '/inspections', label: 'Inspections', title: 'Inspections', icon: ClipboardCheck },
    { to: '/deliveries', label: 'Deliveries', title: 'Deliveries', icon: Truck },
    { to: '/allocation', label: 'Allocation', title: 'Allocation', icon: PackageCheck },
    { to: '/spoilage', label: 'Spoilage', title: 'Spoilage', icon: PackageX },
    { to: '/reports', label: 'Reports', title: 'Reports', icon: FileBarChart },
    { to: '/branches', label: 'Branches', title: 'Branches', icon: Building2 },
    { to: '/routes', label: 'Routes', title: 'Routes', icon: Map },
    { to: '/users', label: 'People', title: 'People', icon: Users },
    { to: '/freshness', label: 'Freshness', title: 'Freshness watch', icon: ShieldAlert },
    { to: '/activity', label: 'Activity', title: 'Activity', icon: Clock3 },
    SYSTEM_ITEM,
  ],
  DRIVER: [
    { to: '/', label: 'Today', title: 'Today', icon: LayoutDashboard, end: true },
    { to: '/deliveries', label: 'Deliveries', title: 'Deliveries', icon: Truck },
    { to: '/spoilage', label: 'Spoilage', title: 'Spoilage', icon: PackageX },
    { to: '/route', label: 'My route', title: 'My route', icon: Route },
    { to: '/history', label: 'History', title: 'Delivery history', icon: Archive },
    { to: '/dependents', label: 'Dependents', title: 'Dependents', icon: UserRound },
    SYSTEM_ITEM,
  ],
  SAFETY_INSPECTOR: [
    { to: '/', label: 'Overview', title: 'Overview', icon: LayoutDashboard, end: true },
    { to: '/inspections', label: 'Queue', title: 'Inspection queue', icon: ClipboardCheck },
    { to: '/freshness', label: 'Freshness', title: 'Freshness watch', icon: ShieldAlert },
    { to: '/activity', label: 'Activity', title: 'Activity', icon: Clock3 },
    SYSTEM_ITEM,
  ],
}

export function navigationForRole(role: Role | null): NavigationItem[] {
  return role ? ROLE_NAVIGATION[role] : NAVIGATION
}

export function titleForPath(pathname: string, role: Role | null = null): string {
  const exact = navigationForRole(role).find((item) => item.to === pathname)
  if (exact) return exact.title
  if (/^\/donations\/new$/.test(pathname)) return 'New donation'
  if (/^\/donations\/\d+$/.test(pathname)) return 'Donation detail'
  if (/^\/deliveries\/\d+$/.test(pathname)) return 'Delivery detail'
  if (/^\/inspections\/\d+$/.test(pathname)) return 'Inspection detail'
  if (pathname.startsWith('/print/')) return 'Report print view'
  return 'Not found'
}

export const ROLE_LABELS: Record<Role, string> = {
  DONOR: 'Donor',
  NGO_MANAGER: 'NGO manager',
  DRIVER: 'Driver',
  SAFETY_INSPECTOR: 'Safety inspector',
}

export const STATUS_ICONS = {
  donation: BadgeCheck,
  delivery: Truck,
  inspection: ClipboardCheck,
  route: Route,
} as const
