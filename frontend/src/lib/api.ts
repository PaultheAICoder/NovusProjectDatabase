/**
 * API client and TanStack Query configuration.
 */

import { QueryClient } from "@tanstack/react-query";

/**
 * Base API URL from environment or default to relative path.
 */
const API_BASE_URL = import.meta.env.VITE_API_URL || "/api/v1";

/**
 * Error context for debugging.
 */
export interface ApiErrorContext {
  contentType?: string;
  responseText?: string;
  url?: string;
  method?: string;
}

/**
 * Detect if content type indicates HTML.
 */
function isHtmlContentType(contentType: string | null): boolean {
  return contentType?.toLowerCase().includes("text/html") ?? false;
}

/**
 * Detect if content type indicates JSON.
 */
function isJsonContentType(contentType: string | null): boolean {
  if (!contentType) return false;
  const lower = contentType.toLowerCase();
  return lower.includes("application/json") || lower.includes("+json");
}

/**
 * Truncate text for error display.
 */
function truncateText(text: string, maxLength: number = 500): string {
  if (text.length <= maxLength) return text;
  return text.substring(0, maxLength) + "... [truncated]";
}

/**
 * Sensitive query parameter names that should be redacted in logs.
 */
const SENSITIVE_PARAMS = [
  "token",
  "key",
  "secret",
  "password",
  "api_key",
  "apikey",
  "authorization",
  "bearer",
  "access_token",
  "refresh_token",
  "client_secret",
  "credential",
];

/**
 * Sanitize URL by redacting sensitive query parameters.
 * @internal - Exported for testing only
 */
export function sanitizeUrl(url: string): string {
  try {
    // Handle relative URLs by adding a dummy origin
    const isRelative = url.startsWith("/");
    const fullUrl = isRelative ? `http://localhost${url}` : url;

    const parsed = new URL(fullUrl);

    SENSITIVE_PARAMS.forEach((param) => {
      // Check both exact match and case-insensitive
      parsed.searchParams.forEach((_, key) => {
        if (key.toLowerCase() === param.toLowerCase()) {
          parsed.searchParams.set(key, "[REDACTED]");
        }
      });
    });

    // Return the sanitized URL, stripping dummy origin if we added it
    if (isRelative) {
      return parsed.pathname + parsed.search + parsed.hash;
    }
    return parsed.toString();
  } catch {
    // If URL parsing fails, return a safe version
    return "[Invalid URL]";
  }
}

/**
 * Patterns to redact in response previews.
 */
const SENSITIVE_PATTERNS: RegExp[] = [
  // API keys and tokens (various formats) - matches "key": "value" patterns
  /("?(?:api[_-]?key|token|secret|password|authorization|bearer|access[_-]?token|refresh[_-]?token|client[_-]?secret|credential)"?\s*[:=]\s*)"[^"]+"/gi,
  // Bearer tokens in text
  /Bearer\s+[A-Za-z0-9\-_]+\.?[A-Za-z0-9\-_]*\.?[A-Za-z0-9\-_]*/gi,
];

/**
 * Sanitize response text by truncating and redacting sensitive patterns.
 * @internal - Exported for testing only
 */
export function sanitizeResponsePreview(
  text: string,
  maxLength: number = 500,
): string {
  if (!text) return text;

  let sanitized = text;

  // Redact sensitive patterns
  SENSITIVE_PATTERNS.forEach((pattern) => {
    sanitized = sanitized.replace(pattern, (_match, prefix) => {
      // If we captured a prefix (for key-value patterns), preserve it
      if (prefix) {
        return `${prefix}"[REDACTED]"`;
      }
      return "[REDACTED]";
    });
  });

  // Truncate after sanitization
  return truncateText(sanitized, maxLength);
}

/**
 * Custom error class for API errors.
 */
export class ApiError extends Error {
  constructor(
    public status: number,
    message: string,
    public data?: unknown,
    public context?: ApiErrorContext,
  ) {
    super(message);
    this.name = "ApiError";
  }

