/**
 * Contact detail page with linked projects.
 */

import { useState } from "react";
import { Link, useNavigate, useParams } from "react-router-dom";
import { format } from "date-fns";
import {
  ArrowLeft,
  Building2,
  Edit,
  ExternalLink,
  FolderKanban,
  Mail,
  Phone,
  User,
} from "lucide-react";
import {
  useContact,
  useUpdateContact,
  useDeleteContact,
} from "@/hooks/useContacts";
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

export function ContactDetailPage() {
  const { id } = useParams<{ id: string }>();
  const navigate = useNavigate();
  const { data: contact, isLoading, isError } = useContact(id);
  const updateContact = useUpdateContact();
  const deleteContact = useDeleteContact();

  const [showEditDialog, setShowEditDialog] = useState(false);
  const [editFormData, setEditFormData] = useState({
    name: "",
    email: "",
    role_title: "",
    phone: "",
    notes: "",
    monday_url: "",
  });

  const handleEditOpen = () => {
    if (contact) {
      setEditFormData({
        name: contact.name,
        email: contact.email,
        role_title: contact.role_title || "",
        phone: contact.phone || "",
        notes: contact.notes || "",
        monday_url: contact.monday_url || "",
      });
      setShowEditDialog(true);
    }
  };

  const handleEditSubmit = async () => {
    if (!id || !editFormData.name.trim() || !editFormData.email.trim()) return;
    await updateContact.mutateAsync({
      id,
      data: {
        name: editFormData.name.trim(),
        email: editFormData.email.trim(),
        role_title: editFormData.role_title || undefined,
        phone: editFormData.phone || undefined,
        notes: editFormData.notes || undefined,
        monday_url: editFormData.monday_url || undefined,
      },
    });
    setShowEditDialog(false);
  };

  const handleDelete = async () => {
    if (!id) return;
    try {
      await deleteContact.mutateAsync(id);
      navigate("/contacts");
    } catch {
      // Error handled by mutation
    }
  };

  if (isLoading) {
    return (
      <div className="flex h-64 items-center justify-center">
        <div className="text-muted-foreground">Loading contact...</div>
      </div>
    );
  }

  if (isError || !contact) {
    return (
      <div className="space-y-4">
        <Button variant="ghost" asChild>
          <Link to="/contacts">
            <ArrowLeft className="mr-2 h-4 w-4" />
            Back to Contacts
          </Link>
        </Button>
        <div className="rounded-md bg-destructive/10 p-4 text-destructive">
          Failed to load contact. It may not exist or you may not have access.
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
            <Link to="/contacts">
              <ArrowLeft className="mr-2 h-4 w-4" />
              Back
            </Link>
          </Button>
          <div>
            <div className="flex items-center gap-2">
              <User className="h-6 w-6 text-muted-foreground" />
              <h1 className="text-2xl font-bold">{contact.name}</h1>
            </div>
            <div className="flex items-center gap-2 text-muted-foreground">
              {contact.role_title && <span>{contact.role_title} at </span>}
              <Link
                to={`/organizations/${contact.organization_id}`}
                className="text-primary hover:underline flex items-center gap-1"
              >
                <Building2 className="h-4 w-4" />
                {contact.organization.name}
              </Link>
            </div>
          </div>
        </div>

        <div className="flex items-center gap-2">
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
                <DialogTitle>Delete Contact</DialogTitle>
                <DialogDescription>
                  Are you sure you want to delete "{contact.name}"? This action
                  cannot be undone.
                </DialogDescription>
              </DialogHeader>
              <DialogFooter>
                <Button
                  variant="destructive"
                  onClick={handleDelete}
                  disabled={deleteContact.isPending}
                >
                  {deleteContact.isPending ? "Deleting..." : "Delete"}
                </Button>
              </DialogFooter>
            </DialogContent>
          </Dialog>
        </div>
      </div>

      {/* Stats Card */}
      <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
        <Card>
          <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
            <CardTitle className="text-sm font-medium">Projects</CardTitle>
            <FolderKanban className="h-4 w-4 text-muted-foreground" />
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold">{contact.project_count}</div>
          </CardContent>
        </Card>
      </div>

      {/* Contact Info Card */}
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <User className="h-5 w-5" />
            Contact Information
          </CardTitle>
        </CardHeader>
        <CardContent className="space-y-4 text-sm">
          <div className="flex items-center gap-2">
            <Mail className="h-4 w-4 text-muted-foreground" />
            <a
              href={`mailto:${contact.email}`}
              className="text-primary hover:underline"
            >
              {contact.email}
            </a>
          </div>
          {contact.phone && (
            <div className="flex items-center gap-2">
              <Phone className="h-4 w-4 text-muted-foreground" />
              <a
                href={`tel:${contact.phone}`}
                className="text-primary hover:underline"
              >
                {contact.phone}
              </a>
            </div>
          )}
          {contact.monday_url && (
            <div className="flex items-center gap-2">
              <ExternalLink className="h-4 w-4 text-muted-foreground" />
              <a
                href={contact.monday_url}
                target="_blank"
                rel="noopener noreferrer"
                className="text-primary hover:underline flex items-center gap-1"
              >
                View on Monday.com
                <ExternalLink className="h-3 w-3" />
              </a>
            </div>
          )}
          {contact.notes && (
            <div>
              <span className="text-muted-foreground">Notes: </span>
              <span>{contact.notes}</span>
            </div>
          )}
        </CardContent>
      </Card>

      {/* Projects Table */}
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <FolderKanban className="h-5 w-5" />
            Projects
          </CardTitle>
          <CardDescription>
            All projects this contact is associated with
          </CardDescription>
        </CardHeader>
        <CardContent>
          {contact.projects && contact.projects.length > 0 ? (
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>Name</TableHead>
                  <TableHead>Organization</TableHead>
                  <TableHead>Status</TableHead>
                  <TableHead>Start Date</TableHead>
                  <TableHead>End Date</TableHead>
                  <TableHead>Role</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {contact.projects.map((project) => (
                  <TableRow key={project.id}>
                    <TableCell>
                      <Link
                        to={`/projects/${project.id}`}
                        className="font-medium text-primary hover:underline"
                      >
                        {project.name}
                      </Link>
                    </TableCell>
                    <TableCell>{project.organization_name}</TableCell>
                    <TableCell>
                      <Badge
                        variant={statusVariants[project.status] || "default"}
                      >
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
                    <TableCell>
                      {project.is_primary && (
                        <Badge variant="secondary">Primary</Badge>
                      )}
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          ) : (
            <div className="py-8 text-center text-muted-foreground">
              No projects yet. This contact has not been added to any projects.
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
              {format(new Date(contact.created_at), "MMM d, yyyy")}
            </span>
          </div>
          <div className="flex justify-between">
            <span className="text-muted-foreground">Updated</span>
            <span>
              {format(new Date(contact.updated_at), "MMM d, yyyy")}
            </span>
          </div>
        </CardContent>
      </Card>

      {/* Edit Contact Dialog */}
      <Dialog open={showEditDialog} onOpenChange={setShowEditDialog}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Edit Contact</DialogTitle>
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
                placeholder="Full name"
              />
            </div>
            <div className="space-y-2">
              <Label htmlFor="edit-email">Email</Label>
              <Input
                id="edit-email"
                type="email"
                value={editFormData.email}
                onChange={(e) =>
                  setEditFormData({ ...editFormData, email: e.target.value })
                }
                placeholder="email@example.com"
              />
            </div>
            <div className="space-y-2">
              <Label htmlFor="edit-role">Role / Title</Label>
              <Input
                id="edit-role"
                value={editFormData.role_title}
                onChange={(e) =>
                  setEditFormData({
                    ...editFormData,
                    role_title: e.target.value,
                  })
                }
                placeholder="e.g. Project Manager"
              />
            </div>
            <div className="space-y-2">
              <Label htmlFor="edit-phone">Phone</Label>
              <Input
                id="edit-phone"
                type="tel"
                value={editFormData.phone}
                onChange={(e) =>
                  setEditFormData({ ...editFormData, phone: e.target.value })
                }
                placeholder="+1 (555) 000-0000"
              />
            </div>
            <div className="space-y-2">
              <Label htmlFor="edit-monday-url">Monday.com URL</Label>
              <Input
                id="edit-monday-url"
                value={editFormData.monday_url}
                onChange={(e) =>
                  setEditFormData({
                    ...editFormData,
                    monday_url: e.target.value,
                  })
                }
                placeholder="https://monday.com/..."
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
                placeholder="Notes about this contact"
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
              disabled={
                updateContact.isPending ||
                !editFormData.name.trim() ||
                !editFormData.email.trim()
              }
            >
              {updateContact.isPending ? "Saving..." : "Save Changes"}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
}
