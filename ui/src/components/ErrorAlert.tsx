// Renders IN PLACE OF the result cards (UI-SPEC §Interaction States "Error"),
// never alongside. Copy is keyed by HTTP status via errorCopyForStatus — the
// UI owns operator-facing error strings, not the server.
import { AlertCircle } from 'lucide-react';
import { Alert, AlertDescription } from '@/components/ui/alert';
import { errorCopyForStatus } from '@/lib/errors';

interface ErrorAlertProps {
  httpStatus: number;
  customerId: string;
}

export function ErrorAlert({ httpStatus, customerId }: ErrorAlertProps) {
  return (
    <Alert variant="destructive">
      <AlertCircle className="h-4 w-4" />
      <AlertDescription>{errorCopyForStatus(httpStatus, customerId)}</AlertDescription>
    </Alert>
  );
}
