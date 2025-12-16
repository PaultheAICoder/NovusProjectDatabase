/**
 * Tag filter combobox with typeahead search functionality.
 * Used in SearchFilters and ProjectSearchFilters for tag filtering with search.
 */

import { useState, useRef, useEffect } from "react";
import { ChevronDown, Search, Check } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import {
  Popover,
  PopoverContent,
  PopoverTrigger,
} from "@/components/ui/popover";
import type { Tag } from "@/types/tag";
import { cn } from "@/lib/utils";

interface TagFilterComboboxProps {
  allTags: Tag[];
  selectedTagIds: string[];
  onTagToggle: (tagId: string) => void;
  placeholder?: string;
}

export function TagFilterCombobox({
  allTags,
  selectedTagIds,
  onTagToggle,
  placeholder = "Tags",
}: TagFilterComboboxProps) {
  const [inputValue, setInputValue] = useState("");
  const [isOpen, setIsOpen] = useState(false);
  const [highlightedIndex, setHighlightedIndex] = useState(-1);
  const inputRef = useRef<HTMLInputElement>(null);
  const listRef = useRef<HTMLUListElement>(null);

  // Filter tags by input value (case-insensitive)
  const filteredTags = allTags.filter((tag) =>
    tag.name.toLowerCase().includes(inputValue.toLowerCase())
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
        Math.min(prev + 1, filteredTags.length - 1)
      );
    } else if (e.key === "ArrowUp") {
      e.preventDefault();
      setHighlightedIndex((prev) => Math.max(prev - 1, 0));
    } else if (e.key === "Enter") {
      e.preventDefault();
      if (highlightedIndex >= 0 && highlightedIndex < filteredTags.length) {
        const selectedTag = filteredTags[highlightedIndex];
        if (selectedTag) {
          onTagToggle(selectedTag.id);
        }
      }
    } else if (e.key === "Escape") {
      e.preventDefault();
      setInputValue("");
      setIsOpen(false);
    }
  };

  const handleTagClick = (tagId: string) => {
    onTagToggle(tagId);
  };

  const selectedCount = selectedTagIds.length;

  return (
    <Popover open={isOpen} onOpenChange={setIsOpen}>
      <PopoverTrigger asChild>
        <Button
          variant="outline"
          role="combobox"
          aria-expanded={isOpen}
          className="w-[150px] justify-between"
        >
          <span className="truncate">
            {selectedCount > 0 ? `${selectedCount} selected` : placeholder}
          </span>
          <ChevronDown className="ml-2 h-4 w-4 shrink-0 opacity-50" />
        </Button>
      </PopoverTrigger>
      <PopoverContent className="w-[200px] p-0" align="start">
        <div className="p-2">
          <div className="relative">
            <Search className="absolute left-2 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
            <Input
              ref={inputRef}
              value={inputValue}
              onChange={(e) => setInputValue(e.target.value)}
              onKeyDown={handleKeyDown}
              placeholder="Search tags..."
              className="pl-8"
            />
          </div>
        </div>
        <ul
          ref={listRef}
          className="max-h-60 overflow-auto border-t"
          role="listbox"
        >
          {filteredTags.length === 0 ? (
            <li className="px-3 py-2 text-sm text-muted-foreground">
              No matching tags
            </li>
          ) : (
            filteredTags.map((tag, index) => {
              const isSelected = selectedTagIds.includes(tag.id);
              const isHighlighted = index === highlightedIndex;

              return (
                <li key={tag.id} role="option" aria-selected={isSelected}>
                  <button
                    type="button"
                    className={cn(
                      "flex w-full items-center gap-2 px-3 py-2 text-left text-sm",
                      isHighlighted ? "bg-accent" : "hover:bg-accent/50"
                    )}
                    onClick={() => handleTagClick(tag.id)}
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
                    <span className="flex-1 truncate">{tag.name}</span>
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
