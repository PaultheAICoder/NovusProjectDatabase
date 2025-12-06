/**
 * Common type definitions.
 */

/**
 * Paginated response wrapper.
 */
export interface PaginatedResponse<T> {
  items: T[];
  total: number;
  page: number;
  page_size: number;
  pages: number;
}

/**
 * API error response.
 */
export interface ErrorResponse {
  error: string;
  message: string;
}

/**
 * Validation error detail.
 */
export interface ValidationErrorDetail {
  field: string;
  message: string;
}

/**
 * Validation error response.
 */
export interface ValidationErrorResponse {
  error: string;
  message: string;
  details: ValidationErrorDetail[];
}

/**
 * User role.
 */
export type UserRole = "user" | "admin";

/**
 * User from API.
 */
export interface User {
  id: string;
  email: string;
  display_name: string;
  role: UserRole;
  is_admin: boolean;
}
