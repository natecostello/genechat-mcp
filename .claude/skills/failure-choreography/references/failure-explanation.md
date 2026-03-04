# Failure Explanation Patterns

Calibrated transparency templates by failure type and audience.

## Explanation Levels

### Level 1: User Summary

What happened in terms the user cares about.

**Characteristics**:
- Task-oriented language (not system language)
- Outcome-focused (what didn't happen)
- No jargon, no error codes
- 1-2 sentences max

**Template**:
```
[Action] failed: [consequence in user terms].
```

**Examples**:
```
Upload failed: your report didn't reach the server.
Sync failed: changes from the last hour aren't saved to cloud.
Analysis failed: the quarterly comparison couldn't be completed.
```

### Level 2: Actionable Detail

What specifically broke and why, with enough detail to inform decisions.

**Characteristics**:
- Identifies the specific failure point
- Explains probable cause(s)
- Uses conditional language when uncertain
- Provides context that aids decision-making

**Template**:
```
[Specific component] failed [when/during what].
[Probable cause]: [evidence supporting this diagnosis].
[If multiple causes possible]: Could also be [alternative cause].
```

**Examples**:
```
Authentication to storage.example.com failed during file upload.
The API key appears to have expired—last successful authentication 
was 3 days ago. Could also be a service outage; the server didn't 
respond to 3 connection attempts.

---

PDF parsing failed on page 7 of invoice_003.pdf.
The page contains image data that couldn't be decoded—likely 
corruption in the original scan. Pages 1-6 parsed successfully.

---

Database write failed after processing 847 records.
Connection dropped mid-transaction. The database may have committed 
partial data (uncertain—see state assessment for verification steps).
```

### Level 3: Technical Trace

Full technical details for debugging or escalation.

**Characteristics**:
- Error codes, stack traces, system state
- Raw response data where relevant
- Timestamps and sequence of events
- Information needed for bug reports or support tickets

**Template**:
```
Error: [error class/code]
Message: [raw error message]
Location: [file:line or API endpoint]
Timestamp: [precise time]
Context: [relevant system state]
Trace: [stack trace or call sequence]
```

**Example**:
```
Error: ConnectionError
Message: HTTPSConnectionPool(host='storage.example.com', port=443): 
         Max retries exceeded with url: /api/v2/upload
Location: upload_client.py:147
Timestamp: 2024-01-15T14:32:17.847Z
Context: 
  - File size: 2.3MB
  - Retry count: 3
  - Last successful request: 2024-01-12T09:15:03Z
Trace:
  requests.exceptions.SSLError: 
    [SSL: CERTIFICATE_VERIFY_FAILED] certificate verify failed
```

## Presentation Patterns

### Default: L1+L2 Visible, L3 Expandable

```
Upload failed: your report didn't reach the server.

Authentication to storage.example.com failed after 3 attempts.
The API key may have expired (last success: 3 days ago) or the 
service may be down.

▶ Show technical details
```

### High-Stakes: All Levels Immediately Visible

```
⚠️ PAYMENT PROCESSING FAILED

Your payment of $147.50 was NOT charged to your card.

The payment processor rejected the request with error code 'card_declined'.
This typically means insufficient funds or the card issuer flagged the 
transaction. Your card has not been charged.

Technical details:
  Processor: Stripe
  Error code: card_declined
  Decline code: insufficient_funds
  Request ID: req_abc123xyz
  Timestamp: 2024-01-15T14:32:17Z
```

### Low-Stakes: L1 Only, L2 On Demand

```
File rename failed.

▶ Why did this fail?
```

## Failure Type Templates

### Network/Connection Failures

```
L1: [Service] is unreachable—your [action] couldn't complete.

L2: Connection to [host] failed after [N] attempts over [duration].
    [If timeout]: Server didn't respond within [N] seconds.
    [If refused]: Server actively rejected the connection.
    [If DNS]:     Could not resolve hostname—check network connection.
    
L3: [Full error with retry timestamps and response codes]
```

### Authentication Failures

```
L1: Access denied—couldn't authenticate with [service].

L2: [Service] rejected the credentials.
    [If expired]: Token/key expired on [date]. Re-authenticate to continue.
    [If invalid]: Credentials not recognized. May need to re-enter.
    [If permissions]: Authenticated but lacks permission for [action].

L3: [Auth endpoint, response code, token metadata if safe]
```

### Data/Parsing Failures

```
L1: Couldn't read [file/data]—format issue.

L2: [File] contains data that couldn't be processed.
    [If corrupt]: [Specific location] is damaged/unreadable.
    [If format]:  Expected [format A], found [format B].
    [If encoding]: Character encoding [X] not supported.
    Successfully processed: [what worked before failure]

L3: [Parser output, byte offsets, character codes]
```

### Resource Exhaustion

```
L1: [Action] stopped—system limit reached.

L2: [Resource] exhausted during [operation].
    [If memory]:  Processing required more memory than available.
    [If disk]:    Output would exceed available storage.
    [If quota]:   API rate limit reached; resets at [time].
    [If timeout]: Operation exceeded maximum allowed time.

L3: [Resource measurements, limits, usage graphs if available]
```

### External Service Errors

```
L1: [Service] returned an error—[action] couldn't complete.

L2: [Service] responded with error: "[error message from service]"
    [If known error]: This typically means [interpretation].
    [If transient]:   Often temporary—retry may succeed.
    [If permanent]:   Requires [action] to resolve.

L3: [Full API response, request ID, correlation IDs]
```

### Agent/Logic Errors

```
L1: I made an error processing your request.

L2: [Specific mistake description].
    [What went wrong]: [e.g., "I misinterpreted the date format"]
    [Impact]: [What this caused]
    [Correction]: [What I'm doing differently]

L3: [Internal state, decision trace if available]
```

## Attribution Clarity

Always be specific about fault location:

| Attribution | Opening Phrase |
|-------------|----------------|
| **External service** | "[Service] returned/reported/rejected..." |
| **Data quality** | "[Input] contains/is missing/has invalid..." |
| **Configuration** | "The configured [setting] is..." |
| **Environment** | "The system/network/resource..." |
| **Agent error** | "I incorrectly/mistakenly/failed to..." |
| **Unknown** | "The failure occurred during [X]; cause unclear..." |

## Forbidden Patterns

```
✗ "Something went wrong"           → Always specify what
✗ "An error occurred"              → Always specify which error
✗ "Please try again"               → Only if retry might help, with why
✗ "Unexpected error"               → Describe what was expected vs actual
✗ "Internal error"                 → Translate to user-meaningful terms
✗ "Error code 47"                  → Always accompany codes with meaning
```

## Uncertainty in Explanations

When cause is uncertain, say so explicitly:

```
✓ "Connection failed. This could be a network issue on your end, 
   or the service may be down—I can't determine which."

✓ "The file couldn't be read. It may be corrupted, or the format 
   may not be what I expected. I'd need to see the original to 
   diagnose further."

✓ "The operation failed partway through. I'm uncertain whether 
   the database write committed—see verification steps below."
```

## trust-calibration Integration

When explaining failures, coordinate with trust-calibration for:

**Uncertainty framing**: Use trust-calibration's uncertainty stack (what/why/how) when cause is unclear.

**Agent error acknowledgment**: If failure was agent's fault, apply trust-calibration's Level 5 recovery sequence:
1. Immediate acknowledgment → "I got this wrong."
2. Impact recognition → "This caused [specific harm]."
3. Causal explanation → "This happened because [specific failure mode]."
4. Correction statement → "I've [specific change] to prevent this."
5. Expectation reset → "For this type of task, I recommend [new protocol]."

**Confidence calibration**: Match linguistic certainty to actual certainty about failure cause:
- High certainty: "The file is corrupted at byte offset 4096."
- Medium certainty: "The API key appears to have expired."
- Low certainty: "The failure could be network-related or service-side; I can't determine which."

Cross-reference: `trust-calibration/references/uncertainty-patterns.md` and `trust-calibration/references/failure-recovery.md`
