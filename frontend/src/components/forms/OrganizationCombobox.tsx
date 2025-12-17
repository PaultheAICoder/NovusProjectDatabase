/**
 * Organization combobox with typeahead search functionality.
 * Used in ProjectForm, SearchFilters, and ContactsPage for organization selection.
 *
 * Two variants:
 * - OrganizationFilterCombobox: For filter dropdowns with optional "All Organizations" option
 * - OrganizationSelectCombobox: For form fields with single value selection
 */

import { useState, useRef, useEffect } from "react";
import { ChevronDown, Search, Check, Building2, Plus, Loader2 } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import {
  Popover,
  PopoverContent,
  PopoverTrigger,
} from "@/components/ui/popover";
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogFooter,
} from "@/components/ui/dialog";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import { useCreateOrganization, useOrganizations, useOrganizationSearch } from "@/hooks/useOrganizations";
import { useDebounce } from "@/hooks/useDebounce";
import type { Organization } from "@/types/organization";
import { cn } from "@/lib/utils";

interface OrganizationFilterComboboxProps {
  /** Optional pre-loaded organizations (for displaying selected item when not in search results) */
  initialOrganizations?: Organization[];
  selectedId: string | undefined;
  onSelect: (id: string | undefined, org?: Organization) => void;
  placeholder?: string;
  showAllOption?: boolean;
}

