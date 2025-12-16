/**
 * Project form page for creating and editing projects.
 */

import { Link, useNavigate, useParams, useSearchParams } from "react-router-dom";
import { ArrowLeft } from "lucide-react";
import { useProject, useCreateProject, useUpdateProject } from "@/hooks/useProjects";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { ProjectForm, type ProjectFormValues } from "@/components/forms/ProjectForm";

export function ProjectFormPage() {
  const { id } = useParams<{ id: string }>();
  const navigate = useNavigate();
  const isEditing = Boolean(id);

  const [searchParams] = useSearchParams();
  const initialOrganizationId = searchParams.get("organization_id") ?? undefined;
  const initialContactId = searchParams.get("contact_id") ?? undefined;

  const { data: project, isLoading } = useProject(id);
  const createProject = useCreateProject();
  const updateProject = useUpdateProject();

  const handleSubmit = async (data: ProjectFormValues) => {
    try {
      if (isEditing && id) {
        await updateProject.mutateAsync({ id, data });
        navigate(`/projects/${id}`);
      } else {
        const created = await createProject.mutateAsync(data);
        navigate(`/projects/${created.id}`);
      }
    } catch {
      // Error handled by mutation hooks
    }
  };

  const handleCancel = () => {
    if (isEditing && id) {
      navigate(`/projects/${id}`);
    } else {
      navigate("/projects");
    }
  };

  if (isEditing && isLoading) {
    return (
      <div className="flex h-64 items-center justify-center">
        <div className="text-muted-foreground">Loading project...</div>
      </div>
    );
  }

  if (isEditing && !project) {
    return (
      <div className="space-y-4">
        <Button variant="ghost" asChild>
          <Link to="/projects">
            <ArrowLeft className="mr-2 h-4 w-4" />
            Back to Projects
          </Link>
        </Button>
        <div className="rounded-md bg-destructive/10 p-4 text-destructive">
          Failed to load project.
        </div>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      <div className="flex items-center gap-4">
        <Button variant="ghost" asChild>
          <Link to={isEditing ? `/projects/${id}` : "/projects"}>
            <ArrowLeft className="mr-2 h-4 w-4" />
            Back
          </Link>
        </Button>
        <h1 className="text-2xl font-bold">
          {isEditing ? "Edit Project" : "New Project"}
        </h1>
      </div>

      <Card>
        <CardHeader>
          <CardTitle>
            {isEditing ? "Update Project Details" : "Project Details"}
          </CardTitle>
        </CardHeader>
        <CardContent>
          <ProjectForm
            project={project}
            initialValues={
              !isEditing
                ? {
                    organization_id: initialOrganizationId,
                    contact_ids: initialContactId ? [initialContactId] : undefined,
                    primary_contact_id: initialContactId,
                  }
                : undefined
            }
            onSubmit={handleSubmit}
            onCancel={handleCancel}
            isSubmitting={createProject.isPending || updateProject.isPending}
          />
        </CardContent>
      </Card>
    </div>
  );
}
