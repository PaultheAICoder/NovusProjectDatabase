/**
 * Search page with search bar, filters, and saved searches.
 */

import { useState, useEffect, useCallback } from "react";
import { useSearchParams } from "react-router-dom";
import { Search, Bookmark, BookmarkPlus, Loader2, ChevronRight } from "lucide-react";
import { Input } from "@/components/ui/input";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogFooter,
} from "@/components/ui/dialog";
import { Label } from "@/components/ui/label";
import { SearchFilters } from "@/components/forms/SearchFilters";
import { SearchResults } from "@/components/tables/SearchResults";
import { SavedSearchList } from "@/components/SavedSearchList";
import { useSearch } from "@/hooks/useSearch";
import { useCreateSavedSearch } from "@/hooks/useSavedSearches";
import type { ProjectStatus } from "@/types/project";
import type { SavedSearch } from "@/types/search";

export function SearchPage() {
  const [searchParams, setSearchParams] = useSearchParams();

  // Parse initial state from URL
  const initialQuery = searchParams.get("q") ?? "";
  const initialStatus = searchParams.getAll("status") as ProjectStatus[];
  const initialOrgId = searchParams.get("organization_id") ?? undefined;
  const initialTagIds = searchParams.getAll("tag_ids");
  const initialPage = parseInt(searchParams.get("page") ?? "1", 10);
  const initialPageSize = parseInt(searchParams.get("page_size") ?? "20", 10);

  // Local state
  const [inputValue, setInputValue] = useState(initialQuery);
  const [query, setQuery] = useState(initialQuery);
  const [status, setStatus] = useState<ProjectStatus[]>(initialStatus);
  const [organizationId, setOrganizationId] = useState<string | undefined>(
    initialOrgId,
  );
  const [tagIds, setTagIds] = useState<string[]>(initialTagIds);
  const [page, setPage] = useState(initialPage);
  const [pageSize, setPageSize] = useState(initialPageSize);

  // Saved search state
  const [showSaveDialog, setShowSaveDialog] = useState(false);
  const [saveSearchName, setSaveSearchName] = useState("");
  const [showSavedSearches, setShowSavedSearches] = useState(false);
  const [selectedSavedSearchId, setSelectedSavedSearchId] = useState<string>();

  const createSavedSearch = useCreateSavedSearch();

  // Fetch search results
  const { data, isLoading } = useSearch({
    q: query,
    status: status.length > 0 ? status : undefined,
    organizationId,
    tagIds: tagIds.length > 0 ? tagIds : undefined,
    page,
    pageSize,
  });

  // Update URL when filters change
  const updateURL = useCallback(() => {
    const params = new URLSearchParams();
    if (query) params.set("q", query);
    status.forEach((s) => params.append("status", s));
    if (organizationId) params.set("organization_id", organizationId);
    tagIds.forEach((id) => params.append("tag_ids", id));
    if (page > 1) params.set("page", String(page));
    if (pageSize !== 20) params.set("page_size", String(pageSize));
    setSearchParams(params);
  }, [query, status, organizationId, tagIds, page, pageSize, setSearchParams]);

  useEffect(() => {
    updateURL();
  }, [updateURL]);

  const handleSearch = (e: React.FormEvent) => {
    e.preventDefault();
    setQuery(inputValue);
    setPage(1);
    setSelectedSavedSearchId(undefined);
  };

  const handleClearAll = () => {
    setStatus([]);
    setOrganizationId(undefined);
    setTagIds([]);
    setPage(1);
    setSelectedSavedSearchId(undefined);
  };

  const handleStatusChange = (newStatus: ProjectStatus[]) => {
    setStatus(newStatus);
    setPage(1);
    setSelectedSavedSearchId(undefined);
  };

  const handleOrganizationChange = (orgId: string | undefined) => {
    setOrganizationId(orgId);
    setPage(1);
    setSelectedSavedSearchId(undefined);
  };

  const handleTagsChange = (newTagIds: string[]) => {
    setTagIds(newTagIds);
    setPage(1);
    setSelectedSavedSearchId(undefined);
  };

  const handleSaveSearch = async () => {
    if (!saveSearchName.trim()) return;

    try {
      await createSavedSearch.mutateAsync({
        name: saveSearchName.trim(),
        query: query || undefined,
        filters: {
          status: status.length > 0 ? status : undefined,
          organization_id: organizationId,
          tag_ids: tagIds.length > 0 ? tagIds : undefined,
        },
      });
      setShowSaveDialog(false);
      setSaveSearchName("");
    } catch {
      // Error handled by mutation
    }
  };

  const handleLoadSavedSearch = (search: SavedSearch) => {
    setSelectedSavedSearchId(search.id);
    setInputValue(search.query ?? "");
    setQuery(search.query ?? "");
    setStatus((search.filters.status as ProjectStatus[]) ?? []);
    setOrganizationId(search.filters.organization_id);
    setTagIds(search.filters.tag_ids ?? []);
    setPage(1);
  };

  const hasActiveSearch =
    query || status.length > 0 || organizationId || tagIds.length > 0;

  return (
    <div className="flex gap-6">
      {/* Saved searches sidebar */}
      {showSavedSearches && (
        <Card className="w-72 flex-shrink-0">
          <CardHeader className="pb-3">
            <CardTitle className="flex items-center gap-2 text-base">
              <Bookmark className="h-4 w-4" />
              Saved Searches
            </CardTitle>
          </CardHeader>
          <CardContent>
            <SavedSearchList
              onSelect={handleLoadSavedSearch}
              selectedId={selectedSavedSearchId}
            />
          </CardContent>
        </Card>
      )}

      {/* Main content */}
      <div className="flex-1 space-y-6">
        <div className="flex items-center justify-between">
          <div>
            <h1 className="text-2xl font-bold">Search Projects</h1>
            <p className="text-muted-foreground">
              Search across all projects by keyword and apply filters
            </p>
          </div>
          <div className="flex items-center gap-2">
            <Button
              variant="outline"
              size="sm"
              onClick={() => setShowSavedSearches(!showSavedSearches)}
            >
              <Bookmark className="mr-2 h-4 w-4" />
              {showSavedSearches ? "Hide" : "Show"} Saved
              <ChevronRight
                className={`ml-1 h-4 w-4 transition-transform ${
                  showSavedSearches ? "rotate-180" : ""
                }`}
              />
            </Button>
            {hasActiveSearch && (
              <Button
                variant="outline"
                size="sm"
                onClick={() => setShowSaveDialog(true)}
              >
                <BookmarkPlus className="mr-2 h-4 w-4" />
                Save Search
              </Button>
            )}
          </div>
        </div>

        <form onSubmit={handleSearch} className="flex gap-2">
          <div className="relative flex-1">
            <Search className="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
            <Input
              type="search"
              placeholder="Search projects by name, description, location..."
              value={inputValue}
              onChange={(e) => setInputValue(e.target.value)}
              className="pl-9"
            />
          </div>
          <Button type="submit">Search</Button>
        </form>

        <SearchFilters
          status={status}
          organizationId={organizationId}
          tagIds={tagIds}
          onStatusChange={handleStatusChange}
          onOrganizationChange={handleOrganizationChange}
          onTagsChange={handleTagsChange}
          onClearAll={handleClearAll}
        />

        {data && (
          <div className="text-sm text-muted-foreground">
            {data.total} result{data.total !== 1 ? "s" : ""} found
            {query && ` for "${query}"`}
          </div>
        )}

        <SearchResults
          data={data?.items ?? []}
          total={data?.total ?? 0}
          page={page}
          pageSize={pageSize}
          isLoading={isLoading}
          onPageChange={setPage}
          onPageSizeChange={setPageSize}
        />
      </div>

      {/* Save search dialog */}
      <Dialog open={showSaveDialog} onOpenChange={setShowSaveDialog}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Save Search</DialogTitle>
          </DialogHeader>
          <div className="space-y-4 py-4">
            <div className="space-y-2">
              <Label htmlFor="search-name">Name</Label>
              <Input
                id="search-name"
                value={saveSearchName}
                onChange={(e) => setSaveSearchName(e.target.value)}
                placeholder="Enter a name for this search"
              />
            </div>
            <div className="rounded-md bg-muted p-3 text-sm">
              <p className="font-medium">Current search:</p>
              {query && <p>Query: "{query}"</p>}
              {status.length > 0 && <p>Status: {status.join(", ")}</p>}
              {organizationId && <p>Organization filter active</p>}
              {tagIds.length > 0 && <p>{tagIds.length} tag(s) selected</p>}
            </div>
          </div>
          <DialogFooter>
            <Button variant="outline" onClick={() => setShowSaveDialog(false)}>
              Cancel
            </Button>
            <Button
              onClick={handleSaveSearch}
              disabled={!saveSearchName.trim() || createSavedSearch.isPending}
            >
              {createSavedSearch.isPending && (
                <Loader2 className="mr-2 h-4 w-4 animate-spin" />
              )}
              Save
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
}
