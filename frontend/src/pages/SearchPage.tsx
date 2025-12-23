/**
 * Search page with search bar, filters, and saved searches.
 */

import { useState, useEffect, useCallback } from "react";
import { useSearchParams } from "react-router-dom";
import { Search, Bookmark, BookmarkPlus, Loader2, ChevronRight, Download, ArrowUpDown } from "lucide-react";
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
import { Switch } from "@/components/ui/switch";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { SearchFilters } from "@/components/forms/SearchFilters";
import { SearchResults } from "@/components/tables/SearchResults";
import { SavedSearchList } from "@/components/SavedSearchList";
import { ParsedQueryBadges } from "@/components/features/ParsedQueryBadges";
import { SearchSummary } from "@/components/features/SearchSummary";
import { useSearch, useSemanticSearch, useSummarization } from "@/hooks/useSearch";
import { useDebounce } from "@/hooks/useDebounce";
import { useCreateSavedSearch } from "@/hooks/useSavedSearches";
import { useExportSearchResults } from "@/hooks/useExport";
import type { ProjectStatus } from "@/types/project";
import type { SavedSearch, SearchParams } from "@/types/search";

const sortOptions = [
  { value: "relevance", label: "Relevance" },
  { value: "name", label: "Name" },
  { value: "start_date", label: "Start Date" },
  { value: "updated_at", label: "Last Updated" },
] as const;

