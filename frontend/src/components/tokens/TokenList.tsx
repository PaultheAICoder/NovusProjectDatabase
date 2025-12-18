/**
 * TokenList component - displays a table of API tokens with actions.
 */

import {
  ChevronLeft,
  ChevronRight,
  Edit,
  Key,
  Loader2,
  MoreHorizontal,
  Power,
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
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import type { APIToken } from "@/types/token";
import { cn } from "@/lib/utils";

interface TokenListProps {
  tokens: APIToken[];
  total: number;
  page: number;
  pageSize: number;
  isLoading: boolean;
  onPageChange: (page: number) => void;
  onRename: (token: APIToken) => void;
  onToggleActive: (token: APIToken) => void;
  onDelete: (token: APIToken) => void;
  isUpdating?: boolean;
  showUserColumn?: boolean; // For admin view
}

export function TokenList({
  tokens,
  total,
  page,
  pageSize,
  isLoading,
  onPageChange,
  onRename,
  onToggleActive,
  onDelete,
  isUpdating = false,
  showUserColumn = false,
}: TokenListProps) {
  const startIndex = (page - 1) * pageSize + 1;
  const endIndex = Math.min(page * pageSize, total);
  const hasMore = page * pageSize < total;

  if (isLoading) {
    return (
      <div className="flex items-center justify-center py-12">
        <Loader2 className="h-6 w-6 animate-spin text-muted-foreground" />
      </div>
    );
  }

  if (tokens.length === 0) {
    return (
      <div className="rounded-md border bg-muted/30 py-12 text-center">
        <Key className="mx-auto h-12 w-12 text-muted-foreground/50" />
        <p className="mt-4 text-muted-foreground">No API tokens found</p>
        <p className="mt-1 text-sm text-muted-foreground">
          Create a token to get started with API access.
        </p>
      </div>
    );
  }

  return (
    <div className="space-y-4">
      {/* Results count */}
      {total > 0 && (
        <div className="text-sm text-muted-foreground">
          Showing {startIndex}-{endIndex} of {total}
        </div>
      )}

      {/* Table */}
      <div className="rounded-md border">
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead>Name</TableHead>
              <TableHead className="w-[120px]">Prefix</TableHead>
              {showUserColumn && <TableHead className="w-[180px]">User</TableHead>}
              <TableHead className="w-[120px]">Created</TableHead>
              <TableHead className="w-[120px]">Last Used</TableHead>
              <TableHead className="w-[100px]">Status</TableHead>
              <TableHead className="w-[80px]">Actions</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {tokens.map((token) => (
              <TableRow key={token.id}>
                <TableCell>
                  <div className="flex items-center gap-2">
                    <Key className="h-4 w-4 text-muted-foreground" />
                    <span className="font-medium">{token.name}</span>
                  </div>
                </TableCell>
                <TableCell>
                  <code className="rounded bg-muted px-2 py-1 text-xs">
                    {token.token_prefix}...
                  </code>
                </TableCell>
                {showUserColumn && (
                  <TableCell className="text-sm text-muted-foreground">
                    {/* User info would come from joined data in admin view */}
                    -
                  </TableCell>
                )}
                <TableCell className="text-sm text-muted-foreground">
                  {formatDistanceToNow(new Date(token.created_at), { addSuffix: true })}
                </TableCell>
                <TableCell className="text-sm text-muted-foreground">
                  {token.last_used_at
                    ? formatDistanceToNow(new Date(token.last_used_at), { addSuffix: true })
                    : "Never"}
                </TableCell>
                <TableCell>
                  <Badge
                    variant="outline"
                    className={cn(
                      "text-xs",
                      token.is_active
                        ? "border-green-200 bg-green-100 text-green-800"
                        : "border-gray-200 bg-gray-100 text-gray-800",
                    )}
                  >
                    {token.is_active ? "Active" : "Revoked"}
                  </Badge>
                </TableCell>
                <TableCell>
                  <DropdownMenu>
                    <DropdownMenuTrigger asChild>
                      <Button variant="ghost" size="sm" disabled={isUpdating}>
                        {isUpdating ? (
                          <Loader2 className="h-4 w-4 animate-spin" />
                        ) : (
                          <MoreHorizontal className="h-4 w-4" />
                        )}
                      </Button>
                    </DropdownMenuTrigger>
                    <DropdownMenuContent align="end">
                      <DropdownMenuItem onClick={() => onRename(token)}>
                        <Edit className="mr-2 h-4 w-4" />
                        Rename
                      </DropdownMenuItem>
                      <DropdownMenuItem onClick={() => onToggleActive(token)}>
                        <Power className="mr-2 h-4 w-4" />
                        {token.is_active ? "Revoke" : "Activate"}
                      </DropdownMenuItem>
                      <DropdownMenuSeparator />
                      <DropdownMenuItem
                        onClick={() => onDelete(token)}
                        className="text-destructive"
                      >
                        <Trash2 className="mr-2 h-4 w-4" />
                        Delete
                      </DropdownMenuItem>
                    </DropdownMenuContent>
                  </DropdownMenu>
                </TableCell>
              </TableRow>
            ))}
          </TableBody>
        </Table>
      </div>

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
