/**
 * Projects list page with TanStack Table, search, and filters.
 */

import { useState, useEffect, useCallback } from "react";
import { Link, useSearchParams } from "react-router-dom";
import {
  useReactTable,
  getCoreRowModel,
  flexRender,
  createColumnHelper,
} from "@tanstack/react-table";
import { format } from "date-fns";
import {
  Plus,
  ChevronLeft,
  ChevronRight,
  Download,
  Loader2,
  Search,
  X,
  ArrowUpDown,
  Eye,
  EyeOff,
} from "lucide-react";
import { useProjects } from "@/hooks/useProjects";
import { useExportProjects } from "@/hooks/useExport";
import { useDebounce } from "@/hooks/useDebounce";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Input } from "@/components/ui/input";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { ProjectSearchFilters } from "@/components/forms/ProjectSearchFilters";
import type { Project, ProjectStatus } from "@/types/project";

const columnHelper = createColumnHelper<Project>();

const statusVariants: Record<
  ProjectStatus,
  "default" | "secondary" | "success" | "warning" | "destructive"
> = {
  approved: "secondary",
  active: "success",
  on_hold: "warning",
  completed: "default",
  cancelled: "destructive",
};

const statusLabels: Record<ProjectStatus, string> = {
  approved: "Approved",
  active: "Active",
  on_hold: "On Hold",
  completed: "Completed",
  cancelled: "Cancelled",
};

const sortOptions = [
  { value: "name", label: "Name" },
  { value: "start_date", label: "Start Date" },
  { value: "updated_at", label: "Last Updated" },
] as const;

const columns = [
  columnHelper.accessor("name", {
    header: "Project Name",
    cell: (info) => (
      <Link
        to={`/projects/${info.row.original.id}`}
        className="font-medium text-primary hover:underline"
      >
        {info.getValue()}
      </Link>
    ),
  }),
  columnHelper.accessor("organization.name", {
    header: "Organization",
    cell: (info) => info.getValue(),
  }),
  columnHelper.accessor("status", {
    header: "Status",
    cell: (info) => {
      const status = info.getValue();
      return (
        <Badge variant={statusVariants[status]}>{statusLabels[status]}</Badge>
      );
    },
  }),
  columnHelper.accessor("visibility", {
    header: "Access",
    cell: (info) => {
      const visibility = info.getValue();
      return visibility === "restricted" ? (
        <EyeOff className="h-4 w-4 text-muted-foreground" />
      ) : (
        <Eye className="h-4 w-4 text-muted-foreground" />
      );
    },
  }),
  columnHelper.accessor("start_date", {
    header: "Start Date",
    cell: (info) => format(new Date(info.getValue()), "MMM d, yyyy"),
  }),
  columnHelper.accessor("owner.display_name", {
    header: "Owner",
    cell: (info) => info.getValue(),
  }),
  columnHelper.accessor("updated_at", {
    header: "Last Updated",
    cell: (info) => format(new Date(info.getValue()), "MMM d, yyyy"),
  }),
];

