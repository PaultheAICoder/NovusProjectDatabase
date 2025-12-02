/**
 * Saved search list component.
 */

import { Bookmark, Globe, Lock, Trash2, Loader2 } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import {
  useSavedSearches,
  useDeleteSavedSearch,
  useToggleSavedSearchGlobal,
} from "@/hooks/useSavedSearches";
import { useAuth } from "@/hooks/useAuth";
import type { SavedSearch, SavedSearchFilters } from "@/types/search";
import { cn } from "@/lib/utils";

interface SavedSearchListProps {
  onSelect: (search: SavedSearch) => void;
  selectedId?: string;
}

export function SavedSearchList({ onSelect, selectedId }: SavedSearchListProps) {
  const { user } = useAuth();
  const { data, isLoading } = useSavedSearches();
  const deleteMutation = useDeleteSavedSearch();
  const toggleGlobalMutation = useToggleSavedSearchGlobal();

  const isAdmin = user?.is_admin ?? false;

  if (isLoading) {
    return (
      <div className="flex items-center justify-center py-4">
        <Loader2 className="h-5 w-5 animate-spin text-muted-foreground" />
      </div>
    );
  }

  const hasSearches =
    (data?.my_searches?.length ?? 0) > 0 ||
    (data?.global_searches?.length ?? 0) > 0;

  if (!hasSearches) {
    return (
      <div className="py-4 text-center text-sm text-muted-foreground">
        No saved searches yet
      </div>
    );
  }

  const formatFilters = (filters: SavedSearchFilters): string => {
    const parts: string[] = [];
    if (filters.status?.length) {
      parts.push(`status: ${filters.status.join(", ")}`);
    }
    if (filters.organization_id) {
      parts.push("org filter");
    }
    if (filters.tag_ids?.length) {
      parts.push(`${filters.tag_ids.length} tags`);
    }
    return parts.join(", ") || "No filters";
  };

  const handleDelete = (e: React.MouseEvent, id: string) => {
    e.stopPropagation();
    if (confirm("Are you sure you want to delete this saved search?")) {
      deleteMutation.mutate(id);
    }
  };

  const handleToggleGlobal = (e: React.MouseEvent, id: string) => {
    e.stopPropagation();
    toggleGlobalMutation.mutate(id);
  };

  const renderSearch = (search: SavedSearch, isOwn: boolean) => (
    <button
      key={search.id}
      onClick={() => onSelect(search)}
      className={cn(
        "flex w-full items-start gap-3 rounded-md p-3 text-left transition-colors",
        selectedId === search.id
          ? "bg-primary/10"
          : "hover:bg-muted/50"
      )}
    >
      <Bookmark className="mt-0.5 h-4 w-4 flex-shrink-0 text-muted-foreground" />
      <div className="flex-1 min-w-0">
        <div className="flex items-center gap-2">
          <span className="font-medium truncate">{search.name}</span>
          {search.is_global && (
            <Badge variant="secondary" className="text-xs">
              <Globe className="mr-1 h-3 w-3" />
              Global
            </Badge>
          )}
        </div>
        {search.query && (
          <p className="text-sm text-muted-foreground truncate">
            "{search.query}"
          </p>
        )}
        <p className="text-xs text-muted-foreground">
          {formatFilters(search.filters)}
        </p>
      </div>
      {isOwn && (
        <div className="flex items-center gap-1">
          {isAdmin && (
            <Button
              variant="ghost"
              size="icon"
              className="h-7 w-7"
              onClick={(e) => handleToggleGlobal(e, search.id)}
              title={search.is_global ? "Make private" : "Make global"}
            >
              {search.is_global ? (
                <Lock className="h-3 w-3" />
              ) : (
                <Globe className="h-3 w-3" />
              )}
            </Button>
          )}
          <Button
            variant="ghost"
            size="icon"
            className="h-7 w-7 text-destructive"
            onClick={(e) => handleDelete(e, search.id)}
          >
            <Trash2 className="h-3 w-3" />
          </Button>
        </div>
      )}
    </button>
  );

  return (
    <div className="space-y-4">
      {data?.my_searches && data.my_searches.length > 0 && (
        <div>
          <h4 className="mb-2 text-sm font-medium text-muted-foreground">
            My Searches
          </h4>
          <div className="space-y-1">
            {data.my_searches.map((search) => renderSearch(search, true))}
          </div>
        </div>
      )}

      {data?.global_searches && data.global_searches.length > 0 && (
        <div>
          <h4 className="mb-2 text-sm font-medium text-muted-foreground">
            Shared Searches
          </h4>
          <div className="space-y-1">
            {data.global_searches.map((search) => renderSearch(search, false))}
          </div>
        </div>
      )}
    </div>
  );
}
