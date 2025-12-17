/**
 * ConflictCard component for the Admin page.
 * Displays sync conflicts with list and detail views.
 */

import { useState } from "react";
import { AlertTriangle, CheckCircle, Loader2 } from "lucide-react";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Alert, AlertDescription } from "@/components/ui/alert";
import { ConflictList } from "./ConflictList";
import { ConflictDetail } from "./ConflictDetail";
import {
  useSyncConflicts,
  useSyncConflictStats,
  useResolveSyncConflict,
} from "@/hooks/useMondaySync";
import type { ConflictResolutionType, SyncConflict } from "@/types/monday";
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

  const { data: conflictsData, isLoading: isLoadingConflicts } = useSyncConflicts({
    page,
    pageSize,
    entityType: entityTypeFilter,
  });

  const { data: stats, isLoading: isLoadingStats } = useSyncConflictStats();

  const resolveConflict = useResolveSyncConflict();

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

  const handleResolve = async (resolution: ConflictResolutionType) => {
    if (!selectedConflict) return;

    try {
      await resolveConflict.mutateAsync({
        conflictId: selectedConflict.id,
        data: { resolution_type: resolution },
      });

      setSuccessMessage(
        `Conflict resolved successfully using ${
          resolution === "keep_npd" ? "NPD" : "Monday.com"
        } data.`
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
            />
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
    </>
  );
}
