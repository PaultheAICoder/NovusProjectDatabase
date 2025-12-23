/**
 * AuditLogCard component for displaying global audit logs on the admin page.
 * Shows all audit entries with filters for entity type, action, and date range.
 */

import { useState } from "react";
import { format } from "date-fns";
import { History, Loader2, ChevronDown, ChevronRight, User } from "lucide-react";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Badge } from "@/components/ui/badge";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { FieldDiff } from "@/components/audit/FieldDiff";
import { useAuditLogs } from "@/hooks/useAuditHistory";
import type { AuditAction, AuditLogEntry } from "@/types/audit";

const PAGE_SIZE = 15;

const ENTITY_TYPES = [
  { value: "all", label: "All Types" },
  { value: "project", label: "Project" },
  { value: "contact", label: "Contact" },
  { value: "organization", label: "Organization" },
  { value: "document", label: "Document" },
];

const ACTION_TYPES = [
  { value: "all", label: "All Actions" },
  { value: "create", label: "Create" },
  { value: "update", label: "Update" },
  { value: "delete", label: "Delete" },
  { value: "archive", label: "Archive" },
];

/**
 * Get badge variant for each action type.
 */
function getActionVariant(
  action: AuditAction
): "default" | "secondary" | "success" | "destructive" {
  switch (action) {
    case "create":
      return "success";
    case "update":
      return "default";
    case "delete":
      return "destructive";
    case "archive":
      return "secondary";
    default:
      return "default";
  }
}

/**
 * Get human-readable label for action type.
 */
function getActionLabel(action: AuditAction): string {
  switch (action) {
    case "create":
      return "Created";
    case "update":
      return "Updated";
    case "delete":
      return "Deleted";
    case "archive":
      return "Archived";
    default:
      return action;
  }
}

/**
 * Inline audit entry row for the admin table view.
 */
function AuditLogRow({ entry }: { entry: AuditLogEntry }) {
  const [isExpanded, setIsExpanded] = useState(false);

  const hasFieldChanges =
    entry.changed_fields && Object.keys(entry.changed_fields).length > 0;
  const canExpand =
    hasFieldChanges && entry.action !== "create" && entry.action !== "delete";

  const userName = entry.user?.display_name ?? "System";
  const formattedDate = format(new Date(entry.created_at), "MMM d, yyyy h:mm a");

  return (
    <div className="border-b last:border-b-0">
      <div className="flex items-center gap-4 p-3 hover:bg-muted/50">
        {/* Expand toggle */}
        <div className="w-6">
          {canExpand && (
            <Button
              variant="ghost"
              size="sm"
              className="h-6 w-6 p-0"
              onClick={() => setIsExpanded(!isExpanded)}
              aria-expanded={isExpanded}
              aria-label={isExpanded ? "Collapse" : "Expand"}
            >
              {isExpanded ? (
                <ChevronDown className="h-4 w-4" />
              ) : (
                <ChevronRight className="h-4 w-4" />
              )}
            </Button>
          )}
        </div>

        {/* Entity type */}
        <div className="w-24">
          <Badge variant="outline" className="capitalize">
            {entry.entity_type}
          </Badge>
        </div>

        {/* Action */}
        <div className="w-20">
          <Badge variant={getActionVariant(entry.action)}>
            {getActionLabel(entry.action)}
          </Badge>
        </div>

        {/* User */}
        <div className="flex items-center gap-1 w-36 text-sm">
          <User className="h-3 w-3 text-muted-foreground" />
          <span className="truncate" title={userName}>
            {userName}
          </span>
        </div>

        {/* Date */}
        <div className="flex-1 text-sm text-muted-foreground">
          {formattedDate}
        </div>

        {/* Field count */}
        {hasFieldChanges && (
          <div className="text-xs text-muted-foreground">
            {Object.keys(entry.changed_fields || {}).length} field(s)
          </div>
        )}
      </div>

      {/* Expanded field changes */}
      {isExpanded && hasFieldChanges && (
        <div className="bg-muted/30 p-3 space-y-2">
          {Object.entries(entry.changed_fields!).map(([fieldName, change]) => (
            <FieldDiff
              key={fieldName}
              fieldName={fieldName}
              oldValue={change.old}
              newValue={change.new}
            />
          ))}
        </div>
      )}
    </div>
  );
}

