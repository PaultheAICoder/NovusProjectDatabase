/**
 * Monday.com contact search component with autocomplete.
 * Allows searching for contacts in Monday and selecting one to link/autofill.
 */

import { useState, useRef, useEffect, useCallback, useMemo } from "react";
import { Search, Loader2, ExternalLink, AlertCircle } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import {
  Popover,
  PopoverContent,
  PopoverTrigger,
} from "@/components/ui/popover";
import { useMondayContactSearch } from "@/hooks/useMondaySync";
import { useDebounce } from "@/hooks/useDebounce";
import type { MondayContactMatch } from "@/types/monday";
import { cn } from "@/lib/utils";

interface MondayContactSearchProps {
  onSelect: (contact: MondayContactMatch) => void;
  disabled?: boolean;
  buttonLabel?: string;
}

export function MondayContactSearch({
  onSelect,
  disabled = false,
  buttonLabel = "Search Monday",
}: MondayContactSearchProps) {
  const [isOpen, setIsOpen] = useState(false);
  const [inputValue, setInputValue] = useState("");
  const [highlightedIndex, setHighlightedIndex] = useState(-1);
  const inputRef = useRef<HTMLInputElement>(null);
  const listRef = useRef<HTMLUListElement>(null);

  // Debounce search query
  const debouncedQuery = useDebounce(inputValue, 300);

  const { data, isLoading, isError, error } =
    useMondayContactSearch(debouncedQuery);

  const matches = useMemo(() => data?.matches ?? [], [data?.matches]);

  // Focus input when popover opens
  useEffect(() => {
    if (isOpen) {
      const timer = setTimeout(() => inputRef.current?.focus(), 0);
      return () => clearTimeout(timer);
    } else {
      setInputValue("");
      setHighlightedIndex(-1);
    }
  }, [isOpen]);

  // Reset highlighted index when results change
  useEffect(() => {
    setHighlightedIndex(-1);
  }, [debouncedQuery]);

  // Scroll highlighted item into view
  useEffect(() => {
    if (highlightedIndex >= 0 && listRef.current) {
      const item = listRef.current.children[highlightedIndex] as HTMLElement;
      item?.scrollIntoView({ block: "nearest" });
    }
  }, [highlightedIndex]);

  const handleSelect = useCallback(
    (contact: MondayContactMatch) => {
      onSelect(contact);
      setIsOpen(false);
    },
    [onSelect]
  );

  // Handle keyboard navigation
  const handleKeyDown = useCallback(
    (e: React.KeyboardEvent) => {
      if (e.key === "ArrowDown") {
        e.preventDefault();
        setHighlightedIndex((prev) => Math.min(prev + 1, matches.length - 1));
      } else if (e.key === "ArrowUp") {
        e.preventDefault();
        setHighlightedIndex((prev) => Math.max(prev - 1, 0));
      } else if (e.key === "Enter") {
        e.preventDefault();
        const selectedContact = matches[highlightedIndex];
        if (highlightedIndex >= 0 && highlightedIndex < matches.length && selectedContact) {
          handleSelect(selectedContact);
        }
      } else if (e.key === "Escape") {
        e.preventDefault();
        setIsOpen(false);
      }
    },
    [matches, highlightedIndex, handleSelect]
  );

  const isRateLimitError =
    error?.message?.includes("429") ||
    error?.message?.toLowerCase().includes("rate limit");

  return (
    <Popover open={isOpen} onOpenChange={setIsOpen}>
      <PopoverTrigger asChild>
        <Button variant="outline" disabled={disabled} className="gap-2">
          <ExternalLink className="h-4 w-4" />
          {buttonLabel}
        </Button>
      </PopoverTrigger>
      <PopoverContent className="w-[380px] p-0" align="start">
        <div className="p-2">
          <div className="relative">
            <Search className="absolute left-2 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
            <Input
              ref={inputRef}
              value={inputValue}
              onChange={(e) => setInputValue(e.target.value)}
              onKeyDown={handleKeyDown}
              placeholder="Search Monday contacts..."
              className="pl-8"
            />
          </div>
        </div>

        {isLoading && (
          <div className="flex items-center justify-center py-6 text-muted-foreground">
            <Loader2 className="h-5 w-5 animate-spin mr-2" />
            Searching Monday...
          </div>
        )}

        {isError && (
          <div className="p-4 text-sm text-destructive flex items-center gap-2">
            <AlertCircle className="h-4 w-4" />
            {isRateLimitError
              ? "Rate limit exceeded. Please wait and try again."
              : "Failed to search Monday contacts."}
          </div>
        )}

        {!isLoading && !isError && debouncedQuery.length < 2 && (
          <div className="px-3 py-6 text-sm text-center text-muted-foreground">
            Type at least 2 characters to search
          </div>
        )}

        {!isLoading &&
          !isError &&
          debouncedQuery.length >= 2 &&
          matches.length === 0 && (
            <div className="px-3 py-6 text-sm text-center text-muted-foreground">
              No matching contacts found
            </div>
          )}

        {!isLoading && !isError && matches.length > 0 && (
          <ul
            ref={listRef}
            className="max-h-60 overflow-auto border-t"
            role="listbox"
          >
            {matches.map((contact, index) => (
              <li key={contact.monday_id} role="option">
                <button
                  type="button"
                  className={cn(
                    "flex w-full items-center gap-2 px-3 py-2 text-left text-sm",
                    index === highlightedIndex
                      ? "bg-accent"
                      : "hover:bg-accent/50"
                  )}
                  onClick={() => handleSelect(contact)}
                  onMouseEnter={() => setHighlightedIndex(index)}
                >
                  <div className="flex-1 min-w-0">
                    <div className="font-medium truncate">{contact.name}</div>
                    <div className="text-xs text-muted-foreground truncate">
                      {contact.email || "No email"}
                      {contact.organization && ` - ${contact.organization}`}
                    </div>
                    {contact.role_title && (
                      <div className="text-xs text-muted-foreground truncate">
                        {contact.role_title}
                      </div>
                    )}
                  </div>
                </button>
              </li>
            ))}
          </ul>
        )}

        {data?.has_more && (
          <div className="px-3 py-2 border-t text-xs text-muted-foreground text-center">
            More results available - refine your search
          </div>
        )}
      </PopoverContent>
    </Popover>
  );
}
