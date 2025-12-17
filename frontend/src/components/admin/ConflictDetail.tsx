/**
 * ConflictDetail component for displaying a full conflict comparison in a dialog.
 * Shows side-by-side comparison with resolution options including field-level merge.
 */

import { useState, useEffect } from "react";
import {
  AlertTriangle,
  Building2,
  Loader2,
  User,
  ExternalLink,
  GitMerge,
  X,
} from "lucide-react";
import { Link } from "react-router-dom";
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogFooter,
  DialogDescription,
} from "@/components/ui/dialog";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { FieldDiffViewer } from "./FieldDiffViewer";
import { formatFieldLabel } from "./conflict-utils";
import type { ConflictResolutionType, SyncConflict } from "@/types/monday";
import { cn } from "@/lib/utils";

interface ConflictDetailProps {
  conflict: SyncConflict;
  isOpen: boolean;
  onClose: () => void;
  onResolve: (
    resolution: ConflictResolutionType,
    mergeSelections?: Record<string, "npd" | "monday">
  ) => void;
  isResolving: boolean;
}

export function ConflictDetail({
  conflict,
  isOpen,
  onClose,
  onResolve,
  isResolving,
}: ConflictDetailProps) {
  const [confirmingResolution, setConfirmingResolution] =
    useState<ConflictResolutionType | null>(null);

  // Merge mode state
  const [mergeMode, setMergeMode] = useState(false);
  const [fieldSelections, setFieldSelections] = useState<
    Record<string, "npd" | "monday">
  >({});

  // Reset state when dialog closes or conflict changes
  useEffect(() => {
    if (!isOpen) {
      setMergeMode(false);
      setFieldSelections({});
      setConfirmingResolution(null);
    }
  }, [isOpen]);

  useEffect(() => {
    // Reset when conflict changes
    setMergeMode(false);
    setFieldSelections({});
    setConfirmingResolution(null);
  }, [conflict.id]);

  // Get entity name from NPD data
  const entityName =
    (conflict.npd_data.name as string) ||
    (conflict.monday_data.name as string) ||
    "Unknown";

  // Get all unique fields from both data sources
  const allFields = new Set<string>([
    ...Object.keys(conflict.npd_data),
    ...Object.keys(conflict.monday_data),
  ]);

  // Sort fields: conflicting fields first, then alphabetically
  const sortedFields = Array.from(allFields).sort((a, b) => {
    const aIsConflict = conflict.conflict_fields.includes(a);
    const bIsConflict = conflict.conflict_fields.includes(b);
    if (aIsConflict && !bIsConflict) return -1;
    if (!aIsConflict && bIsConflict) return 1;
    return a.localeCompare(b);
  });

  // Check if all conflicting fields have a selection
  const allFieldsSelected = conflict.conflict_fields.every(
    (field) => fieldSelections[field] !== undefined
  );

  // Count of selected fields
  const selectedCount = Object.keys(fieldSelections).length;
  const totalConflictFields = conflict.conflict_fields.length;

  // Get fields that still need selection
  const unselectedFields = conflict.conflict_fields.filter(
    (field) => fieldSelections[field] === undefined
  );

  const handleFieldSelect = (field: string, source: "npd" | "monday") => {
    setFieldSelections((prev) => ({ ...prev, [field]: source }));
  };

  const handleResolutionClick = (resolution: ConflictResolutionType) => {
    setConfirmingResolution(resolution);
  };

  const handleConfirmResolution = () => {
    if (confirmingResolution) {
      if (confirmingResolution === "merge") {
        onResolve(confirmingResolution, fieldSelections);
      } else {
        onResolve(confirmingResolution);
      }
      setConfirmingResolution(null);
    }
  };

  const handleCancelConfirmation = () => {
    setConfirmingResolution(null);
  };

  const handleToggleMergeMode = () => {
    if (mergeMode) {
      // Exiting merge mode - clear selections
      setFieldSelections({});
      setConfirmingResolution(null);
    }
    setMergeMode(!mergeMode);
  };

  const handleApplyMerge = () => {
    if (allFieldsSelected) {
      setConfirmingResolution("merge");
    }
  };

  // Build the entity link
  const entityLink =
    conflict.entity_type === "contact"
      ? `/contacts/${conflict.entity_id}`
      : `/organizations/${conflict.entity_id}`;

  return (
    <Dialog open={isOpen} onOpenChange={(open) => !open && onClose()}>
      <DialogContent className="max-h-[90vh] max-w-4xl overflow-y-auto">
        <DialogHeader>
          <DialogTitle className="flex items-center gap-2">
            {mergeMode ? (
              <>
                <GitMerge className="h-5 w-5 text-green-600" />
                Merge Fields
              </>
            ) : (
              <>
                <AlertTriangle className="h-5 w-5 text-amber-500" />
                Resolve Sync Conflict
              </>
            )}
          </DialogTitle>
          <DialogDescription>
            {mergeMode ? (
              <>
                Select which source to use for each conflicting field. Click on
                the NPD or Monday.com value to select it.
              </>
            ) : (
              <>
                Compare the NPD and Monday.com versions of this{" "}
                {conflict.entity_type} and choose which data to keep.
              </>
            )}
          </DialogDescription>
        </DialogHeader>

        {/* Entity Header */}
        <div className="rounded-md border bg-muted/50 p-4">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-3">
              {conflict.entity_type === "organization" ? (
                <Building2 className="h-5 w-5 text-muted-foreground" />
              ) : (
                <User className="h-5 w-5 text-muted-foreground" />
              )}
              <div>
                <div className="font-medium">{entityName}</div>
                <div className="flex items-center gap-2 text-sm text-muted-foreground">
                  <Badge variant="outline" className="capitalize">
                    {conflict.entity_type}
                  </Badge>
                  <span>
                    {conflict.conflict_fields.length} conflicting field
                    {conflict.conflict_fields.length !== 1 ? "s" : ""}
                  </span>
                </div>
              </div>
            </div>
            <Link to={entityLink}>
              <Button variant="outline" size="sm">
                <ExternalLink className="mr-2 h-4 w-4" />
                View in NPD
              </Button>
            </Link>
          </div>
        </div>

        {/* Merge Mode Instructions */}
        {mergeMode && (
          <div className="rounded-md border border-blue-200 bg-blue-50 p-4">
            <div className="flex items-start gap-3">
              <GitMerge className="mt-0.5 h-5 w-5 text-blue-600" />
              <div className="flex-1">
                <div className="font-medium text-blue-800">
                  Field Selection Mode
                </div>
                <p className="mt-1 text-sm text-blue-700">
                  Click on the NPD (blue) or Monday.com (purple) value for each
                  conflicting field to select which value to keep. You must
                  select a source for all {totalConflictFields} conflicting
                  field{totalConflictFields !== 1 ? "s" : ""} before applying
                  the merge.
                </p>
              </div>
            </div>
          </div>
        )}

        {/* Merge Preview */}
        {mergeMode && selectedCount > 0 && (
          <div className="rounded-md border border-green-200 bg-green-50 p-4">
            <div className="mb-2 text-sm font-medium text-green-800">
              Merge Preview ({selectedCount}/{totalConflictFields} selected)
            </div>
            <div className="space-y-1 text-sm text-green-700">
              {Object.entries(fieldSelections).map(([field, source]) => (
                <div key={field} className="flex items-center gap-2">
                  <span className="font-medium">{formatFieldLabel(field)}:</span>
                  <span
                    className={cn(
                      "rounded px-1.5 py-0.5 text-xs font-medium",
                      source === "npd"
                        ? "bg-blue-100 text-blue-700"
                        : "bg-purple-100 text-purple-700"
                    )}
                  >
                    {source === "npd" ? "NPD" : "Monday.com"}
                  </span>
                </div>
              ))}
            </div>
            {unselectedFields.length > 0 && (
              <div className="mt-2 text-xs text-green-600">
                Still need to select:{" "}
                {unselectedFields.map((f) => formatFieldLabel(f)).join(", ")}
              </div>
            )}
          </div>
        )}

        {/* Confirmation Dialog */}
        {confirmingResolution && (
          <div className="rounded-md border border-amber-200 bg-amber-50 p-4">
            <div className="flex items-start gap-3">
              <AlertTriangle className="mt-0.5 h-5 w-5 text-amber-600" />
              <div className="flex-1">
                <div className="font-medium text-amber-800">
                  Confirm Resolution
                </div>
                <p className="mt-1 text-sm text-amber-700">
                  {confirmingResolution === "keep_npd" ? (
                    <>
                      This will keep the NPD data and update Monday.com to match.
                      This action cannot be undone.
                    </>
                  ) : confirmingResolution === "keep_monday" ? (
                    <>
                      This will keep the Monday.com data and update NPD to match.
                      This action cannot be undone.
                    </>
                  ) : (
                    <>
                      This will merge the selected field values. NPD will be
                      updated with the merged result and synced to Monday.com.
                      This action cannot be undone.
                    </>
                  )}
                </p>
                <div className="mt-3 flex gap-2">
                  <Button
                    size="sm"
                    variant="outline"
                    onClick={handleCancelConfirmation}
                    disabled={isResolving}
                  >
                    Cancel
                  </Button>
                  <Button
                    size="sm"
                    variant={
                      confirmingResolution === "keep_npd"
                        ? "default"
                        : confirmingResolution === "merge"
                          ? "default"
                          : "secondary"
                    }
                    onClick={handleConfirmResolution}
                    disabled={isResolving}
                    className={cn(
                      confirmingResolution === "merge" &&
                        "bg-green-600 hover:bg-green-700"
                    )}
                  >
                    {isResolving && (
                      <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                    )}
                    Confirm{" "}
                    {confirmingResolution === "keep_npd"
                      ? "Keep NPD"
                      : confirmingResolution === "keep_monday"
                        ? "Keep Monday"
                        : "Apply Merge"}
                  </Button>
                </div>
              </div>
            </div>
          </div>
        )}

        {/* Field Comparisons */}
        <div className="space-y-3">
          <div className="text-sm font-medium text-muted-foreground">
            Field Comparison
          </div>
          {sortedFields.map((field) => (
            <FieldDiffViewer
              key={field}
              fieldName={field}
              npdValue={conflict.npd_data[field]}
              mondayValue={conflict.monday_data[field]}
              isDifferent={conflict.conflict_fields.includes(field)}
              selectable={mergeMode && conflict.conflict_fields.includes(field)}
              selected={fieldSelections[field] ?? null}
              onSelect={(source) => handleFieldSelect(field, source)}
            />
          ))}
        </div>

        {/* Resolution Actions */}
        <DialogFooter className="gap-2 sm:gap-0">
          {mergeMode ? (
            // Merge mode footer
            <>
              <Button
                variant="outline"
                onClick={handleToggleMergeMode}
                disabled={isResolving}
              >
                <X className="mr-2 h-4 w-4" />
                Exit Merge
              </Button>
              <Button
                variant="default"
                onClick={handleApplyMerge}
                disabled={
                  isResolving ||
                  !allFieldsSelected ||
                  confirmingResolution !== null
                }
                className="bg-green-600 hover:bg-green-700"
              >
                <GitMerge className="mr-2 h-4 w-4" />
                Apply Merge
                {!allFieldsSelected && (
                  <span className="ml-1 text-xs opacity-80">
                    ({selectedCount}/{totalConflictFields})
                  </span>
                )}
              </Button>
            </>
          ) : (
            // Normal mode footer
            <>
              <Button variant="outline" onClick={onClose} disabled={isResolving}>
                Cancel
              </Button>
              <div className="flex gap-2">
                <Button
                  variant="outline"
                  onClick={handleToggleMergeMode}
                  disabled={isResolving || confirmingResolution !== null}
                >
                  <GitMerge className="mr-2 h-4 w-4" />
                  Merge Fields
                </Button>
                <Button
                  variant="default"
                  onClick={() => handleResolutionClick("keep_npd")}
                  disabled={isResolving || confirmingResolution !== null}
                  className={cn(
                    "bg-blue-600 hover:bg-blue-700",
                    confirmingResolution === "keep_npd" && "ring-2 ring-blue-300"
                  )}
                >
                  Keep NPD
                </Button>
                <Button
                  variant="secondary"
                  onClick={() => handleResolutionClick("keep_monday")}
                  disabled={isResolving || confirmingResolution !== null}
                  className={cn(
                    "bg-purple-600 text-white hover:bg-purple-700",
                    confirmingResolution === "keep_monday" &&
                      "ring-2 ring-purple-300"
                  )}
                >
                  Keep Monday
                </Button>
              </div>
            </>
          )}
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
