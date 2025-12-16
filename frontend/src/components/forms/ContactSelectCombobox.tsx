/**
 * Contact combobox with typeahead search and inline creation functionality.
 * Used in ProjectForm for contact selection.
 *
 * Based on OrganizationSelectCombobox pattern from Issue #38.
 */

import { useState, useRef, useEffect } from "react";
import { ChevronDown, Search, Check, User, Plus, Loader2 } from "lucide-react";
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
import { useCreateContact } from "@/hooks/useContacts";
import type { Contact } from "@/types/contact";
import { cn } from "@/lib/utils";

interface ContactSelectComboboxProps {
  contacts: Contact[];
  value: string;
  onChange: (value: string) => void;
  placeholder?: string;
  disabled?: boolean;
  triggerClassName?: string;
  allowCreate?: boolean;
  defaultOrganizationId?: string;
  onContactCreated?: (contact: Contact) => void;
}

export function ContactSelectCombobox({
  contacts,
  value,
  onChange,
  placeholder = "Select contact",
  disabled = false,
  triggerClassName,
  allowCreate = false,
  defaultOrganizationId,
  onContactCreated,
}: ContactSelectComboboxProps) {
  const [inputValue, setInputValue] = useState("");
  const [isOpen, setIsOpen] = useState(false);
  const [highlightedIndex, setHighlightedIndex] = useState(-1);
  const inputRef = useRef<HTMLInputElement>(null);
  const listRef = useRef<HTMLUListElement>(null);

  // State for inline contact creation
  const [showCreateDialog, setShowCreateDialog] = useState(false);
  const [formData, setFormData] = useState({
    name: "",
    email: "",
    role_title: "",
    phone: "",
    notes: "",
  });

  const createMutation = useCreateContact();

  // Filter contacts by input value (case-insensitive, search name and email)
  const filteredContacts = contacts.filter(
    (contact) =>
      contact.name.toLowerCase().includes(inputValue.toLowerCase()) ||
      contact.email.toLowerCase().includes(inputValue.toLowerCase())
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
        Math.min(prev + 1, filteredContacts.length - 1)
      );
    } else if (e.key === "ArrowUp") {
      e.preventDefault();
      setHighlightedIndex((prev) => Math.max(prev - 1, 0));
    } else if (e.key === "Enter") {
      e.preventDefault();
      if (highlightedIndex >= 0 && highlightedIndex < filteredContacts.length) {
        const selectedContact = filteredContacts[highlightedIndex];
        if (selectedContact) {
          onChange(selectedContact.id);
          setIsOpen(false);
        }
      }
    } else if (e.key === "Escape") {
      e.preventDefault();
      setInputValue("");
      setIsOpen(false);
    }
  };

  const handleContactClick = (contactId: string) => {
    onChange(contactId);
    setIsOpen(false);
  };

  const handleCreateSubmit = async () => {
    if (!formData.name.trim() || !formData.email.trim() || !defaultOrganizationId) return;

    try {
      const newContact = await createMutation.mutateAsync({
        name: formData.name.trim(),
        email: formData.email.trim(),
        organization_id: defaultOrganizationId,
        role_title: formData.role_title.trim() || undefined,
        phone: formData.phone.trim() || undefined,
        notes: formData.notes.trim() || undefined,
      });
      // Auto-select the newly created contact
      onChange(newContact.id);
      // Notify parent if callback provided
      onContactCreated?.(newContact);
      // Reset and close
      setFormData({
        name: "",
        email: "",
        role_title: "",
        phone: "",
        notes: "",
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
        email: "",
        role_title: "",
        phone: "",
        notes: "",
      });
    }
    setShowCreateDialog(open);
  };

  // Simple email validation
  const isEmailValid = (email: string) => {
    return /^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(email);
  };

  // Get display text for trigger button
  const selectedContact = value ? contacts.find((c) => c.id === value) : null;
  const displayText = selectedContact
    ? `${selectedContact.name} (${selectedContact.email})`
    : placeholder;

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
              !selectedContact && "text-muted-foreground",
              triggerClassName
            )}
          >
            <div className="flex items-center gap-2 truncate">
              <User className="h-4 w-4 shrink-0 opacity-50" />
              <span className="truncate">{displayText}</span>
            </div>
            <ChevronDown className="ml-2 h-4 w-4 shrink-0 opacity-50" />
          </Button>
        </PopoverTrigger>
        <PopoverContent className="w-[320px] p-0" align="start">
          <div className="p-2">
            <div className="relative">
              <Search className="absolute left-2 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
              <Input
                ref={inputRef}
                value={inputValue}
                onChange={(e) => setInputValue(e.target.value)}
                onKeyDown={handleKeyDown}
                placeholder="Search contacts..."
                className="pl-8"
              />
            </div>
          </div>
          <ul
            ref={listRef}
            className="max-h-60 overflow-auto border-t"
            role="listbox"
          >
            {filteredContacts.length === 0 ? (
              <li className="px-3 py-2 text-sm text-muted-foreground">
                No matching contacts
              </li>
            ) : (
              filteredContacts.map((contact, index) => {
                const isSelected = value === contact.id;
                const isHighlighted = index === highlightedIndex;

                return (
                  <li key={contact.id} role="option" aria-selected={isSelected}>
                    <button
                      type="button"
                      className={cn(
                        "flex w-full items-center gap-2 px-3 py-2 text-left text-sm",
                        isHighlighted ? "bg-accent" : "hover:bg-accent/50"
                      )}
                      onClick={() => handleContactClick(contact.id)}
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
                      <div className="flex-1 truncate">
                        <div className="font-medium truncate">{contact.name}</div>
                        <div className="text-xs text-muted-foreground truncate">
                          {contact.email}
                        </div>
                      </div>
                    </button>
                  </li>
                );
              })
            )}
            {allowCreate && defaultOrganizationId && (
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
                  <span>Create New Contact</span>
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
              <DialogTitle>New Contact</DialogTitle>
            </DialogHeader>
            <div className="space-y-4 py-4">
              <div className="space-y-2">
                <Label htmlFor="new-contact-name">Name *</Label>
                <Input
                  id="new-contact-name"
                  value={formData.name}
                  onChange={(e) =>
                    setFormData({ ...formData, name: e.target.value })
                  }
                  placeholder="Enter contact name"
                />
              </div>
              <div className="space-y-2">
                <Label htmlFor="new-contact-email">Email *</Label>
                <Input
                  id="new-contact-email"
                  type="email"
                  value={formData.email}
                  onChange={(e) =>
                    setFormData({ ...formData, email: e.target.value })
                  }
                  placeholder="Enter email address"
                />
                {formData.email && !isEmailValid(formData.email) && (
                  <p className="text-xs text-destructive">
                    Please enter a valid email address
                  </p>
                )}
              </div>
              <div className="space-y-2">
                <Label htmlFor="new-contact-role">Role/Title</Label>
                <Input
                  id="new-contact-role"
                  value={formData.role_title}
                  onChange={(e) =>
                    setFormData({ ...formData, role_title: e.target.value })
                  }
                  placeholder="e.g., Project Manager, Engineer"
                />
              </div>
              <div className="space-y-2">
                <Label htmlFor="new-contact-phone">Phone</Label>
                <Input
                  id="new-contact-phone"
                  type="tel"
                  value={formData.phone}
                  onChange={(e) =>
                    setFormData({ ...formData, phone: e.target.value })
                  }
                  placeholder="Enter phone number"
                />
              </div>
              <div className="space-y-2">
                <Label htmlFor="new-contact-notes">Notes</Label>
                <Textarea
                  id="new-contact-notes"
                  value={formData.notes}
                  onChange={(e) =>
                    setFormData({ ...formData, notes: e.target.value })
                  }
                  placeholder="Optional notes about this contact"
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
                disabled={
                  !formData.name.trim() ||
                  !formData.email.trim() ||
                  !isEmailValid(formData.email) ||
                  createMutation.isPending
                }
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
