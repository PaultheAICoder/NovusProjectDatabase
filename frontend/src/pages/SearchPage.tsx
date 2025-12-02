/**
 * Search page with search bar and filters.
 */

import { useState, useEffect, useCallback } from "react";
import { useSearchParams } from "react-router-dom";
import { Search } from "lucide-react";
import { Input } from "@/components/ui/input";
import { Button } from "@/components/ui/button";
import { SearchFilters } from "@/components/forms/SearchFilters";
import { SearchResults } from "@/components/tables/SearchResults";
import { useSearch } from "@/hooks/useSearch";
import type { ProjectStatus } from "@/types/project";

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
  };

  const handleClearAll = () => {
    setStatus([]);
    setOrganizationId(undefined);
    setTagIds([]);
    setPage(1);
  };

  const handleStatusChange = (newStatus: ProjectStatus[]) => {
    setStatus(newStatus);
    setPage(1);
  };

  const handleOrganizationChange = (orgId: string | undefined) => {
    setOrganizationId(orgId);
    setPage(1);
  };

  const handleTagsChange = (newTagIds: string[]) => {
    setTagIds(newTagIds);
    setPage(1);
  };

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-bold">Search Projects</h1>
        <p className="text-muted-foreground">
          Search across all projects by keyword and apply filters
        </p>
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
  );
}
