const API_BASE = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000/api";
const TOKEN_KEY = "auth_token";

export interface SignupPayload {
  organization_name: string;
  organization_type: "constructora" | "proveedor";
  tax_id?: string;
  full_name: string;
  email: string;
  password: string;
}

export interface LoginPayload {
  email: string;
  password: string;
}

export interface TokenResponse {
  access_token: string;
  token_type: string;
}

export interface Organization {
  id: number;
  name: string;
  type: "constructora" | "proveedor";
  tax_id?: string;
  created_at: string;
}

export interface User {
  id: number;
  email: string;
  full_name: string;
  role: "admin" | "gestor" | "lector";
  organization_id: number;
  created_at: string;
  organization?: Organization;
}

async function fetchAPI<T>(
  path: string,
  options: RequestInit = {},
): Promise<T> {
  const headers = new Headers({
    "Content-Type": "application/json",
    ...(typeof options.headers === "object" && options.headers),
  });

  const token = getToken();
  if (token) {
    headers.set("Authorization", `Bearer ${token}`);
  }

  const response = await fetch(`${API_BASE}${path}`, {
    ...options,
    headers,
  });

  if (!response.ok) {
    const error = await response.json().catch(() => ({}));
    throw new Error(error.detail || `API error: ${response.status}`);
  }

  return response.json();
}

export function getToken(): string | null {
  if (typeof window === "undefined") return null;
  return localStorage.getItem(TOKEN_KEY);
}

export function setToken(token: string): void {
  localStorage.setItem(TOKEN_KEY, token);
  if (typeof document !== "undefined") {
    document.cookie = `auth_token=${token}; path=/; max-age=${60 * 60 * 24 * 7}`;
  }
}

export function clearToken(): void {
  localStorage.removeItem(TOKEN_KEY);
  if (typeof document !== "undefined") {
    document.cookie = "auth_token=; path=/; max-age=0";
  }
}

export async function signup(payload: SignupPayload): Promise<User> {
  const data = await fetchAPI<User>("/users/signup", {
    method: "POST",
    body: JSON.stringify(payload),
  });
  return data;
}

export async function login(payload: LoginPayload): Promise<string> {
  const data = await fetchAPI<TokenResponse>("/users/login", {
    method: "POST",
    body: JSON.stringify(payload),
  });
  return data.access_token;
}

export async function getMe(): Promise<User> {
  return fetchAPI<User>("/users/me");
}

export interface OfferCriteria {
  compatibilidad: number;
  disponibilidad: number;
  precio: number;
  unidad_compatible: boolean;
  stock_suficiente: boolean;
  vs_presupuesto?: number;
}

export interface ProviderOffer {
  match_id: number;
  provider_org_id: number;
  provider_name: string;
  material_name: string;
  unit: string;
  unit_price: number | null;
  quantity_available: number;
  subtotal: number | null;
  score: number;
  criteria: OfferCriteria;
  is_cheapest: boolean;
  is_best: boolean;
}

export interface ItemComparison {
  item_id: number;
  material_name: string;
  quantity: number;
  unit: string;
  budget_unit_price: number | null;
  offers: ProviderOffer[];
}

export interface ProviderRanking {
  provider_org_id: number;
  provider_name: string;
  score: number;
  coverage: number;
  items_covered: number;
  items_full_stock: number;
  cheapest_items: number;
  unit_mismatches: number;
  total_cost: number;
  justificacion: string;
  match_ids: number[];
}

export interface BestCombination {
  items: { item_id: number; material_name: string; provider_org_id: number; provider_name: string; unit_price: number | null; subtotal: number | null }[];
  total_cost: number;
  items_covered: number;
  providers_count: number;
  savings_vs_recommendation: number | null;
}

export interface QuotationResult {
  quotation_id: number;
  title: string;
  items_extracted: number;
  matches_found: number;
  items_total: number;
  items_without_offers: number;
  items: ItemComparison[];
  providers: ProviderRanking[];
  recommendation: ProviderRanking | null;
  best_combination: BestCombination;
}

export async function uploadQuotationFile(
  file: File,
  title: string,
): Promise<QuotationResult> {
  const formData = new FormData();
  formData.append("file", file);
  formData.append("title", title);

  const token = getToken();
  const headers = new Headers();
  if (token) {
    headers.set("Authorization", `Bearer ${token}`);
  }

  const response = await fetch(`${API_BASE}/matching/quotations/upload`, {
    method: "POST",
    headers,
    body: formData,
  });

  if (!response.ok) {
    const error = await response.json().catch(() => ({}));
    throw new Error(error.detail || `Upload error: ${response.status}`);
  }

  return response.json();
}

export interface InventoryUploadResult {
  provider_org_id: number;
  items_extracted: number;
  items_saved: number;
  file_name: string;
  saved_items: any[];
}

export async function uploadInventoryFile(
  file: File,
  orgId: number,
): Promise<InventoryUploadResult> {
  const formData = new FormData();
  formData.append("file", file);

  const token = getToken();
  const headers = new Headers();
  if (token) {
    headers.set("Authorization", `Bearer ${token}`);
  }

  const response = await fetch(`${API_BASE}/documents/inventory/${orgId}/upload`, {
    method: "POST",
    headers,
    body: formData,
  });

  if (!response.ok) {
    const error = await response.json().catch(() => ({}));
    throw new Error(error.detail || `Upload error: ${response.status}`);
  }

  return response.json();
}
