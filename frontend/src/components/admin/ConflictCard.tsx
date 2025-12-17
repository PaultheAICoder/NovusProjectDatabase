/**
 * ConflictCard component for the Admin page.
 * Displays sync conflicts with list and detail views.
 */

import { useState } from "react";
import { AlertTriangle, CheckCircle, CheckSquare, Loader2 } from "lucide-react";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Alert, AlertDescription } from "@/components/ui/alert";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { ConflictList } from "./ConflictList";
import { ConflictDetail } from "./ConflictDetail";
import {
  useSyncConflicts,
  useSyncConflictStats,
  useResolveSyncConflict,
  useBulkResolveSyncConflicts,
} from "@/hooks/useMondaySync";
import type { BulkResolveResult, ConflictResolutionType, SyncConflict } from "@/types/monday";
import { cn } from "@/lib/utils";

export function ConflictCard() {
  const [page, setPage] = useState(1);
  const [pageSize] = useState(10);
  const [entityTypeFilter, setEntityTypeFilter] = useState<
    "contact" | "organization" | null
  >(null);
  const [selectedConflict, setSelectedConflict] = useState<SyncConflict | null>(
    null
  );
  const [successMessage, setSuccessMessage] = useState<string | null>(null);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);

  // Selection state for bulk operations
  const [selectedIds, setSelectedIds] = useState<Set<string>>(new Set());

  // Bulk resolve state
  const [isBulkConfirmOpen, setIsBulkConfirmOpen] = useState(false);
  const [bulkResolutionType, setBulkResolutionType] = useState<"keep_npd" | "keep_monday" | null>(null);
  const [bulkResults, setBulkResults] = useState<BulkResolveResult[] | null>(null);
  const [isBulkResultsOpen, setIsBulkResultsOpen] = useState(false);

  const { data: conflictsData, isLoading: isLoadingConflicts } = useSyncConflicts({
    page,
    pageSize,
    entityType: entityTypeFilter,
  });

  const { data: stats, isLoading: isLoadingStats } = useSyncConflictStats();

  const resolveConflict = useResolveSyncConflict();
  const bulkResolveConflicts = useBulkResolveSyncConflicts();

  const handleEntityTypeFilterChange = (
    type: "contact" | "organization" | null
  ) => {
    setEntityTypeFilter(type);
    setPage(1); // Reset to first page on filter change
  };

  const handleViewConflict = (conflict: SyncConflict) => {
    setSelectedConflict(conflict);
    setSuccessMessage(null);
    setErrorMessage(null);
  };

  const handleCloseDetail = () => {
    setSelectedConflict(null);
  };

  const handleResolve = async (
    resolution: ConflictResolutionType,
    mergeSelections?: Record<string, "npd" | "monday">
  ) => {
    if (!selectedConflict) return;

    try {
      await resolveConflict.mutateAsync({
        conflictId: selectedConflict.id,
        data: {
          resolution_type: resolution,
          merge_selections: mergeSelections,
        },
      });

      // Build resolution label based on type
      const resolutionLabel =
        resolution === "merge"
          ? "merged field selections"
          : resolution === "keep_npd"
            ? "NPD"
            : "Monday.com";

      setSuccessMessage(
        `Conflict resolved successfully using ${resolutionLabel}.`
      );
      setSelectedConflict(null);

      // Clear success message after 5 seconds
      setTimeout(() => setSuccessMessage(null), 5000);
    } catch (err) {
      const errorMsg =
        err instanceof Error ? err.message : "Failed to resolve conflict";
      setErrorMessage(errorMsg);

      // Clear error message after 5 seconds
      setTimeout(() => setErrorMessage(null), 5000);
    }
  };

  // Bulk operation handlers
  const handleBulkResolveClick = (type: "keep_npd" | "keep_monday") => {
    setBulkResolutionType(type);
    setIsBulkConfirmOpen(true);
  };

  const handleBulkResolveConfirm = async () => {
    if (!bulkResolutionType || selectedIds.size === 0) return;

    try {
      const response = await bulkResolveConflicts.mutateAsync({
        conflict_ids: Array.from(selectedIds),
        resolution_type: bulkResolutionType,
      });

      setBulkResults(response.results);
      setIsBulkConfirmOpen(false);
      setIsBulkResultsOpen(true);
      setSelectedIds(new Set());

      if (response.succeeded > 0) {
        setSuccessMessage(
          `Resolved ${response.succeeded} conflict${response.succeeded !== 1 ? "s" : ""}.${
            response.failed > 0 ? ` ${response.failed} failed.` : ""
          }`
        );
      }
    } catch (err) {
      setErrorMessage(
        err instanceof Error ? err.message : "Failed to bulk resolve conflicts"
      );
    }
    setBulkResolutionType(null);
  };

  const handleBulkCancel = () => {
    setIsBulkConfirmOpen(false);
    setBulkResolutionType(null);
  };

  const handleClearSelection = () => {
    setSelectedIds(new Set());
  };

  const isLoading = isLoadingConflicts || isLoadingStats;

  return (
    <>
      <Card>
        <CardHeader>
          <div className="flex items-center justify-between">
            <div>
              <CardTitle className="flex items-center gap-2">
                <AlertTriangle className="h-5 w-5" />
                Sync Conflicts
                {stats && stats.unresolved > 0 && (
                  <Badge
                    variant="destructive"
                    className="ml-2"
                  >
                    {stats.unresolved}
                  </Badge>
                )}
              </CardTitle>
              <CardDescription>
                Review and resolve data conflicts between NPD and Monday.com
              </CardDescription>
            </div>
            {stats && !isLoadingStats && (
              <div className="flex items-center gap-4 text-sm">
                <div className="flex items-center gap-1">
                  <span
                    className={cn(
                      "font-medium",
                      stats.unresolved > 0 ? "text-amber-600" : "text-green-600"
                    )}
                  >
                    {stats.unresolved}
                  </span>
                  <span className="text-muted-foreground">unresolved</span>
                </div>
                <div className="flex items-center gap-1">
                  <span className="font-medium text-green-600">
                    {stats.resolved}
                  </span>
                  <span className="text-muted-foreground">resolved</span>
                </div>
              </div>
            )}
          </div>
        </CardHeader>
        <CardContent className="space-y-4">
          {/* Success Message */}
          {successMessage && (
            <Alert className="border-green-200 bg-green-50">
              <CheckCircle className="h-4 w-4 text-green-600" />
              <AlertDescription className="text-green-800">
                {successMessage}
              </AlertDescription>
            </Alert>
          )}

          {/* Error Message */}
          {errorMessage && (
            <Alert variant="destructive">
              <AlertTriangle className="h-4 w-4" />
              <AlertDescription>{errorMessage}</AlertDescription>
            </Alert>
          )}

          {/* Loading State */}
          {isLoading && !conflictsData ? (
            <div className="flex items-center justify-center py-8">
              <Loader2 className="h-6 w-6 animate-spin text-muted-foreground" />
            </div>
          ) : (
            <>
              {/* Bulk Action Bar */}
              {selectedIds.size > 0 && (
                <div className="flex items-center justify-between rounded-md border bg-muted/50 p-3">
                  <div className="flex items-center gap-2">
                    <CheckSquare className="h-4 w-4 text-muted-foreground" />
                    <span className="text-sm font-medium">
                      {selectedIds.size} conflict{selectedIds.size !== 1 ? "s" : ""} selected
                    </span>
                    <Button
                      variant="ghost"
                      size="sm"
                      onClick={handleClearSelection}
                      className="text-muted-foreground"
                    >
                      Clear
                    </Button>
                  </div>
                  <div className="flex gap-2">
                    <Button
                      variant="default"
                      size="sm"
                      onClick={() => handleBulkResolveClick("keep_npd")}
                      disabled={bulkResolveConflicts.isPending}
                      className="bg-blue-600 hover:bg-blue-700"
                    >
                      Keep All NPD
                    </Button>
                    <Button
                      variant="secondary"
                      size="sm"
                      onClick={() => handleBulkResolveClick("keep_monday")}
                      disabled={bulkResolveConflicts.isPending}
                      className="bg-purple-600 text-white hover:bg-purple-700"
                    >
                      Keep All Monday
                    </Button>
                  </div>
                </div>
              )}

              <ConflictList
                conflicts={conflictsData?.items ?? []}
                total={conflictsData?.total ?? 0}
                page={page}
                pageSize={pageSize}
                hasMore={conflictsData?.has_more ?? false}
                isLoading={isLoadingConflicts}
                entityTypeFilter={entityTypeFilter}
                onEntityTypeFilterChange={handleEntityTypeFilterChange}
                onPageChange={setPage}
                onViewConflict={handleViewConflict}
                selectedIds={selectedIds}
                onSelectionChange={setSelectedIds}
              />
            </>
          )}
        </CardContent>
      </Card>

      {/* Detail Dialog */}
      {selectedConflict && (
        <ConflictDetail
          conflict={selectedConflict}
          isOpen={true}
          onClose={handleCloseDetail}
          onResolve={handleResolve}
          isResolving={resolveConflict.isPending}
        />
      )}

      {/* Bulk Resolve Confirmation Dialog */}
      <Dialog open={isBulkConfirmOpen} onOpenChange={setIsBulkConfirmOpen}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Confirm Bulk Resolution</DialogTitle>
            <DialogDescription>
              You are about to resolve {selectedIds.size} conflict{selectedIds.size !== 1 ? "s" : ""} using{" "}
              <strong>{bulkResolutionType === "keep_npd" ? "NPD" : "Monday.com"}</strong> data.
            </DialogDescription>
          </DialogHeader>
          <div className="py-4">
            <p className="text-sm text-muted-foreground">
              {bulkResolutionType === "keep_npd"
                ? "NPD data will be kept and pushed to Monday.com for all selected conflicts."
                : "Monday.com data will be kept and NPD will be updated for all selected conflicts."}
            </p>
            <p className="mt-2 text-sm text-amber-600">
              This action cannot be undone.
            </p>
          </div>
          <DialogFooter>
            <Button
              variant="outline"
              onClick={handleBulkCancel}
              disabled={bulkResolveConflicts.isPending}
            >
              Cancel
            </Button>
            <Button
              variant={bulkResolutionType === "keep_npd" ? "default" : "secondary"}
              onClick={handleBulkResolveConfirm}
              disabled={bulkResolveConflicts.isPending}
              className={
                bulkResolutionType === "keep_npd"
                  ? "bg-blue-600 hover:bg-blue-700"
                  : "bg-purple-600 text-white hover:bg-purple-700"
              }
            >
              {bulkResolveConflicts.isPending && (
                <Loader2 className="mr-2 h-4 w-4 animate-spin" />
              )}
              Confirm
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {/* Bulk Results Dialog */}
      <Dialog open={isBulkResultsOpen} onOpenChange={setIsBulkResultsOpen}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Bulk Resolution Results</DialogTitle>
          </DialogHeader>
          <div className="py-4 space-y-3">
            {bulkResults && (
              <>
                <div className="flex items-center gap-4">
                  <div className="flex items-center gap-2 text-green-600">
                    <CheckCircle className="h-4 w-4" />
                    <span>{bulkResults.filter((r) => r.success).length} succeeded</span>
                  </div>
                  {bulkResults.filter((r) => !r.success).length > 0 && (
                    <div className="flex items-center gap-2 text-red-600">
                      <AlertTriangle className="h-4 w-4" />
                      <span>{bulkResults.filter((r) => !r.success).length} failed</span>
                    </div>
                  )}
                </div>
                {bulkResults.filter((r) => !r.success).length > 0 && (
                  <div className="rounded-md border border-red-200 bg-red-50 p-3">
                    <div className="text-sm font-medium text-red-800 mb-2">Failed Conflicts:</div>
                    <ul className="text-sm text-red-700 space-y-1">
                      {bulkResults
                        .filter((r) => !r.success)
                        .map((r) => (
                          <li key={r.conflict_id}>
                            {r.conflict_id.substring(0, 8)}...: {r.error}
                          </li>
                        ))}
                    </ul>
                  </div>
                )}
              </>
            )}
          </div>
          <DialogFooter>
            <Button onClick={() => setIsBulkResultsOpen(false)}>
              Close
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </>
  );
}
