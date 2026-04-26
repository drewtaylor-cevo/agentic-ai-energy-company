import { describe, it, expect } from 'vitest';
import { MOCK_RECOMMENDATIONS } from './recommendations';

// Mirrors agent/tests/test_fallbacks_pass_validator.py: every committed
// narrative + call_script string must pass the Phase 6 validator rules
// (no digit, no currency/percent, word-count cap). Catches mock-authoring
// drift if someone pastes a `$` or a digit into the fixture during rehearsal.

const FORBIDDEN = /[\d$£€%]/;
const countWords = (s: string) => s.trim().split(/\s+/).length;

describe('MOCK_RECOMMENDATIONS narrative + call_script validator rules', () => {
  for (const [customerId, response] of Object.entries(MOCK_RECOMMENDATIONS)) {
    for (const track of ['green', 'cheapest'] as const) {
      const info = response[track];
      describe(`${customerId} / ${track}`, () => {
        it('usage_narrative is present and non-empty', () => {
          expect(info.usage_narrative.length).toBeGreaterThan(0);
        });
        it('usage_narrative contains no digit, currency, or percent', () => {
          expect(FORBIDDEN.test(info.usage_narrative)).toBe(false);
        });
        it('usage_narrative is ≤ 20 words', () => {
          expect(countWords(info.usage_narrative)).toBeLessThanOrEqual(20);
        });
        it('call_script is present and non-empty', () => {
          expect(info.call_script.length).toBeGreaterThan(0);
        });
        it('call_script contains no digit, currency, or percent', () => {
          expect(FORBIDDEN.test(info.call_script)).toBe(false);
        });
        it('call_script is ≤ 22 words', () => {
          expect(countWords(info.call_script)).toBeLessThanOrEqual(22);
        });
      });
    }
  }
});
