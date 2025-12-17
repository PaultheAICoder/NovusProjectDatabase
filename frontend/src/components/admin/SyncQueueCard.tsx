/**
 * SyncQueueCard component for the Admin page.
 * Displays sync queue with stats, table view, and retry functionality.
 */

import { useState } from "react";
import { CheckCircle, Loader2, RefreshCw, AlertTriangle } from "lucide-react";
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
import { SyncQueueTable } from "./SyncQueueTable";
import {
  useSyncQueue,
  useSyncQueueStats,
  useRetrySyncQueueItem,
} from "@/hooks/useMondaySync";
import type {
  SyncQueueItem,
  SyncQueueStatus,
  SyncQueueDirection,
} from "@/types/monday";
import { cn } from "@/lib/utils";

export function SyncQueueCard() {
  const [page, setPage] = useState(1);
  const [pageSize] = useState(10);
  const [entityTypeFilter, setEntityTypeFilter] = useState<
    "contact" | "organization" | null
  >(null);
  const [directionFilter, setDirectionFilter] =
    useState<SyncQueueDirection | null>(null);
  const [statusFilter, setStatusFilter] = useState<SyncQueueStatus | null>(
    null
  );
  const [successMessage, setSuccessMessage] = useState<string | null>(null);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);

  const {
    data: queueData,
    isLoading: isLoadingQueue,
    refetch,
  } = useSyncQueue({
    page,
    pageSize,
    entityType: entityTypeFilter,
    direction: directionFilter,
    status: statusFilter,
  });

  const { data: stats, isLoading: isLoadingStats } = useSyncQueueStats();

  const retryMutation = useRetrySyncQueueItem();

  const handleEntityTypeFilterChange = (
    type: "contact" | "organization" | null
  ) => {
    setEntityTypeFilter(type);
    setPage(1);
  };

  const handleDirectionFilterChange = (
    direction: SyncQueueDirection | null
  ) => {
    setDirectionFilter(direction);
    setPage(1);
  };

  const handleStatusFilterChange = (status: SyncQueueStatus | null) => {
    setStatusFilter(status);
    setPage(1);
  };

  const handleRetry = async (item: SyncQueueItem) => {
    setSuccessMessage(null);
    setErrorMessage(null);

    try {
      await retryMutation.mutateAsync({
        queueId: item.id,
        resetAttempts: true,
      });
      setSuccessMessage(
        `Queue item for ${item.entity_type} retry scheduled successfully.`
      );
      setTimeout(() => setSuccessMessage(null), 5000);
    } catch (err) {
      const errorMsg =
        err instanceof Error ? err.message : "Failed to retry queue item";
      setErrorMessage(errorMsg);
      setTimeout(() => setErrorMessage(null), 5000);
    }
  };

  const handleRefresh = () => {
    refetch();
  };

  const isLoading = isLoadingQueue || isLoadingStats;
  const pendingCount = stats?.pending ?? 0;
  const failedCount = stats?.failed ?? 0;

  return (
    <Card>
      <CardHeader>
        <div className="flex items-center justify-between">
          <div>
            <CardTitle className="flex items-center gap-2">
              <RefreshCw className="h-5 w-5" />
              Sync Queue
              {stats && (pendingCount > 0 || failedCount > 0) && (
                <div className="flex gap-1 ml-2">
                  {pendingCount > 0 && (
                    <Badge variant="secondary">{pendingCount} pending</Badge>
                  )}
                  {failedCount > 0 && (
                    <Badge variant="destructive">{failedCount} failed</Badge>
                  )}
                </div>
              )}
            </CardTitle>
            <CardDescription>
              View and manage pending sync operations
            </CardDescription>
          </div>
          <div className="flex items-center gap-4">
            {stats && !isLoadingStats && (
              <div className="flex items-center gap-4 text-sm">
                <div className="flex items-center gap-1">
                  <span
                    className={cn(
                      "font-medium",
                      pendingCount > 0 ? "text-yellow-600" : "text-muted-foreground"
                    )}
                  >
                    {pendingCount}
                  </span>
                  <span className="text-muted-foreground">pending</span>
                </div>
                <div className="flex items-center gap-1">
                  <span
                    className={cn(
                      "font-medium",
                      failedCount > 0 ? "text-red-600" : "text-muted-foreground"
                    )}
                  >
                    {failedCount}
                  </span>
                  <span className="text-muted-foreground">failed</span>
                </div>
                <div className="flex items-center gap-1">
                  <span className="font-medium text-green-600">
                    {stats.completed}
                  </span>
                  <span className="text-muted-foreground">completed</span>
                </div>
              </div>
            )}
            <Button
              variant="outline"
              size="sm"
              onClick={handleRefresh}
              disabled={isLoading}
            >
              {isLoading ? (
                <Loader2 className="h-4 w-4 animate-spin" />
              ) : (
                <RefreshCw className="h-4 w-4" />
              )}
            </Button>
          </div>
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
        {isLoading && !queueData ? (
          <div className="flex items-center justify-center py-8">
            <Loader2 className="h-6 w-6 animate-spin text-muted-foreground" />
          </div>
        ) : (
          <SyncQueueTable
            items={queueData?.items ?? []}
            total={queueData?.total ?? 0}
            page={page}
            pageSize={pageSize}
            hasMore={queueData?.has_more ?? false}
            isLoading={isLoadingQueue}
            entityTypeFilter={entityTypeFilter}
            directionFilter={directionFilter}
            statusFilter={statusFilter}
            onEntityTypeFilterChange={handleEntityTypeFilterChange}
            onDirectionFilterChange={handleDirectionFilterChange}
            onStatusFilterChange={handleStatusFilterChange}
            onPageChange={setPage}
            onRetry={handleRetry}
            isRetrying={retryMutation.isPending}
          />
        )}
      </CardContent>
    </Card>
  );
}
