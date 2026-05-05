// Conversational chat layer — ChatInputBox component tests.
import { describe, it, expect, vi } from 'vitest';
import { render, screen, fireEvent } from '@testing-library/react';
import { ChatInputBox } from './ChatInputBox';

describe('ChatInputBox', () => {
  it('renders input with placeholder when visible', () => {
    render(<ChatInputBox onSend={vi.fn()} disabled={false} visible={true} />);
    expect(
      screen.getByPlaceholderText('Ask anything about this customer…')
    ).toBeInTheDocument();
  });

  it('renders nothing when visible is false', () => {
    const { container } = render(
      <ChatInputBox onSend={vi.fn()} disabled={false} visible={false} />
    );
    expect(container.firstChild).toBeNull();
  });

  it('disables input and button when disabled prop is true', () => {
    render(<ChatInputBox onSend={vi.fn()} disabled={true} visible={true} />);
    const input = screen.getByPlaceholderText('Ask anything about this customer…');
    const button = screen.getByRole('button', { name: /send message/i });
    expect(input).toBeDisabled();
    expect(button).toBeDisabled();
  });

  it('calls onSend with trimmed message on form submit', () => {
    const onSend = vi.fn();
    render(<ChatInputBox onSend={onSend} disabled={false} visible={true} />);
    const input = screen.getByPlaceholderText('Ask anything about this customer…');
    fireEvent.change(input, { target: { value: '  Why did her bill jump?  ' } });
    fireEvent.submit(input.closest('form')!);
    expect(onSend).toHaveBeenCalledWith('Why did her bill jump?');
  });

  it('clears input after submission', () => {
    const onSend = vi.fn();
    render(<ChatInputBox onSend={onSend} disabled={false} visible={true} />);
    const input = screen.getByPlaceholderText(
      'Ask anything about this customer…'
    ) as HTMLInputElement;
    fireEvent.change(input, { target: { value: 'Hello' } });
    fireEvent.submit(input.closest('form')!);
    expect(input.value).toBe('');
  });

  it('does not call onSend for empty/whitespace-only messages', () => {
    const onSend = vi.fn();
    render(<ChatInputBox onSend={onSend} disabled={false} visible={true} />);
    const input = screen.getByPlaceholderText('Ask anything about this customer…');
    fireEvent.change(input, { target: { value: '   ' } });
    fireEvent.submit(input.closest('form')!);
    expect(onSend).not.toHaveBeenCalled();
  });

  it('submits on Enter key press (without Shift)', () => {
    const onSend = vi.fn();
    render(<ChatInputBox onSend={onSend} disabled={false} visible={true} />);
    const input = screen.getByPlaceholderText('Ask anything about this customer…');
    fireEvent.change(input, { target: { value: 'Test message' } });
    fireEvent.keyDown(input, { key: 'Enter', shiftKey: false });
    expect(onSend).toHaveBeenCalledWith('Test message');
  });

  it('does not submit on Shift+Enter', () => {
    const onSend = vi.fn();
    render(<ChatInputBox onSend={onSend} disabled={false} visible={true} />);
    const input = screen.getByPlaceholderText('Ask anything about this customer…');
    fireEvent.change(input, { target: { value: 'Test message' } });
    fireEvent.keyDown(input, { key: 'Enter', shiftKey: true });
    expect(onSend).not.toHaveBeenCalled();
  });

  it('has accessible form landmark', () => {
    render(<ChatInputBox onSend={vi.fn()} disabled={false} visible={true} />);
    expect(screen.getByRole('form', { name: /chat input/i })).toBeInTheDocument();
  });
});
