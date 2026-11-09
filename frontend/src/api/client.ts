// Fetch-based API client with Django session auth + CSRF.
//
// Flow: call ensureCsrf() once (sets the csrftoken cookie), then every unsafe
// request echoes that token in the X-CSRFToken header. Cookies are sent with
// credentials: "include". The session cookie stays HttpOnly; only the CSRF
// cookie is read here.

import type {
  Aisle,
  AisleCage,
  AisleDetailMode,
  AssumptionSet,
  Bay,
  CatalogueSummary,
  CageLog,
  DashboardSummary,
  ReportsSummary,
  Store,
  User,
  WorkDay,
  FeedSummary,
  ClockSession,
  ClockSummary,
} from "./types";

const BASE = "/api";

export class ApiError extends Error {
  status: number;
  detail: unknown;
  constructor(status: number, detail: unknown) {
    super(typeof detail === "string" ? detail : `Request failed (${status})`);
    this.status = status;
    this.detail = detail;
  }
}

function getCookie(name: string): string | null {
  const match = document.cookie.match(
    new RegExp("(^|;\\s*)" + name + "=([^;]*)")
  );
  return match ? decodeURIComponent(match[2]) : null;
}

async function request<T>(
  method: string,
  path: string,
  body?: unknown
): Promise<T> {
  const headers: Record<string, string> = {};
  const unsafe = !["GET", "HEAD", "OPTIONS"].includes(method.toUpperCase());
  if (unsafe) {
    const token = getCookie("csrftoken");
    if (token) headers["X-CSRFToken"] = token;
  }
  if (body !== undefined) headers["Content-Type"] = "application/json";

  const resp = await fetch(BASE + path, {
    method,
    credentials: "include",
    headers,
    body: body !== undefined ? JSON.stringify(body) : undefined,
  });

  if (resp.status === 204) return undefined as T;

  let data: unknown = null;
  const text = await resp.text();
  if (text) {
    try {
      data = JSON.parse(text);
    } catch {
      data = text;
    }
  }
  if (!resp.ok) {
    const detail =
      data && typeof data === "object" && "detail" in data
        ? (data as { detail: unknown }).detail
        : data;
    throw new ApiError(resp.status, detail);
  }
  return data as T;
}

let csrfReady = false;
export async function ensureCsrf(): Promise<void> {
  if (csrfReady) return;
  await request("GET", "/auth/csrf/");
  csrfReady = true;
}

