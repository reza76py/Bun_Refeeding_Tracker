// Shared API types — kept in one place so the frontend and the DRF responses
// stay in step (brief: "Use a shared TypeScript API type definition ... to
// prevent drift").

export interface User {
  id: number;
  username: string;
  first_name: string;
  last_name: string;
}

export type Provenance = "assumed" | "user_estimate" | "measured";

export type CageStatus =
  | "planned"
  | "in_progress"
  | "complete"
  | "partial"
  | "blocked";

export interface AssumptionSet {
  id: number;
  version: number;
  effective_at: string;
  cages_min: number;
  cages_max: number;
  default_lines_per_cage: number;
  units_per_line: number;
  find_sec: number;
  unpack_sec: number;
  seconds_per_unit: number;
  other_sec: number;
  provenance: Provenance;
  notes: string;
}

export interface Bay {
  id: number;
  aisle: number;
  bay_number: number;
  estimated_catalogue_lines: number;
  seconds_per_line: number | null;
  estimated_seconds: number | null; // lines x seconds_per_line
}

export interface AisleCage {
  id: number;
  aisle: number;
  code: string; // e.g. "A10"
  lines: number;
  seconds_per_line: number | null;
  minutes: number | null; // quick entry; when set, it is the cage's time
  estimated_seconds: number | null; // lines x seconds_per_line
}

export type AisleDetailMode = "cages" | "bays";

export interface Aisle {
  id: number;
  store: number;
  label: string;
  active: boolean;
  aisle_total_lines: number;
  detail_mode: AisleDetailMode;
  cages: AisleCage[];
  bays: Bay[];
  catalogue_lines: number;
  estimated_seconds: number | null;
  rows_missing_time: number;
}

export interface Store {
  id: number;
  name: string;
  timezone: string;
}

export interface CageLog {
  id: number;
  work_day: number;
  aisle: number | null;
  reference: string;
  line_count: number | null;
  units_per_line: number | null;
  estimated_seconds: number; // forecast snapshot
  estimated_hm: string;
  actual_active_seconds: number | null; // measured actual
  actual_active_hm: string | null;
  status: CageStatus;
  completed_line_count: number | null;
  notes: string;
}

export interface WorkDay {
  id: number;
  store: number;
  work_date: string;
  assumption_set: number;
  assumption_snapshot: Record<string, number>;
  shift_minutes: number | null;
  interrupted_minutes: number | null;
  notes: string;
  cages: CageLog[];
  estimated_day_seconds: number;
  measured_active_seconds: number | null;
  created_at: string;
}

export interface ScenarioRow {
  cages: number;
  line_operations: number;
  units_handled: number;
  day_seconds: number;
}

export interface DashboardWorkDay {
  id: number;
  cage_count: number;
  estimated_seconds: number;
  estimated_hm: string;
  measured_active_seconds: number | null;
  measured_active_hm: string | null;
  interrupted_minutes: number | null;
  shift_minutes: number | null;
  forecast_vs_actual_seconds: number | null;
  workload_gap_seconds: number | null;
  shift_minutes_note: string;
}

export interface DashboardSummary {
  date: string;
  active_assumptions: AssumptionSet;
  scenarios: ScenarioRow[];
  work_day: DashboardWorkDay | null;
}

export interface ReportRow {
  work_date: string;
  estimated_seconds: number;
  measured_active_seconds: number | null;
  interrupted_minutes: number | null;
  variance_seconds: number | null;
}

export interface ReportsSummary {
  from: string;
  to: string;
  day_count: number;
  total_estimated_seconds: number;
  total_estimated_hm: string;
  total_measured_active_seconds: number;
  total_measured_active_hm: string;
  complete_cage_count: number;
  avg_net_seconds_per_measured_cage: number | null;
  avg_measured_seconds_per_line: number | null;
  total_interrupted_minutes: number;
  rows: ReportRow[];
}

export interface CatalogueSummary {
  per_aisle: {
    aisle_id: number;
    label: string;
    catalogue_lines: number;
    estimated_seconds: number | null;
  }[];
  combined_catalogue_lines: number;
  combined_estimated_seconds: number | null;
  note: string;
}
