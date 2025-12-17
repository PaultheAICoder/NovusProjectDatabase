/**
 * Import preview component with editable rows.
 */

import { useState, useEffect, useCallback } from "react";
import {
  CheckCircle,
  XCircle,
  AlertTriangle,
  Sparkles,
  Loader2,
} from "lucide-react";
import { useDebounce } from "@/hooks/useDebounce";
import { useValidateRows } from "@/hooks/useImport";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { OrganizationSelectCombobox } from "@/components/forms/OrganizationCombobox";
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
import { useAllTags } from "@/hooks/useTags";
import type {
  ImportRowPreview,
  ImportRowUpdate,
  ImportRowValidation,
  ImportRowsValidateRequest,
} from "@/types/import";
import type { ProjectLocation, ProjectStatus } from "@/types/project";
import { cn } from "@/lib/utils";

const projectLocations: { value: ProjectLocation; label: string }[] = [
  { value: "headquarters", label: "Headquarters/HQ" },
  { value: "test_house", label: "Test House" },
  { value: "remote", label: "Remote" },
  { value: "client_site", label: "Client Site" },
  { value: "other", label: "Other" },
];

// Mapping of CSV location strings to enum values
const LOCATION_MAPPINGS: Record<string, ProjectLocation> = {
  "hq": "headquarters",
  "headquarters": "headquarters",
  "head quarters": "headquarters",
  "test house": "test_house",
  "test_house": "test_house",
  "testhouse": "test_house",
  "remote": "remote",
  "wfh": "remote",
  "work from home": "remote",
  "client site": "client_site",
  "client_site": "client_site",
  "on-site": "client_site",
  "onsite": "client_site",
  "other": "other",
};

const mapLocation = (loc: string | undefined): ProjectLocation | undefined => {
  if (!loc) return undefined;
  const normalized = loc.toLowerCase().trim();
  return LOCATION_MAPPINGS[normalized] || "other";
};

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
  const { data: allTags } = useAllTags();

  // Local state for editable rows
  const [editedRows, setEditedRows] = useState<Map<number, Partial<ImportRowUpdate>>>(
    new Map()
  );

  // Track validation results from revalidation
  const [revalidatedRows, setRevalidatedRows] = useState<
    Map<number, ImportRowValidation>
  >(new Map());

  // Initialize validation mutation
  const validateMutation = useValidateRows();

  // Debounce edited rows to avoid excessive API calls (500ms delay)
  const debouncedEditedRows = useDebounce(editedRows, 500);

  // Revalidate when edits are debounced
  useEffect(() => {
    // Clear revalidation results if no edits
    if (debouncedEditedRows.size === 0) {
      setRevalidatedRows(new Map());
      return;
    }

    // Build validation request from edited rows
    const rowsToValidate: ImportRowsValidateRequest = {
      rows: Array.from(debouncedEditedRows.entries()).map(([rowNum, edits]) => {
        const originalRow = rows.find((r) => r.row_number === rowNum);
        return {
          row_number: rowNum,
          name: edits.name ?? originalRow?.name,
          organization_id:
            edits.organization_id ?? originalRow?.resolved_organization_id,
          start_date: edits.start_date ?? originalRow?.start_date,
          end_date: edits.end_date ?? originalRow?.end_date,
          location:
            edits.location ??
            (originalRow?.location ? mapLocation(originalRow.location) : undefined),
        };
      }),
    };

    validateMutation.mutate(rowsToValidate, {
      onSuccess: (response) => {
        const newValidationMap = new Map<number, ImportRowValidation>();
        response.results.forEach((result) => {
          newValidationMap.set(result.row_number, result.validation);
        });
        setRevalidatedRows(newValidationMap);
      },
    });
    // eslint-disable-next-line react-hooks/exhaustive-deps -- validateMutation is stable
  }, [debouncedEditedRows, rows]);

  // Get current validation state for a row (revalidated or original)
  const getRowValidation = useCallback(
    (row: ImportRowPreview): ImportRowValidation => {
      // If row was edited and revalidated, use new validation
      if (revalidatedRows.has(row.row_number)) {
        return revalidatedRows.get(row.row_number)!;
      }
      // Otherwise use original validation
      return row.validation;
    },
    [revalidatedRows]
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
        // Map location - if edited, use directly; otherwise map from CSV string
        const mappedLocation = edited.location
          ? edited.location as ProjectLocation
          : mapLocation(row.location);
        // Preserve original location value as location_other if mapped to "other"
        const locationOther = mappedLocation === "other" && row.location
          ? row.location
          : undefined;

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
          location: mappedLocation,
          location_other: locationOther,
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

  // Calculate counts considering revalidation results
  const validCount = rows.filter((r) => getRowValidation(r).is_valid).length;
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
            {validateMutation.isPending && (
              <Badge variant="outline" className="gap-1">
                <Loader2 className="h-3 w-3 animate-spin" />
                Validating...
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
                    !getRowValidation(row).is_valid && "bg-red-50/50"
                  )}
                >
                  <TableCell className="font-mono text-xs">
                    {row.row_number}
                  </TableCell>
                  <TableCell>
                    {getRowValidation(row).is_valid ? (
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
                      <OrganizationSelectCombobox
                        value={
                          getEditedValue(
                            row.row_number,
                            "organization_id",
                            row.resolved_organization_id
                          ) || ""
                        }
                        onChange={(v) =>
                          updateRow(row.row_number, "organization_id", v)
                        }
                        placeholder="Select org..."
                        triggerClassName="h-8 w-[180px]"
                      />
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
                    <Select
                      value={
                        getEditedValue(row.row_number, "location", mapLocation(row.location)) || ""
                      }
                      onValueChange={(v) => updateRow(row.row_number, "location", v)}
                    >
                      <SelectTrigger className="h-8 w-[160px]">
                        <SelectValue placeholder="Select location" />
                      </SelectTrigger>
                      <SelectContent>
                        {projectLocations.map((loc) => (
                          <SelectItem key={loc.value} value={loc.value}>
                            {loc.label}
                          </SelectItem>
                        ))}
                      </SelectContent>
                    </Select>
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
                      {getRowValidation(row).errors.map((err, i) => (
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
                      {getRowValidation(row).warnings.map((warn, i) => (
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
