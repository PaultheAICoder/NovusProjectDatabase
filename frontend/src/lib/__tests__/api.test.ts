/**
 * Unit tests for API client utilities.
 * Tests sanitization functions used to prevent sensitive data leakage in dev logs.
 */

import { describe, it, expect } from "vitest";
import { sanitizeUrl, sanitizeResponsePreview } from "../api";

describe("sanitizeUrl", () => {
  it("redacts token query parameter", () => {
    const url = "https://api.example.com/data?token=secret123";
    const result = sanitizeUrl(url);
    expect(result).toBe("https://api.example.com/data?token=%5BREDACTED%5D");
    expect(result).not.toContain("secret123");
  });

  it("redacts multiple sensitive params", () => {
    const url =
      "https://api.example.com/auth?token=abc&password=xyz&api_key=def";
    const result = sanitizeUrl(url);
    expect(result).not.toContain("abc");
    expect(result).not.toContain("xyz");
    expect(result).not.toContain("def");
    expect(result).toContain("token=%5BREDACTED%5D");
    expect(result).toContain("password=%5BREDACTED%5D");
    expect(result).toContain("api_key=%5BREDACTED%5D");
  });

  it("preserves non-sensitive params", () => {
    const url = "https://api.example.com/search?q=test&page=1&token=secret";
    const result = sanitizeUrl(url);
    expect(result).toContain("q=test");
    expect(result).toContain("page=1");
    expect(result).not.toContain("secret");
  });

  it("handles relative URLs", () => {
    const url = "/api/v1/data?token=secret123&filter=active";
    const result = sanitizeUrl(url);
    expect(result).toBe("/api/v1/data?token=%5BREDACTED%5D&filter=active");
    expect(result).not.toContain("secret123");
  });

  it("handles URLs without query params", () => {
    const url = "https://api.example.com/data";
    const result = sanitizeUrl(url);
    expect(result).toBe("https://api.example.com/data");
  });

  it("handles invalid URLs gracefully", () => {
    // URL constructor throws for truly malformed URLs
    // Note: "not-a-valid-url:::" is treated as a valid URL with scheme "not-a-valid-url"
    // We need something that actually fails URL parsing
    const url = "://invalid";
    const result = sanitizeUrl(url);
    expect(result).toBe("[Invalid URL]");
  });

  it("is case-insensitive for param names", () => {
    const url = "https://api.example.com/data?TOKEN=secret&API_KEY=key123";
    const result = sanitizeUrl(url);
    expect(result).not.toContain("secret");
    expect(result).not.toContain("key123");
  });

  it("redacts access_token parameter", () => {
    const url = "https://api.example.com/oauth?access_token=jwt.token.here";
    const result = sanitizeUrl(url);
    expect(result).not.toContain("jwt.token.here");
  });

  it("redacts refresh_token parameter", () => {
    const url = "https://api.example.com/oauth?refresh_token=refresh123";
    const result = sanitizeUrl(url);
    expect(result).not.toContain("refresh123");
  });

  it("redacts client_secret parameter", () => {
    const url =
      "https://api.example.com/oauth?client_id=app&client_secret=secret123";
    const result = sanitizeUrl(url);
    expect(result).toContain("client_id=app");
    expect(result).not.toContain("secret123");
  });

  it("redacts authorization parameter", () => {
    const url = "https://api.example.com/data?authorization=Bearer+abc";
    const result = sanitizeUrl(url);
    expect(result).not.toContain("Bearer+abc");
  });

  it("redacts bearer parameter", () => {
    const url = "https://api.example.com/data?bearer=token123";
    const result = sanitizeUrl(url);
    expect(result).not.toContain("token123");
  });

  it("redacts credential parameter", () => {
    const url = "https://api.example.com/login?credential=user:pass";
    const result = sanitizeUrl(url);
    expect(result).not.toContain("user:pass");
  });

  it("preserves URL hash", () => {
    const url = "/api/v1/data?token=secret#section";
    const result = sanitizeUrl(url);
    expect(result).toContain("#section");
    expect(result).not.toContain("secret");
  });
});

describe("sanitizeResponsePreview", () => {
  it("redacts Bearer tokens in text", () => {
    const text = "Error: Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.payload.sig";
    const result = sanitizeResponsePreview(text);
    expect(result).toContain("[REDACTED]");
    expect(result).not.toContain("eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9");
  });

  it("redacts JSON password fields", () => {
    const text = '{"username": "admin", "password": "secret123"}';
    const result = sanitizeResponsePreview(text);
    expect(result).toContain('"username": "admin"');
    expect(result).toContain('"[REDACTED]"');
    expect(result).not.toContain("secret123");
  });

  it("redacts JSON token fields", () => {
    const text = '{"access_token": "jwt.token.here", "expires_in": 3600}';
    const result = sanitizeResponsePreview(text);
    expect(result).toContain('"[REDACTED]"');
    expect(result).toContain('"expires_in": 3600');
    expect(result).not.toContain("jwt.token.here");
  });

  it("redacts api_key fields", () => {
    const text = '{"api_key": "sk-1234567890", "status": "active"}';
    const result = sanitizeResponsePreview(text);
    expect(result).toContain('"[REDACTED]"');
    expect(result).toContain('"status": "active"');
    expect(result).not.toContain("sk-1234567890");
  });

  it("truncates long responses", () => {
    const longText = "a".repeat(1000);
    const result = sanitizeResponsePreview(longText, 100);
    expect(result.length).toBeLessThanOrEqual(120); // 100 + truncation message
    expect(result).toContain("[truncated]");
  });

  it("handles empty input", () => {
    const result = sanitizeResponsePreview("");
    expect(result).toBe("");
  });

  it("handles null-ish input gracefully", () => {
    // TypeScript would prevent null, but testing runtime behavior
    const result = sanitizeResponsePreview(null as unknown as string);
    expect(result).toBe(null);
  });

  it("redacts secret fields", () => {
    const text = '{"client_secret": "verysecret123"}';
    const result = sanitizeResponsePreview(text);
    expect(result).not.toContain("verysecret123");
  });

  it("redacts credential fields", () => {
    const text = '{"credential": "user:password123"}';
    const result = sanitizeResponsePreview(text);
    expect(result).not.toContain("user:password123");
  });

  it("redacts refresh_token fields", () => {
    const text = '{"refresh_token": "refresh_abc123"}';
    const result = sanitizeResponsePreview(text);
    expect(result).not.toContain("refresh_abc123");
  });

  it("handles multiple Bearer tokens", () => {
    const text = "Token 1: Bearer abc123 and Token 2: Bearer def456";
    const result = sanitizeResponsePreview(text);
    expect(result).not.toContain("abc123");
    expect(result).not.toContain("def456");
    expect(result.match(/\[REDACTED\]/g)?.length).toBe(2);
  });

  it("uses default maxLength of 500", () => {
    const longText = "x".repeat(600);
    const result = sanitizeResponsePreview(longText);
    expect(result.length).toBeLessThanOrEqual(520); // 500 + truncation message
  });

  it("does not truncate short responses", () => {
    const shortText = "Short error message";
    const result = sanitizeResponsePreview(shortText);
    expect(result).toBe(shortText);
    expect(result).not.toContain("[truncated]");
  });

  it("redacts case-insensitive patterns", () => {
    const text = '{"PASSWORD": "UPPER", "Token": "Mixed"}';
    const result = sanitizeResponsePreview(text);
    expect(result).not.toContain("UPPER");
    expect(result).not.toContain("Mixed");
  });
});
