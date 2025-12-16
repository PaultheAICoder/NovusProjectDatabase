/**
 * Organization combobox with typeahead search functionality.
 * Used in ProjectForm, SearchFilters, and ContactsPage for organization selection.
 *
 * Two variants:
 * - OrganizationFilterCombobox: For filter dropdowns with optional "All Organizations" option
 * - OrganizationSelectCombobox: For form fields with single value selection
 */

import { useState, useRef, useEffect } from "react";
import { ChevronDown, Search, Check, Building2 } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import {
  Popover,
  PopoverContent,
  PopoverTrigger,
} from "@/components/ui/popover";
import type { Organization } from "@/types/organization";
import { cn } from "@/lib/utils";

interface OrganizationFilterComboboxProps {
  organizations: Organization[];
  selectedId: string | undefined;
  onSelect: (id: string | undefined) => void;
  placeholder?: string;
  showAllOption?: boolean;
}

export function OrganizationFilterCombobox({
  organizations,
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

  // Filter organizations by input value (case-insensitive)
  const filteredOrgs = organizations.filter((org) =>
    org.name.toLowerCase().includes(inputValue.toLowerCase())
  );

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
    const maxIndex = filteredOrgs.length - 1;

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
      } else if (highlightedIndex >= 0 && highlightedIndex < filteredOrgs.length) {
        const selectedOrg = filteredOrgs[highlightedIndex];
        if (selectedOrg) {
          onSelect(selectedOrg.id);
          setIsOpen(false);
        }
      }
    } else if (e.key === "Escape") {
      e.preventDefault();
      setInputValue("");
      setIsOpen(false);
    }
  };

  const handleOrgClick = (orgId: string | undefined) => {
    onSelect(orgId);
    setIsOpen(false);
  };

  // Get display text for trigger button
  const selectedOrg = selectedId
    ? organizations.find((o) => o.id === selectedId)
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
                onClick={() => handleOrgClick(undefined)}
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
          {filteredOrgs.length === 0 ? (
            <li className="px-3 py-2 text-sm text-muted-foreground">
              No matching organizations
            </li>
          ) : (
            filteredOrgs.map((org, index) => {
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
                    onClick={() => handleOrgClick(org.id)}
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
  organizations: Organization[];
  value: string;
  onChange: (value: string) => void;
  placeholder?: string;
  disabled?: boolean;
  triggerClassName?: string;
}

export function OrganizationSelectCombobox({
  organizations,
  value,
  onChange,
  placeholder = "Select organization",
  disabled = false,
  triggerClassName,
}: OrganizationSelectComboboxProps) {
  const [inputValue, setInputValue] = useState("");
  const [isOpen, setIsOpen] = useState(false);
  const [highlightedIndex, setHighlightedIndex] = useState(-1);
  const inputRef = useRef<HTMLInputElement>(null);
  const listRef = useRef<HTMLUListElement>(null);

  // Filter organizations by input value (case-insensitive)
  const filteredOrgs = organizations.filter((org) =>
    org.name.toLowerCase().includes(inputValue.toLowerCase())
  );

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
        Math.min(prev + 1, filteredOrgs.length - 1)
      );
    } else if (e.key === "ArrowUp") {
      e.preventDefault();
      setHighlightedIndex((prev) => Math.max(prev - 1, 0));
    } else if (e.key === "Enter") {
      e.preventDefault();
      if (highlightedIndex >= 0 && highlightedIndex < filteredOrgs.length) {
        const selectedOrg = filteredOrgs[highlightedIndex];
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

  const handleOrgClick = (orgId: string) => {
    onChange(orgId);
    setIsOpen(false);
  };

  // Get display text for trigger button
  const selectedOrg = value ? organizations.find((o) => o.id === value) : null;
  const displayText = selectedOrg?.name ?? placeholder;

  return (
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
        <ul
          ref={listRef}
          className="max-h-60 overflow-auto border-t"
          role="listbox"
        >
          {filteredOrgs.length === 0 ? (
            <li className="px-3 py-2 text-sm text-muted-foreground">
              No matching organizations
            </li>
          ) : (
            filteredOrgs.map((org, index) => {
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
                    onClick={() => handleOrgClick(org.id)}
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
