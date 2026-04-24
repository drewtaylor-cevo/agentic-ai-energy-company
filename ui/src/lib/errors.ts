/**
 * Returns operator-facing error copy keyed by HTTP status code.
 *
 * Copy strings from UI-SPEC §Copywriting Contract (lines 119-122). The UI
 * IGNORES `response.json().error` text and keys on status code alone — the
 * spec owns operator-facing strings, not the server.
 *
 * Characters to preserve:
 *   - en-dash "–" in "3–6 digits" (U+2013)
 *   - em-dash "—" in "Try again — if it persists" (U+2014)
 *
 * @param status HTTP status code returned by the API (use 0 for network failures)
 * @param customerId the normalized customer ID, echoed into the 404 copy
 */
export function errorCopyForStatus(status: number, customerId: string): string {
  switch (status) {
    case 400:
      return "That doesn't look like a customer ID. Format is CUST followed by 3–6 digits.";
    case 404:
      return `No customer found for ${customerId}. Check the ID and try again.`;
    case 504:
      return "Recommendations are taking longer than expected. Try again in a moment.";
    case 500:
    case 502:
      return "Something went wrong on our end. Try again — if it persists, contact support.";
    default:
      // Network failure, unexpected status — fall back to the generic server copy.
      return "Something went wrong on our end. Try again — if it persists, contact support.";
  }
}
