/**
 * Project form component with React Hook Form + Zod validation.
 */

import { useEffect } from "react";
import { useForm } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { z } from "zod";
import { format } from "date-fns";
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
  primary_contact_id: z.string().optional(),
  tag_ids: z.array(z.string()).default([]),
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

  const handleSubmit = form.handleSubmit((data) => {
    const cleanData = {
      ...data,
      end_date: data.end_date || undefined,
      monday_url: data.monday_url || undefined,
      jira_url: data.jira_url || undefined,
      gitlab_url: data.gitlab_url || undefined,
    };
    onSubmit(cleanData);
  });

  return (
    <Form {...form}>
      <form onSubmit={handleSubmit} className="space-y-6">
        <div className="grid gap-4 md:grid-cols-2">
          <FormField
            control={form.control}
            name="name"
            render={({ field }) => (
              <FormItem>
                <FormLabel>Project Name *</FormLabel>
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
                <FormLabel>Organization *</FormLabel>
                <Select
                  onValueChange={field.onChange}
                  defaultValue={field.value}
                >
                  <FormControl>
                    <SelectTrigger>
                      <SelectValue placeholder="Select organization" />
                    </SelectTrigger>
                  </FormControl>
                  <SelectContent>
                    {orgsData?.items.map((org) => (
                      <SelectItem key={org.id} value={org.id}>
                        {org.name}
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
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
              <FormLabel>Description *</FormLabel>
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
                <FormLabel>Status *</FormLabel>
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
                <FormLabel>Start Date *</FormLabel>
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
              <FormLabel>Location *</FormLabel>
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
                <FormLabel>Primary Contact</FormLabel>
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
                <FormLabel>Tags</FormLabel>
                <div className="flex flex-wrap gap-2 rounded-md border p-2 min-h-[40px]">
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
