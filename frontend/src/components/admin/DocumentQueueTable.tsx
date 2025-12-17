/**
 * DocumentQueueTable component for displaying a table of document queue items.
 * Includes filtering, pagination, retry and cancel actions.
 */

import {
  ChevronLeft,
  ChevronRight,
  FileText,
  Loader2,
  RefreshCw,
  X,
} from "lucide-react";
import { formatDistanceToNow } from "date-fns";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import {
  Tooltip,
  TooltipContent,
  TooltipProvider,
  TooltipTrigger,
} from "@/components/ui/tooltip";
import type { DocumentQueueItem, DocumentQueueStatus } from "@/types/document-queue";
import { cn } from "@/lib/utils";

interface DocumentQueueTableProps {
  items: DocumentQueueItem[];
  total: number;
  page: number;
  pageSize: number;
  hasMore: boolean;
  isLoading: boolean;
  statusFilter: DocumentQueueStatus | null;
  onStatusFilterChange: (status: DocumentQueueStatus | null) => void;
  onPageChange: (page: number) => void;
  onRetry: (item: DocumentQueueItem) => void;
  onCancel: (item: DocumentQueueItem) => void;
  isRetrying: boolean;
  isCancelling: boolean;
}

const statusColors: Record<DocumentQueueStatus, string> = {
  pending: "bg-yellow-100 text-yellow-800 border-yellow-200",
  in_progress: "bg-blue-100 text-blue-800 border-blue-200",
  completed: "bg-green-100 text-green-800 border-green-200",
  failed: "bg-red-100 text-red-800 border-red-200",
};

const statusLabels: Record<DocumentQueueStatus, string> = {
  pending: "Pending",
  in_progress: "In Progress",
  completed: "Completed",
  failed: "Failed",
};

const operationLabels: Record<string, string> = {
  process: "Process",
  reprocess: "Reprocess",
};

export function DocumentQueueTable({
  items,
  total,
  page,
  pageSize,
  hasMore,
  isLoading,
  statusFilter,
  onStatusFilterChange,
  onPageChange,
  onRetry,
  onCancel,
  isRetrying,
  isCancelling,
}: DocumentQueueTableProps) {
  const startIndex = (page - 1) * pageSize + 1;
  const endIndex = Math.min(page * pageSize, total);

  if (isLoading) {
    return (
      <div className="flex items-center justify-center py-12">
        <Loader2 className="h-6 w-6 animate-spin text-muted-foreground" />
      </div>
    );
  }

  return (
    <div className="space-y-4">
      {/* Filters */}
      <div className="flex flex-wrap items-center gap-4">
        <Select
          value={statusFilter || "all"}
          onValueChange={(v) =>
            onStatusFilterChange(v === "all" ? null : (v as DocumentQueueStatus))
          }
        >
          <SelectTrigger className="w-[150px]">
            <SelectValue placeholder="Status" />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value="all">All Statuses</SelectItem>
            <SelectItem value="pending">Pending</SelectItem>
            <SelectItem value="in_progress">In Progress</SelectItem>
            <SelectItem value="completed">Completed</SelectItem>
            <SelectItem value="failed">Failed</SelectItem>
          </SelectContent>
        </Select>

        {total > 0 && (
          <div className="ml-auto text-sm text-muted-foreground">
            Showing {startIndex}-{endIndex} of {total}
          </div>
        )}
      </div>

      {/* Table or Empty State */}
      {items.length === 0 ? (
        <div className="rounded-md border bg-muted/30 py-12 text-center">
          <p className="text-muted-foreground">No queue items found</p>
          <p className="mt-1 text-sm text-muted-foreground">
            {statusFilter
              ? "Try adjusting your filter."
              : "The document processing queue is empty."}
          </p>
        </div>
      ) : (
        <div className="rounded-md border">
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>Document</TableHead>
                <TableHead className="w-[100px]">Operation</TableHead>
                <TableHead className="w-[100px]">Status</TableHead>
                <TableHead className="w-[80px]">Attempts</TableHead>
                <TableHead className="w-[120px]">Next Retry</TableHead>
                <TableHead>Error</TableHead>
                <TableHead className="w-[100px]">Actions</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {items.map((item) => (
                <TableRow key={item.id}>
                  <TableCell>
                    <div className="flex items-center gap-2">
                      <FileText className="h-4 w-4 text-muted-foreground" />
                      <span className="text-sm font-medium truncate max-w-[200px]">
                        {item.document_name}
                      </span>
                    </div>
                  </TableCell>
                  <TableCell>
                    <Badge variant="outline" className="text-xs">
                      {operationLabels[item.operation] || item.operation}
                    </Badge>
                  </TableCell>
                  <TableCell>
                    <Badge
                      variant="outline"
                      className={cn("text-xs", statusColors[item.status])}
                    >
                      {statusLabels[item.status]}
                    </Badge>
                  </TableCell>
                  <TableCell className="text-sm">
                    {item.attempts} / {item.max_attempts}
                  </TableCell>
                  <TableCell className="text-sm text-muted-foreground">
                    {item.status === "failed" ? (
                      <span className="text-red-600">Never</span>
                    ) : item.next_retry ? (
                      formatDistanceToNow(new Date(item.next_retry), {
                        addSuffix: true,
                      })
                    ) : (
                      "-"
                    )}
                  </TableCell>
                  <TableCell className="max-w-[200px]">
                    {item.error_message ? (
                      <TooltipProvider>
                        <Tooltip>
                          <TooltipTrigger asChild>
                            <span className="line-clamp-1 cursor-help text-sm text-red-600">
                              {item.error_message}
                            </span>
                          </TooltipTrigger>
                          <TooltipContent
                            side="bottom"
                            className="max-w-[400px] break-words"
                          >
                            {item.error_message}
                          </TooltipContent>
                        </Tooltip>
                      </TooltipProvider>
                    ) : (
                      <span className="text-sm text-muted-foreground">-</span>
                    )}
                  </TableCell>
                  <TableCell>
                    <div className="flex gap-1">
                      {item.status === "failed" && (
                        <Button
                          variant="outline"
                          size="sm"
                          onClick={() => onRetry(item)}
                          disabled={isRetrying}
                          title="Retry"
                        >
                          {isRetrying ? (
                            <Loader2 className="h-4 w-4 animate-spin" />
                          ) : (
                            <RefreshCw className="h-4 w-4" />
                          )}
                        </Button>
                      )}
                      {item.status === "pending" && (
                        <Button
                          variant="outline"
                          size="sm"
                          onClick={() => onCancel(item)}
                          disabled={isCancelling}
                          title="Cancel"
                        >
                          {isCancelling ? (
                            <Loader2 className="h-4 w-4 animate-spin" />
                          ) : (
                            <X className="h-4 w-4" />
                          )}
                        </Button>
                      )}
                    </div>
                  </TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        </div>
      )}

      {/* Pagination */}
      {total > pageSize && (
        <div className="flex items-center justify-end gap-2">
          <Button
            variant="outline"
            size="sm"
            onClick={() => onPageChange(page - 1)}
            disabled={page <= 1}
          >
            <ChevronLeft className="mr-1 h-4 w-4" />
            Previous
          </Button>
          <Button
            variant="outline"
            size="sm"
            onClick={() => onPageChange(page + 1)}
            disabled={!hasMore}
          >
            Next
            <ChevronRight className="ml-1 h-4 w-4" />
          </Button>
        </div>
      )}
    </div>
  );
}
