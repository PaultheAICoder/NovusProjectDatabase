/**
 * Tag selector component with autocomplete and fuzzy matching suggestions.
 */

import { useState, useRef, useEffect } from "react";
import { X, Plus, Tag as TagIcon, Loader2, AlertCircle } from "lucide-react";
import { Input } from "@/components/ui/input";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { useTagSuggestions, useCreateTag, useAllTags } from "@/hooks/useTags";
import type { Tag, TagType } from "@/types/tag";
import { cn } from "@/lib/utils";

const tagTypeColors: Record<TagType, string> = {
  technology: "bg-blue-100 text-blue-800 border-blue-200",
  domain: "bg-green-100 text-green-800 border-green-200",
  test_type: "bg-purple-100 text-purple-800 border-purple-200",
  freeform: "bg-gray-100 text-gray-800 border-gray-200",
};

const tagTypeLabels: Record<TagType, string> = {
  technology: "Tech",
  domain: "Domain",
  test_type: "Test Type",
  freeform: "Custom",
};

interface TagSelectorProps {
  selectedTags: Tag[];
  onTagsChange: (tags: Tag[]) => void;
  filterType?: TagType;
  allowCreate?: boolean;
  placeholder?: string;
  disabled?: boolean;
}

export function TagSelector({
  selectedTags,
  onTagsChange,
  filterType,
  allowCreate = true,
  placeholder = "Search or add tags...",
  disabled = false,
}: TagSelectorProps) {
  const [inputValue, setInputValue] = useState("");
  const [isOpen, setIsOpen] = useState(false);
  const [highlightedIndex, setHighlightedIndex] = useState(-1);
  const inputRef = useRef<HTMLInputElement>(null);
  const dropdownRef = useRef<HTMLDivElement>(null);

  const { data: suggestions, isLoading } = useTagSuggestions({
    query: inputValue,
    type: filterType,
    includeFuzzy: true,
  });

  const { data: allTags } = useAllTags();
  const createTagMutation = useCreateTag();

  // Filter out already selected tags from suggestions
  const filteredSuggestions =
    suggestions?.suggestions.filter(
      (s) => !selectedTags.some((t) => t.id === s.tag.id)
    ) ?? [];

  // Check if exact match exists
  const exactMatch = filteredSuggestions.find(
    (s) => s.tag.name.toLowerCase() === inputValue.toLowerCase()
  );

  // Can create new tag if input has value, no exact match, and create is allowed
  const canCreateNew = allowCreate && inputValue.trim() && !exactMatch;

  // Close dropdown when clicking outside
  useEffect(() => {
    const handleClickOutside = (e: MouseEvent) => {
      if (
        dropdownRef.current &&
        !dropdownRef.current.contains(e.target as Node) &&
        inputRef.current &&
        !inputRef.current.contains(e.target as Node)
      ) {
        setIsOpen(false);
      }
    };

    document.addEventListener("mousedown", handleClickOutside);
    return () => document.removeEventListener("mousedown", handleClickOutside);
  }, []);

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === "ArrowDown") {
      e.preventDefault();
      const maxIndex = canCreateNew
        ? filteredSuggestions.length
        : filteredSuggestions.length - 1;
      setHighlightedIndex((prev) => Math.min(prev + 1, maxIndex));
    } else if (e.key === "ArrowUp") {
      e.preventDefault();
      setHighlightedIndex((prev) => Math.max(prev - 1, -1));
    } else if (e.key === "Enter") {
      e.preventDefault();
      if (highlightedIndex === filteredSuggestions.length && canCreateNew) {
        handleCreateTag();
      } else if (highlightedIndex >= 0 && highlightedIndex < filteredSuggestions.length) {
        handleSelectTag(filteredSuggestions[highlightedIndex].tag);
      } else if (canCreateNew) {
        handleCreateTag();
      }
    } else if (e.key === "Escape") {
      setIsOpen(false);
      setHighlightedIndex(-1);
    }
  };

  const handleSelectTag = (tag: Tag) => {
    if (!selectedTags.some((t) => t.id === tag.id)) {
      onTagsChange([...selectedTags, tag]);
    }
    setInputValue("");
    setIsOpen(false);
    setHighlightedIndex(-1);
  };

  const handleRemoveTag = (tagId: string) => {
    onTagsChange(selectedTags.filter((t) => t.id !== tagId));
  };

  const handleCreateTag = async () => {
    if (!inputValue.trim()) return;

    try {
      const newTag = await createTagMutation.mutateAsync({ name: inputValue.trim() });
      onTagsChange([...selectedTags, newTag]);
      setInputValue("");
      setIsOpen(false);
      setHighlightedIndex(-1);
    } catch {
      // Error handled by mutation
    }
  };

  return (
    <div className="space-y-2">
      {/* Selected tags */}
      {selectedTags.length > 0 && (
        <div className="flex flex-wrap gap-1.5">
          {selectedTags.map((tag) => (
            <Badge
              key={tag.id}
              variant="outline"
              className={cn(
                "gap-1 pr-1",
                tagTypeColors[tag.type]
              )}
            >
              <span className="text-xs opacity-60">{tagTypeLabels[tag.type]}</span>
              <span>{tag.name}</span>
              {!disabled && (
                <button
                  type="button"
                  onClick={() => handleRemoveTag(tag.id)}
                  className="ml-1 rounded-full p-0.5 hover:bg-black/10"
                >
                  <X className="h-3 w-3" />
                </button>
              )}
            </Badge>
          ))}
        </div>
      )}

      {/* Input with dropdown */}
      <div className="relative">
        <div className="relative">
          <TagIcon className="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
          <Input
            ref={inputRef}
            value={inputValue}
            onChange={(e) => {
              setInputValue(e.target.value);
              setIsOpen(true);
              setHighlightedIndex(-1);
            }}
            onFocus={() => setIsOpen(true)}
            onKeyDown={handleKeyDown}
            placeholder={placeholder}
            disabled={disabled}
            className="pl-9"
          />
          {isLoading && inputValue.length >= 2 && (
            <Loader2 className="absolute right-3 top-1/2 h-4 w-4 -translate-y-1/2 animate-spin text-muted-foreground" />
          )}
        </div>

        {/* Dropdown */}
        {isOpen && inputValue.length >= 2 && (
          <div
            ref={dropdownRef}
            className="absolute z-50 mt-1 w-full rounded-md border bg-popover shadow-lg"
          >
            {filteredSuggestions.length === 0 && !canCreateNew ? (
              <div className="p-3 text-sm text-muted-foreground">
                No matching tags found
              </div>
            ) : (
              <ul className="max-h-60 overflow-auto py-1">
                {filteredSuggestions.map((suggestion, index) => (
                  <li key={suggestion.tag.id}>
                    <button
                      type="button"
                      className={cn(
                        "flex w-full items-center gap-2 px-3 py-2 text-left text-sm",
                        highlightedIndex === index
                          ? "bg-accent"
                          : "hover:bg-accent/50"
                      )}
                      onClick={() => handleSelectTag(suggestion.tag)}
                      onMouseEnter={() => setHighlightedIndex(index)}
                    >
                      <Badge
                        variant="outline"
                        className={cn("text-xs", tagTypeColors[suggestion.tag.type])}
                      >
                        {tagTypeLabels[suggestion.tag.type]}
                      </Badge>
                      <span className="flex-1">{suggestion.tag.name}</span>
                      {suggestion.suggestion && (
                        <span className="flex items-center gap-1 text-xs text-amber-600">
                          <AlertCircle className="h-3 w-3" />
                          {suggestion.suggestion}
                        </span>
                      )}
                    </button>
                  </li>
                ))}

                {canCreateNew && (
                  <li>
                    <button
                      type="button"
                      className={cn(
                        "flex w-full items-center gap-2 px-3 py-2 text-left text-sm border-t",
                        highlightedIndex === filteredSuggestions.length
                          ? "bg-accent"
                          : "hover:bg-accent/50"
                      )}
                      onClick={handleCreateTag}
                      onMouseEnter={() => setHighlightedIndex(filteredSuggestions.length)}
                      disabled={createTagMutation.isPending}
                    >
                      <Plus className="h-4 w-4 text-muted-foreground" />
                      <span>
                        Create new tag{" "}
                        <strong className="font-medium">"{inputValue}"</strong>
                      </span>
                      {createTagMutation.isPending && (
                        <Loader2 className="h-3 w-3 animate-spin" />
                      )}
                    </button>
                  </li>
                )}
              </ul>
            )}
          </div>
        )}
      </div>
    </div>
  );
}

/**
 * Simplified tag badge display component.
 */
interface TagBadgeProps {
  tag: Tag;
  onRemove?: () => void;
}

export function TagBadge({ tag, onRemove }: TagBadgeProps) {
  return (
    <Badge
      variant="outline"
      className={cn("gap-1", tagTypeColors[tag.type])}
    >
      {tag.name}
      {onRemove && (
        <button
          type="button"
          onClick={onRemove}
          className="ml-1 rounded-full p-0.5 hover:bg-black/10"
        >
          <X className="h-3 w-3" />
        </button>
      )}
    </Badge>
  );
}
