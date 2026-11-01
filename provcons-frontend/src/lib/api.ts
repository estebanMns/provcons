// Sin NEXT_PUBLIC_API_URL, la API usa el mismo host que la página (localhost o la IP de la red local).
export const API_BASE =
  process.env.NEXT_PUBLIC_API_URL ||
  (typeof window !== "undefined"
    ? `http://${window.location.hostname}:8000/api`
    : "http://localhost:8000/api");
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
  // "texto": coincidió por nombre; "ia": sinónimo que solo encontró la IA;
  // "texto+ia": coincidió por nombre y la IA lo confirmó
  metodo: "texto" | "ia" | "texto+ia";
  revision_ia?: { equivalente: boolean; confianza: number; motivo: string };
}

export interface AIReview {
  // "stored": comparación reabierta del historial (la IA ya revisó al comparar)
  status: "ok" | "failed" | "disabled" | "stored";
  products_reviewed: number;
  matches_added: number;
  matches_rejected: number;
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
  items: { item_id: number; material_name: string; provider_org_id: number; provider_name: string; match_id: number; unit_price: number | null; subtotal: number | null }[];
  total_cost: number;
  items_covered: number;
  providers_count: number;
  savings_vs_recommendation: number | null;
}

export interface QuotationSummary {
  id: number;
  title: string;
  status: "abierta" | "en_negociacion" | "cerrada" | "cancelada";
  created_at: string;
  items_count: number;
  active_orders: number;
}

export async function listQuotations(): Promise<QuotationSummary[]> {
  return fetchAPI<QuotationSummary[]>("/matching/quotations");
}

// Comparación guardada: no vuelve a llamar a la IA
export async function getComparison(quotationId: number): Promise<QuotationResult> {
  return fetchAPI<QuotationResult>(`/matching/quotations/${quotationId}/comparison`);
}

// Vuelve a buscar proveedores con el inventario actual (incluye revisión con IA)
export async function rerunComparison(quotationId: number): Promise<QuotationResult> {
  return fetchAPI<QuotationResult>(`/matching/quotations/${quotationId}/run`, { method: "POST" });
}

// Predicción del resultado futuro de cada opción de compra. Las cifras las
// calcula el backend con el historial; la IA solo redacta los textos.
export interface DeliveryDays { median: number; p25: number; p75: number }
export type ForecastConfidence = "baja" | "media" | "alta";

export interface ProviderProfile {
  provider_org_id: number;
  provider_name: string;
  orders_closed: number;
  orders_delivered: number;
  orders_rejected: number;
  orders_open: number;
  orders_with_you: number;
  reliability: number;
  confidence: ForecastConfidence;
  delivery_days: DeliveryDays | null;
  price_trend_pct_30d: number | null;
  market_premium_pct: number | null;
  unit_mismatches: number;
}

export interface ForecastOption {
  key: string;
  label: string;
  kind: "proveedor" | "combinacion";
  provider_org_ids: number[];
  main_provider_id: number | null;
  items_from_main: number;
  complement_items: number;
  cost_today: number;
  expected_cost: number;
  success_probability: number;
  confidence: ForecastConfidence;
  delivery_days: DeliveryDays | null;
  shortfalls: { material_name: string; provider_name: string; missing_quantity: number; alternative_provider: string | null; extra_cost: number }[];
  scenarios: Record<"optimista" | "probable" | "pesimista", { cost: number; days: number | null }>;
  narrative: { que_pasara: string; riesgos: string[]; consejo: string };
}

export interface QuotationForecast {
  quotation_id: number;
  items_total: number;
  items_unavailable: string[];
  providers: ProviderProfile[];
  options: ForecastOption[];
  best_option_key: string | null;
  current_recommendation_key: string | null;
  summary: string;
  narrative_source: "ia" | "plantilla";
  generated_at: string;
  cached: boolean;
}

export async function getForecast(quotationId: number): Promise<QuotationForecast> {
  return fetchAPI<QuotationForecast>(`/matching/quotations/${quotationId}/forecast`);
}

