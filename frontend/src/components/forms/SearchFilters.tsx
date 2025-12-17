/**
 * Search filters component.
 */

import { useState } from "react";
import { X } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { TagFilterCombobox } from "@/components/forms/TagFilterCombobox";
import { OrganizationFilterCombobox } from "@/components/forms/OrganizationCombobox";
import { StatusFilterMultiSelect } from "@/components/forms/StatusFilterMultiSelect";
import { useAllTags } from "@/hooks/useTags";
import type { Organization } from "@/types/organization";
import type { ProjectStatus } from "@/types/project";

const statusOptions: { value: ProjectStatus; label: string }[] = [
  { value: "approved", label: "Approved" },
  { value: "active", label: "Active" },
  { value: "on_hold", label: "On Hold" },
  { value: "completed", label: "Completed" },
  { value: "cancelled", label: "Cancelled" },
];

interface SearchFiltersProps {
  status: ProjectStatus[];
  organizationId: string | undefined;
  tagIds: string[];
  onStatusChange: (status: ProjectStatus[]) => void;
  onOrganizationChange: (orgId: string | undefined) => void;
  onTagsChange: (tagIds: string[]) => void;
  onClearAll: () => void;
}

export function SearchFilters({
  status,
  organizationId,
  tagIds,
  onStatusChange,
  onOrganizationChange,
  onTagsChange,
  onClearAll,
}: SearchFiltersProps) {
  // Track selected organization for display in badge
  const [selectedOrg, setSelectedOrg] = useState<Organization | null>(null);
  // Keep useAllTags for badge display
  const { data: allTags } = useAllTags();

  // Wrapper for org selection to track the selected org name
  const handleOrganizationSelect = (id: string | undefined, org?: Organization) => {
    if (org) {
      setSelectedOrg(org);
    } else if (!id) {
      setSelectedOrg(null);
    }
    onOrganizationChange(id);
  };

  const hasFilters =
    status.length > 0 || organizationId !== undefined || tagIds.length > 0;

  const handleTagToggle = (tagId: string) => {
    if (tagIds.includes(tagId)) {
      onTagsChange(tagIds.filter((id) => id !== tagId));
    } else {
      onTagsChange([...tagIds, tagId]);
    }
  };

  const removeStatus = (s: ProjectStatus) => {
    onStatusChange(status.filter((st) => st !== s));
  };

  const removeTag = (tagId: string) => {
    onTagsChange(tagIds.filter((id) => id !== tagId));
  };

  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-center gap-4">
        <StatusFilterMultiSelect
          selectedStatuses={status}
          onStatusToggle={(statusValue) => {
            if (status.includes(statusValue)) {
              onStatusChange(status.filter((s) => s !== statusValue));
            } else {
              onStatusChange([...status, statusValue]);
            }
          }}
          placeholder="Status"
        />

        <OrganizationFilterCombobox
          selectedId={organizationId}
          onSelect={handleOrganizationSelect}
          placeholder="Organization"
          showAllOption={true}
        />

        <TagFilterCombobox
          selectedTagIds={tagIds}
          onTagToggle={handleTagToggle}
          placeholder="Tags"
        />

        {hasFilters && (
          <Button variant="ghost" size="sm" onClick={onClearAll}>
            Clear all
          </Button>
        )}
      </div>

      {hasFilters && (
        <div className="flex flex-wrap gap-2">
          {status.map((s) => (
            <Badge key={s} variant="secondary" className="gap-1">
              {statusOptions.find((opt) => opt.value === s)?.label}
              <button
                onClick={() => removeStatus(s)}
                className="ml-1 rounded-full hover:bg-muted"
              >
                <X className="h-3 w-3" />
              </button>
            </Badge>
          ))}
          {organizationId && selectedOrg && (
            <Badge variant="secondary" className="gap-1">
              {selectedOrg.name}
              <button
                onClick={() => handleOrganizationSelect(undefined)}
                className="ml-1 rounded-full hover:bg-muted"
              >
                <X className="h-3 w-3" />
              </button>
            </Badge>
          )}
          {tagIds.map((tagId) => {
            const tag = allTags?.find((t) => t.id === tagId);
            return tag ? (
              <Badge key={tagId} variant="secondary" className="gap-1">
                {tag.name}
                <button
                  onClick={() => removeTag(tagId)}
                  className="ml-1 rounded-full hover:bg-muted"
                >
                  <X className="h-3 w-3" />
                </button>
              </Badge>
            ) : null;
          })}
        </div>
      )}
    </div>
  );
}
