/**
 * Project detail page.
 */

import { useState } from "react";
import { Link, useNavigate, useParams } from "react-router-dom";
import { format } from "date-fns";
import {
  ArrowLeft,
  Edit,
  ExternalLink,
  MapPin,
  Calendar,
  User,
  FileText,
  History,
} from "lucide-react";
import { useProject, useDeleteProject } from "@/hooks/useProjects";
import { useProjectMondayBoard } from "@/hooks/useMondaySync";
import { JiraLinksSection } from "@/components/jira/JiraLinksSection";
import { DocumentUpload } from "@/components/forms/DocumentUpload";
import { DocumentList } from "@/components/tables/DocumentList";
import { DocumentTagSuggestions } from "@/components/features/DocumentTagSuggestions";
import { DetailPageSkeleton } from "@/components/skeletons/DetailPageSkeleton";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
} from "@/components/ui/dialog";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { AuditTimeline } from "@/components/audit/AuditTimeline";
import type { ProjectLocation, ProjectStatus } from "@/types/project";

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

const locationLabels: Record<ProjectLocation, string> = {
  headquarters: "Headquarters/HQ",
  test_house: "Test House",
  remote: "Remote",
  client_site: "Client Site",
  other: "Other",
};

const formatLocation = (
  location: ProjectLocation,
  locationOther: string | null
): string => {
  if (location === "other" && locationOther) {
    return `Other (${locationOther})`;
  }
  return locationLabels[location] || location;
};

