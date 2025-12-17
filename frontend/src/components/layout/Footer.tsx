/**
 * Footer component with version info.
 */

// Version is auto-incremented by git pre-commit hook
export const APP_VERSION = "0.25.66";
export const BUILD_TIMESTAMP = "2025-12-17T06:12:37Z";

export function Footer() {
  return (
    <footer className="fixed bottom-0 left-0 right-0 bg-muted/50 border-t py-2 px-4 text-xs text-muted-foreground">
      <div className="flex justify-between items-center max-w-screen-2xl mx-auto">
        <span>Novus Project Database</span>
        <span>v{APP_VERSION} • {new Date(BUILD_TIMESTAMP).toLocaleString()}</span>
      </div>
    </footer>
  );
}
