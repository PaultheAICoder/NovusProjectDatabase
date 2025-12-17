/**
 * DocumentQueueCard component for the Admin page.
 * Displays document processing queue with stats, table view, and management functionality.
 */

import { useState } from "react";
import { CheckCircle, FileText, Loader2, RefreshCw, AlertTriangle } from "lucide-react";
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
import { DocumentQueueTable } from "./DocumentQueueTable";
import {
  useDocumentQueue,
  useDocumentQueueStats,
  useRetryDocumentQueueItem,
  useCancelDocumentQueueItem,
} from "@/hooks/useDocumentQueue";
import type { DocumentQueueItem, DocumentQueueStatus } from "@/types/document-queue";
import { cn } from "@/lib/utils";

export function DocumentQueueCard() {
  const [page, setPage] = useState(1);
  const [pageSize] = useState(10);
  const [statusFilter, setStatusFilter] = useState<DocumentQueueStatus | null>(null);
  const [successMessage, setSuccessMessage] = useState<string | null>(null);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);

  const {
    data: queueData,
    isLoading: isLoadingQueue,
    refetch,
  } = useDocumentQueue({
    page,
    pageSize,
    status: statusFilter,
  });

  const { data: stats, isLoading: isLoadingStats } = useDocumentQueueStats();

  const retryMutation = useRetryDocumentQueueItem();
  const cancelMutation = useCancelDocumentQueueItem();

  const handleStatusFilterChange = (status: DocumentQueueStatus | null) => {
    setStatusFilter(status);
    setPage(1);
  };

  const handleRetry = async (item: DocumentQueueItem) => {
    setSuccessMessage(null);
    setErrorMessage(null);

    try {
      await retryMutation.mutateAsync({
        queueId: item.id,
        resetAttempts: true,
      });
      setSuccessMessage(
        `Document "${item.document_name}" retry scheduled successfully.`
      );
      setTimeout(() => setSuccessMessage(null), 5000);
    } catch (err) {
      const errorMsg =
        err instanceof Error ? err.message : "Failed to retry queue item";
      setErrorMessage(errorMsg);
      setTimeout(() => setErrorMessage(null), 5000);
    }
  };

  const handleCancel = async (item: DocumentQueueItem) => {
    setSuccessMessage(null);
    setErrorMessage(null);

    try {
      await cancelMutation.mutateAsync(item.id);
      setSuccessMessage(
        `Document "${item.document_name}" removed from queue.`
      );
      setTimeout(() => setSuccessMessage(null), 5000);
    } catch (err) {
      const errorMsg =
        err instanceof Error ? err.message : "Failed to cancel queue item";
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
  const inProgressCount = stats?.in_progress ?? 0;

  return (
    <Card>
      <CardHeader>
        <div className="flex items-center justify-between">
          <div>
            <CardTitle className="flex items-center gap-2">
              <FileText className="h-5 w-5" />
              Document Processing Queue
              {stats && (pendingCount > 0 || failedCount > 0 || inProgressCount > 0) && (
                <div className="flex gap-1 ml-2">
                  {inProgressCount > 0 && (
                    <Badge variant="secondary">{inProgressCount} processing</Badge>
                  )}
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
              View and manage document processing operations
            </CardDescription>
          </div>
          <div className="flex items-center gap-4">
            {stats && !isLoadingStats && (
              <div className="flex items-center gap-4 text-sm">
                <div className="flex items-center gap-1">
                  <span
                    className={cn(
                      "font-medium",
                      inProgressCount > 0 ? "text-blue-600" : "text-muted-foreground"
                    )}
                  >
                    {inProgressCount}
                  </span>
                  <span className="text-muted-foreground">processing</span>
                </div>
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
          <DocumentQueueTable
            items={queueData?.items ?? []}
            total={queueData?.total ?? 0}
            page={page}
            pageSize={pageSize}
            hasMore={queueData?.has_more ?? false}
            isLoading={isLoadingQueue}
            statusFilter={statusFilter}
            onStatusFilterChange={handleStatusFilterChange}
            onPageChange={setPage}
            onRetry={handleRetry}
            onCancel={handleCancel}
            isRetrying={retryMutation.isPending}
            isCancelling={cancelMutation.isPending}
          />
        )}
      </CardContent>
    </Card>
  );
}
