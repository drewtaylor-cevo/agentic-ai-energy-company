// Equal-cards contract (UI-SPEC §Color lines 88-94, load-bearing for REC-03):
// A single component renders BOTH Green and Cheapest tracks. The ONLY permitted
// visual differences are accent color, heading, icon, badge text, methodology
// line. No ranking, no "recommended" badge, no comparative weighting.
//
// Card ordering (Green first, Cheapest second — UI-SPEC §Specifics "Card order
// is stable") is the parent's responsibility; this component is track-agnostic.
import { Card, CardHeader, CardTitle, CardContent } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { Leaf, PiggyBank } from 'lucide-react';
import type { TrackInfo } from '@/lib/types';

const TRACK_CONFIG = {
  green: {
    heading: 'Green Option',
    badge: '100% renewable',
    icon: Leaf,
    accentBorder: 'border-t-emerald-600',
    accentText: 'text-emerald-600',
    methodologyTemplate:
      'Based on your 12-month kWh usage at the {plan_name} rate (100% renewable).',
  },
  cheapest: {
    heading: 'Cheapest Option',
    badge: 'Lowest unit price',
    icon: PiggyBank,
    accentBorder: 'border-t-blue-600',
    accentText: 'text-blue-600',
    methodologyTemplate:
      'Based on your 12-month kWh usage at the {plan_name} rate (lowest unit price).',
  },
} as const;

interface RecommendationCardProps {
  track: 'green' | 'cheapest';
  data: TrackInfo;
}

export function RecommendationCard({ track, data }: RecommendationCardProps) {
  const config = TRACK_CONFIG[track];
  const Icon = config.icon;

  // Methodology templating per UI-SPEC §Copywriting lines 125-126:
  // substitute {plan_name}; fall back to "selected" if the field is missing or empty.
  const planName = data.plan_name || 'selected';
  const methodology = config.methodologyTemplate.replace('{plan_name}', planName);

  return (
    <Card className={`border-t-4 ${config.accentBorder}`}>
      <CardHeader className="pb-4">
        <div className="flex items-center gap-2">
          <Icon className={`h-5 w-5 ${config.accentText}`} />
          <CardTitle className="text-xl font-semibold">{config.heading}</CardTitle>
        </div>
        <Badge variant="secondary" className="w-fit">
          {config.badge}
        </Badge>
      </CardHeader>
      <CardContent className="space-y-4">
        <div>
          <p className="text-sm font-semibold text-muted-foreground">Recommended plan</p>
          <p className={`text-lg font-semibold ${config.accentText}`}>{data.plan_name}</p>
        </div>
        <div className="grid grid-cols-2 gap-4">
          <div>
            <p className="text-sm font-semibold text-muted-foreground">Monthly saving</p>
            <p className="text-2xl font-semibold">
              ${data.saving_monthly.toFixed(2)}
              <span className="text-sm font-normal text-muted-foreground">/mo</span>
            </p>
          </div>
          <div>
            <p className="text-sm font-semibold text-muted-foreground">Annual saving</p>
            <p className="text-2xl font-semibold">
              ${data.saving_annual.toFixed(2)}
              <span className="text-sm font-normal text-muted-foreground">/yr</span>
            </p>
          </div>
        </div>
        <p className="text-sm text-muted-foreground">{methodology}</p>
      </CardContent>
    </Card>
  );
}
