/**
 * Application sidebar navigation component.
 */

import { Link, useLocation } from "react-router-dom";
import { cn } from "@/lib/utils";
import { useAuth } from "@/hooks/useAuth";

interface NavItem {
  label: string;
  href: string;
  adminOnly?: boolean;
}

const navItems: NavItem[] = [
  { label: "Dashboard", href: "/" },
  { label: "Projects", href: "/projects" },
  { label: "Organizations", href: "/organizations" },
  { label: "Contacts", href: "/contacts" },
  { label: "Search", href: "/search" },
  { label: "Import", href: "/import", adminOnly: true },
  { label: "Admin", href: "/admin", adminOnly: true },
];

interface SidebarProps {
  className?: string;
}

export function Sidebar({ className }: SidebarProps) {
  const location = useLocation();
  const { isAdmin } = useAuth();

  const filteredItems = navItems.filter(
    (item) => !item.adminOnly || isAdmin,
  );

  return (
    <aside
      className={cn(
        "w-64 border-r bg-background px-4 py-6",
        className,
      )}
    >
      <nav className="space-y-2">
        {filteredItems.map((item) => {
          const isActive = location.pathname === item.href ||
            (item.href !== "/" && location.pathname.startsWith(item.href));

          return (
            <Link
              key={item.href}
              to={item.href}
              className={cn(
                "block rounded-md px-3 py-2 text-sm font-medium transition-colors",
                isActive
                  ? "bg-primary text-primary-foreground"
                  : "text-muted-foreground hover:bg-muted hover:text-foreground",
              )}
            >
              {item.label}
            </Link>
          );
        })}
      </nav>
    </aside>
  );
}
