// Rendered when state.status === 'idle'. Copy verbatim from UI-SPEC
// §Copywriting lines 111-112.
export function EmptyState() {
  return (
    <div className="text-center py-12">
      <h2 className="text-xl font-semibold">No customer selected</h2>
      <p className="text-muted-foreground mt-2">
        Enter a customer ID to see tariff recommendations.
      </p>
    </div>
  );
}
