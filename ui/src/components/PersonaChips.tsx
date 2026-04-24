// D-08 / D-09: quick-pick chips for the 3 seeded personas — presenter-safety
// during a live call. One click (or Enter / Space when focused) fires
// onSelect(persona.id); the parent wires this to useRecommendations.lookup().
//
// Keyboard accessibility: role="button" + tabIndex=0 + Enter/Space handler,
// so chips reach feature-parity with a <button> despite being rendered as
// shadcn Badges (span-based). `disabled` blocks interaction during loading.
import type { KeyboardEvent } from 'react';
import { Badge } from '@/components/ui/badge';
import { PERSONAS } from '@/personas';

interface PersonaChipsProps {
  onSelect: (customerId: string) => void;
  disabled: boolean;
}

export function PersonaChips({ onSelect, disabled }: PersonaChipsProps) {
  const handleKeyDown = (persona: { id: string }) => (e: KeyboardEvent<HTMLSpanElement>) => {
    if ((e.key === 'Enter' || e.key === ' ') && !disabled) {
      e.preventDefault();
      onSelect(persona.id);
    }
  };

  return (
    <div className="flex flex-wrap gap-2">
      {PERSONAS.map((persona) => (
        <Badge
          key={persona.id}
          variant="outline"
          className="cursor-pointer hover:bg-accent px-3 py-1 text-sm"
          onClick={() => !disabled && onSelect(persona.id)}
          role="button"
          tabIndex={disabled ? -1 : 0}
          aria-disabled={disabled}
          onKeyDown={handleKeyDown(persona)}
        >
          {persona.label}
        </Badge>
      ))}
    </div>
  );
}