export interface QuotationResult {
  quotation_id: number;
  title: string;
  items_extracted?: number;  // solo al subir un archivo
  matches_found: number;
  ai_review: AIReview;
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

export interface InventoryItem {
  id: number;
  material_name: string;
  quantity_available: number;
  unit: string;
  unit_price: number | string | null;
}

export interface InventoryUploadResult {
  provider_org_id: number;
  items_extracted: number;
  items_saved: number;
  file_name: string;
  saved_items: InventoryItem[];
}

export async function getInventory(orgId: number): Promise<InventoryItem[]> {
  return fetchAPI<InventoryItem[]>(`/documents/inventory/${orgId}`);
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

export interface RecentOrder {
  id: number;
  counterpart: string;
  status: OrderStatus;
  total_amount: number | null;
  created_at: string;
}

export interface SalesOpportunity {
  quotation_id: number;
  title: string;
  constructora: string;
  created_at: string;
  items_matched: number;
  items_total: number;
  cheapest_items: number;
  estimated_value: number;
  score: number;
}

export type DashboardSummary =
  | {
      role: "constructora";
      open_quotations: number;
      active_orders: number;
      awaiting_confirmation: number;
      in_transit: number;
      delivered_orders: number;
      committed_spend: number;
      recent_orders: RecentOrder[];
    }
  | {
      role: "proveedor";
      inventory_products: number;
      orders_to_confirm: number;
      orders_to_ship: number;
      in_transit: number;
      delivered_sales: number;
      opportunities_value: number;
      opportunities: SalesOpportunity[];
      recent_orders: RecentOrder[];
    };

export async function getDashboardSummary(): Promise<DashboardSummary> {
  return fetchAPI<DashboardSummary>("/dashboard/summary");
}

export interface LatencyStats {
  count: number;
  p50: number | null;
  p95: number | null;
  p99: number | null;
}

export interface MetricsSummary {
  uptime_seconds: number;
  http: (LatencyStats & { method: string; route: string; errors: number })[];
  ai: (LatencyStats & { kind: string; errors: number })[];
  grpc: (LatencyStats & { method: string; errors: number })[];
  engine_fallbacks: number;
  event_loop_lag_ms: LatencyStats & { current: number | null };
  web_vitals: Record<string, { count: number; p75: number | null }>;
}

export async function getMetricsSummary(): Promise<MetricsSummary> {
  return fetchAPI<MetricsSummary>("/metrics/summary");
}

export type AuditCategory = "ordenes" | "cotizaciones" | "inventario" | "cuenta";

export interface AuditEntry {
  id: number;
  created_at: string;
  action: string;
  resource_type: string;
  resource_id: number | null;
  actor_name: string | null;
  actor_organization_name: string | null;
  own_organization: boolean;  // false = la hizo la otra parte de una orden
  description: string;
}

export async function listActivity(offset = 0, limit = 50, category?: AuditCategory): Promise<AuditEntry[]> {
  const params = new URLSearchParams({ offset: String(offset), limit: String(limit) });
  if (category) params.set("category", category);
  return fetchAPI<AuditEntry[]>(`/audit?${params}`);
}

export type OrderStatus = "pendiente" | "confirmada" | "en_transito" | "entregada" | "cancelada";
export type PaymentTerms = "contado" | "cuotas";

export interface OrderItem {
  id: number;
  requested_material: string;
  material_name: string;
  quantity: number;
  unit: string;
  unit_price: number | null;
  subtotal: number | null;
}

export interface Order {
  id: number;
  quotation_id: number | null;
  quotation_title: string | null;
  constructora_org_id: number;
  constructora_name: string | null;
  provider_org_id: number;
  provider_name: string | null;
  status: OrderStatus;
  payment_terms: PaymentTerms | null;
  total_amount: number | null;
  items: OrderItem[];
  created_at: string;
  updated_at: string;
}

// Crea una orden por cada proveedor de las ofertas elegidas
export async function createOrders(quotationId: number, matchIds: number[], paymentTerms: PaymentTerms): Promise<Order[]> {
  return fetchAPI<Order[]>("/orders", {
    method: "POST",
    body: JSON.stringify({ quotation_id: quotationId, match_ids: matchIds, payment_terms: paymentTerms }),
  });
}

export async function listOrders(): Promise<Order[]> {
  return fetchAPI<Order[]>("/orders");
}

export async function confirmOrder(orderId: number): Promise<Order> {
  return fetchAPI<Order>(`/orders/${orderId}/confirm`, { method: "POST" });
}

export async function advanceOrder(orderId: number): Promise<Order> {
  return fetchAPI<Order>(`/orders/${orderId}/advance`, { method: "POST" });
}

export async function cancelOrder(orderId: number): Promise<Order> {
  return fetchAPI<Order>(`/orders/${orderId}/cancel`, { method: "POST" });
}
