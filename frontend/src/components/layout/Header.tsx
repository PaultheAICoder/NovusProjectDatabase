/**
 * Application header component.
 */

import { useAuth } from "@/hooks/useAuth";
import { cn } from "@/lib/utils";

interface HeaderProps {
  className?: string;
}

export function Header({ className }: HeaderProps) {
  const { user, isAuthenticated, login, logout } = useAuth();

  return (
    <header
      className={cn(
        "border-b bg-background px-6 py-4",
        className,
      )}
    >
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-4">
          <h1 className="text-xl font-semibold">Novus Project Database</h1>
        </div>

        <div className="flex items-center gap-4">
          {isAuthenticated ? (
            <>
              <span className="text-sm text-muted-foreground">
                {user?.display_name}
              </span>
              <button
                onClick={() => logout()}
                className="text-sm text-muted-foreground hover:text-foreground"
              >
                Sign out
              </button>
            </>
          ) : (
            <button
              onClick={login}
              className="text-sm font-medium text-primary hover:underline"
            >
              Sign in
            </button>
          )}
        </div>
      </div>
    </header>
  );
}
