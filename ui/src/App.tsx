// Phase 4 agent-assist UI composition. Wires the `useRecommendations` hook
// (data layer, 04-03) to the 6 presentation components (04-04) behind a
// state-driven result region.
//
// Phase 15 WF-01: adds FollowUpDrawer below the card grid in the success
// state. The drawer is reset when a new lookup is triggered.
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
import { useCallback } from 'react';
import { useRecommendations } from '@/hooks/useRecommendations';
import { useFollowUp } from '@/hooks/useFollowUp';
import { useChat } from '@/hooks/useChat';
import { LookupForm } from '@/components/LookupForm';
import { PersonaChips } from '@/components/PersonaChips';
import { RecommendationCard } from '@/components/RecommendationCard';
import { ReasoningTrace } from '@/components/ReasoningTrace';
import { RecommendationSkeletons } from '@/components/RecommendationSkeletons';
import { ErrorAlert } from '@/components/ErrorAlert';
import { EmptyState } from '@/components/EmptyState';
import { RetentionQueue } from '@/components/RetentionQueue';
import { HardshipBanner } from '@/components/HardshipBanner';
import { FollowUpDrawer } from '@/components/FollowUpDrawer';
import { ChatInputBox } from '@/components/ChatInputBox';
import { ChatThread } from '@/components/ChatThread';
import { VersionIndicator } from '@/components/VersionIndicator';
import { ActionCard } from '@/components/ActionCard';
import { NARRATIVE_ENABLED } from '@/lib/flags';

function App() {
  const { state, lookup } = useRecommendations();
  const { state: followUpState, fetchFollowUp, reset: resetFollowUp } = useFollowUp();
  const customerId = (state.status === 'success' || state.status === 'streaming' || state.status === 'error' || state.status === 'hardship') ? state.customerId : '';
  const { state: chatState, sendMessage, reset: resetChat } = useChat(customerId);
  const isLoading = state.status === 'loading';

  // LD-7: ?narrative=off collapses v3.0 surfaces to v2.0 shape.
  const narrativeOff = new URLSearchParams(window.location.search).get('narrative') === 'off';

  // Chat is visible when recommendations loaded and narrative is not off (Req 6.1, 7.5).
  const chatVisible = state.status === 'success' && !narrativeOff;

  // Wrap lookup to reset follow-up and chat state on new lookup (Req 6.7).
  const handleLookup = useCallback((rawId: string) => {
    resetFollowUp();
    resetChat();
    lookup(rawId);
  }, [lookup, resetFollowUp, resetChat]);

  return (
    <div className="min-h-screen bg-background text-foreground">
      <main className="mx-auto max-w-4xl px-6 py-16">
        {/* Page title — UI-SPEC Display role: 28px / semibold / 1.2 line-height. */}
        <h1 className="text-[28px] font-semibold leading-[34px] mb-12">
          Tariff Recommendations
        </h1>

        {/* Form — Customer ID input + "Look up customer" CTA (D-12 submit). */}
        <section className="mb-8">
          <LookupForm onLookup={handleLookup} isLoading={isLoading} />
        </section>

        {/* Persona quick-pick chips (D-08) — one click fires lookup. */}
        <section className="mb-8">
          <PersonaChips onSelect={handleLookup} disabled={isLoading} />
        </section>

        {/* Result region — state-driven. Error replaces cards, never alongside. */}
        <section>
          {state.status === 'idle' && <RetentionQueue onInvestigate={handleLookup} />}

          {state.status === 'loading' && <RecommendationSkeletons />}

          {state.status === 'streaming' && (
            <>
              {/* Progressive trace rendering during streaming (Task 7.5, Req 5.2/5.6).
                  Show received trace steps + skeleton while waiting for result. */}
              <ReasoningTrace trace={state.traceSteps} isStreaming />
              <RecommendationSkeletons />
            </>
          )}

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
                  component renders null. Streaming trace steps take priority
                  over batch reasoning_trace when available. */}
              <ReasoningTrace trace={state.traceSteps.length > 0 ? state.traceSteps : (state.data.reasoning_trace ?? [])} />
              <div className="grid grid-cols-1 md:grid-cols-2 gap-8">
                {/* Card order stable: Green first, Cheapest second. */}
                <RecommendationCard track="green" data={state.data.green} />
                <RecommendationCard track="cheapest" data={state.data.cheapest} />
              </div>

              {/* Agentic Actions Portfolio: ActionCards below recommendation cards.
                  Hidden when ?narrative=off is active (LD-7 kill-switch — actions
                  contain LLM-generated SMS content). Only render when pending_actions
                  is non-empty. */}
              {NARRATIVE_ENABLED && state.data.pending_actions && state.data.pending_actions.length > 0 && (
                <div className="mt-8 space-y-3" data-testid="action-cards-section">
                  {state.data.pending_actions.map((action) => (
                    <ActionCard key={action.action_id} action={action} />
                  ))}
                </div>
              )}

              {/* Phase 15 WF-01: Follow-up email drawer below the cards.
                  ?narrative=off → drawer renders null (LD-7). */}
              <FollowUpDrawer
                state={followUpState}
                onDraft={() => fetchFollowUp(state.customerId)}
                narrativeOff={narrativeOff}
              />

              {/* Conversational chat layer — ChatThread + ChatInputBox.
                  Hidden when ?narrative=off is active (Req 7.5, kill-switch). */}
              <ChatThread
                messages={chatState.messages}
                isProcessing={chatState.isProcessing}
                currentTrace={chatState.currentTrace}
                error={chatState.error}
              />
              <ChatInputBox
                onSend={sendMessage}
                disabled={chatState.isProcessing}
                visible={chatVisible}
              />
            </>
          )}
        </section>
      </main>
      <VersionIndicator />
    </div>
  );
}

export default App;