export function ProjectsPage() {
  const [searchParams, setSearchParams] = useSearchParams();

  // Parse initial state from URL
  const initialQuery = searchParams.get("q") ?? "";
  const initialStatus = searchParams.getAll("status") as ProjectStatus[];
  const initialOrgId = searchParams.get("organization_id") ?? undefined;
  const initialTagIds = searchParams.getAll("tag_ids");
  const initialPage = parseInt(searchParams.get("page") ?? "1", 10);
  const initialPageSize = parseInt(searchParams.get("page_size") ?? "20", 10);
  const initialSortBy =
    (searchParams.get("sort_by") as "name" | "start_date" | "updated_at") ??
    "updated_at";
  const initialSortOrder =
    (searchParams.get("sort_order") as "asc" | "desc") ?? "desc";

  // Default active statuses (excludes cancelled)
  const defaultActiveStatuses: ProjectStatus[] = [
    "approved",
    "active",
    "on_hold",
    "completed",
  ];

  // Local state
  const [inputValue, setInputValue] = useState(initialQuery);
  const [query, setQuery] = useState(initialQuery);
  // Use URL status if provided, otherwise default to active statuses (exclude cancelled)
  const [statusFilter, setStatusFilter] = useState<ProjectStatus[]>(
    initialStatus.length > 0 ? initialStatus : defaultActiveStatuses,
  );
  const [organizationId, setOrganizationId] = useState<string | undefined>(
    initialOrgId,
  );
  const [tagIds, setTagIds] = useState<string[]>(initialTagIds);
  const [page, setPage] = useState(initialPage);
  const [pageSize, setPageSize] = useState(initialPageSize);
  const [sortBy, setSortBy] = useState<"name" | "start_date" | "updated_at">(
    initialSortBy,
  );
  const [sortOrder, setSortOrder] = useState<"asc" | "desc">(initialSortOrder);

  const { exportProjects, isExporting } = useExportProjects();

  // Debounce filter values to prevent excessive API calls
  const debouncedQuery = useDebounce(query, 300);
  const debouncedStatus = useDebounce(statusFilter, 300);
  const debouncedOrgId = useDebounce(organizationId, 300);
  const debouncedTagIds = useDebounce(tagIds, 300);

  const { data, isLoading, isError } = useProjects({
    page,
    pageSize,
    q: debouncedQuery || undefined,
    status: debouncedStatus.length > 0 ? debouncedStatus : undefined,
    organizationId: debouncedOrgId,
    tagIds: debouncedTagIds.length > 0 ? debouncedTagIds : undefined,
    sortBy,
    sortOrder,
  });

  // Update URL when filters change
  const updateURL = useCallback(() => {
    const params = new URLSearchParams();
    if (query) params.set("q", query);
    statusFilter.forEach((s) => params.append("status", s));
    if (organizationId) params.set("organization_id", organizationId);
    tagIds.forEach((id) => params.append("tag_ids", id));
    if (sortBy !== "updated_at") params.set("sort_by", sortBy);
    if (sortOrder !== "desc") params.set("sort_order", sortOrder);
    if (page > 1) params.set("page", String(page));
    if (pageSize !== 20) params.set("page_size", String(pageSize));
    setSearchParams(params);
  }, [
    query,
    statusFilter,
    organizationId,
    tagIds,
    sortBy,
    sortOrder,
    page,
    pageSize,
    setSearchParams,
  ]);

  useEffect(() => {
    updateURL();
  }, [updateURL]);

  const table = useReactTable({
    data: data?.items ?? [],
    columns,
    getCoreRowModel: getCoreRowModel(),
    manualPagination: true,
    pageCount: data ? Math.ceil(data.total / pageSize) : 0,
  });

  const handleClearAll = () => {
    setInputValue("");
    setQuery("");
    setStatusFilter(defaultActiveStatuses);
    setOrganizationId(undefined);
    setTagIds([]);
    setSortBy("updated_at");
    setSortOrder("desc");
    setPage(1);
  };

  const handleClearSearch = () => {
    setInputValue("");
    setQuery("");
    setPage(1);
  };

  // Check if status filter differs from default (includes cancelled or is subset)
  const isNonDefaultStatusFilter =
    statusFilter.length !== defaultActiveStatuses.length ||
    statusFilter.some((s) => !defaultActiveStatuses.includes(s));

  const hasActiveFilters =
    query ||
    isNonDefaultStatusFilter ||
    organizationId !== undefined ||
    tagIds.length > 0;

  if (isError) {
    return (
      <div className="rounded-md bg-destructive/10 p-4 text-destructive">
        Failed to load projects. Please try again.
      </div>
    );
  }

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold">Projects</h1>
          <p className="text-muted-foreground">
            Manage and track all your projects
          </p>
        </div>
        <div className="flex items-center gap-2">
          <Button
            variant="outline"
            onClick={() =>
              exportProjects({
                status: statusFilter.length > 0 ? statusFilter : undefined,
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
          <Button asChild>
            <Link to="/projects/new">
              <Plus className="mr-2 h-4 w-4" />
              New Project
            </Link>
          </Button>
        </div>
      </div>

      {/* Search bar */}
      <div className="flex gap-2">
        <div className="relative flex-1">
          <Search className="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
          <Input
            type="search"
            placeholder="Search projects by name, description, location..."
            value={inputValue}
            onChange={(e) => {
              setInputValue(e.target.value);
              setQuery(e.target.value);
              setPage(1);
            }}
            className="pl-9 pr-9"
          />
          {inputValue && (
            <button
              onClick={handleClearSearch}
              className="absolute right-3 top-1/2 -translate-y-1/2 text-muted-foreground hover:text-foreground"
            >
              <X className="h-4 w-4" />
            </button>
          )}
        </div>
      </div>

      {/* Filters */}
      <ProjectSearchFilters
        status={statusFilter}
        organizationId={organizationId}
        tagIds={tagIds}
        onStatusChange={(newStatus) => {
          setStatusFilter(newStatus);
          setPage(1);
        }}
        onOrganizationChange={(orgId) => {
          setOrganizationId(orgId);
          setPage(1);
        }}
        onTagsChange={(newTagIds) => {
          setTagIds(newTagIds);
          setPage(1);
        }}
        onClearAll={handleClearAll}
      />

      {/* Result count and sort controls */}
      <div className="flex items-center justify-between">
        {data && (
          <span className="text-sm text-muted-foreground">
            {data.total} project{data.total !== 1 ? "s" : ""}
            {hasActiveFilters ? " found" : " total"}
            {query && ` for "${query}"`}
          </span>
        )}
        <div className="flex items-center gap-2">
          <ArrowUpDown className="h-4 w-4 text-muted-foreground" />
          <span className="text-sm text-muted-foreground">Sort by</span>
          <Select
            value={sortBy}
            onValueChange={(value) => {
              setSortBy(value as "name" | "start_date" | "updated_at");
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

      <div className="rounded-md border">
        <Table>
          <TableHeader>
            {table.getHeaderGroups().map((headerGroup) => (
              <TableRow key={headerGroup.id}>
                {headerGroup.headers.map((header) => (
                  <TableHead key={header.id}>
                    {header.isPlaceholder
                      ? null
                      : flexRender(
                          header.column.columnDef.header,
                          header.getContext(),
                        )}
                  </TableHead>
                ))}
              </TableRow>
            ))}
          </TableHeader>
          <TableBody>
            {isLoading ? (
              <TableRow>
                <TableCell
                  colSpan={columns.length}
                  className="h-24 text-center"
                >
                  <div className="flex items-center justify-center gap-2">
                    <Loader2 className="h-5 w-5 animate-spin text-muted-foreground" />
                    <span className="text-muted-foreground">
                      Loading projects...
                    </span>
                  </div>
                </TableCell>
              </TableRow>
            ) : table.getRowModel().rows.length === 0 ? (
              <TableRow>
                <TableCell
                  colSpan={columns.length}
                  className="h-24 text-center"
                >
                  No projects found.
                </TableCell>
              </TableRow>
            ) : (
              table.getRowModel().rows.map((row) => (
                <TableRow key={row.id}>
                  {row.getVisibleCells().map((cell) => (
                    <TableCell key={cell.id}>
                      {flexRender(
                        cell.column.columnDef.cell,
                        cell.getContext(),
                      )}
                    </TableCell>
                  ))}
                </TableRow>
              ))
            )}
          </TableBody>
        </Table>
      </div>

      {data && data.total > 0 && (
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-2">
            <span className="text-sm text-muted-foreground">Rows per page</span>
            <Select
              value={String(pageSize)}
              onValueChange={(value) => {
                setPageSize(Number(value));
                setPage(1);
              }}
            >
              <SelectTrigger className="w-[70px]">
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="10">10</SelectItem>
                <SelectItem value="20">20</SelectItem>
                <SelectItem value="50">50</SelectItem>
                <SelectItem value="100">100</SelectItem>
              </SelectContent>
            </Select>
          </div>

          <div className="flex items-center gap-2">
            <span className="text-sm text-muted-foreground">
              Page {page} of {Math.ceil(data.total / pageSize)}
            </span>
            <Button
              variant="outline"
              size="icon"
              onClick={() => setPage(page - 1)}
              disabled={page === 1}
            >
              <ChevronLeft className="h-4 w-4" />
            </Button>
            <Button
              variant="outline"
              size="icon"
              onClick={() => setPage(page + 1)}
              disabled={page >= Math.ceil(data.total / pageSize)}
            >
              <ChevronRight className="h-4 w-4" />
            </Button>
          </div>
        </div>
      )}
    </div>
  );
}
