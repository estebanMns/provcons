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
  const headers: HeadersInit = {
    "Content-Type": "application/json",
    ...options.headers,
  };

  const token = getToken();
  if (token) {
    headers.Authorization = `Bearer ${token}`;
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
}

export function clearToken(): void {
  localStorage.removeItem(TOKEN_KEY);
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
