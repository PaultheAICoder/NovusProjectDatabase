/**
 * ConflictDetail component for displaying a full conflict comparison in a dialog.
 * Shows side-by-side comparison with resolution options.
 */

import { useState } from "react";
import { AlertTriangle, Building2, Loader2, User, ExternalLink } from "lucide-react";
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
import type { ConflictResolutionType, SyncConflict } from "@/types/monday";
import { cn } from "@/lib/utils";

interface ConflictDetailProps {
  conflict: SyncConflict;
  isOpen: boolean;
  onClose: () => void;
  onResolve: (resolution: ConflictResolutionType) => void;
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

  const handleResolutionClick = (resolution: ConflictResolutionType) => {
    setConfirmingResolution(resolution);
  };

  const handleConfirmResolution = () => {
    if (confirmingResolution) {
      onResolve(confirmingResolution);
      setConfirmingResolution(null);
    }
  };

  const handleCancelConfirmation = () => {
    setConfirmingResolution(null);
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
            <AlertTriangle className="h-5 w-5 text-amber-500" />
            Resolve Sync Conflict
          </DialogTitle>
          <DialogDescription>
            Compare the NPD and Monday.com versions of this{" "}
            {conflict.entity_type} and choose which data to keep.
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
                  ) : (
                    <>
                      This will keep the Monday.com data and update NPD to match.
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
                      confirmingResolution === "keep_npd" ? "default" : "secondary"
                    }
                    onClick={handleConfirmResolution}
                    disabled={isResolving}
                  >
                    {isResolving && (
                      <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                    )}
                    Confirm{" "}
                    {confirmingResolution === "keep_npd"
                      ? "Keep NPD"
                      : "Keep Monday"}
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
            />
          ))}
        </div>

        {/* Resolution Actions */}
        <DialogFooter className="gap-2 sm:gap-0">
          <Button variant="outline" onClick={onClose} disabled={isResolving}>
            Cancel
          </Button>
          <div className="flex gap-2">
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
                confirmingResolution === "keep_monday" && "ring-2 ring-purple-300"
              )}
            >
              Keep Monday
            </Button>
          </div>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
