/**
 * Organization detail page with nested projects and contacts.
 */

import { useState } from "react";
import { Link, useNavigate, useParams } from "react-router-dom";
import { format } from "date-fns";
import {
  ArrowLeft,
  Building2,
  Edit,
  ExternalLink,
  Plus,
  Users,
  FolderKanban,
  MapPin,
  Receipt,
} from "lucide-react";
import {
  useOrganization,
  useUpdateOrganization,
  useDeleteOrganization,
} from "@/hooks/useOrganizations";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
} from "@/components/ui/dialog";

const statusVariants: Record<
  string,
  "default" | "secondary" | "success" | "warning" | "destructive"
> = {
  approved: "secondary",
  active: "success",
  on_hold: "warning",
  completed: "default",
  cancelled: "destructive",
};

const statusLabels: Record<string, string> = {
  approved: "Approved",
  active: "Active",
  on_hold: "On Hold",
  completed: "Completed",
  cancelled: "Cancelled",
};

export function OrganizationDetailPage() {
  const { id } = useParams<{ id: string }>();
  const navigate = useNavigate();
  const { data: organization, isLoading, isError } = useOrganization(id);
  const updateOrganization = useUpdateOrganization();
  const deleteOrganization = useDeleteOrganization();

  const [showEditDialog, setShowEditDialog] = useState(false);
  const [editFormData, setEditFormData] = useState({
    name: "",
    aliases: "",
    notes: "",
    address_street: "",
    address_city: "",
    address_state: "",
    address_zip: "",
    address_country: "",
    inventory_url: "",
  });

  const handleEditOpen = () => {
    if (organization) {
      setEditFormData({
        name: organization.name,
        aliases: organization.aliases?.join(", ") || "",
        notes: organization.notes || "",
        address_street: organization.address_street || "",
        address_city: organization.address_city || "",
        address_state: organization.address_state || "",
        address_zip: organization.address_zip || "",
        address_country: organization.address_country || "",
        inventory_url: organization.inventory_url || "",
      });
      setShowEditDialog(true);
    }
  };

  const handleEditSubmit = async () => {
    if (!id || !editFormData.name.trim()) return;
    const aliasesArray = editFormData.aliases
      .split(",")
      .map((a) => a.trim())
      .filter((a) => a.length > 0);
    await updateOrganization.mutateAsync({
      id,
      data: {
        name: editFormData.name.trim(),
        aliases: aliasesArray.length > 0 ? aliasesArray : undefined,
        notes: editFormData.notes || undefined,
        address_street: editFormData.address_street || undefined,
        address_city: editFormData.address_city || undefined,
        address_state: editFormData.address_state || undefined,
        address_zip: editFormData.address_zip || undefined,
        address_country: editFormData.address_country || undefined,
        inventory_url: editFormData.inventory_url || undefined,
      },
    });
    setShowEditDialog(false);
  };

  const handleDelete = async () => {
    if (!id) return;
    try {
      await deleteOrganization.mutateAsync(id);
      navigate("/organizations");
    } catch {
      // Error handled by mutation
    }
  };

  if (isLoading) {
    return (
      <div className="flex h-64 items-center justify-center">
        <div className="text-muted-foreground">Loading organization...</div>
      </div>
    );
  }

  if (isError || !organization) {
    return (
      <div className="space-y-4">
        <Button variant="ghost" asChild>
          <Link to="/organizations">
            <ArrowLeft className="mr-2 h-4 w-4" />
            Back to Organizations
          </Link>
        </Button>
        <div className="rounded-md bg-destructive/10 p-4 text-destructive">
          Failed to load organization. It may not exist or you may not have
          access.
        </div>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-4">
          <Button variant="ghost" asChild>
            <Link to="/organizations">
              <ArrowLeft className="mr-2 h-4 w-4" />
              Back
            </Link>
          </Button>
          <div>
            <div className="flex items-center gap-2">
              <Building2 className="h-6 w-6 text-muted-foreground" />
              <h1 className="text-2xl font-bold">{organization.name}</h1>
            </div>
            {organization.aliases && organization.aliases.length > 0 && (
              <p className="text-muted-foreground">
                Also known as: {organization.aliases.join(", ")}
              </p>
            )}
          </div>
        </div>

        <div className="flex items-center gap-2">
          <Button variant="outline" asChild>
            <Link to={`/projects/new?organization_id=${id}`}>
              <Plus className="mr-2 h-4 w-4" />
              Add Project
            </Link>
          </Button>
          <Button variant="outline" asChild>
            <Link to={`/contacts?organization_id=${id}`}>
              <Plus className="mr-2 h-4 w-4" />
              Add Contact
            </Link>
          </Button>
          <Button variant="outline" onClick={handleEditOpen}>
            <Edit className="mr-2 h-4 w-4" />
            Edit
          </Button>
          <Dialog>
            <DialogTrigger asChild>
              <Button variant="destructive">Delete</Button>
            </DialogTrigger>
            <DialogContent>
              <DialogHeader>
                <DialogTitle>Delete Organization</DialogTitle>
                <DialogDescription>
                  Are you sure you want to delete "{organization.name}"? This
                  action cannot be undone. All associated projects and contacts
                  will be affected.
                </DialogDescription>
              </DialogHeader>
              <DialogFooter>
                <Button
                  variant="destructive"
                  onClick={handleDelete}
                  disabled={deleteOrganization.isPending}
                >
                  {deleteOrganization.isPending ? "Deleting..." : "Delete"}
                </Button>
              </DialogFooter>
            </DialogContent>
          </Dialog>
        </div>
      </div>

      {/* Stats Cards */}
      <div className="grid gap-4 sm:grid-cols-2">
        <Card>
          <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
            <CardTitle className="text-sm font-medium">Projects</CardTitle>
            <FolderKanban className="h-4 w-4 text-muted-foreground" />
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold">
              {organization.projects?.length || 0}
            </div>
          </CardContent>
        </Card>
        <Card>
          <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
            <CardTitle className="text-sm font-medium">Contacts</CardTitle>
            <Users className="h-4 w-4 text-muted-foreground" />
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold">
              {organization.contacts?.length || 0}
            </div>
          </CardContent>
        </Card>
      </div>

      {/* Address Card */}
      {(organization.address_street ||
        organization.address_city ||
        organization.address_state ||
        organization.address_zip ||
        organization.address_country) && (
        <Card>
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              <MapPin className="h-5 w-5" />
              Address
            </CardTitle>
          </CardHeader>
          <CardContent className="text-sm">
            {organization.address_street && <div>{organization.address_street}</div>}
            {(organization.address_city || organization.address_state || organization.address_zip) && (
              <div>
                {organization.address_city}
                {organization.address_city && organization.address_state && ", "}
                {organization.address_state} {organization.address_zip}
              </div>
            )}
            {organization.address_country && <div>{organization.address_country}</div>}
          </CardContent>
        </Card>
      )}

      {/* Billing & Links Card */}
      {(organization.billing_contact || organization.inventory_url || organization.notes) && (
        <Card>
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              <Receipt className="h-5 w-5" />
              Billing & Links
            </CardTitle>
          </CardHeader>
          <CardContent className="space-y-3 text-sm">
            {organization.billing_contact && (
              <div>
                <span className="text-muted-foreground">Billing Contact: </span>
                <span className="font-medium">{organization.billing_contact.name}</span>
                {" - "}
                <a
                  href={`mailto:${organization.billing_contact.email}`}
                  className="text-primary hover:underline"
                >
                  {organization.billing_contact.email}
                </a>
              </div>
            )}
            {organization.inventory_url && (
              <div className="flex items-center gap-2">
                <span className="text-muted-foreground">Inventory:</span>
                <a
                  href={organization.inventory_url}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="text-primary hover:underline flex items-center gap-1"
                >
                  View Inventory
                  <ExternalLink className="h-3 w-3" />
                </a>
              </div>
            )}
            {organization.notes && (
              <div>
                <span className="text-muted-foreground">Notes: </span>
                <span>{organization.notes}</span>
              </div>
            )}
          </CardContent>
        </Card>
      )}

      {/* Projects Table */}
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <FolderKanban className="h-5 w-5" />
            Projects
          </CardTitle>
          <CardDescription>All projects for this organization</CardDescription>
        </CardHeader>
        <CardContent>
          {organization.projects && organization.projects.length > 0 ? (
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>Name</TableHead>
                  <TableHead>Status</TableHead>
                  <TableHead>Start Date</TableHead>
                  <TableHead>End Date</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {organization.projects.map((project) => (
                  <TableRow key={project.id}>
                    <TableCell>
                      <Link
                        to={`/projects/${project.id}`}
                        className="font-medium text-primary hover:underline"
                      >
                        {project.name}
                      </Link>
                    </TableCell>
                    <TableCell>
                      <Badge variant={statusVariants[project.status] || "default"}>
                        {statusLabels[project.status] || project.status}
                      </Badge>
                    </TableCell>
                    <TableCell>
                      {format(new Date(project.start_date), "MMM d, yyyy")}
                    </TableCell>
                    <TableCell>
                      {project.end_date
                        ? format(new Date(project.end_date), "MMM d, yyyy")
                        : "-"}
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          ) : (
            <div className="py-8 text-center text-muted-foreground">
              No projects yet.{" "}
              <Link
                to={`/projects/new?organization_id=${id}`}
                className="text-primary hover:underline"
              >
                Create one
              </Link>
            </div>
          )}
        </CardContent>
      </Card>

      {/* Contacts Table */}
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <Users className="h-5 w-5" />
            Contacts
          </CardTitle>
          <CardDescription>All contacts at this organization</CardDescription>
        </CardHeader>
        <CardContent>
          {organization.contacts && organization.contacts.length > 0 ? (
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>Name</TableHead>
                  <TableHead>Email</TableHead>
                  <TableHead>Role</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {organization.contacts.map((contact) => (
                  <TableRow key={contact.id}>
                    <TableCell className="font-medium">{contact.name}</TableCell>
                    <TableCell>
                      <a
                        href={`mailto:${contact.email}`}
                        className="text-primary hover:underline"
                      >
                        {contact.email}
                      </a>
                    </TableCell>
                    <TableCell>{contact.role_title || "-"}</TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          ) : (
            <div className="py-8 text-center text-muted-foreground">
              No contacts yet.{" "}
              <Link
                to={`/contacts?organization_id=${id}`}
                className="text-primary hover:underline"
              >
                Add one
              </Link>
            </div>
          )}
        </CardContent>
      </Card>

      {/* Metadata Card */}
      <Card>
        <CardHeader>
          <CardTitle>Metadata</CardTitle>
          <CardDescription>Creation and update information</CardDescription>
        </CardHeader>
        <CardContent className="space-y-2 text-sm">
          <div className="flex justify-between">
            <span className="text-muted-foreground">Created</span>
            <span>
              {format(new Date(organization.created_at), "MMM d, yyyy")}
            </span>
          </div>
          <div className="flex justify-between">
            <span className="text-muted-foreground">Updated</span>
            <span>
              {format(new Date(organization.updated_at), "MMM d, yyyy")}
            </span>
          </div>
        </CardContent>
      </Card>

      {/* Edit Organization Dialog */}
      <Dialog open={showEditDialog} onOpenChange={setShowEditDialog}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Edit Organization</DialogTitle>
          </DialogHeader>
          <div className="space-y-4 py-4">
            <div className="space-y-2">
              <Label htmlFor="edit-name">Name</Label>
              <Input
                id="edit-name"
                value={editFormData.name}
                onChange={(e) =>
                  setEditFormData({ ...editFormData, name: e.target.value })
                }
                placeholder="Organization name"
              />
            </div>
            <div className="space-y-2">
              <Label htmlFor="edit-aliases">Aliases (comma-separated)</Label>
              <Input
                id="edit-aliases"
                value={editFormData.aliases}
                onChange={(e) =>
                  setEditFormData({ ...editFormData, aliases: e.target.value })
                }
                placeholder="e.g. Acme, Acme Inc"
              />
            </div>
            <div className="space-y-2">
              <Label htmlFor="edit-notes">Notes</Label>
              <Textarea
                id="edit-notes"
                value={editFormData.notes}
                onChange={(e) =>
                  setEditFormData({ ...editFormData, notes: e.target.value })
                }
                placeholder="Notes about this organization"
              />
            </div>
            <div className="space-y-2">
              <Label>Address</Label>
              <Input
                value={editFormData.address_street}
                onChange={(e) =>
                  setEditFormData({ ...editFormData, address_street: e.target.value })
                }
                placeholder="Street address"
              />
              <div className="grid grid-cols-2 gap-2">
                <Input
                  value={editFormData.address_city}
                  onChange={(e) =>
                    setEditFormData({ ...editFormData, address_city: e.target.value })
                  }
                  placeholder="City"
                />
                <Input
                  value={editFormData.address_state}
                  onChange={(e) =>
                    setEditFormData({ ...editFormData, address_state: e.target.value })
                  }
                  placeholder="State"
                />
              </div>
              <div className="grid grid-cols-2 gap-2">
                <Input
                  value={editFormData.address_zip}
                  onChange={(e) =>
                    setEditFormData({ ...editFormData, address_zip: e.target.value })
                  }
                  placeholder="ZIP Code"
                />
                <Input
                  value={editFormData.address_country}
                  onChange={(e) =>
                    setEditFormData({ ...editFormData, address_country: e.target.value })
                  }
                  placeholder="Country"
                />
              </div>
            </div>
            <div className="space-y-2">
              <Label htmlFor="edit-inventory-url">Inventory Link</Label>
              <Input
                id="edit-inventory-url"
                value={editFormData.inventory_url}
                onChange={(e) =>
                  setEditFormData({ ...editFormData, inventory_url: e.target.value })
                }
                placeholder="https://inventory.example.com/client/123"
              />
            </div>
          </div>
          <DialogFooter>
            <Button
              variant="outline"
              onClick={() => setShowEditDialog(false)}
            >
              Cancel
            </Button>
            <Button
              onClick={handleEditSubmit}
              disabled={updateOrganization.isPending || !editFormData.name.trim()}
            >
              {updateOrganization.isPending ? "Saving..." : "Save Changes"}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
}
