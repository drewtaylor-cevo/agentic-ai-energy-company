// Conversational chat layer — ChatInputBox component.
// Renders a text input + send button below recommendation cards.
// Hidden when `?narrative=off` is active (kill-switch, Req 7.5).
// Disabled during agent processing (Req 6.3).
import { useState } from 'react';
import type { FormEvent, KeyboardEvent } from 'react';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Send } from 'lucide-react';

interface ChatInputBoxProps {
  onSend: (message: string) => void;
  disabled: boolean;
  visible: boolean;
}

export function ChatInputBox({ onSend, disabled, visible }: ChatInputBoxProps) {
  const [value, setValue] = useState('');

  if (!visible) return null;

  const canSend = value.trim().length > 0 && !disabled;

  const handleSubmit = (e: FormEvent) => {
    e.preventDefault();
    if (!canSend) return;
    onSend(value.trim());
    setValue('');
  };

  const handleKeyDown = (e: KeyboardEvent<HTMLInputElement>) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      if (!canSend) return;
      onSend(value.trim());
      setValue('');
    }
  };

  return (
    <form onSubmit={handleSubmit} className="mt-8 flex gap-2" aria-label="Chat input">
      <Input
        type="text"
        placeholder="Ask anything about this customer…"
        value={value}
        onChange={(e) => setValue(e.target.value)}
        onKeyDown={handleKeyDown}
        disabled={disabled}
        className="flex-1"
        aria-label="Chat message"
      />
      <Button
        type="submit"
        size="icon"
        disabled={!canSend}
        aria-label="Send message"
      >
        <Send className="size-4" />
      </Button>
    </form>
  );
}
