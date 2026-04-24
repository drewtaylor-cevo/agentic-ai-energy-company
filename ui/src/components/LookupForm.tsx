// D-12: Enter and button-click both submit via <form onSubmit> + type="submit".
// D-10: Input value is passed raw to onLookup — the parent (via
// useRecommendations.lookup()) normalizes with normalizeCustomerId and gates
// against CUSTOMER_ID_PATTERN. The form intentionally avoids reproducing that
// logic so there is a single canonical normalization surface.
// D-11: Placeholder uses the dashed canonical format.
import { useState } from 'react';
import type { FormEvent } from 'react';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';

interface LookupFormProps {
  onLookup: (rawId: string) => void;
  isLoading: boolean;
}

export function LookupForm({ onLookup, isLoading }: LookupFormProps) {
  const [value, setValue] = useState('');

  const handleSubmit = (e: FormEvent) => {
    e.preventDefault();
    if (!value.trim()) return;
    onLookup(value);
  };

  return (
    <form onSubmit={handleSubmit} className="space-y-2">
      <Label htmlFor="customer-id" className="text-sm font-semibold">
        Customer ID
      </Label>
      <div className="flex gap-2">
        <Input
          id="customer-id"
          type="text"
          placeholder="e.g. CUST-001234"
          value={value}
          onChange={(e) => setValue(e.target.value)}
          disabled={isLoading}
          className="max-w-xs"
        />
        <Button type="submit" disabled={isLoading || !value.trim()}>
          {isLoading ? 'Looking up…' : 'Look up customer'}
        </Button>
      </div>
    </form>
  );
}
