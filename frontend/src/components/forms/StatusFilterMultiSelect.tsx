/**
 * Status filter multi-select component with Popover-based UI.
 * Provides a true multi-select experience for status filtering.
 * Pattern: Follows TagFilterCombobox structure but simplified (no search, static list).
 */

import { useState, useRef, useEffect } from "react";
import { ChevronDown, Check } from "lucide-react";
import { Button } from "@/components/ui/button";
import {
  Popover,
  PopoverContent,
  PopoverTrigger,
} from "@/components/ui/popover";
import { cn } from "@/lib/utils";
import type { ProjectStatus } from "@/types/project";

const statusOptions: { value: ProjectStatus; label: string }[] = [
  { value: "approved", label: "Approved" },
  { value: "active", label: "Active" },
  { value: "on_hold", label: "On Hold" },
  { value: "completed", label: "Completed" },
  { value: "cancelled", label: "Cancelled" },
];

interface StatusFilterMultiSelectProps {
  selectedStatuses: ProjectStatus[];
  onStatusToggle: (status: ProjectStatus) => void;
  placeholder?: string;
}

export function StatusFilterMultiSelect({
  selectedStatuses,
  onStatusToggle,
  placeholder = "Status",
}: StatusFilterMultiSelectProps) {
  const [isOpen, setIsOpen] = useState(false);
  const [highlightedIndex, setHighlightedIndex] = useState(-1);
  const listRef = useRef<HTMLUListElement>(null);
  const triggerRef = useRef<HTMLButtonElement>(null);

  // Reset highlighted index when popover closes
  useEffect(() => {
    if (!isOpen) {
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
        Math.min(prev + 1, statusOptions.length - 1)
      );
    } else if (e.key === "ArrowUp") {
      e.preventDefault();
      setHighlightedIndex((prev) => Math.max(prev - 1, 0));
    } else if (e.key === "Enter") {
      e.preventDefault();
      if (highlightedIndex >= 0 && highlightedIndex < statusOptions.length) {
        const selectedOption = statusOptions[highlightedIndex];
        if (selectedOption) {
          onStatusToggle(selectedOption.value);
        }
      }
    } else if (e.key === "Escape") {
      e.preventDefault();
      setIsOpen(false);
    }
  };

  const handleStatusClick = (status: ProjectStatus) => {
    onStatusToggle(status);
  };

  const selectedCount = selectedStatuses.length;

  // Determine trigger display text
  const getTriggerText = () => {
    if (selectedCount === 0) {
      return placeholder;
    }
    if (selectedCount === 1) {
      const selectedOption = statusOptions.find(
        (opt) => opt.value === selectedStatuses[0]
      );
      return selectedOption?.label ?? placeholder;
    }
    return `${selectedCount} selected`;
  };

  return (
    <Popover open={isOpen} onOpenChange={setIsOpen}>
      <PopoverTrigger asChild>
        <Button
          ref={triggerRef}
          variant="outline"
          role="combobox"
          aria-expanded={isOpen}
          className="w-[150px] justify-between"
          onKeyDown={handleKeyDown}
        >
          <span className="truncate">{getTriggerText()}</span>
          <ChevronDown className="ml-2 h-4 w-4 shrink-0 opacity-50" />
        </Button>
      </PopoverTrigger>
      <PopoverContent className="w-[200px] p-0" align="start">
        <ul
          ref={listRef}
          className="max-h-60 overflow-auto py-1"
          role="listbox"
          onKeyDown={handleKeyDown}
        >
          {statusOptions.map((option, index) => {
            const isSelected = selectedStatuses.includes(option.value);
            const isHighlighted = index === highlightedIndex;

            return (
              <li key={option.value} role="option" aria-selected={isSelected}>
                <button
                  type="button"
                  className={cn(
                    "flex w-full items-center gap-2 px-3 py-2 text-left text-sm",
                    isHighlighted ? "bg-accent" : "hover:bg-accent/50"
                  )}
                  onClick={() => handleStatusClick(option.value)}
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
                  <span className="flex-1 truncate">{option.label}</span>
                </button>
              </li>
            );
          })}
        </ul>
      </PopoverContent>
    </Popover>
  );
}
