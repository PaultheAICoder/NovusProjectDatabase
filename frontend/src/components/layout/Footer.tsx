/**
 * Footer component with version info.
 */

// Version is auto-incremented by git pre-commit hook
export const APP_VERSION = "0.25.172";
export const BUILD_TIMESTAMP = "2026-01-05T05:14:42Z";

export function Footer() {
  return (
    <footer className="fixed bottom-0 left-0 right-0 border-t bg-muted/50 px-4 py-2 text-xs text-muted-foreground">
      <div className="mx-auto flex max-w-screen-2xl items-center justify-between">
        <span>Novus Project Database</span>
        <span>
          v{APP_VERSION} • {new Date(BUILD_TIMESTAMP).toLocaleString()}
        </span>
      </div>
    </footer>
  );
}
