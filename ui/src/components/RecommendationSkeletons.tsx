// Two skeleton placeholders that mirror the exact shape of two
// RecommendationCard renders (same width, same approximate height). Prevents
// layout shift across the loading → success transition.
//
// The grid class `grid grid-cols-1 md:grid-cols-2 gap-8` MUST match the
// layout used by App.tsx's success state so skeleton → cards is zero-reflow.
import { Card, CardHeader, CardContent } from '@/components/ui/card';
import { Skeleton } from '@/components/ui/skeleton';
import { NARRATIVE_ENABLED } from '@/lib/flags';

export function RecommendationSkeletons() {
  return (
    <div className="grid grid-cols-1 md:grid-cols-2 gap-8">
      {[0, 1].map((i) => (
        <Card key={i} className="border-t-4 border-t-muted">
          <CardHeader className="pb-4">
            <div className="flex items-center gap-2">
              <Skeleton className="h-5 w-5 rounded" />
              <Skeleton className="h-6 w-36" />
            </div>
            <Skeleton className="h-5 w-28 mt-2" />
          </CardHeader>
          <CardContent className="space-y-4">
            <div>
              <Skeleton className="h-4 w-32" />
              <Skeleton className="h-6 w-40 mt-1" />
            </div>
            <div className="grid grid-cols-2 gap-4">
              <div>
                <Skeleton className="h-4 w-28" />
                <Skeleton className="h-8 w-24 mt-1" />
              </div>
              <div>
                <Skeleton className="h-4 w-28" />
                <Skeleton className="h-8 w-24 mt-1" />
              </div>
            </div>
            {NARRATIVE_ENABLED && (
              <div className="space-y-2">
                <Skeleton className="h-4 w-full" />
                <Skeleton className="h-4 w-4/5" />
              </div>
            )}
            <Skeleton className="h-4 w-full" />
            {NARRATIVE_ENABLED && (
              <div className="border-l-4 border-l-muted pl-4 py-2 space-y-2">
                <Skeleton className="h-5 w-full" />
                <Skeleton className="h-5 w-5/6" />
                <Skeleton className="h-5 w-3/5" />
              </div>
            )}
          </CardContent>
        </Card>
      ))}
    </div>
  );
}