export function ProjectDetailPage() {
  const { id } = useParams<{ id: string }>();
  const navigate = useNavigate();
  const { data: project, isLoading, isError } = useProject(id);
  const deleteProject = useDeleteProject();
  const { data: mondayBoard } = useProjectMondayBoard(id);
  const [docPage, setDocPage] = useState(1);
  const [docPageSize, setDocPageSize] = useState(20);

  const handleDelete = async () => {
    if (!id) return;
    try {
      await deleteProject.mutateAsync(id);
      navigate("/projects");
    } catch {
      // Error handled by mutation
    }
  };

  if (isLoading) {
    return <DetailPageSkeleton type="project" />;
  }

  if (isError || !project) {
    return (
      <div className="space-y-4">
        <Button variant="ghost" asChild>
          <Link to="/projects">
            <ArrowLeft className="mr-2 h-4 w-4" />
            Back to Projects
          </Link>
        </Button>
        <div className="rounded-md bg-destructive/10 p-4 text-destructive">
          Failed to load project. It may not exist or you may not have access.
        </div>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-4">
          <Button variant="ghost" asChild>
            <Link to="/projects">
              <ArrowLeft className="mr-2 h-4 w-4" />
              Back
            </Link>
          </Button>
          <div>
            <div className="flex items-center gap-2">
              <h1 className="text-2xl font-bold">{project.name}</h1>
              <Badge variant={statusVariants[project.status]}>
                {statusLabels[project.status]}
              </Badge>
            </div>
            <p className="text-muted-foreground">{project.organization.name}</p>
          </div>
        </div>

        <div className="flex items-center gap-2">
          <Button variant="outline" asChild>
            <Link to={`/projects/${id}/edit`}>
              <Edit className="mr-2 h-4 w-4" />
              Edit
            </Link>
          </Button>
          <Dialog>
            <DialogTrigger asChild>
              <Button variant="outline">Cancel Project</Button>
            </DialogTrigger>
            <DialogContent>
              <DialogHeader>
                <DialogTitle>Cancel Project</DialogTitle>
                <DialogDescription>
                  Are you sure you want to cancel "{project.name}"? The project
                  will be marked as cancelled and hidden from default lists. You
                  can restore it later by changing the status.
                </DialogDescription>
              </DialogHeader>
              <DialogFooter>
                <Button
                  variant="destructive"
                  onClick={handleDelete}
                  disabled={deleteProject.isPending}
                >
                  {deleteProject.isPending ? "Cancelling..." : "Cancel Project"}
                </Button>
              </DialogFooter>
            </DialogContent>
          </Dialog>
        </div>
      </div>

      <Tabs defaultValue="details" className="w-full">
        <TabsList>
          <TabsTrigger value="details">Details</TabsTrigger>
          <TabsTrigger value="history">
            <History className="mr-2 h-4 w-4" />
            History
          </TabsTrigger>
        </TabsList>

        <TabsContent value="details">
          <div className="grid gap-6 lg:grid-cols-3">
            <div className="lg:col-span-2 space-y-6">
              <Card>
                <CardHeader>
                  <CardTitle>Description</CardTitle>
            </CardHeader>
            <CardContent>
              <p className="whitespace-pre-wrap">{project.description}</p>
            </CardContent>
          </Card>

          <Card>
            <CardHeader>
              <CardTitle>Project Details</CardTitle>
            </CardHeader>
            <CardContent className="grid gap-4 sm:grid-cols-2">
              <div className="flex items-center gap-2">
                <Calendar className="h-4 w-4 text-muted-foreground" />
                <span className="text-sm">
                  Start: {format(new Date(project.start_date), "MMM d, yyyy")}
                </span>
              </div>
              {project.end_date && (
                <div className="flex items-center gap-2">
                  <Calendar className="h-4 w-4 text-muted-foreground" />
                  <span className="text-sm">
                    End: {format(new Date(project.end_date), "MMM d, yyyy")}
                  </span>
                </div>
              )}
              <div className="flex items-center gap-2">
                <MapPin className="h-4 w-4 text-muted-foreground" />
                <span className="text-sm">
                  {formatLocation(project.location, project.location_other)}
                </span>
              </div>
              <div className="flex items-center gap-2">
                <User className="h-4 w-4 text-muted-foreground" />
                <span className="text-sm">{project.owner.display_name}</span>
              </div>
            </CardContent>
          </Card>

          {project.contacts && project.contacts.length > 0 && (
            <Card>
              <CardHeader>
                <CardTitle>Contacts</CardTitle>
              </CardHeader>
              <CardContent>
                <div className="space-y-3">
                  {project.contacts.map((contact) => (
                    <div
                      key={contact.id}
                      className="flex items-center justify-between rounded-md border p-3"
                    >
                      <div>
                        <div className="flex items-center gap-2">
                          <span className="font-medium">{contact.name}</span>
                          {contact.is_primary && (
                            <Badge variant="secondary">Primary</Badge>
                          )}
                        </div>
                        <div className="text-sm text-muted-foreground">
                          {contact.role && `${contact.role} • `}
                          {contact.email}
                        </div>
                      </div>
                    </div>
                  ))}
                </div>
              </CardContent>
            </Card>
          )}

          {(project.milestone_version || project.run_number || project.engagement_period) && (
            <Card>
              <CardHeader>
                <CardTitle>Project Tracking</CardTitle>
              </CardHeader>
              <CardContent className="space-y-2">
                {project.milestone_version && (
                  <div className="flex justify-between">
                    <span className="text-muted-foreground">Milestone/Version</span>
                    <span className="font-medium">{project.milestone_version}</span>
                  </div>
                )}
                {project.run_number && (
                  <div className="flex justify-between">
                    <span className="text-muted-foreground">Run Number</span>
                    <span className="font-medium">{project.run_number}</span>
                  </div>
                )}
                {project.engagement_period && (
                  <div className="flex justify-between">
                    <span className="text-muted-foreground">Engagement Period</span>
                    <span className="font-medium">{project.engagement_period}</span>
                  </div>
                )}
              </CardContent>
            </Card>
          )}

          {project.pm_notes && (
            <Card>
              <CardHeader>
                <CardTitle>PM Notes</CardTitle>
              </CardHeader>
              <CardContent>
                <p className="whitespace-pre-wrap">{project.pm_notes}</p>
              </CardContent>
            </Card>
          )}

          <Card>
            <CardHeader>
              <CardTitle className="flex items-center gap-2">
                <FileText className="h-5 w-5" />
                Documents
              </CardTitle>
            </CardHeader>
            <CardContent className="space-y-4">
              <DocumentUpload projectId={id!} />
              <DocumentList
                projectId={id!}
                page={docPage}
                pageSize={docPageSize}
                onPageChange={setDocPage}
                onPageSizeChange={setDocPageSize}
              />
            </CardContent>
          </Card>
        </div>

        <div className="space-y-6">
          {/* Document Tag Suggestions - show above Tags card */}
          <DocumentTagSuggestions
            projectId={id!}
            currentTagIds={project.tags?.map((t) => t.id) || []}
          />

          {/* Jira Links Section */}
          <JiraLinksSection projectId={id!} />

          {project.tags && project.tags.length > 0 && (
            <Card>
              <CardHeader>
                <CardTitle>Tags</CardTitle>
              </CardHeader>
              <CardContent>
                <div className="flex flex-wrap gap-2">
                  {project.tags
                    .slice()
                    .sort((a, b) => a.name.localeCompare(b.name))
                    .map((tag) => (
                      <Badge key={tag.id} variant="outline">
                        {tag.name}
                      </Badge>
                    ))}
                </div>
              </CardContent>
            </Card>
          )}

          <Card>
            <CardHeader>
              <CardTitle>Billing</CardTitle>
            </CardHeader>
            <CardContent className="space-y-2">
              {project.billing_amount !== null && (
                <div className="flex justify-between">
                  <span className="text-muted-foreground">Amount</span>
                  <span className="font-medium">
                    ${project.billing_amount.toLocaleString()}
                  </span>
                </div>
              )}
              {project.invoice_count !== null && (
                <div className="flex justify-between">
                  <span className="text-muted-foreground">Invoices</span>
                  <span className="font-medium">{project.invoice_count}</span>
                </div>
              )}
              {project.billing_recipient && (
                <div className="flex justify-between">
                  <span className="text-muted-foreground">Recipient</span>
                  <span className="font-medium">
                    {project.billing_recipient}
                  </span>
                </div>
              )}
              {project.billing_notes && (
                <div className="mt-2 border-t pt-2">
                  <span className="text-sm text-muted-foreground">Notes:</span>
                  <p className="mt-1 text-sm">{project.billing_notes}</p>
                </div>
              )}
            </CardContent>
          </Card>

          {(project.monday_url || project.monday_board_id || project.jira_url || project.gitlab_url) && (
            <Card>
              <CardHeader>
                <CardTitle>External Links</CardTitle>
              </CardHeader>
              <CardContent className="space-y-2">
                {project.monday_url && (
                  <a
                    href={project.monday_url}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="flex items-center gap-2 text-sm text-primary hover:underline"
                  >
                    <ExternalLink className="h-4 w-4" />
                    Monday.com
                  </a>
                )}
                {project.monday_board_id && mondayBoard && (
                  <div className="flex items-center gap-2 text-sm text-muted-foreground">
                    <ExternalLink className="h-4 w-4" />
                    <span>Linked Board: {mondayBoard.name}</span>
                  </div>
                )}
                {project.jira_url && (
                  <a
                    href={project.jira_url}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="flex items-center gap-2 text-sm text-primary hover:underline"
                  >
                    <ExternalLink className="h-4 w-4" />
                    Jira
                  </a>
                )}
                {project.gitlab_url && (
                  <a
                    href={project.gitlab_url}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="flex items-center gap-2 text-sm text-primary hover:underline"
                  >
                    <ExternalLink className="h-4 w-4" />
                    GitLab
                  </a>
                )}
              </CardContent>
            </Card>
          )}

          <Card>
            <CardHeader>
              <CardTitle>Metadata</CardTitle>
              <CardDescription>Creation and update information</CardDescription>
            </CardHeader>
            <CardContent className="space-y-2 text-sm">
              <div className="flex justify-between">
                <span className="text-muted-foreground">Created</span>
                <span>{format(new Date(project.created_at), "MMM d, yyyy")}</span>
              </div>
              <div className="flex justify-between">
                <span className="text-muted-foreground">Created by</span>
                <span>{project.created_by.display_name}</span>
              </div>
              <div className="flex justify-between">
                <span className="text-muted-foreground">Updated</span>
                <span>{format(new Date(project.updated_at), "MMM d, yyyy")}</span>
              </div>
              <div className="flex justify-between">
                <span className="text-muted-foreground">Updated by</span>
                <span>{project.updated_by.display_name}</span>
              </div>
            </CardContent>
          </Card>
            </div>
          </div>
        </TabsContent>

        <TabsContent value="history">
          <Card>
            <CardContent className="pt-6">
              <AuditTimeline entityType="project" entityId={id!} />
            </CardContent>
          </Card>
        </TabsContent>
      </Tabs>
    </div>
  );
}
