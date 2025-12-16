/**
 * Project form component with React Hook Form + Zod validation.
 */

import { useEffect } from "react";
import { useForm } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { z } from "zod";
import { format } from "date-fns";
import { Sparkles, Loader2, AlertCircle } from "lucide-react";
import { cn } from "@/lib/utils";
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";
import { useAutofill } from "@/hooks/useImport";
import {
  Form,
  FormControl,
  FormField,
  FormItem,
  FormLabel,
  FormMessage,
} from "@/components/ui/form";
import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";
import { Button } from "@/components/ui/button";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { OrganizationSelectCombobox } from "@/components/forms/OrganizationCombobox";
import { useOrganizations } from "@/hooks/useOrganizations";
import { useContacts } from "@/hooks/useContacts";
import { useAllTags } from "@/hooks/useTags";
import type { ProjectDetail, ProjectStatus } from "@/types/project";

const projectStatuses: { value: ProjectStatus; label: string }[] = [
  { value: "approved", label: "Approved" },
  { value: "active", label: "Active" },
  { value: "on_hold", label: "On Hold" },
  { value: "completed", label: "Completed" },
  { value: "cancelled", label: "Cancelled" },
];

const projectFormSchema = z.object({
  name: z.string().min(1, "Project name is required").max(255),
  organization_id: z.string().min(1, "Organization is required"),
  description: z.string().min(1, "Description is required"),
  status: z.enum(["approved", "active", "on_hold", "completed", "cancelled"]),
  start_date: z.string().min(1, "Start date is required"),
  end_date: z.string().optional(),
  location: z.string().min(1, "Location is required").max(255),
  contact_ids: z.array(z.string()).default([]),
  primary_contact_id: z.string().min(1, "Primary contact is required"),
  tag_ids: z.array(z.string()).min(1, "At least one tag is required"),
  billing_amount: z.number().optional(),
  invoice_count: z.number().int().optional(),
  billing_recipient: z.string().max(255).optional(),
  billing_notes: z.string().optional(),
  pm_notes: z.string().optional(),
  monday_url: z.string().url().optional().or(z.literal("")),
  jira_url: z.string().url().optional().or(z.literal("")),
  gitlab_url: z.string().url().optional().or(z.literal("")),
});

export type ProjectFormValues = z.infer<typeof projectFormSchema>;

const fieldLabels: Record<string, string> = {
  name: "Project Name",
  organization_id: "Organization",
  description: "Description",
  status: "Status",
  start_date: "Start Date",
  end_date: "End Date",
  location: "Location",
  primary_contact_id: "Primary Contact",
  tag_ids: "Tags",
  contact_ids: "Contacts",
  billing_amount: "Billing Amount",
  invoice_count: "Invoice Count",
  billing_recipient: "Billing Recipient",
  billing_notes: "Billing Notes",
  pm_notes: "PM Notes",
  monday_url: "Monday.com URL",
  jira_url: "Jira URL",
  gitlab_url: "GitLab URL",
};

interface ProjectFormProps {
  project?: ProjectDetail;
  onSubmit: (data: ProjectFormValues) => void;
  onCancel: () => void;
  isSubmitting?: boolean;
}

