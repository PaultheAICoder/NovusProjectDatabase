/**
 * SynonymTable component for displaying a table of tag synonym relationships.
 * Includes pagination and delete actions.
 */

import {
  ArrowLeftRight,
  ChevronLeft,
  ChevronRight,
  Loader2,
  Trash2,
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
import type { TagSynonymDetail, TagType } from "@/types/tag";
import { cn } from "@/lib/utils";

interface SynonymTableProps {
  items: TagSynonymDetail[];
  total: number;
  page: number;
  pageSize: number;
  hasMore: boolean;
  isLoading: boolean;
  onPageChange: (page: number) => void;
  onDelete: (item: TagSynonymDetail) => void;
  isDeleting: boolean;
}

const tagTypeColors: Record<TagType, string> = {
  technology: "bg-blue-100 text-blue-800 border-blue-200",
  domain: "bg-green-100 text-green-800 border-green-200",
  test_type: "bg-purple-100 text-purple-800 border-purple-200",
  freeform: "bg-gray-100 text-gray-800 border-gray-200",
};

const tagTypeLabels: Record<TagType, string> = {
  technology: "Technology",
  domain: "Domain",
  test_type: "Test Type",
  freeform: "Custom",
};

export function SynonymTable({
  items,
  total,
  page,
  pageSize,
  hasMore,
  isLoading,
  onPageChange,
  onDelete,
  isDeleting,
}: SynonymTableProps) {
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
      {/* Info bar */}
      {total > 0 && (
        <div className="text-sm text-muted-foreground">
          Showing {startIndex}-{endIndex} of {total}
        </div>
      )}

      {/* Table or Empty State */}
      {items.length === 0 ? (
        <div className="rounded-md border bg-muted/30 py-12 text-center">
          <p className="text-muted-foreground">No synonym relationships found</p>
          <p className="mt-1 text-sm text-muted-foreground">
            Create a synonym to link similar tags together.
          </p>
        </div>
      ) : (
        <div className="rounded-md border">
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>Primary Tag</TableHead>
                <TableHead className="w-[50px]"></TableHead>
                <TableHead>Synonym Tag</TableHead>
                <TableHead className="w-[100px]">Confidence</TableHead>
                <TableHead className="w-[120px]">Created</TableHead>
                <TableHead className="w-[80px]">Action</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {items.map((item) => (
                <TableRow key={item.id}>
                  <TableCell>
                    <div className="flex items-center gap-2">
                      <Badge
                        variant="outline"
                        className={cn("text-xs", tagTypeColors[item.tag.type])}
                      >
                        {tagTypeLabels[item.tag.type]}
                      </Badge>
                      <span className="font-medium">{item.tag.name}</span>
                    </div>
                  </TableCell>
                  <TableCell>
                    <ArrowLeftRight className="h-4 w-4 text-muted-foreground" />
                  </TableCell>
                  <TableCell>
                    <div className="flex items-center gap-2">
                      <Badge
                        variant="outline"
                        className={cn("text-xs", tagTypeColors[item.synonym_tag.type])}
                      >
                        {tagTypeLabels[item.synonym_tag.type]}
                      </Badge>
                      <span className="font-medium">{item.synonym_tag.name}</span>
                    </div>
                  </TableCell>
                  <TableCell>
                    <span
                      className={cn(
                        "text-sm",
                        item.confidence >= 1.0
                          ? "text-green-600 font-medium"
                          : "text-muted-foreground"
                      )}
                    >
                      {(item.confidence * 100).toFixed(0)}%
                    </span>
                  </TableCell>
                  <TableCell className="text-sm text-muted-foreground">
                    {formatDistanceToNow(new Date(item.created_at), {
                      addSuffix: true,
                    })}
                  </TableCell>
                  <TableCell>
                    <Button
                      variant="ghost"
                      size="sm"
                      onClick={() => onDelete(item)}
                      disabled={isDeleting}
                    >
                      {isDeleting ? (
                        <Loader2 className="h-4 w-4 animate-spin" />
                      ) : (
                        <Trash2 className="h-4 w-4 text-destructive" />
                      )}
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
