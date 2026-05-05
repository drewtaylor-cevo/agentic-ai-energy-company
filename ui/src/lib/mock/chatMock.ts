import type { ReasoningTraceEntry } from '../types';

/**
 * Callbacks for chat streaming simulation events.
 * Mirrors the SSE wire protocol event types from design.md §Chat SSE Events.
 */
export interface ChatStreamingCallbacks {
  onTraceStep: (event: ReasoningTraceEntry) => void;
  onReply: (reply: string, reasoning_trace: ReasoningTraceEntry[], session_id: string) => void;
  onError: (status: number, message: string) => void;
  onDone: () => void;
}

/** Known customer IDs that the mock supports. Unknown IDs trigger a 404 error. */
const KNOWN_CUSTOMER_IDS = new Set(['CUST-001', 'CUST-002', 'CUST-003']);

/**
 * Mock reply routing table.
 * Each entry maps a keyword (matched case-insensitively in the message) to
 * a set of trace steps and a contextual reply with realistic numbers matching
 * the demo personas (Sarah CUST-001, Marcus CUST-002, Elena CUST-003).
 *
 * Requirements: 9.2, 9.3
 */
interface MockRoute {
  trace: ReasoningTraceEntry[];
  reply: string;
}

function getRoutes(customerId: string): Record<string, MockRoute> {
  // Persona-specific numbers from the demo fixtures:
  // Sarah (CUST-001): Green $30/mo, Cheapest $55/mo
  // Marcus (CUST-002): Green $16.90/mo, Cheapest $30.98/mo
  // Elena (CUST-003): Green $14.00/mo, Cheapest $25.67/mo, bill shock +$65.16
  const personaData: Record<string, { green: string; cheapest: string; shock?: string; shockMonth?: string }> = {
    'CUST-001': { green: '$30.00', cheapest: '$55.00' },
    'CUST-002': { green: '$16.90', cheapest: '$30.98' },
    'CUST-003': { green: '$14.00', cheapest: '$25.67', shock: '$65.16', shockMonth: '2025-10' },
  };

  const data = personaData[customerId] ?? personaData['CUST-001'];

  return {
    bill: {
      trace: [
        { tool: 'get_billing_history', summary: '12 months billing data retrieved' },
      ],
      reply: `Based on the billing records, this customer has had consistent usage over the past 12 months. The average monthly bill is within normal range for their household profile. The most recent bill is current and paid on time.`,
    },
    shock: {
      trace: [
        { tool: 'get_billing_history', summary: '12 months billing data retrieved' },
        { tool: 'detect_bill_shock', summary: `Bill shock detected: +${data.shock ?? '$45.60'} ${data.shockMonth ?? '2025-02'} vs 11-month avg` },
      ],
      reply: `Bill shock analysis shows an anomaly of +${data.shock ?? '$45.60'} in ${data.shockMonth ?? '2025-02'} compared to the 11-month average. This spike appears to be driven by increased usage during that billing period. I'd recommend discussing the customer's usage patterns for that month.`,
    },
    solar: {
      trace: [
        { tool: 'simulate_savings', summary: `Green ${data.green}/mo; Cheapest ${data.cheapest}/mo` },
      ],
      reply: `Based on the savings simulation, a solar-aligned plan (EcoFlex 100) could save this customer ${data.green} per month. The plan sources 100% renewable energy and suits their usage profile well.`,
    },
    green: {
      trace: [
        { tool: 'simulate_savings', summary: `Green ${data.green}/mo; Cheapest ${data.cheapest}/mo` },
      ],
      reply: `The green energy plan (EcoFlex 100) offers 100% renewable energy sourcing with a projected saving of ${data.green} per month (${customerId === 'CUST-001' ? '$360.00' : customerId === 'CUST-002' ? '$202.80' : '$168.00'} annually). It's well-suited to this customer's usage pattern.`,
    },
    savings: {
      trace: [
        { tool: 'get_billing_history', summary: '12 months billing data retrieved' },
        { tool: 'simulate_savings', summary: `Green ${data.green}/mo; Cheapest ${data.cheapest}/mo` },
      ],
      reply: `Savings simulation complete. The green plan (EcoFlex 100) would save ${data.green}/month and the cheapest plan (Value 12) would save ${data.cheapest}/month based on this customer's 12-month usage history.`,
    },
    hardship: {
      trace: [
        { tool: 'get_hardship_flag', summary: 'hardship_flag=False' },
      ],
      reply: `The hardship flag check shows this customer is not currently flagged for hardship support. Their account is in good standing with no payment assistance markers.`,
    },
  };
}

/**
 * Simulate chat SSE streaming for mock mode (VITE_API_URL unset).
 *
 * Emits trace_step events with ~300ms delays to simulate streaming,
 * followed by a chat_reply event and a done event.
 *
 * Returns an abort function to cancel the simulation.
 *
 * Requirements: 9.1, 9.2, 9.3, 9.4
 */
export function simulateChatStreaming(
  customerId: string,
  message: string,
  callbacks: ChatStreamingCallbacks,
): () => void {
  let aborted = false;
  const timers: ReturnType<typeof setTimeout>[] = [];

  const schedule = (fn: () => void, delay: number) => {
    const timer = setTimeout(() => {
      if (!aborted) fn();
    }, delay);
    timers.push(timer);
  };

  // Requirement 9.4: Return mock error for unknown customer IDs
  if (!KNOWN_CUSTOMER_IDS.has(customerId)) {
    schedule(() => {
      callbacks.onError(404, 'Customer not found. Please verify the customer ID.');
    }, 300);
    schedule(() => {
      callbacks.onDone();
    }, 350);
    return () => {
      aborted = true;
      timers.forEach(clearTimeout);
    };
  }

  // Keyword-based mock routing (Requirement 9.2)
  const lowerMessage = message.toLowerCase();
  const routes = getRoutes(customerId);

  let matchedRoute: MockRoute | null = null;

  // Match keywords in priority order (more specific first)
  const keywordOrder: string[] = ['shock', 'hardship', 'savings', 'solar', 'green', 'bill'];
  for (const keyword of keywordOrder) {
    if (lowerMessage.includes(keyword)) {
      matchedRoute = routes[keyword];
      break;
    }
  }

  // Default fallback for unmatched messages
  const mockTrace: ReasoningTraceEntry[] = matchedRoute?.trace ?? [];
  const mockReply: string = matchedRoute?.reply ??
    'Based on the customer records, I can help with that query. Could you provide more details about what specific aspect of the account you would like to know about?';

  // Emit trace steps with ~300ms delays (Requirement 9.3)
  let delay = 300;
  for (const step of mockTrace) {
    const currentDelay = delay;
    schedule(() => {
      callbacks.onTraceStep(step);
    }, currentDelay);
    delay += 300;
  }

  // Emit reply after trace steps
  const replyDelay = delay + 200;
  schedule(() => {
    callbacks.onReply(mockReply, mockTrace, `mock-session-${customerId}`);
  }, replyDelay);

  // Emit done as terminal event
  schedule(() => {
    callbacks.onDone();
  }, replyDelay + 50);

  return () => {
    aborted = true;
    timers.forEach(clearTimeout);
  };
}