  /**
   * Get a detailed error message for debugging.
   * URL and response text are sanitized to prevent leaking sensitive data.
   */
  getDebugInfo(): string {
    const parts = [`Status: ${this.status}`, `Message: ${this.message}`];
    if (this.context?.url) parts.push(`URL: ${sanitizeUrl(this.context.url)}`);
    if (this.context?.method) parts.push(`Method: ${this.context.method}`);
    if (this.context?.contentType)
      parts.push(`Content-Type: ${this.context.contentType}`);
    if (this.context?.responseText) {
      parts.push(
        `Response Preview: ${sanitizeResponsePreview(this.context.responseText)}`,
      );
    }
    return parts.join("\n");
  }
}

/**
 * Handle API response and throw on error.
 */
async function handleResponse<T>(
  response: Response,
  requestContext?: { url: string; method: string },
): Promise<T> {
  if (!response.ok) {
    const contentType = response.headers.get("Content-Type");
    let errorData: unknown;
    let rawText: string | undefined;

    try {
      // Get raw text first (we can always do this)
      rawText = await response.text();

      // Try to parse as JSON if content type suggests it or if no content type
      if (isJsonContentType(contentType) || !contentType) {
        try {
          errorData = JSON.parse(rawText);
        } catch {
          // JSON parse failed, errorData stays undefined
        }
      }
    } catch {
      // Could not read response body at all
      rawText = "[Unable to read response body]";
    }

    // Build informative error message
    let message: string;

    if (
      typeof errorData === "object" &&
      errorData !== null &&
      "detail" in errorData
    ) {
      // FastAPI-style error with detail field
      message = String((errorData as { detail: unknown }).detail);
    } else if (isHtmlContentType(contentType)) {
      // HTML response (likely proxy error, nginx error page, etc.)
      message = `HTTP ${response.status}: Server returned HTML instead of JSON (possible proxy/server error)`;
    } else if (rawText && !errorData) {
      // Non-JSON text response
      message = `HTTP ${response.status}: ${response.statusText || "Error"}`;
    } else {
      // Fallback
      message = `HTTP ${response.status}: ${response.statusText || "Unknown error"}`;
    }

    // Build error context for debugging
    const context: ApiErrorContext = {
      contentType: contentType || undefined,
      responseText: rawText ? truncateText(rawText) : undefined,
      url: requestContext?.url,
      method: requestContext?.method,
    };

    // Log in development mode for easier debugging
    if (import.meta.env.DEV) {
      console.error("[API Error]", {
        status: response.status,
        statusText: response.statusText,
        url: sanitizeUrl(requestContext?.url || response.url),
        method: requestContext?.method,
        contentType,
        responsePreview: rawText
          ? sanitizeResponsePreview(rawText, 1000)
          : undefined,
      });
    }

    throw new ApiError(response.status, message, errorData, context);
  }

  // Handle 204 No Content
  if (response.status === 204) {
    return undefined as T;
  }

  return response.json();
}

/**
 * API client with typed methods.
 */
