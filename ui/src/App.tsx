// Phase 4 agent-assist UI composition. Wires the `useRecommendations` hook
// (data layer, 04-03) to the 6 presentation components (04-04) behind a
// state-driven result region.
//
// UI-SPEC contracts observed here:
//   - §Interaction States lines 144-152: idle → EmptyState; loading →
//     RecommendationSkeletons; success → two RecommendationCards;
//     error → ErrorAlert IN PLACE OF the cards (not alongside).
//   - §Specifics "Card order is stable" — Green first, Cheapest second.
//   - §Color card-layout contract (REC-03) — equal cards, differentiation
//     lives inside RecommendationCard via track prop only.
//   - §Typography Display (28px/600/1.2) — page title.
//   - §Spacing scale (xl=32px between cards, 2xl=48px title→form, xl=32px
//     form→chips→results, 3xl=64px page rhythm).
//
// CONTEXT.md decisions observed:
//   - D-08: PersonaChips sits between the form and results; onSelect is
//     wired directly to lookup so a single click fires the full flow.
//   - D-12: LookupForm.onLookup flows raw input to the hook, which performs
//     normalization + regex gating. No double-validation at the App layer.
//   - isLoading / disabled both derive from `state.status === 'loading'`.
import { useRecommendations } from '@/hooks/useRecommendations';
import { LookupForm } from '@/components/LookupForm';
import { PersonaChips } from '@/components/PersonaChips';
import { RecommendationCard } from '@/components/RecommendationCard';
import { ReasoningTrace } from '@/components/ReasoningTrace';
import { RecommendationSkeletons } from '@/components/RecommendationSkeletons';
import { ErrorAlert } from '@/components/ErrorAlert';
import { EmptyState } from '@/components/EmptyState';
import { HardshipBanner } from '@/components/HardshipBanner';
import { VersionIndicator } from '@/components/VersionIndicator';

function App() {
  const { state, lookup } = useRecommendations();
  const isLoading = state.status === 'loading';

  return (
    <div className="min-h-screen bg-background text-foreground">
      <main className="mx-auto max-w-4xl px-6 py-16">
        {/* Page title — UI-SPEC Display role: 28px / semibold / 1.2 line-height. */}
        <h1 className="text-[28px] font-semibold leading-[34px] mb-12">
          Tariff Recommendations
        </h1>

        {/* Form — Customer ID input + "Look up customer" CTA (D-12 submit). */}
        <section className="mb-8">
          <LookupForm onLookup={lookup} isLoading={isLoading} />
        </section>

        {/* Persona quick-pick chips (D-08) — one click fires lookup. */}
        <section className="mb-8">
          <PersonaChips onSelect={lookup} disabled={isLoading} />
        </section>

        {/* Result region — state-driven. Error replaces cards, never alongside. */}
        <section>
          {state.status === 'idle' && <EmptyState />}

          {state.status === 'loading' && <RecommendationSkeletons />}

          {state.status === 'error' && (
            <ErrorAlert httpStatus={state.httpStatus} customerId={state.customerId} />
          )}

          {state.status === 'hardship' && (
            <HardshipBanner data={state.data} />
          )}

          {state.status === 'success' && (
            <>
              {/* Phase 13 D-28: ReasoningTrace lives ABOVE the card grid
                  (turn-level, shared). Empty trace / ?narrative=off →
                  component renders null. */}
              <ReasoningTrace trace={state.data.reasoning_trace ?? []} />
              <div className="grid grid-cols-1 md:grid-cols-2 gap-8">
                {/* Card order stable: Green first, Cheapest second. */}
                <RecommendationCard track="green" data={state.data.green} />
                <RecommendationCard track="cheapest" data={state.data.cheapest} />
              </div>
            </>
          )}
        </section>
      </main>
      <VersionIndicator />
    </div>
  );
}

export default App;
