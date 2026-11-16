export type Role = 'DONOR' | 'NGO_MANAGER' | 'DRIVER' | 'SAFETY_INSPECTOR'

export type AccountStatus = 'ACTIVE' | 'INACTIVE' | 'SUSPENDED'

export type User = {
  user_id: number
  full_name: string
  email: string
  phone: string
  role: Role
  account_status: AccountStatus
  primary_branch_id: number | null
  branch_name: string | null
  primary_branch: { branch_id: number; branch_name: string } | null
  supervisor_user_id: number | null
  must_change_password?: boolean
  last_login_at?: string | null
}

export type BranchRef = { branch_id: number; branch_name: string | null }

export type DonationStatus =
  | 'PENDING'
  | 'SCHEDULED'
  | 'COLLECTED'
  | 'APPROVED'
  | 'REJECTED'
  | 'PARTIALLY_DISTRIBUTED'
  | 'COMPLETED'
  | 'CANCELLED'

export type DonationItem = {
  food_item_id: number
  donation_id: number
  category: { category_id: number; category_name: string } | null
  item_name: string
  prepared_at: string | null
  best_before: string
  quantity_kg: string
  allocated_kg: string
  delivered_kg: string
  spoiled_kg: string
  available_kg: string
}

export type RouteRef = {
  route_id: number
  managing_branch_id: number
  designated_driver_user_id: number
  route_type?: string
  managing_branch?: BranchRef
  designated_driver?: { user_id: number; full_name: string }
  coverage_area?: { coverage_area_id: number; area_name: string; city: string }
  route_status?: string
}

export type DonationSummary = {
  donation_id: number
  donor: { user_id: number; full_name: string | null }
  pickup_route: RouteRef | null
  pickup_datetime: string
  pickup_address: string | null
  pickup_pincode: string | null
  pickup_contact: string | null
  status: DonationStatus
  urgency: 'LOW' | 'NORMAL' | 'HIGH'
  item_count: number
  total_quantity_kg: string
}

export type DonationDetail = DonationSummary & {
  items: DonationItem[]
  latest_inspection: Inspection | null
  deliveries: Delivery[]
  history: HistoryRow[]
}

export type Inspection = {
  inspection_id: number
  donation_id: number
  inspector: { user_id: number; full_name: string | null }
  inspected_at: string
  temperature_c: string | null
  packaging_integrity: string
  safety_status: 'PASSED' | 'FAILED' | 'NEEDS_REVIEW'
  remarks: string | null
}

export type Delivery = {
  delivery_id: number
  donation: {
    donation_id: number
    status: DonationStatus | null
    donor: { user_id: number; full_name: string | null } | null
  }
  route: { route_id: number; route_type: string | null; managing_branch_id: number | null }
  driver: { user_id: number; full_name: string } | null
  recipient_branch: BranchRef
  scheduled_for: string | null
  delivered_at: string | null
  status: 'PLANNED' | 'IN_TRANSIT' | 'DELIVERED' | 'FAILED' | 'CANCELLED'
  items?: DeliveryItem[]
  review?: Review | null
}

export type DeliveryItem = {
  delivery_item_id: number
  food_item_id: number
  item_name: string | null
  quantity_delivered_kg: string
}

export type Review = {
  review_id: number
  delivery_id: number
  reviewed_by: { user_id: number; full_name: string | null }
  rating: number
  quality_notes: string | null
  review_date: string | null
}

export type HistoryRow = {
  history_id: number
  donation_id: number
  from_status: DonationStatus | null
  to_status: DonationStatus
  changed_by: { user_id: number; full_name: string } | null
  changed_at: string | null
  is_reconstructed: boolean
  note: string | null
}

export type BackendBranch = {
  branch_id: number
  branch_name: string
  organization: { organization_id: number; organization_name: string | null }
  address: string
  pincode: string
  contact_no: string
  established_date: string
  regional_manager: { user_id: number; full_name: string | null } | null
}

export type Paged<T> = {
  data: T[]
  meta: { pagination?: { page: number; page_size: number; total: number; pages: number } }
}

export type Overview = Record<string, unknown>

export type ActivityEvent = {
  event_type: string
  timestamp: string | null
  donation_id: number
  description: string
  actor: string | null
}

export type DonorReport = {
  donor_id: number
  donor_name: string
  email?: string | null
  total_donations: number
  total_donated_kg: string
  delivered_kg: string
  spoiled_kg: string
  undistributed_balance_kg: string
  balance_kg?: string
  items?: { donation_id: number; donation_status: string; pickup_datetime: string; food_item: DonationItem }[]
}

export type DriverReport = {
  driver_id: number
  driver_name: string
  assigned_routes: number
  completed_deliveries: number
  delivered_quantity_kg: string
}

export type BranchReport = {
  branch_id: number
  branch_name: string
  total_donations: number
  total_donated_kg: string
  delivered_kg: string
  spoiled_kg: string
  balance_kg: string
  avg_rating: string
}

export type FreshnessItem = {
  food_item_id: number
  donation_id: number
  item_name: string
  category: string | null
  quantity_kg: string
  best_before: string
  hours_remaining: string
  is_expired: boolean
  open_allocated_kg: string
}