export const api = {
  /**
   * GET request.
   */
  async get<T>(endpoint: string): Promise<T> {
    const url = `${API_BASE_URL}${endpoint}`;
    const response = await fetch(url, {
      method: "GET",
      credentials: "include",
      headers: {
        Accept: "application/json",
      },
    });
    return handleResponse<T>(response, { url, method: "GET" });
  },

  /**
   * POST request.
   */
  async post<T>(endpoint: string, data?: unknown): Promise<T> {
    const url = `${API_BASE_URL}${endpoint}`;
    const response = await fetch(url, {
      method: "POST",
      credentials: "include",
      headers: {
        "Content-Type": "application/json",
        Accept: "application/json",
      },
      body: data ? JSON.stringify(data) : undefined,
    });
    return handleResponse<T>(response, { url, method: "POST" });
  },

  /**
   * PUT request.
   */
  async put<T>(endpoint: string, data: unknown): Promise<T> {
    const url = `${API_BASE_URL}${endpoint}`;
    const response = await fetch(url, {
      method: "PUT",
      credentials: "include",
      headers: {
        "Content-Type": "application/json",
        Accept: "application/json",
      },
      body: JSON.stringify(data),
    });
    return handleResponse<T>(response, { url, method: "PUT" });
  },

  /**
   * PATCH request.
   */
  async patch<T>(endpoint: string, data: unknown): Promise<T> {
    const url = `${API_BASE_URL}${endpoint}`;
    const response = await fetch(url, {
      method: "PATCH",
      credentials: "include",
      headers: {
        "Content-Type": "application/json",
        Accept: "application/json",
      },
      body: JSON.stringify(data),
    });
    return handleResponse<T>(response, { url, method: "PATCH" });
  },

  /**
   * DELETE request.
   */
  async delete<T = void>(endpoint: string): Promise<T> {
    const url = `${API_BASE_URL}${endpoint}`;
    const response = await fetch(url, {
      method: "DELETE",
      credentials: "include",
      headers: {
        Accept: "application/json",
      },
    });
    return handleResponse<T>(response, { url, method: "DELETE" });
  },

  /**
   * Upload file with multipart/form-data.
   */
  async upload<T>(endpoint: string, formData: FormData): Promise<T> {
    const url = `${API_BASE_URL}${endpoint}`;
    const response = await fetch(url, {
      method: "POST",
      credentials: "include",
      body: formData,
    });
    return handleResponse<T>(response, { url, method: "POST" });
  },

  /**
   * Upload file with progress tracking using XMLHttpRequest.
   */
  async uploadWithProgress<T>(
    endpoint: string,
    formData: FormData,
    onProgress?: (progress: number) => void,
  ): Promise<T> {
    const url = `${API_BASE_URL}${endpoint}`;

    return new Promise((resolve, reject) => {
      const xhr = new XMLHttpRequest();

      xhr.upload.addEventListener("progress", (event) => {
        if (event.lengthComputable && onProgress) {
          const percentComplete = Math.round(
            (event.loaded / event.total) * 100,
          );
          onProgress(percentComplete);
        }
      });

      xhr.addEventListener("load", () => {
        if (xhr.status >= 200 && xhr.status < 300) {
          try {
            const data = JSON.parse(xhr.responseText);
            resolve(data as T);
          } catch {
            reject(new ApiError(xhr.status, "Invalid JSON response"));
          }
        } else {
          let message = `HTTP ${xhr.status}: ${xhr.statusText}`;
          try {
            const errorData = JSON.parse(xhr.responseText);
            if (errorData.detail) {
              message = errorData.detail;
            }
          } catch {
            // Use default message
          }
          reject(new ApiError(xhr.status, message));
        }
      });

      xhr.addEventListener("error", () => {
        reject(new ApiError(0, "Network error during upload"));
      });

      xhr.addEventListener("abort", () => {
        reject(new ApiError(0, "Upload cancelled"));
      });

      xhr.open("POST", url);
      xhr.withCredentials = true;
      xhr.send(formData);
    });
  },

  /**
   * Download file and trigger browser download.
   */
  async download(endpoint: string, filename: string): Promise<void> {
    const url = `${API_BASE_URL}${endpoint}`;
    const response = await fetch(url, {
      method: "GET",
      credentials: "include",
    });

    if (!response.ok) {
      const contentType = response.headers.get("Content-Type");
      let rawText: string | undefined;

      try {
        rawText = await response.text();
      } catch {
        rawText = "[Unable to read response body]";
      }

      const context: ApiErrorContext = {
        contentType: contentType || undefined,
        responseText: rawText ? truncateText(rawText) : undefined,
        url,
        method: "GET",
      };

      if (import.meta.env.DEV) {
        console.error("[API Download Error]", {
          status: response.status,
          url: sanitizeUrl(url),
          contentType,
          responsePreview: rawText
            ? sanitizeResponsePreview(rawText, 1000)
            : undefined,
        });
      }

      throw new ApiError(
        response.status,
        `Download failed: HTTP ${response.status}: ${response.statusText}`,
        undefined,
        context,
      );
    }

    const blob = await response.blob();
    const blobUrl = window.URL.createObjectURL(blob);
    const link = document.createElement("a");
    link.href = blobUrl;
    link.download = filename;
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
    window.URL.revokeObjectURL(blobUrl);
  },
};

/**
 * TanStack Query client with default options.
 */
export const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      staleTime: 1000 * 60, // 1 minute
      retry: (failureCount, error) => {
        // Don't retry on 4xx errors
        if (
          error instanceof ApiError &&
          error.status >= 400 &&
          error.status < 500
        ) {
          return false;
        }
        return failureCount < 3;
      },
    },
    mutations: {
      retry: false,
    },
  },
});