export function SearchPage() {
  const [searchParams, setSearchParams] = useSearchParams();

  // Parse initial state from URL
  const initialQuery = searchParams.get("q") ?? "";
  const initialStatus = searchParams.getAll("status") as ProjectStatus[];
  const initialOrgId = searchParams.get("organization_id") ?? undefined;
  const initialTagIds = searchParams.getAll("tag_ids");
  const initialPage = parseInt(searchParams.get("page") ?? "1", 10);
  const initialPageSize = parseInt(searchParams.get("page_size") ?? "20", 10);
  const initialSortBy = (searchParams.get("sort_by") as SearchParams["sortBy"]) ?? "relevance";
  const initialSortOrder = (searchParams.get("sort_order") as "asc" | "desc") ?? "desc";

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
  const [sortBy, setSortBy] = useState<SearchParams["sortBy"]>(initialSortBy);
  const [sortOrder, setSortOrder] = useState<"asc" | "desc">(initialSortOrder);

  // Smart search state
  const [isSmartSearch, setIsSmartSearch] = useState(false);

  // Saved search state
  const [showSaveDialog, setShowSaveDialog] = useState(false);
  const [saveSearchName, setSaveSearchName] = useState("");
  const [showSavedSearches, setShowSavedSearches] = useState(false);
  const [selectedSavedSearchId, setSelectedSavedSearchId] = useState<string>();

  const createSavedSearch = useCreateSavedSearch();
  const { exportSearchResults, isExporting } = useExportSearchResults();

  // Debounce filter values to prevent excessive API calls during rapid filter changes
  // 300ms delay allows for a good balance between responsiveness and reducing API calls
  const debouncedStatus = useDebounce(status, 300);
  const debouncedOrgId = useDebounce(organizationId, 300);
  const debouncedTagIds = useDebounce(tagIds, 300);

  // Fetch search results using debounced filter values
  // Note: query is submitted via form so no debounce needed
  const { data, isLoading } = useSearch({
    q: query,
    status: debouncedStatus.length > 0 ? debouncedStatus : undefined,
    organizationId: debouncedOrgId,
    tagIds: debouncedTagIds.length > 0 ? debouncedTagIds : undefined,
    sortBy,
    sortOrder,
    page,
    pageSize,
  });

  // Semantic search (only when smart search is enabled)
  const semanticSearchParams = isSmartSearch && query ? {
    query: query,
    filters: {
      status: debouncedStatus.length > 0 ? debouncedStatus : undefined,
      organization_id: debouncedOrgId,
      tag_ids: debouncedTagIds.length > 0 ? debouncedTagIds : undefined,
    },
    page,
    page_size: pageSize,
  } : null;

  const { data: semanticData, isLoading: isSemanticLoading, error: semanticError } = useSemanticSearch(semanticSearchParams);

  // Summarization (only when smart search has results)
  const summarizationParams = isSmartSearch && query && semanticData && semanticData.total > 0 ? {
    query: query,
    project_ids: semanticData.items.slice(0, 10).map(item => item.id),
    max_chunks: 10,
  } : null;

  const { data: summaryData, isLoading: isSummaryLoading, error: summaryError } = useSummarization(summarizationParams);

  // Use appropriate data source based on mode
  const activeData = isSmartSearch ? semanticData : data;
  const activeLoading = isSmartSearch ? isSemanticLoading : isLoading;

  // Update URL when filters change
  const updateURL = useCallback(() => {
    const params = new URLSearchParams();
    if (query) params.set("q", query);
    status.forEach((s) => params.append("status", s));
    if (organizationId) params.set("organization_id", organizationId);
    tagIds.forEach((id) => params.append("tag_ids", id));
    if (sortBy && sortBy !== "relevance") params.set("sort_by", sortBy);
    if (sortOrder && sortOrder !== "desc") params.set("sort_order", sortOrder);
    if (page > 1) params.set("page", String(page));
    if (pageSize !== 20) params.set("page_size", String(pageSize));
    setSearchParams(params);
  }, [query, status, organizationId, tagIds, sortBy, sortOrder, page, pageSize, setSearchParams]);

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
    setSortBy("relevance");
    setSortOrder("desc");
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
          sort_by: sortBy !== "relevance" ? sortBy : undefined,
          sort_order: sortOrder !== "desc" ? sortOrder : undefined,
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
    setSortBy((search.filters.sort_by as SearchParams["sortBy"]) ?? "relevance");
    setSortOrder((search.filters.sort_order as "asc" | "desc") ?? "desc");
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
            {data && data.total > 0 && (
              <Button
                variant="outline"
                size="sm"
                onClick={() =>
                  exportSearchResults({
                    q: query,
                    status: status.length > 0 ? status : undefined,
                    organizationId,
                    tagIds: tagIds.length > 0 ? tagIds : undefined,
                  })
                }
                disabled={isExporting}
              >
                {isExporting ? (
                  <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                ) : (
                  <Download className="mr-2 h-4 w-4" />
                )}
                Export CSV
              </Button>
            )}
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

        {/* Smart Search Toggle */}
        <div className="flex items-center gap-2">
          <Switch
            id="smart-search"
            checked={isSmartSearch}
            onCheckedChange={setIsSmartSearch}
          />
          <Label htmlFor="smart-search" className="text-sm cursor-pointer">
            Smart Search
          </Label>
          <span className="text-xs text-muted-foreground">
            {isSmartSearch ? "Natural language enabled" : "Classic keyword search"}
          </span>
        </div>

        {/* Parsed Query Interpretation */}
        {isSmartSearch && semanticData?.parsed_query && (
          <ParsedQueryBadges
            intent={semanticData.parsed_query.parsed_intent}
            className="mt-4"
          />
        )}

        <SearchFilters
          status={status}
          organizationId={organizationId}
          tagIds={tagIds}
          onStatusChange={handleStatusChange}
          onOrganizationChange={handleOrganizationChange}
          onTagsChange={handleTagsChange}
          onClearAll={handleClearAll}
        />

        {/* AI Summary */}
        {isSmartSearch && query && !semanticError && (
          <SearchSummary
            summary={summaryData}
            isLoading={isSummaryLoading}
            error={summaryError instanceof Error ? summaryError : null}
          />
        )}

        {/* Semantic search error */}
        {isSmartSearch && semanticError && (
          <div className="rounded-md bg-destructive/10 p-3 text-sm text-destructive">
            Smart search failed. {semanticError instanceof Error ? semanticError.message : "Please try again."}
          </div>
        )}

        {/* Result count and sort controls */}
        <div className="flex items-center justify-between">
          {activeData && (
            <span className="text-sm text-muted-foreground">
              {activeData.total} result{activeData.total !== 1 ? "s" : ""} found
              {query && ` for "${query}"`}
            </span>
          )}
          <div className="flex items-center gap-2">
            <ArrowUpDown className="h-4 w-4 text-muted-foreground" />
            <span className="text-sm text-muted-foreground">Sort by</span>
            <Select
              value={sortBy}
              onValueChange={(value) => {
                setSortBy(value as SearchParams["sortBy"]);
                setPage(1);
              }}
            >
              <SelectTrigger className="w-[140px]">
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                {sortOptions.map((option) => (
                  <SelectItem key={option.value} value={option.value}>
                    {option.label}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
            <Select
              value={sortOrder}
              onValueChange={(value) => {
                setSortOrder(value as "asc" | "desc");
                setPage(1);
              }}
            >
              <SelectTrigger className="w-[100px]">
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="asc">Ascending</SelectItem>
                <SelectItem value="desc">Descending</SelectItem>
              </SelectContent>
            </Select>
          </div>
        </div>

        <SearchResults
          data={activeData?.items ?? []}
          total={activeData?.total ?? 0}
          page={page}
          pageSize={pageSize}
          isLoading={activeLoading}
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
