/**
 * ConflictList component for displaying a table of sync conflicts.
 * Includes filtering, pagination, and actions.
 */

import { Building2, ChevronLeft, ChevronRight, Eye, Loader2, User } from "lucide-react";
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
import type { SyncConflict } from "@/types/monday";

interface ConflictListProps {
  conflicts: SyncConflict[];
  total: number;
  page: number;
  pageSize: number;
  hasMore: boolean;
  isLoading: boolean;
  entityTypeFilter: "contact" | "organization" | null;
  onEntityTypeFilterChange: (type: "contact" | "organization" | null) => void;
  onPageChange: (page: number) => void;
  onViewConflict: (conflict: SyncConflict) => void;
}

export function ConflictList({
  conflicts,
  total,
  page,
  pageSize,
  hasMore,
  isLoading,
  entityTypeFilter,
  onEntityTypeFilterChange,
  onPageChange,
  onViewConflict,
}: ConflictListProps) {
  const startIndex = (page - 1) * pageSize + 1;
  const endIndex = Math.min(page * pageSize, total);

  // Get entity name from conflict data
  const getEntityName = (conflict: SyncConflict): string => {
    return (
      (conflict.npd_data.name as string) ||
      (conflict.monday_data.name as string) ||
      "Unknown"
    );
  };

  if (isLoading) {
    return (
      <div className="flex items-center justify-center py-12">
        <Loader2 className="h-6 w-6 animate-spin text-muted-foreground" />
      </div>
    );
  }

  return (
    <div className="space-y-4">
      {/* Filter */}
      <div className="flex items-center justify-between">
        <Select
          value={entityTypeFilter || "all"}
          onValueChange={(v) =>
            onEntityTypeFilterChange(v === "all" ? null : (v as "contact" | "organization"))
          }
        >
          <SelectTrigger className="w-[180px]">
            <SelectValue placeholder="Filter by type" />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value="all">All Types</SelectItem>
            <SelectItem value="contact">Contacts</SelectItem>
            <SelectItem value="organization">Organizations</SelectItem>
          </SelectContent>
        </Select>

        {total > 0 && (
          <div className="text-sm text-muted-foreground">
            Showing {startIndex}-{endIndex} of {total}
          </div>
        )}
      </div>

      {/* Table or Empty State */}
      {conflicts.length === 0 ? (
        <div className="rounded-md border bg-muted/30 py-12 text-center">
          <p className="text-muted-foreground">No conflicts to resolve</p>
          <p className="mt-1 text-sm text-muted-foreground">
            All sync conflicts have been resolved.
          </p>
        </div>
      ) : (
        <div className="rounded-md border">
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead className="w-[100px]">Type</TableHead>
                <TableHead>Name</TableHead>
                <TableHead className="w-[140px]">Conflicting Fields</TableHead>
                <TableHead className="w-[140px]">Detected</TableHead>
                <TableHead className="w-[100px]">Action</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {conflicts.map((conflict) => (
                <TableRow key={conflict.id}>
                  <TableCell>
                    <div className="flex items-center gap-2">
                      {conflict.entity_type === "organization" ? (
                        <Building2 className="h-4 w-4 text-muted-foreground" />
                      ) : (
                        <User className="h-4 w-4 text-muted-foreground" />
                      )}
                      <span className="capitalize text-sm">
                        {conflict.entity_type}
                      </span>
                    </div>
                  </TableCell>
                  <TableCell className="font-medium">
                    {getEntityName(conflict)}
                  </TableCell>
                  <TableCell>
                    <Badge variant="secondary">
                      {conflict.conflict_fields.length} field
                      {conflict.conflict_fields.length !== 1 ? "s" : ""}
                    </Badge>
                  </TableCell>
                  <TableCell className="text-sm text-muted-foreground">
                    {formatDistanceToNow(new Date(conflict.detected_at), {
                      addSuffix: true,
                    })}
                  </TableCell>
                  <TableCell>
                    <Button
                      variant="outline"
                      size="sm"
                      onClick={() => onViewConflict(conflict)}
                    >
                      <Eye className="mr-1 h-4 w-4" />
                      View
                    </Button>
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