export function OrganizationFilterCombobox({
  initialOrganizations,
  selectedId,
  onSelect,
  placeholder = "Organization",
  showAllOption = false,
}: OrganizationFilterComboboxProps) {
  const [inputValue, setInputValue] = useState("");
  const [isOpen, setIsOpen] = useState(false);
  const [highlightedIndex, setHighlightedIndex] = useState(-1);
  const inputRef = useRef<HTMLInputElement>(null);
  const listRef = useRef<HTMLUListElement>(null);

  // Debounce search input for server-side search
  const debouncedSearch = useDebounce(inputValue, 300);

  // Server-side search when user types
  const { data: searchResults, isLoading } = useOrganizationSearch({
    search: debouncedSearch,
    pageSize: 50,
  });

  // Initial data for when dropdown opens with no search
  const { data: initialData } = useOrganizations({ pageSize: 50 });

  // Use search results if searching, otherwise initial data
  const organizations = debouncedSearch
    ? (searchResults?.items ?? [])
    : (initialData?.items ?? []);

  // Reset highlighted index when filter changes
  useEffect(() => {
    setHighlightedIndex(-1);
  }, [inputValue]);

  // Focus input when popover opens
  useEffect(() => {
    if (isOpen) {
      // Small delay to ensure popover is mounted
      const timer = setTimeout(() => {
        inputRef.current?.focus();
      }, 0);
      return () => clearTimeout(timer);
    } else {
      // Clear filter when closing
      setInputValue("");
      setHighlightedIndex(-1);
    }
  }, [isOpen]);

  // Scroll highlighted item into view
  useEffect(() => {
    if (highlightedIndex >= 0 && listRef.current) {
      const offset = showAllOption ? 1 : 0;
      const item = listRef.current.children[highlightedIndex + offset] as HTMLElement;
      item?.scrollIntoView({ block: "nearest" });
    }
  }, [highlightedIndex, showAllOption]);

  const handleKeyDown = (e: React.KeyboardEvent) => {
    const maxIndex = organizations.length - 1;

    if (e.key === "ArrowDown") {
      e.preventDefault();
      setHighlightedIndex((prev) => Math.min(prev + 1, maxIndex));
    } else if (e.key === "ArrowUp") {
      e.preventDefault();
      setHighlightedIndex((prev) => Math.max(prev - 1, showAllOption ? -1 : 0));
    } else if (e.key === "Enter") {
      e.preventDefault();
      if (highlightedIndex === -1 && showAllOption) {
        onSelect(undefined);
        setIsOpen(false);
      } else if (highlightedIndex >= 0 && highlightedIndex < organizations.length) {
        const org = organizations[highlightedIndex];
        if (org) {
          onSelect(org.id, org);
          setIsOpen(false);
        }
      }
    } else if (e.key === "Escape") {
      e.preventDefault();
      setInputValue("");
      setIsOpen(false);
    }
  };

  const handleOrgClick = (orgId: string | undefined, org?: Organization) => {
    onSelect(orgId, org);
    setIsOpen(false);
  };

  // Get display text for trigger button - look in both searched and initial orgs
  const selectedOrg = selectedId
    ? organizations.find((o) => o.id === selectedId) ||
      initialOrganizations?.find((o) => o.id === selectedId)
    : null;
  const displayText = selectedOrg?.name ?? placeholder;

  return (
    <Popover open={isOpen} onOpenChange={setIsOpen}>
      <PopoverTrigger asChild>
        <Button
          variant="outline"
          role="combobox"
          aria-expanded={isOpen}
          className="w-[200px] justify-between"
        >
          <span className="truncate">{displayText}</span>
          <ChevronDown className="ml-2 h-4 w-4 shrink-0 opacity-50" />
        </Button>
      </PopoverTrigger>
      <PopoverContent className="w-[250px] p-0" align="start">
        <div className="p-2">
          <div className="relative">
            <Search className="absolute left-2 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
            <Input
              ref={inputRef}
              value={inputValue}
              onChange={(e) => setInputValue(e.target.value)}
              onKeyDown={handleKeyDown}
              placeholder="Search organizations..."
              className="pl-8"
            />
          </div>
        </div>
        {isLoading && debouncedSearch && (
          <div className="flex items-center justify-center py-2 border-t">
            <Loader2 className="h-4 w-4 animate-spin text-muted-foreground" />
          </div>
        )}
        <ul
          ref={listRef}
          className="max-h-60 overflow-auto border-t"
          role="listbox"
        >
          {showAllOption && (
            <li role="option" aria-selected={!selectedId}>
              <button
                type="button"
                className={cn(
                  "flex w-full items-center gap-2 px-3 py-2 text-left text-sm",
                  highlightedIndex === -1 ? "bg-accent" : "hover:bg-accent/50"
                )}
                onClick={() => handleOrgClick(undefined, undefined)}
                onMouseEnter={() => setHighlightedIndex(-1)}
              >
                <span
                  className={cn(
                    "flex h-4 w-4 items-center justify-center",
                    !selectedId ? "text-primary" : "text-transparent"
                  )}
                >
                  <Check className="h-4 w-4" />
                </span>
                <span className="flex-1">All Organizations</span>
              </button>
            </li>
          )}
          {organizations.length === 0 && !isLoading ? (
            <li className="px-3 py-2 text-sm text-muted-foreground">
              No matching organizations
            </li>
          ) : (
            organizations.map((org, index) => {
              const isSelected = selectedId === org.id;
              const isHighlighted = index === highlightedIndex;

              return (
                <li key={org.id} role="option" aria-selected={isSelected}>
                  <button
                    type="button"
                    className={cn(
                      "flex w-full items-center gap-2 px-3 py-2 text-left text-sm",
                      isHighlighted ? "bg-accent" : "hover:bg-accent/50"
                    )}
                    onClick={() => handleOrgClick(org.id, org)}
                    onMouseEnter={() => setHighlightedIndex(index)}
                  >
                    <span
                      className={cn(
                        "flex h-4 w-4 items-center justify-center",
                        isSelected ? "text-primary" : "text-transparent"
                      )}
                    >
                      <Check className="h-4 w-4" />
                    </span>
                    <span className="flex-1 truncate">{org.name}</span>
                  </button>
                </li>
              );
            })
          )}
        </ul>
      </PopoverContent>
    </Popover>
  );
}

interface OrganizationSelectComboboxProps {
  /** Optional pre-loaded organizations (for displaying selected item when not in search results) */
  initialOrganizations?: Organization[];
  value: string;
  onChange: (value: string) => void;
  placeholder?: string;
  disabled?: boolean;
  triggerClassName?: string;
  allowCreate?: boolean;
  onOrganizationCreated?: (org: Organization) => void;
}

