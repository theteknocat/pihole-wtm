export interface TopDomain {
  domain: string
  query_count: number
}

export interface CompanyStat {
  company_name: string
  query_count: number
  blocked_count: number
  allowed_count: number
  top_domains: TopDomain[]
}

export interface CategoryStat {
  category: string
  query_count: number
  blocked_count: number
  allowed_count: number
  companies: CompanyStat[]
}

export interface TrackerStats {
  window_hours: number
  total_queries: number
  tracker_queries: number
  tracker_percent: number
  truncated: boolean
  by_category: CategoryStat[]
}

export interface DomainStat {
  domain: string
  category: string
  company_name: string
  tracker_name: string | null
  query_count: number
  blocked_count: number
  allowed_count: number
  block_rate: number
  can_reenrich: boolean
  rdap_pending: boolean
}

export interface DomainStats {
  window_hours: number
  filter_category: string | null
  filter_company: string | null
  domains: DomainStat[]
}

export interface ClientStat {
  client_ip: string
  client_name: string | null
  query_count: number
  blocked_count: number
  allowed_count: number
  block_rate: number
}

export interface ClientStats {
  window_hours: number
  clients: ClientStat[]
}

export interface TimelineBucket {
  timestamp: number
  total: number
  blocked: number
  allowed: number
}

export interface TimelineStats {
  window_hours: number
  bucket_seconds: number
  buckets: TimelineBucket[]
}

export interface ClientTimelineBucket {
  timestamp: number
  count: number
}

export interface ClientTimelineEntry {
  client_ip: string
  client_name: string | null
  total: number
  buckets: ClientTimelineBucket[]
}

export interface ClientTimelineStats {
  window_hours: number
  bucket_seconds: number
  clients: ClientTimelineEntry[]
}

export interface EnrichedQuery {
  id: number
  timestamp: number
  domain: string
  client: string
  client_name: string | null
  status: string
  status_label: string
  query_type: string
  reply_type: string | null
  reply_time: number | null
  tracker_name: string | null
  category: string | null
  company_name: string | null
  company_country: string | null
}

export interface GroupedQuery {
  domain: string
  timestamp: number
  query_count: number
  company_name: string | null
  tracker_name: string | null
  category: string | null
  company_country: string | null
}
