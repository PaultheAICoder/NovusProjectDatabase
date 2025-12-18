/**
 * API Token types for token management UI.
 */

/** API Token response from backend (metadata only, no secrets). */
export interface APIToken {
  id: string;
  name: string;
  token_prefix: string;
  scopes: string[] | null;
  expires_at: string | null;
  last_used_at: string | null;
  is_active: boolean;
  created_at: string;
}

/** Response after token creation (includes plaintext token ONCE). */
export interface APITokenCreateResponse {
  token: string;
  token_info: APIToken;
}

/** Paginated list of API tokens. */
export interface APITokenListResponse {
  items: APIToken[];
  total: number;
  page: number;
  page_size: number;
}

/** Request to create a new token. */
export interface APITokenCreateRequest {
  name: string;
  scopes?: string[];
  expires_at?: string;
}

/** Request to update a token. */
export interface APITokenUpdateRequest {
  name?: string;
  is_active?: boolean;
}

/** Expiration option for token creation. */
export interface ExpirationOption {
  label: string;
  value: string | null; // null means "never"
  days: number | null;
}

/** Standard expiration options. */
export const EXPIRATION_OPTIONS: ExpirationOption[] = [
  { label: "30 days", value: "30", days: 30 },
  { label: "90 days", value: "90", days: 90 },
  { label: "1 year", value: "365", days: 365 },
  { label: "Never", value: null, days: null },
];
