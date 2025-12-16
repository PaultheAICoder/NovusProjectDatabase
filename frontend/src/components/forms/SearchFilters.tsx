/**
 * Search filters component.
 */

import { X } from "lucide-react";
import { Button } from "@/components/ui/button";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { Badge } from "@/components/ui/badge";
import { TagFilterCombobox } from "@/components/forms/TagFilterCombobox";
import { OrganizationFilterCombobox } from "@/components/forms/OrganizationCombobox";
import { useOrganizations } from "@/hooks/useOrganizations";
import { useAllTags } from "@/hooks/useTags";
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
  const { data: orgsData } = useOrganizations({ pageSize: 100 });
  const { data: allTags } = useAllTags();

  const hasFilters =
    status.length > 0 || organizationId !== undefined || tagIds.length > 0;

  const handleStatusChange = (value: string) => {
    if (value === "all") {
      onStatusChange([]);
    } else {
      const statusValue = value as ProjectStatus;
      if (status.includes(statusValue)) {
        onStatusChange(status.filter((s) => s !== statusValue));
      } else {
        onStatusChange([...status, statusValue]);
      }
    }
  };

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
        <Select value="" onValueChange={handleStatusChange}>
          <SelectTrigger className="w-[150px]">
            <SelectValue placeholder="Status" />
          </SelectTrigger>
          <SelectContent>
            {statusOptions.map((option) => (
              <SelectItem key={option.value} value={option.value}>
                <span className="flex items-center gap-2">
                  {status.includes(option.value) && (
                    <span className="text-primary">✓</span>
                  )}
                  {option.label}
                </span>
              </SelectItem>
            ))}
          </SelectContent>
        </Select>

        <OrganizationFilterCombobox
          organizations={orgsData?.items ?? []}
          selectedId={organizationId}
          onSelect={onOrganizationChange}
          placeholder="Organization"
          showAllOption={true}
        />

        <TagFilterCombobox
          allTags={allTags ?? []}
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
          {organizationId && orgsData?.items && (
            <Badge variant="secondary" className="gap-1">
              {orgsData.items.find((o) => o.id === organizationId)?.name}
              <button
                onClick={() => onOrganizationChange(undefined)}
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
