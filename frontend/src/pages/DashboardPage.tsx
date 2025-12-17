/**
 * Dashboard page with project overview.
 */

import { Link } from "react-router-dom";
import { format } from "date-fns";
import {
  FolderOpen,
  Building,
  Users,
  TrendingUp,
  ArrowRight,
} from "lucide-react";
import { useProjects } from "@/hooks/useProjects";
import { useOrganizations } from "@/hooks/useOrganizations";
import { useContacts } from "@/hooks/useContacts";
import { RecentProjectsSkeleton } from "@/components/skeletons/DashboardSkeleton";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import type { ProjectStatus } from "@/types/project";

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

export function DashboardPage() {
  const { data: activeProjects, isLoading: loadingActive } = useProjects({
    status: ["active"],
    pageSize: 5,
    sortBy: "updated_at",
    sortOrder: "desc",
  });

  const { data: allProjects, isLoading: loadingAll } = useProjects({
    pageSize: 1,
  });

  const { data: organizations, isLoading: loadingOrgs } = useOrganizations({
    pageSize: 1,
  });

  const { data: contacts, isLoading: loadingContacts } = useContacts({
    pageSize: 1,
  });

  const isLoading =
    loadingActive || loadingAll || loadingOrgs || loadingContacts;

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-bold">Dashboard</h1>
        <p className="text-muted-foreground">
          Overview of your project portfolio
        </p>
      </div>

      <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-4">
        <Card>
          <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
            <CardTitle className="text-sm font-medium">
              Total Projects
            </CardTitle>
            <FolderOpen className="h-4 w-4 text-muted-foreground" />
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold">
              {isLoading ? "..." : allProjects?.total ?? 0}
            </div>
            <p className="text-xs text-muted-foreground">
              All time project count
            </p>
          </CardContent>
        </Card>

        <Card>
          <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
            <CardTitle className="text-sm font-medium">
              Active Projects
            </CardTitle>
            <TrendingUp className="h-4 w-4 text-muted-foreground" />
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold">
              {isLoading ? "..." : activeProjects?.total ?? 0}
            </div>
            <p className="text-xs text-muted-foreground">Currently in progress</p>
          </CardContent>
        </Card>

        <Card>
          <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
            <CardTitle className="text-sm font-medium">Organizations</CardTitle>
            <Building className="h-4 w-4 text-muted-foreground" />
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold">
              {isLoading ? "..." : organizations?.total ?? 0}
            </div>
            <p className="text-xs text-muted-foreground">Client organizations</p>
          </CardContent>
        </Card>

        <Card>
          <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
            <CardTitle className="text-sm font-medium">Contacts</CardTitle>
            <Users className="h-4 w-4 text-muted-foreground" />
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold">
              {isLoading ? "..." : contacts?.total ?? 0}
            </div>
            <p className="text-xs text-muted-foreground">
              People in your network
            </p>
          </CardContent>
        </Card>
      </div>

      <div className="grid gap-6 lg:grid-cols-2">
        <Card>
          <CardHeader>
            <CardTitle>Recent Active Projects</CardTitle>
            <CardDescription>
              Your most recently updated active projects
            </CardDescription>
          </CardHeader>
          <CardContent>
            {loadingActive ? (
              <RecentProjectsSkeleton />
            ) : activeProjects?.items.length === 0 ? (
              <div className="py-4 text-center text-muted-foreground">
                No active projects found.
              </div>
            ) : (
              <div className="space-y-4">
                {activeProjects?.items.map((project) => (
                  <div
                    key={project.id}
                    className="flex items-center justify-between rounded-md border p-3"
                  >
                    <div className="min-w-0 flex-1">
                      <Link
                        to={`/projects/${project.id}`}
                        className="font-medium hover:underline"
                      >
                        {project.name}
                      </Link>
                      <div className="flex items-center gap-2 text-sm text-muted-foreground">
                        <span>{project.organization.name}</span>
                        <span>•</span>
                        <span>
                          Updated{" "}
                          {format(new Date(project.updated_at), "MMM d")}
                        </span>
                      </div>
                    </div>
                    <Badge variant={statusVariants[project.status]}>
                      {statusLabels[project.status]}
                    </Badge>
                  </div>
                ))}

                {activeProjects && activeProjects.total > 5 && (
                  <Button variant="ghost" asChild className="w-full">
                    <Link to="/projects?status=active">
                      View all active projects
                      <ArrowRight className="ml-2 h-4 w-4" />
                    </Link>
                  </Button>
                )}
              </div>
            )}
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle>Quick Actions</CardTitle>
            <CardDescription>Common tasks and shortcuts</CardDescription>
          </CardHeader>
          <CardContent className="space-y-2">
            <Button asChild variant="outline" className="w-full justify-start">
              <Link to="/projects/new">
                <FolderOpen className="mr-2 h-4 w-4" />
                Create New Project
              </Link>
            </Button>
            <Button asChild variant="outline" className="w-full justify-start">
              <Link to="/organizations">
                <Building className="mr-2 h-4 w-4" />
                Manage Organizations
              </Link>
            </Button>
            <Button asChild variant="outline" className="w-full justify-start">
              <Link to="/contacts">
                <Users className="mr-2 h-4 w-4" />
                Manage Contacts
              </Link>
            </Button>
            <Button asChild variant="outline" className="w-full justify-start">
              <Link to="/search">
                <TrendingUp className="mr-2 h-4 w-4" />
                Search Projects
              </Link>
            </Button>
          </CardContent>
        </Card>
      </div>
    </div>
  );
}
