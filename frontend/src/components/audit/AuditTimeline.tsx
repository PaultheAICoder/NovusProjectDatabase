/**
 * AuditTimeline component for displaying a list of audit entries.
 * Supports filtering by date range and pagination.
 */

import { useState } from "react";
import { Loader2, History } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { AuditEntry } from "./AuditEntry";
import { useProjectAuditHistory, useContactAuditHistory } from "@/hooks/useAuditHistory";

interface AuditTimelineProps {
  entityType: "project" | "contact";
  entityId: string;
  /** Optional: show date range filters */
  showFilters?: boolean;
}

const PAGE_SIZE = 10;

export function AuditTimeline({
  entityType,
  entityId,
  showFilters = true,
}: AuditTimelineProps) {
  const [page, setPage] = useState(1);
  const [fromDate, setFromDate] = useState("");
  const [toDate, setToDate] = useState("");

  // Use the appropriate hook based on entity type
  const projectQuery = useProjectAuditHistory(
    entityType === "project" ? entityId : undefined,
    { page, page_size: PAGE_SIZE }
  );

  const contactQuery = useContactAuditHistory(
    entityType === "contact" ? entityId : undefined,
    { page, page_size: PAGE_SIZE }
  );

  // Select the active query based on entity type
  const query = entityType === "project" ? projectQuery : contactQuery;
  const { data, isLoading, isError, error } = query;

  // Filter entries by date range (client-side for simplicity)
  const filteredItems =
    data?.items.filter((entry) => {
      if (fromDate && new Date(entry.created_at) < new Date(fromDate)) {
        return false;
      }
      if (toDate) {
        const endOfDay = new Date(toDate);
        endOfDay.setHours(23, 59, 59, 999);
        if (new Date(entry.created_at) > endOfDay) {
          return false;
        }
      }
      return true;
    }) ?? [];

  const totalPages = data?.pages ?? 0;

  return (
    <div className="space-y-4">
      {/* Header */}
      <div className="flex items-center gap-2">
        <History className="h-5 w-5 text-muted-foreground" />
        <h3 className="text-lg font-semibold">Change History</h3>
      </div>

      {/* Filters */}
      {showFilters && (
        <div className="flex flex-wrap gap-4 rounded-md border bg-muted/50 p-3">
          <div className="flex items-center gap-2">
            <Label htmlFor="from-date" className="text-sm whitespace-nowrap">
              From:
            </Label>
            <Input
              id="from-date"
              type="date"
              value={fromDate}
              onChange={(e) => setFromDate(e.target.value)}
              className="h-8 w-auto"
            />
          </div>
          <div className="flex items-center gap-2">
            <Label htmlFor="to-date" className="text-sm whitespace-nowrap">
              To:
            </Label>
            <Input
              id="to-date"
              type="date"
              value={toDate}
              onChange={(e) => setToDate(e.target.value)}
              className="h-8 w-auto"
            />
          </div>
          {(fromDate || toDate) && (
            <Button
              variant="ghost"
              size="sm"
              onClick={() => {
                setFromDate("");
                setToDate("");
              }}
            >
              Clear filters
            </Button>
          )}
        </div>
      )}

      {/* Loading state */}
      {isLoading && (
        <div className="flex items-center justify-center gap-2 py-8">
          <Loader2 className="h-6 w-6 animate-spin text-muted-foreground" />
          <span className="text-muted-foreground">Loading history...</span>
        </div>
      )}

      {/* Error state */}
      {isError && (
        <div className="rounded-md bg-destructive/10 p-4 text-destructive">
          Failed to load audit history.{" "}
          {error instanceof Error ? error.message : "Unknown error"}
        </div>
      )}

      {/* Empty state */}
      {!isLoading && !isError && filteredItems.length === 0 && (
        <div className="py-8 text-center text-muted-foreground">
          {fromDate || toDate
            ? "No changes found in the selected date range."
            : "No changes recorded yet."}
        </div>
      )}

      {/* Timeline entries */}
      {!isLoading && !isError && filteredItems.length > 0 && (
        <div className="space-y-0 ml-2">
          {filteredItems.map((entry) => (
            <AuditEntry key={entry.id} entry={entry} />
          ))}
        </div>
      )}

      {/* Pagination */}
      {!isLoading && totalPages > 1 && (
        <div className="flex items-center justify-between border-t pt-4">
          <div className="text-sm text-muted-foreground">
            Page {page} of {totalPages}
          </div>
          <div className="flex gap-2">
            <Button
              variant="outline"
              size="sm"
              onClick={() => setPage((p) => Math.max(1, p - 1))}
              disabled={page <= 1}
            >
              Previous
            </Button>
            <Button
              variant="outline"
              size="sm"
              onClick={() => setPage((p) => Math.min(totalPages, p + 1))}
              disabled={page >= totalPages}
            >
              Next
            </Button>
          </div>
        </div>
      )}
    </div>
  );
}