export function OrganizationSelectCombobox({
  initialOrganizations,
  value,
  onChange,
  placeholder = "Select organization",
  disabled = false,
  triggerClassName,
  allowCreate = false,
  onOrganizationCreated,
}: OrganizationSelectComboboxProps) {
  const [inputValue, setInputValue] = useState("");
  const [isOpen, setIsOpen] = useState(false);
  const [highlightedIndex, setHighlightedIndex] = useState(-1);
  const inputRef = useRef<HTMLInputElement>(null);
  const listRef = useRef<HTMLUListElement>(null);

  // State for inline organization creation
  const [showCreateDialog, setShowCreateDialog] = useState(false);
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

  const createMutation = useCreateOrganization();

  // Debounce search input for server-side search
  const debouncedSearch = useDebounce(inputValue, 300);

  // Server-side search when user types
  const { data: searchResults, isLoading } = useOrganizationSearch({
    search: debouncedSearch,
    pageSize: 50,
  });

  // Initial data for when dropdown opens with no search
  const { data: initialData } = useOrganizations({ pageSize: 50 });

  // Use search results if searching, otherwise initial data
  const organizations = debouncedSearch
    ? (searchResults?.items ?? [])
    : (initialData?.items ?? []);

  // Reset highlighted index when filter changes
  useEffect(() => {
    setHighlightedIndex(-1);
  }, [inputValue]);

  // Focus input when popover opens
  useEffect(() => {
    if (isOpen) {
      // Small delay to ensure popover is mounted
      const timer = setTimeout(() => {
        inputRef.current?.focus();
      }, 0);
      return () => clearTimeout(timer);
    } else {
      // Clear filter when closing
      setInputValue("");
      setHighlightedIndex(-1);
    }
  }, [isOpen]);

  // Scroll highlighted item into view
  useEffect(() => {
    if (highlightedIndex >= 0 && listRef.current) {
      const item = listRef.current.children[highlightedIndex] as HTMLElement;
      item?.scrollIntoView({ block: "nearest" });
    }
  }, [highlightedIndex]);

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === "ArrowDown") {
      e.preventDefault();
      setHighlightedIndex((prev) =>
        Math.min(prev + 1, organizations.length - 1)
      );
    } else if (e.key === "ArrowUp") {
      e.preventDefault();
      setHighlightedIndex((prev) => Math.max(prev - 1, 0));
    } else if (e.key === "Enter") {
      e.preventDefault();
      if (highlightedIndex >= 0 && highlightedIndex < organizations.length) {
        const selectedOrg = organizations[highlightedIndex];
        if (selectedOrg) {
          onChange(selectedOrg.id);
          setIsOpen(false);
        }
      }
    } else if (e.key === "Escape") {
      e.preventDefault();
      setInputValue("");
      setIsOpen(false);
    }
  };

  const handleSelectOrgClick = (orgId: string) => {
    onChange(orgId);
    setIsOpen(false);
  };

  const handleCreateSubmit = async () => {
    if (!formData.name.trim()) return;

    try {
      const newOrg = await createMutation.mutateAsync(formData);
      // Auto-select the newly created organization
      onChange(newOrg.id);
      // Notify parent if callback provided
      onOrganizationCreated?.(newOrg);
      // Reset and close
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
      setShowCreateDialog(false);
    } catch {
      // Error handled by mutation
    }
  };

  const handleDialogClose = (open: boolean) => {
    if (!open) {
      // Reset form when closing
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
    }
    setShowCreateDialog(open);
  };

  // Get display text for trigger button - look in both searched and initial orgs
  const selectedOrg = value
    ? organizations.find((o) => o.id === value) ||
      initialOrganizations?.find((o) => o.id === value)
    : null;
  const displayText = selectedOrg?.name ?? placeholder;

  return (
    <>
    <Popover open={isOpen} onOpenChange={setIsOpen}>
      <PopoverTrigger asChild>
        <Button
          variant="outline"
          role="combobox"
          aria-expanded={isOpen}
          disabled={disabled}
          className={cn(
            "w-full justify-between",
            !selectedOrg && "text-muted-foreground",
            triggerClassName
          )}
        >
          <div className="flex items-center gap-2 truncate">
            <Building2 className="h-4 w-4 shrink-0 opacity-50" />
            <span className="truncate">{displayText}</span>
          </div>
          <ChevronDown className="ml-2 h-4 w-4 shrink-0 opacity-50" />
        </Button>
      </PopoverTrigger>
      <PopoverContent className="w-[280px] p-0" align="start">
        <div className="p-2">
          <div className="relative">
            <Search className="absolute left-2 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
            <Input
              ref={inputRef}
              value={inputValue}
              onChange={(e) => setInputValue(e.target.value)}
              onKeyDown={handleKeyDown}
              placeholder="Search organizations..."
              className="pl-8"
            />
          </div>
        </div>
        {isLoading && debouncedSearch && (
          <div className="flex items-center justify-center py-2 border-t">
            <Loader2 className="h-4 w-4 animate-spin text-muted-foreground" />
          </div>
        )}
        <ul
          ref={listRef}
          className="max-h-60 overflow-auto border-t"
          role="listbox"
        >
          {organizations.length === 0 && !isLoading ? (
            <li className="px-3 py-2 text-sm text-muted-foreground">
              No matching organizations
            </li>
          ) : (
            organizations.map((org, index) => {
              const isSelected = value === org.id;
              const isHighlighted = index === highlightedIndex;

              return (
                <li key={org.id} role="option" aria-selected={isSelected}>
                  <button
                    type="button"
                    className={cn(
                      "flex w-full items-center gap-2 px-3 py-2 text-left text-sm",
                      isHighlighted ? "bg-accent" : "hover:bg-accent/50"
                    )}
                    onClick={() => handleSelectOrgClick(org.id)}
                    onMouseEnter={() => setHighlightedIndex(index)}
                  >
                    <span
                      className={cn(
                        "flex h-4 w-4 items-center justify-center",
                        isSelected ? "text-primary" : "text-transparent"
                      )}
                    >
                      <Check className="h-4 w-4" />
                    </span>
                    <span className="flex-1 truncate">{org.name}</span>
                  </button>
                </li>
              );
            })
          )}
          {allowCreate && (
            <li className="border-t">
              <button
                type="button"
                className="flex w-full items-center gap-2 px-3 py-2 text-left text-sm hover:bg-accent/50"
                onClick={() => {
                  setIsOpen(false);
                  setShowCreateDialog(true);
                }}
              >
                <Plus className="h-4 w-4 text-muted-foreground" />
                <span>Create New Organization</span>
              </button>
            </li>
          )}
        </ul>
      </PopoverContent>
    </Popover>

    {allowCreate && (
      <Dialog open={showCreateDialog} onOpenChange={handleDialogClose}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>New Organization</DialogTitle>
          </DialogHeader>
          <div className="space-y-4 py-4">
            <div className="space-y-2">
              <Label htmlFor="new-org-name">Name *</Label>
              <Input
                id="new-org-name"
                value={formData.name}
                onChange={(e) =>
                  setFormData({ ...formData, name: e.target.value })
                }
                placeholder="Enter organization name"
              />
            </div>
            <div className="space-y-2">
              <Label htmlFor="new-org-notes">Notes</Label>
              <Textarea
                id="new-org-notes"
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
              <Label htmlFor="new-org-inventory-url">Inventory Link</Label>
              <Input
                id="new-org-inventory-url"
                value={formData.inventory_url}
                onChange={(e) =>
                  setFormData({ ...formData, inventory_url: e.target.value })
                }
                placeholder="https://inventory.example.com/client/123"
              />
            </div>
          </div>
          <DialogFooter>
            <Button
              variant="outline"
              onClick={() => setShowCreateDialog(false)}
            >
              Cancel
            </Button>
            <Button
              onClick={handleCreateSubmit}
              disabled={!formData.name.trim() || createMutation.isPending}
            >
              {createMutation.isPending && (
                <Loader2 className="mr-2 h-4 w-4 animate-spin" />
              )}
              Create
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    )}
    </>
  );
}
