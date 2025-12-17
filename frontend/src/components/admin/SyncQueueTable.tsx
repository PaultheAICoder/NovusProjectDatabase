/**
 * SyncQueueTable component for displaying a table of sync queue items.
 * Includes filtering, pagination, and retry actions.
 */

import {
  ArrowLeftRight,
  Building2,
  ChevronLeft,
  ChevronRight,
  Loader2,
  RefreshCw,
  User,
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
import type {
  SyncQueueItem,
  SyncQueueStatus,
  SyncQueueDirection,
} from "@/types/monday";
import { cn } from "@/lib/utils";

interface SyncQueueTableProps {
  items: SyncQueueItem[];
  total: number;
  page: number;
  pageSize: number;
  hasMore: boolean;
  isLoading: boolean;
  entityTypeFilter: "contact" | "organization" | null;
  directionFilter: SyncQueueDirection | null;
  statusFilter: SyncQueueStatus | null;
  onEntityTypeFilterChange: (type: "contact" | "organization" | null) => void;
  onDirectionFilterChange: (direction: SyncQueueDirection | null) => void;
  onStatusFilterChange: (status: SyncQueueStatus | null) => void;
  onPageChange: (page: number) => void;
  onRetry: (item: SyncQueueItem) => void;
  isRetrying: boolean;
}

const statusColors: Record<SyncQueueStatus, string> = {
  pending: "bg-yellow-100 text-yellow-800 border-yellow-200",
  in_progress: "bg-blue-100 text-blue-800 border-blue-200",
  completed: "bg-green-100 text-green-800 border-green-200",
  failed: "bg-red-100 text-red-800 border-red-200",
};

const statusLabels: Record<SyncQueueStatus, string> = {
  pending: "Pending",
  in_progress: "In Progress",
  completed: "Completed",
  failed: "Failed",
};

const directionLabels: Record<SyncQueueDirection, string> = {
  to_monday: "To Monday",
  to_npd: "To NPD",
};

const operationLabels: Record<string, string> = {
  create: "Create",
  update: "Update",
  delete: "Delete",
};

export function SyncQueueTable({
  items,
  total,
  page,
  pageSize,
  hasMore,
  isLoading,
  entityTypeFilter,
  directionFilter,
  statusFilter,
  onEntityTypeFilterChange,
  onDirectionFilterChange,
  onStatusFilterChange,
  onPageChange,
  onRetry,
  isRetrying,
}: SyncQueueTableProps) {
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
          value={entityTypeFilter || "all"}
          onValueChange={(v) =>
            onEntityTypeFilterChange(
              v === "all" ? null : (v as "contact" | "organization")
            )
          }
        >
          <SelectTrigger className="w-[150px]">
            <SelectValue placeholder="Entity Type" />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value="all">All Types</SelectItem>
            <SelectItem value="contact">Contacts</SelectItem>
            <SelectItem value="organization">Organizations</SelectItem>
          </SelectContent>
        </Select>

        <Select
          value={directionFilter || "all"}
          onValueChange={(v) =>
            onDirectionFilterChange(
              v === "all" ? null : (v as SyncQueueDirection)
            )
          }
        >
          <SelectTrigger className="w-[150px]">
            <SelectValue placeholder="Direction" />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value="all">All Directions</SelectItem>
            <SelectItem value="to_monday">To Monday</SelectItem>
            <SelectItem value="to_npd">To NPD</SelectItem>
          </SelectContent>
        </Select>

        <Select
          value={statusFilter || "all"}
          onValueChange={(v) =>
            onStatusFilterChange(v === "all" ? null : (v as SyncQueueStatus))
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
            {statusFilter || directionFilter || entityTypeFilter
              ? "Try adjusting your filters."
              : "The sync queue is empty."}
          </p>
        </div>
      ) : (
        <div className="rounded-md border">
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead className="w-[100px]">Type</TableHead>
                <TableHead className="w-[100px]">Direction</TableHead>
                <TableHead className="w-[80px]">Operation</TableHead>
                <TableHead className="w-[100px]">Status</TableHead>
                <TableHead className="w-[80px]">Attempts</TableHead>
                <TableHead className="w-[120px]">Next Retry</TableHead>
                <TableHead>Error</TableHead>
                <TableHead className="w-[80px]">Action</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {items.map((item) => (
                <TableRow key={item.id}>
                  <TableCell>
                    <div className="flex items-center gap-2">
                      {item.entity_type === "organization" ? (
                        <Building2 className="h-4 w-4 text-muted-foreground" />
                      ) : (
                        <User className="h-4 w-4 text-muted-foreground" />
                      )}
                      <span className="text-sm capitalize">
                        {item.entity_type}
                      </span>
                    </div>
                  </TableCell>
                  <TableCell>
                    <div className="flex items-center gap-1">
                      <ArrowLeftRight className="h-3 w-3 text-muted-foreground" />
                      <span className="text-sm">
                        {directionLabels[item.direction]}
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
                    {item.status === "failed" && (
                      <Button
                        variant="outline"
                        size="sm"
                        onClick={() => onRetry(item)}
                        disabled={isRetrying}
                      >
                        {isRetrying ? (
                          <Loader2 className="h-4 w-4 animate-spin" />
                        ) : (
                          <RefreshCw className="h-4 w-4" />
                        )}
                      </Button>
                    )}
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
