/**
 * Organizations list page with CRUD operations.
 */

import { useState } from "react";
import { Link } from "react-router-dom";
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
  Edit,
  Trash2,
  Loader2,
} from "lucide-react";
import {
  useOrganizations,
  useCreateOrganization,
  useUpdateOrganization,
  useDeleteOrganization,
} from "@/hooks/useOrganizations";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";
import { Label } from "@/components/ui/label";
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
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogFooter,
} from "@/components/ui/dialog";
import { SyncStatusBadge } from "@/components/sync/SyncStatusBadge";
import type { Organization } from "@/types/organization";

const columnHelper = createColumnHelper<Organization>();

export function OrganizationsPage() {
  const [page, setPage] = useState(1);
  const [pageSize, setPageSize] = useState(20);
  const [showDialog, setShowDialog] = useState(false);
  const [editingOrg, setEditingOrg] = useState<Organization | null>(null);
  const [formData, setFormData] = useState({
    name: "",
    notes: "",
    address_street: "",
    address_city: "",
    address_state: "",
    address_zip: "",
    address_country: "",
    inventory_url: "",
  });

  const { data, isLoading, isError } = useOrganizations({ page, pageSize });
  const createMutation = useCreateOrganization();
  const updateMutation = useUpdateOrganization();
  const deleteMutation = useDeleteOrganization();

  const columns = [
    columnHelper.accessor("name", {
      header: "Organization Name",
      cell: (info) => (
        <Link
          to={`/organizations/${info.row.original.id}`}
          className="font-medium text-primary hover:underline"
        >
          {info.getValue()}
        </Link>
      ),
    }),
    columnHelper.accessor("notes", {
      header: "Notes",
      cell: (info) => (
        <span className="text-muted-foreground line-clamp-2">
          {info.getValue() || "-"}
        </span>
      ),
    }),
    columnHelper.accessor("sync_status", {
      header: "Sync",
      cell: (info) => <SyncStatusBadge status={info.getValue()} />,
    }),
    columnHelper.accessor("created_at", {
      header: "Created",
      cell: (info) => format(new Date(info.getValue()), "MMM d, yyyy"),
    }),
    columnHelper.display({
      id: "actions",
      header: "",
      cell: (info) => (
        <div className="flex items-center gap-1">
          <Button
            variant="ghost"
            size="icon"
            onClick={() => handleEdit(info.row.original)}
          >
            <Edit className="h-4 w-4" />
          </Button>
          <Button
            variant="ghost"
            size="icon"
            className="text-destructive"
            onClick={() => handleDelete(info.row.original.id)}
          >
            <Trash2 className="h-4 w-4" />
          </Button>
        </div>
      ),
    }),
  ];

  const table = useReactTable({
    data: data?.items ?? [],
    columns,
    getCoreRowModel: getCoreRowModel(),
    manualPagination: true,
    pageCount: data ? Math.ceil(data.total / pageSize) : 0,
  });

  const handleCreate = () => {
    setEditingOrg(null);
    setFormData({
      name: "",
      notes: "",
      address_street: "",
      address_city: "",
      address_state: "",
      address_zip: "",
      address_country: "",
      inventory_url: "",
    });
    setShowDialog(true);
  };

  const handleEdit = (org: Organization) => {
    setEditingOrg(org);
    setFormData({
      name: org.name,
      notes: org.notes || "",
      address_street: org.address_street || "",
      address_city: org.address_city || "",
      address_state: org.address_state || "",
      address_zip: org.address_zip || "",
      address_country: org.address_country || "",
      inventory_url: org.inventory_url || "",
    });
    setShowDialog(true);
  };

  const handleDelete = async (id: string) => {
    if (confirm("Are you sure you want to delete this organization?")) {
      await deleteMutation.mutateAsync(id);
    }
  };

  const handleSubmit = async () => {
    if (!formData.name.trim()) return;

    if (editingOrg) {
      await updateMutation.mutateAsync({
        id: editingOrg.id,
        data: formData,
      });
    } else {
      await createMutation.mutateAsync(formData);
    }
    setShowDialog(false);
  };

  const isPending = createMutation.isPending || updateMutation.isPending;

  if (isError) {
    return (
      <div className="rounded-md bg-destructive/10 p-4 text-destructive">
        Failed to load organizations. Please try again.
      </div>
    );
  }

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold">Organizations</h1>
          <p className="text-muted-foreground">
            Manage client organizations
          </p>
        </div>
        <Button onClick={handleCreate}>
          <Plus className="mr-2 h-4 w-4" />
          New Organization
        </Button>
      </div>

      {data && (
        <span className="text-sm text-muted-foreground">
          {data.total} organization{data.total !== 1 ? "s" : ""} total
        </span>
      )}

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
                          header.getContext()
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
                  Loading organizations...
                </TableCell>
              </TableRow>
            ) : table.getRowModel().rows.length === 0 ? (
              <TableRow>
                <TableCell
                  colSpan={columns.length}
                  className="h-24 text-center"
                >
                  No organizations found.
                </TableCell>
              </TableRow>
            ) : (
              table.getRowModel().rows.map((row) => (
                <TableRow key={row.id}>
                  {row.getVisibleCells().map((cell) => (
                    <TableCell key={cell.id}>
                      {flexRender(
                        cell.column.columnDef.cell,
                        cell.getContext()
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

      <Dialog open={showDialog} onOpenChange={setShowDialog}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>
              {editingOrg ? "Edit Organization" : "New Organization"}
            </DialogTitle>
          </DialogHeader>
          <div className="space-y-4 py-4">
            <div className="space-y-2">
              <Label htmlFor="org-name">Name *</Label>
              <Input
                id="org-name"
                value={formData.name}
                onChange={(e) =>
                  setFormData({ ...formData, name: e.target.value })
                }
                placeholder="Enter organization name"
              />
            </div>
            <div className="space-y-2">
              <Label htmlFor="org-notes">Notes</Label>
              <Textarea
                id="org-notes"
                value={formData.notes}
                onChange={(e) =>
                  setFormData({ ...formData, notes: e.target.value })
                }
                placeholder="Optional notes about this organization"
              />
            </div>
            <div className="space-y-2">
              <Label>Address</Label>
              <Input
                value={formData.address_street}
                onChange={(e) =>
                  setFormData({ ...formData, address_street: e.target.value })
                }
                placeholder="Street address"
              />
              <div className="grid grid-cols-2 gap-2">
                <Input
                  value={formData.address_city}
                  onChange={(e) =>
                    setFormData({ ...formData, address_city: e.target.value })
                  }
                  placeholder="City"
                />
                <Input
                  value={formData.address_state}
                  onChange={(e) =>
                    setFormData({ ...formData, address_state: e.target.value })
                  }
                  placeholder="State"
                />
              </div>
              <div className="grid grid-cols-2 gap-2">
                <Input
                  value={formData.address_zip}
                  onChange={(e) =>
                    setFormData({ ...formData, address_zip: e.target.value })
                  }
                  placeholder="ZIP Code"
                />
                <Input
                  value={formData.address_country}
                  onChange={(e) =>
                    setFormData({ ...formData, address_country: e.target.value })
                  }
                  placeholder="Country"
                />
              </div>
            </div>
            <div className="space-y-2">
              <Label htmlFor="org-inventory-url">Inventory Link</Label>
              <Input
                id="org-inventory-url"
                value={formData.inventory_url}
                onChange={(e) =>
                  setFormData({ ...formData, inventory_url: e.target.value })
                }
                placeholder="https://inventory.example.com/client/123"
              />
            </div>
          </div>
          <DialogFooter>
            <Button variant="outline" onClick={() => setShowDialog(false)}>
              Cancel
            </Button>
            <Button
              onClick={handleSubmit}
              disabled={!formData.name.trim() || isPending}
            >
              {isPending && <Loader2 className="mr-2 h-4 w-4 animate-spin" />}
              {editingOrg ? "Update" : "Create"}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
}