export function AuditLogCard() {
  const [page, setPage] = useState(1);
  const [entityType, setEntityType] = useState<string>("all");
  const [action, setAction] = useState<string>("all");
  const [fromDate, setFromDate] = useState("");
  const [toDate, setToDate] = useState("");

  const { data, isLoading, isError, error } = useAuditLogs({
    entity_type: entityType !== "all" ? entityType : undefined,
    action: action !== "all" ? (action as AuditAction) : undefined,
    from_date: fromDate || undefined,
    to_date: toDate || undefined,
    page,
    page_size: PAGE_SIZE,
  });

  const totalPages = data?.pages ?? 0;
  const items = data?.items ?? [];

  const clearFilters = () => {
    setEntityType("all");
    setAction("all");
    setFromDate("");
    setToDate("");
    setPage(1);
  };

  const hasFilters =
    entityType !== "all" || action !== "all" || fromDate || toDate;

  return (
    <Card>
      <CardHeader>
        <CardTitle className="flex items-center gap-2">
          <History className="h-5 w-5" />
          Audit Log
        </CardTitle>
        <CardDescription>View all system changes and modifications</CardDescription>
      </CardHeader>
      <CardContent className="space-y-4">
        {/* Filters */}
        <div className="flex flex-wrap gap-4 rounded-md border bg-muted/50 p-3">
          <div className="flex items-center gap-2">
            <Label htmlFor="entity-type" className="text-sm whitespace-nowrap">
              Entity:
            </Label>
            <Select value={entityType} onValueChange={(v) => { setEntityType(v); setPage(1); }}>
              <SelectTrigger id="entity-type" className="h-8 w-32">
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                {ENTITY_TYPES.map((type) => (
                  <SelectItem key={type.value} value={type.value}>
                    {type.label}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>

          <div className="flex items-center gap-2">
            <Label htmlFor="action-type" className="text-sm whitespace-nowrap">
              Action:
            </Label>
            <Select value={action} onValueChange={(v) => { setAction(v); setPage(1); }}>
              <SelectTrigger id="action-type" className="h-8 w-32">
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                {ACTION_TYPES.map((type) => (
                  <SelectItem key={type.value} value={type.value}>
                    {type.label}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>

          <div className="flex items-center gap-2">
            <Label htmlFor="from-date-admin" className="text-sm whitespace-nowrap">
              From:
            </Label>
            <Input
              id="from-date-admin"
              type="date"
              value={fromDate}
              onChange={(e) => { setFromDate(e.target.value); setPage(1); }}
              className="h-8 w-auto"
            />
          </div>

          <div className="flex items-center gap-2">
            <Label htmlFor="to-date-admin" className="text-sm whitespace-nowrap">
              To:
            </Label>
            <Input
              id="to-date-admin"
              type="date"
              value={toDate}
              onChange={(e) => { setToDate(e.target.value); setPage(1); }}
              className="h-8 w-auto"
            />
          </div>

          {hasFilters && (
            <Button variant="ghost" size="sm" onClick={clearFilters}>
              Clear filters
            </Button>
          )}
        </div>

        {/* Loading state */}
        {isLoading && (
          <div className="flex items-center justify-center gap-2 py-8">
            <Loader2 className="h-6 w-6 animate-spin text-muted-foreground" />
            <span className="text-muted-foreground">Loading audit logs...</span>
          </div>
        )}

        {/* Error state */}
        {isError && (
          <div className="rounded-md bg-destructive/10 p-4 text-destructive">
            Failed to load audit logs.{" "}
            {error instanceof Error ? error.message : "Unknown error"}
          </div>
        )}

        {/* Empty state */}
        {!isLoading && !isError && items.length === 0 && (
          <div className="py-8 text-center text-muted-foreground">
            {hasFilters
              ? "No audit logs found matching the filters."
              : "No audit logs recorded yet."}
          </div>
        )}

        {/* Audit log entries */}
        {!isLoading && !isError && items.length > 0 && (
          <div className="rounded-md border">
            {items.map((entry) => (
              <AuditLogRow key={entry.id} entry={entry} />
            ))}
          </div>
        )}

        {/* Pagination */}
        {!isLoading && totalPages > 1 && (
          <div className="flex items-center justify-between border-t pt-4">
            <div className="text-sm text-muted-foreground">
              Page {page} of {totalPages} ({data?.total ?? 0} total entries)
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
      </CardContent>
    </Card>
  );
}
