/**
 * Tests for ParsedQueryBadges component.
 */

import { render, screen } from "@testing-library/react";
import { describe, it, expect } from "vitest";
import { ParsedQueryBadges } from "../components/features/ParsedQueryBadges";
import type { ParsedQueryIntent } from "../types/search";

describe("ParsedQueryBadges", () => {
  const emptyIntent: ParsedQueryIntent = {
    search_text: "",
    date_range: null,
    organization_name: null,
    organization_id: null,
    technology_keywords: [],
    tag_ids: [],
    status: [],
    confidence: 0,
  };

  it("renders nothing when no parsed data", () => {
    const { container } = render(<ParsedQueryBadges intent={emptyIntent} />);
    expect(container.firstChild).toBeNull();
  });

  it("renders date range badge", () => {
    const intent: ParsedQueryIntent = {
      ...emptyIntent,
      date_range: {
        start_date: "2023-01-01",
        end_date: "2023-12-31",
        original_expression: "in 2023",
      },
    };
    render(<ParsedQueryBadges intent={intent} />);
    expect(screen.getByText("Time:")).toBeInTheDocument();
    expect(screen.getByText("in 2023")).toBeInTheDocument();
  });

  it("renders organization badge", () => {
    const intent: ParsedQueryIntent = {
      ...emptyIntent,
      organization_name: "Acme Corp",
      organization_id: "123",
    };
    render(<ParsedQueryBadges intent={intent} />);
    expect(screen.getByText("Client:")).toBeInTheDocument();
    expect(screen.getByText("Acme Corp")).toBeInTheDocument();
  });

  it("renders technology badges", () => {
    const intent: ParsedQueryIntent = {
      ...emptyIntent,
      technology_keywords: ["Bluetooth", "IoT"],
    };
    render(<ParsedQueryBadges intent={intent} />);
    expect(screen.getByText("Tech:")).toBeInTheDocument();
    expect(screen.getByText("Bluetooth, IoT")).toBeInTheDocument();
  });

  it("renders keywords badge", () => {
    const intent: ParsedQueryIntent = {
      ...emptyIntent,
      search_text: "sensor project",
    };
    render(<ParsedQueryBadges intent={intent} />);
    expect(screen.getByText("Keywords:")).toBeInTheDocument();
    expect(screen.getByText("sensor project")).toBeInTheDocument();
  });

  it("renders multiple badges together", () => {
    const intent: ParsedQueryIntent = {
      search_text: "sensors",
      date_range: { start_date: "2023-01-01", end_date: null, original_expression: "last year" },
      organization_name: "Acme",
      organization_id: "123",
      technology_keywords: ["Bluetooth"],
      tag_ids: [],
      status: ["active"],
      confidence: 0.9,
    };
    render(<ParsedQueryBadges intent={intent} />);
    expect(screen.getByText("Searching for:")).toBeInTheDocument();
    expect(screen.getByText("Time:")).toBeInTheDocument();
    expect(screen.getByText("Client:")).toBeInTheDocument();
    expect(screen.getByText("Tech:")).toBeInTheDocument();
    expect(screen.getByText("Status:")).toBeInTheDocument();
  });
});
