/**
 * Import preview component with editable rows.
 */

import { useState } from "react";
import {
  CheckCircle,
  XCircle,
  AlertTriangle,
  Sparkles,
  Loader2,
} from "lucide-react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { Badge } from "@/components/ui/badge";
import {
  Tooltip,
  TooltipContent,
  TooltipProvider,
  TooltipTrigger,
} from "@/components/ui/tooltip";
import { useOrganizations } from "@/hooks/useOrganizations";
import { useAllTags } from "@/hooks/useTags";
import type { ImportRowPreview, ImportRowUpdate } from "@/types/import";
import type { ProjectStatus } from "@/types/project";
import { cn } from "@/lib/utils";

const statusOptions: { value: ProjectStatus; label: string }[] = [
  { value: "approved", label: "Approved" },
  { value: "active", label: "Active" },
  { value: "on_hold", label: "On Hold" },
  { value: "completed", label: "Completed" },
  { value: "cancelled", label: "Cancelled" },
];

interface ImportPreviewProps {
  rows: ImportRowPreview[];
  onRowsChange: (rows: ImportRowUpdate[]) => void;
  onCommit: () => void;
  isCommitting?: boolean;
}

export function ImportPreview({
  rows,
  onRowsChange,
  onCommit,
  isCommitting = false,
}: ImportPreviewProps) {
  const { data: orgsData } = useOrganizations({ pageSize: 100 });
  const { data: allTags } = useAllTags();

  // Local state for editable rows
  const [editedRows, setEditedRows] = useState<Map<number, Partial<ImportRowUpdate>>>(
    new Map()
  );

  const getEditedValue = <K extends keyof ImportRowUpdate>(
    rowNum: number,
    field: K,
    originalValue: ImportRowPreview[keyof ImportRowPreview]
  ): ImportRowUpdate[K] | undefined => {
    const edited = editedRows.get(rowNum);
    if (edited && field in edited) {
      return edited[field] as ImportRowUpdate[K];
    }
    return originalValue as ImportRowUpdate[K];
  };

  const updateRow = (rowNum: number, field: keyof ImportRowUpdate, value: unknown) => {
    setEditedRows((prev) => {
      const newMap = new Map(prev);
      const existing = newMap.get(rowNum) || {};
      newMap.set(rowNum, { ...existing, [field]: value });
      return newMap;
    });
  };

  const applySuggestion = (row: ImportRowPreview, field: string) => {
    if (!row.suggestions) return;

    if (field === "organization" && row.suggestions.suggested_organization_id) {
      updateRow(row.row_number, "organization_id", row.suggestions.suggested_organization_id);
    } else if (field === "tags" && row.suggestions.suggested_tags) {
      // Find tag IDs for suggested tags
      const tagIds = row.suggestions.suggested_tags
        .map((name) => allTags?.find((t) => t.name === name)?.id)
        .filter((id): id is string => !!id);
      updateRow(row.row_number, "tag_ids", tagIds);
    }
  };

  const handleCommit = () => {
    const updatedRows: ImportRowUpdate[] = rows
      .filter((row) => row.validation.is_valid || editedRows.has(row.row_number))
      .map((row) => {
        const edited = editedRows.get(row.row_number) || {};
        return {
          row_number: row.row_number,
          name: edited.name ?? row.name,
          organization_id:
            edited.organization_id ?? row.resolved_organization_id,
          owner_id: edited.owner_id ?? row.resolved_owner_id,
          description: edited.description ?? row.description,
          status: (edited.status ?? row.status?.toLowerCase()) as ProjectStatus,
          start_date: edited.start_date ?? row.start_date,
          end_date: edited.end_date ?? row.end_date,
          location: edited.location ?? row.location,
          tag_ids: edited.tag_ids ?? row.resolved_tag_ids,
          billing_amount: edited.billing_amount,
          billing_recipient: edited.billing_recipient ?? row.billing_recipient,
          billing_notes: edited.billing_notes ?? row.billing_notes,
          pm_notes: edited.pm_notes ?? row.pm_notes,
          monday_url: edited.monday_url ?? row.monday_url,
          jira_url: edited.jira_url ?? row.jira_url,
          gitlab_url: edited.gitlab_url ?? row.gitlab_url,
        };
      });

    onRowsChange(updatedRows);
    onCommit();
  };

  const validCount = rows.filter((r) => r.validation.is_valid).length;
  const invalidCount = rows.length - validCount;

  return (
    <TooltipProvider>
      <div className="space-y-4">
        {/* Summary */}
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-4">
            <Badge variant="outline" className="gap-1">
              <CheckCircle className="h-3 w-3 text-green-600" />
              {validCount} valid
            </Badge>
            {invalidCount > 0 && (
              <Badge variant="outline" className="gap-1">
                <XCircle className="h-3 w-3 text-red-600" />
                {invalidCount} invalid
              </Badge>
            )}
          </div>
          <Button onClick={handleCommit} disabled={isCommitting || validCount === 0}>
            {isCommitting ? (
              <>
                <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                Importing...
              </>
            ) : (
              `Import ${validCount} Projects`
            )}
          </Button>
        </div>

        {/* Table */}
        <div className="rounded-md border overflow-auto max-h-[600px]">
          <Table>
            <TableHeader className="sticky top-0 bg-background">
              <TableRow>
                <TableHead className="w-[50px]">#</TableHead>
                <TableHead className="w-[80px]">Status</TableHead>
                <TableHead>Name</TableHead>
                <TableHead>Organization</TableHead>
                <TableHead>Start Date</TableHead>
                <TableHead>Location</TableHead>
                <TableHead>Tags</TableHead>
                <TableHead className="w-[100px]">Validation</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {rows.map((row) => (
                <TableRow
                  key={row.row_number}
                  className={cn(
                    !row.validation.is_valid && "bg-red-50/50"
                  )}
                >
                  <TableCell className="font-mono text-xs">
                    {row.row_number}
                  </TableCell>
                  <TableCell>
                    {row.validation.is_valid ? (
                      <CheckCircle className="h-4 w-4 text-green-600" />
                    ) : (
                      <XCircle className="h-4 w-4 text-red-600" />
                    )}
                  </TableCell>
                  <TableCell>
                    <Input
                      value={getEditedValue(row.row_number, "name", row.name) || ""}
                      onChange={(e) =>
                        updateRow(row.row_number, "name", e.target.value)
                      }
                      className="h-8"
                    />
                  </TableCell>
                  <TableCell>
                    <div className="flex items-center gap-1">
                      <Select
                        value={
                          getEditedValue(
                            row.row_number,
                            "organization_id",
                            row.resolved_organization_id
                          ) || ""
                        }
                        onValueChange={(v) =>
                          updateRow(row.row_number, "organization_id", v)
                        }
                      >
                        <SelectTrigger className="h-8 w-[180px]">
                          <SelectValue placeholder="Select org..." />
                        </SelectTrigger>
                        <SelectContent>
                          {orgsData?.items.map((org) => (
                            <SelectItem key={org.id} value={org.id}>
                              {org.name}
                            </SelectItem>
                          ))}
                        </SelectContent>
                      </Select>
                      {row.suggestions?.suggested_organization_id && (
                        <Tooltip>
                          <TooltipTrigger asChild>
                            <Button
                              variant="ghost"
                              size="icon"
                              className="h-8 w-8"
                              onClick={() => applySuggestion(row, "organization")}
                            >
                              <Sparkles className="h-4 w-4 text-amber-500" />
                            </Button>
                          </TooltipTrigger>
                          <TooltipContent>Apply AI suggestion</TooltipContent>
                        </Tooltip>
                      )}
                    </div>
                  </TableCell>
                  <TableCell>
                    <Input
                      type="date"
                      value={
                        getEditedValue(row.row_number, "start_date", row.start_date) ||
                        ""
                      }
                      onChange={(e) =>
                        updateRow(row.row_number, "start_date", e.target.value)
                      }
                      className="h-8 w-[140px]"
                    />
                  </TableCell>
                  <TableCell>
                    <Input
                      value={
                        getEditedValue(row.row_number, "location", row.location) || ""
                      }
                      onChange={(e) =>
                        updateRow(row.row_number, "location", e.target.value)
                      }
                      className="h-8"
                      placeholder="Required"
                    />
                  </TableCell>
                  <TableCell>
                    <div className="flex flex-wrap gap-1">
                      {row.tags?.slice(0, 3).map((tag, i) => (
                        <Badge key={i} variant="secondary" className="text-xs">
                          {tag}
                        </Badge>
                      ))}
                      {row.tags && row.tags.length > 3 && (
                        <Badge variant="secondary" className="text-xs">
                          +{row.tags.length - 3}
                        </Badge>
                      )}
                      {row.suggestions?.suggested_tags &&
                        row.suggestions.suggested_tags.length > 0 && (
                          <Tooltip>
                            <TooltipTrigger asChild>
                              <Button
                                variant="ghost"
                                size="icon"
                                className="h-6 w-6"
                                onClick={() => applySuggestion(row, "tags")}
                              >
                                <Sparkles className="h-3 w-3 text-amber-500" />
                              </Button>
                            </TooltipTrigger>
                            <TooltipContent>
                              Suggested: {row.suggestions.suggested_tags.join(", ")}
                            </TooltipContent>
                          </Tooltip>
                        )}
                    </div>
                  </TableCell>
                  <TableCell>
                    <div className="flex flex-col gap-1">
                      {row.validation.errors.map((err, i) => (
                        <Tooltip key={i}>
                          <TooltipTrigger asChild>
                            <div className="flex items-center gap-1 text-xs text-red-600">
                              <XCircle className="h-3 w-3" />
                              <span className="truncate max-w-[80px]">{err}</span>
                            </div>
                          </TooltipTrigger>
                          <TooltipContent>{err}</TooltipContent>
                        </Tooltip>
                      ))}
                      {row.validation.warnings.map((warn, i) => (
                        <Tooltip key={i}>
                          <TooltipTrigger asChild>
                            <div className="flex items-center gap-1 text-xs text-amber-600">
                              <AlertTriangle className="h-3 w-3" />
                              <span className="truncate max-w-[80px]">{warn}</span>
                            </div>
                          </TooltipTrigger>
                          <TooltipContent>{warn}</TooltipContent>
                        </Tooltip>
                      ))}
                    </div>
                  </TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        </div>
      </div>
    </TooltipProvider>
  );
}