export function ProjectForm({
  project,
  onSubmit,
  onCancel,
  isSubmitting = false,
}: ProjectFormProps) {
  const { data: orgsData } = useOrganizations({ pageSize: 100 });
  const { data: allTags } = useAllTags();
  const autofillMutation = useAutofill();

  const form = useForm<ProjectFormValues>({
    resolver: zodResolver(projectFormSchema),
    defaultValues: {
      name: project?.name ?? "",
      organization_id: project?.organization?.id ?? "",
      description: project?.description ?? "",
      status: project?.status ?? "approved",
      start_date: project?.start_date
        ? format(new Date(project.start_date), "yyyy-MM-dd")
        : format(new Date(), "yyyy-MM-dd"),
      end_date: project?.end_date
        ? format(new Date(project.end_date), "yyyy-MM-dd")
        : "",
      location: project?.location ?? "",
      contact_ids: project?.contacts?.map((c) => c.id) ?? [],
      primary_contact_id:
        project?.contacts?.find((c) => c.is_primary)?.id ?? "",
      tag_ids: project?.tags?.map((t) => t.id) ?? [],
      billing_amount: project?.billing_amount ?? undefined,
      invoice_count: project?.invoice_count ?? undefined,
      billing_recipient: project?.billing_recipient ?? "",
      billing_notes: project?.billing_notes ?? "",
      pm_notes: project?.pm_notes ?? "",
      monday_url: project?.monday_url ?? "",
      jira_url: project?.jira_url ?? "",
      gitlab_url: project?.gitlab_url ?? "",
    },
  });

  const selectedOrgId = form.watch("organization_id");
  const { data: contactsData } = useContacts({
    organizationId: selectedOrgId,
    pageSize: 100,
  });

  useEffect(() => {
    if (selectedOrgId && selectedOrgId !== project?.organization?.id) {
      form.setValue("contact_ids", []);
      form.setValue("primary_contact_id", "");
    }
  }, [selectedOrgId, project?.organization?.id, form]);

  const handleSubmit = form.handleSubmit(
    (data) => {
      // Ensure primary_contact_id is included in contact_ids
      const contactIds = data.contact_ids.includes(data.primary_contact_id)
        ? data.contact_ids
        : [...data.contact_ids, data.primary_contact_id];

      const cleanData = {
        ...data,
        contact_ids: contactIds,
        end_date: data.end_date || undefined,
        monday_url: data.monday_url || undefined,
        jira_url: data.jira_url || undefined,
        gitlab_url: data.gitlab_url || undefined,
      };
      onSubmit(cleanData);
    },
    // Error handler - scroll to first error
    (errors) => {
      const firstErrorField = Object.keys(errors)[0];
      if (firstErrorField) {
        const element = document.querySelector(`[name="${firstErrorField}"]`);
        if (element) {
          element.scrollIntoView({ behavior: "smooth", block: "center" });
          (element as HTMLElement).focus?.();
        }
      }
    },
  );

  const handleAutofill = async () => {
    const name = form.getValues("name");
    const description = form.getValues("description");
    const organizationId = form.getValues("organization_id");

    if (!name.trim()) {
      return; // Name is required for autofill
    }

    try {
      const result = await autofillMutation.mutateAsync({
        name,
        existing_description: description || undefined,
        organization_id: organizationId || undefined,
      });

      // Apply suggested tags if available
      if (result.suggested_tag_ids && result.suggested_tag_ids.length > 0) {
        const currentTags = form.getValues("tag_ids");
        // Merge suggested tags with existing, avoiding duplicates
        const mergedTags = [...new Set([...currentTags, ...result.suggested_tag_ids])];
        form.setValue("tag_ids", mergedTags);
      }

      // Apply suggested description if available and field is empty
      if (result.suggested_description && !description) {
        form.setValue("description", result.suggested_description);
      }
    } catch {
      // Error is handled by mutation - could add toast notification here
    }
  };

  return (
    <Form {...form}>
      <form onSubmit={handleSubmit} className="space-y-6">
        {Object.keys(form.formState.errors).length > 0 &&
          form.formState.isSubmitted && (
            <Alert variant="destructive" className="mb-6">
              <AlertCircle className="h-4 w-4" />
              <AlertTitle>Please fix the following errors</AlertTitle>
              <AlertDescription>
                <ul className="list-disc list-inside mt-2 space-y-1">
                  {Object.entries(form.formState.errors).map(
                    ([field, error]) => (
                      <li key={field}>
                        {fieldLabels[field] || field}:{" "}
                        {error?.message as string}
                      </li>
                    ),
                  )}
                </ul>
              </AlertDescription>
            </Alert>
          )}

        <div className="grid gap-4 md:grid-cols-2">
          <FormField
            control={form.control}
            name="name"
            render={({ field }) => (
              <FormItem>
                <FormLabel>Project Name <span className="text-destructive">*</span></FormLabel>
                <FormControl>
                  <Input placeholder="Enter project name" {...field} />
                </FormControl>
                <FormMessage />
              </FormItem>
            )}
          />

          <FormField
            control={form.control}
            name="organization_id"
            render={({ field }) => (
              <FormItem>
                <FormLabel>Organization <span className="text-destructive">*</span></FormLabel>
                <FormControl>
                  <OrganizationSelectCombobox
                    organizations={orgsData?.items ?? []}
                    value={field.value}
                    onChange={field.onChange}
                    placeholder="Select organization"
                  />
                </FormControl>
                <FormMessage />
              </FormItem>
            )}
          />
        </div>

        <FormField
          control={form.control}
          name="description"
          render={({ field }) => (
            <FormItem>
              <FormLabel>Description <span className="text-destructive">*</span></FormLabel>
              <FormControl>
                <Textarea
                  placeholder="Describe the project scope and objectives"
                  className="min-h-[100px]"
                  {...field}
                />
              </FormControl>
              <FormMessage />
            </FormItem>
          )}
        />

        <div className="grid gap-4 md:grid-cols-3">
          <FormField
            control={form.control}
            name="status"
            render={({ field }) => (
              <FormItem>
                <FormLabel>Status <span className="text-destructive">*</span></FormLabel>
                <Select
                  onValueChange={field.onChange}
                  defaultValue={field.value}
                >
                  <FormControl>
                    <SelectTrigger>
                      <SelectValue placeholder="Select status" />
                    </SelectTrigger>
                  </FormControl>
                  <SelectContent>
                    {projectStatuses.map((status) => (
                      <SelectItem key={status.value} value={status.value}>
                        {status.label}
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
                <FormMessage />
              </FormItem>
            )}
          />

          <FormField
            control={form.control}
            name="start_date"
            render={({ field }) => (
              <FormItem>
                <FormLabel>Start Date <span className="text-destructive">*</span></FormLabel>
                <FormControl>
                  <Input type="date" {...field} />
                </FormControl>
                <FormMessage />
              </FormItem>
            )}
          />

          <FormField
            control={form.control}
            name="end_date"
            render={({ field }) => (
              <FormItem>
                <FormLabel>End Date</FormLabel>
                <FormControl>
                  <Input type="date" {...field} />
                </FormControl>
                <FormMessage />
              </FormItem>
            )}
          />
        </div>

        <FormField
          control={form.control}
          name="location"
          render={({ field }) => (
            <FormItem>
              <FormLabel>Location <span className="text-destructive">*</span></FormLabel>
              <FormControl>
                <Input placeholder="Enter project location" {...field} />
              </FormControl>
              <FormMessage />
            </FormItem>
          )}
        />

        <div className="grid gap-4 md:grid-cols-2">
          <FormField
            control={form.control}
            name="primary_contact_id"
            render={({ field }) => (
              <FormItem>
                <FormLabel>Primary Contact <span className="text-destructive">*</span></FormLabel>
                <Select
                  onValueChange={field.onChange}
                  defaultValue={field.value}
                  disabled={!selectedOrgId}
                >
                  <FormControl>
                    <SelectTrigger>
                      <SelectValue placeholder="Select primary contact" />
                    </SelectTrigger>
                  </FormControl>
                  <SelectContent>
                    {contactsData?.items.map((contact) => (
                      <SelectItem key={contact.id} value={contact.id}>
                        {contact.name} ({contact.email})
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
                <FormMessage />
              </FormItem>
            )}
          />

          <FormField
            control={form.control}
            name="tag_ids"
            render={() => (
              <FormItem>
                <FormLabel>Tags <span className="text-destructive">*</span></FormLabel>
                <div
                  className={cn(
                    "flex flex-wrap gap-2 rounded-md border p-2 min-h-[40px]",
                    form.formState.errors.tag_ids && "border-destructive",
                  )}
                >
                  {allTags?.map((tag) => {
                    const isSelected = form.watch("tag_ids").includes(tag.id);
                    return (
                      <button
                        key={tag.id}
                        type="button"
                        onClick={() => {
                          const current = form.getValues("tag_ids");
                          if (isSelected) {
                            form.setValue(
                              "tag_ids",
                              current.filter((id) => id !== tag.id),
                            );
                          } else {
                            form.setValue("tag_ids", [...current, tag.id]);
                          }
                        }}
                        className={`rounded-full px-2 py-1 text-xs transition-colors ${
                          isSelected
                            ? "bg-primary text-primary-foreground"
                            : "bg-muted text-muted-foreground hover:bg-muted/80"
                        }`}
                      >
                        {tag.name}
                      </button>
                    );
                  })}
                </div>
                <FormMessage />
              </FormItem>
            )}
          />
        </div>

        <div className="border-t pt-4">
          <h3 className="mb-4 text-sm font-medium">Billing Information</h3>
          <div className="grid gap-4 md:grid-cols-3">
            <FormField
              control={form.control}
              name="billing_amount"
              render={({ field }) => (
                <FormItem>
                  <FormLabel>Billing Amount</FormLabel>
                  <FormControl>
                    <Input
                      type="number"
                      step="0.01"
                      placeholder="0.00"
                      {...field}
                      onChange={(e) =>
                        field.onChange(
                          e.target.value ? parseFloat(e.target.value) : undefined,
                        )
                      }
                    />
                  </FormControl>
                  <FormMessage />
                </FormItem>
              )}
            />

            <FormField
              control={form.control}
              name="invoice_count"
              render={({ field }) => (
                <FormItem>
                  <FormLabel>Invoice Count</FormLabel>
                  <FormControl>
                    <Input
                      type="number"
                      placeholder="0"
                      {...field}
                      onChange={(e) =>
                        field.onChange(
                          e.target.value ? parseInt(e.target.value, 10) : undefined,
                        )
                      }
                    />
                  </FormControl>
                  <FormMessage />
                </FormItem>
              )}
            />

            <FormField
              control={form.control}
              name="billing_recipient"
              render={({ field }) => (
                <FormItem>
                  <FormLabel>Billing Recipient</FormLabel>
                  <FormControl>
                    <Input placeholder="Recipient name" {...field} />
                  </FormControl>
                  <FormMessage />
                </FormItem>
              )}
            />
          </div>

          <FormField
            control={form.control}
            name="billing_notes"
            render={({ field }) => (
              <FormItem className="mt-4">
                <FormLabel>Billing Notes</FormLabel>
                <FormControl>
                  <Textarea placeholder="Additional billing notes" {...field} />
                </FormControl>
                <FormMessage />
              </FormItem>
            )}
          />
        </div>

        <div className="border-t pt-4">
          <h3 className="mb-4 text-sm font-medium">External Links</h3>
          <div className="grid gap-4 md:grid-cols-3">
            <FormField
              control={form.control}
              name="monday_url"
              render={({ field }) => (
                <FormItem>
                  <FormLabel>Monday.com URL</FormLabel>
                  <FormControl>
                    <Input
                      type="url"
                      placeholder="https://monday.com/..."
                      {...field}
                    />
                  </FormControl>
                  <FormMessage />
                </FormItem>
              )}
            />

            <FormField
              control={form.control}
              name="jira_url"
              render={({ field }) => (
                <FormItem>
                  <FormLabel>Jira URL</FormLabel>
                  <FormControl>
                    <Input
                      type="url"
                      placeholder="https://jira.example.com/..."
                      {...field}
                    />
                  </FormControl>
                  <FormMessage />
                </FormItem>
              )}
            />

            <FormField
              control={form.control}
              name="gitlab_url"
              render={({ field }) => (
                <FormItem>
                  <FormLabel>GitLab URL</FormLabel>
                  <FormControl>
                    <Input
                      type="url"
                      placeholder="https://gitlab.com/..."
                      {...field}
                    />
                  </FormControl>
                  <FormMessage />
                </FormItem>
              )}
            />
          </div>
        </div>

        <FormField
          control={form.control}
          name="pm_notes"
          render={({ field }) => (
            <FormItem>
              <FormLabel>PM Notes</FormLabel>
              <FormControl>
                <Textarea
                  placeholder="Internal notes for project management"
                  {...field}
                />
              </FormControl>
              <FormMessage />
            </FormItem>
          )}
        />

        <div className="flex justify-end gap-2">
          <Button
            type="button"
            variant="outline"
            onClick={handleAutofill}
            disabled={!form.watch("name")?.trim() || isSubmitting || autofillMutation.isPending}
          >
            {autofillMutation.isPending ? (
              <>
                <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                Suggesting...
              </>
            ) : (
              <>
                <Sparkles className="mr-2 h-4 w-4 text-amber-500" />
                Autofill
              </>
            )}
          </Button>
          <Button type="button" variant="outline" onClick={onCancel}>
            Cancel
          </Button>
          <Button type="submit" disabled={isSubmitting}>
            {isSubmitting ? "Saving..." : project ? "Update Project" : "Create Project"}
          </Button>
        </div>
      </form>
    </Form>
  );
}
