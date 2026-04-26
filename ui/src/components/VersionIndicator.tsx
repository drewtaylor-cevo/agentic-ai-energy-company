// Bottom-right fixed build marker (UI-07, D-14–D-17). Embedded at build time
// via `define: { __GIT_SHA__ }` in vite.config.ts (Plan 01); renders
// `v2.0 · <7-char-sha>` so the presenter can verify at demo time which
// bundle is live (defends against stale-bundle risk). Uses U+00B7 MIDDLE DOT
// as separator — same convention as personas.ts line 18 and ROADMAP success
// criterion 4 verbatim. Bottom-right (not top-right) so DevTools docked
// right at 1280px does not collide (D-14). z-50 guards against future
// modals/toasts occluding the marker.
export function VersionIndicator() {
  return (
    <span className="fixed bottom-2 right-2 z-50 text-xs text-muted-foreground opacity-60">
      v2.0 · {__GIT_SHA__}
    </span>
  );
}