export const api = {
  // Auth
  async login(username: string, password: string): Promise<User> {
    await ensureCsrf();
    return request<User>("POST", "/auth/login/", { username, password });
  },
  logout: () => request<void>("POST", "/auth/logout/"),
  me: () => request<User>("GET", "/auth/me/"),

  // Stores
  stores: () => request<Store[]>("GET", "/stores/"),
  updateStore: (id: number, body: Partial<Store>) =>
    request<Store>("PATCH", `/stores/${id}/`, body),

  // Aisles & bays
  aisles: () => request<Aisle[]>("GET", "/aisles/"),
  createAisle: (label: string, detailMode: AisleDetailMode = "cages") =>
    request<Aisle>("POST", "/aisles/", { label, detail_mode: detailMode }),
  updateAisle: (
    id: number,
    body: {
      label?: string;
      active?: boolean;
      aisle_total_lines?: number;
      detail_mode?: AisleDetailMode;
    }
  ) =>
    request<Aisle>("PATCH", `/aisles/${id}/`, body),
  deleteAisle: (id: number) => request<void>("DELETE", `/aisles/${id}/`),
  /** Removes ALL of the user's aisles, with their cages and bays. */
  deleteAllAisles: () =>
    request<{ deleted_aisles: number }>("DELETE", "/aisles/"),
  createBay: (
    aisleId: number,
    body: {
      bay_number: number;
      estimated_catalogue_lines: number;
      seconds_per_line?: number | null;
    }
  ) => request<Bay>("POST", `/aisles/${aisleId}/bays/`, body),
  updateBay: (
    id: number,
    body: { estimated_catalogue_lines?: number; seconds_per_line?: number | null }
  ) =>
    request<unknown>("PATCH", `/bays/${id}/`, body),
  deleteBay: (id: number) => request<void>("DELETE", `/bays/${id}/`),
  createAisleCage: (
    aisleId: number,
    body: {
      code: string;
      lines?: number;
      seconds_per_line?: number | null;
      minutes?: number | null;
    }
  ) =>
    request<AisleCage>("POST", `/aisles/${aisleId}/cages/`, body),
  updateAisleCage: (
    id: number,
    body: {
      code?: string;
      lines?: number;
      seconds_per_line?: number | null;
      minutes?: number | null;
    }
  ) =>
    request<AisleCage>("PATCH", `/aisle-cages/${id}/`, body),
  deleteAisleCage: (id: number) =>
    request<void>("DELETE", `/aisle-cages/${id}/`),
  catalogue: () => request<CatalogueSummary>("GET", "/catalogue/summary/"),

  // Today: how much (0-100 %) of each cage was fed on a date.
  feedSummary: (date: string) =>
    request<FeedSummary>("GET", `/feed/summary/?date=${date}`),
  setFeed: (body: { date: string; cage_id: number; percent: number }) =>
    request<{ cage_id: number; date: string; percent: number }>(
      "PUT",
      "/feed/",
      body
    ),

  // Clock: real start / end sessions per cage (kept as history).
  clockSummary: () => request<ClockSummary>("GET", "/clock/summary/"),
  clockStart: (cageId: number) =>
    request<ClockSession>("POST", "/clock/start", { cage_id: cageId }),
  clockEnd: (cageId: number) =>
    request<ClockSession>("POST", "/clock/end", { cage_id: cageId }),
  /** Record a finished session by hand (local Brisbane "YYYY-MM-DDTHH:MM"). */
  clockManual: (cageId: number, startAt: string, endAt: string) =>
    request<ClockSession>("POST", "/clock/manual", {
      cage_id: cageId,
      start_at: startAt,
      end_at: endAt,
    }),
  clockCancel: (cageId: number) =>
    request<{ cancelled: boolean }>("POST", "/clock/cancel", { cage_id: cageId }),

  // Assumptions
  assumptions: () => request<AssumptionSet[]>("GET", "/assumptions/"),
  activeAssumptions: () => request<AssumptionSet>("GET", "/assumptions/active/"),
  createAssumptions: (body: Partial<AssumptionSet>) =>
    request<AssumptionSet>("POST", "/assumptions/", body),

  // Work days & cages
  workDays: (from?: string, to?: string) => {
    const q = new URLSearchParams();
    if (from) q.set("from", from);
    if (to) q.set("to", to);
    const qs = q.toString();
    return request<WorkDay[]>("GET", `/workdays/${qs ? "?" + qs : ""}`);
  },
  createWorkDay: (body: {
    work_date: string;
    shift_minutes?: number | null;
    interrupted_minutes?: number | null;
    notes?: string;
    cages?: Partial<CageLog>[];
  }) => request<WorkDay>("POST", "/workdays/", body),
  workDay: (id: number) => request<WorkDay>("GET", `/workdays/${id}/`),
  updateWorkDay: (id: number, body: Partial<WorkDay>) =>
    request<WorkDay>("PATCH", `/workdays/${id}/`, body),
  addCage: (workDayId: number, body: Partial<CageLog>) =>
    request<CageLog>("POST", `/workdays/${workDayId}/cages/`, body),
  updateCage: (id: number, body: Partial<CageLog>) =>
    request<CageLog>("PATCH", `/cages/${id}/`, body),
  deleteCage: (id: number) => request<void>("DELETE", `/cages/${id}/`),

  // Dashboard & reports
  dashboard: (date?: string) =>
    request<DashboardSummary>(
      "GET",
      `/dashboard/summary/${date ? "?date=" + date : ""}`
    ),
  reports: (from: string, to: string) =>
    request<ReportsSummary>("GET", `/reports/summary/?from=${from}&to=${to}`),
};

/** Download link for every Clock session as CSV (the training dataset). */
export const clockExportUrl = `${BASE}/clock/export.csv`;
