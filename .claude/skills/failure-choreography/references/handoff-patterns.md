# Handoff Patterns

Domain-specific templates for transferring control to humans with dignity.

## Handoff Structure

Every handoff contains these components in order:

1. **Header**: Task identifier and status
2. **Situation**: 1-3 sentence summary
3. **Progress**: What completed, what failed, what's pending
4. **State**: Preserved / Lost / Uncertain assessment
5. **Options**: Available recovery paths
6. **Recommendation**: Agent's suggested path (when appropriate)
7. **Continuation**: What happens if user proceeds
8. **Artifacts**: Where everything is

## Domain Templates

### Data Processing Handoff

```
HANDOFF: Data Pipeline - customer_sync_20240115
════════════════════════════════════════════════════════════

SITUATION
Attempted to sync 10,000 customer records from CRM to warehouse.
Completed extraction and transformation; failed during load phase
after 7,847 records due to database connection timeout.

PROGRESS
✓ Extract    10,000 records from Salesforce API
✓ Transform  Cleaned, deduplicated (9,847 valid records)  
✗ Load       7,847 of 9,847 loaded before connection timeout
⏸ Verify     Not attempted

STATE
Preserved:
  - Extracted data: staging/extract_20240115.parquet (10,000 records)
  - Transformed data: staging/clean_20240115.parquet (9,847 records)
  - Load progress: 7,847 records committed to warehouse

Lost:
  - None (failure at clean transaction boundary)

Uncertain:
  - Last batch status (records 7,800-7,847 may or may not be committed)
  
  VERIFICATION: Run this query to check:
  SELECT MAX(sync_batch_id) FROM customers WHERE sync_date = '2024-01-15'
  If returns 'batch_7847': all committed. If 'batch_7800': last batch failed.

YOUR OPTIONS
1. Resume    Load remaining 2,000 records from checkpoint
2. Retry     Re-attempt full load (idempotent—uses upsert)
3. Manual    Use staging files to load via database client
4. Abandon   Keep partial sync, address remaining records later

RECOMMENDATION
Option 1 (Resume)—7,847 records already loaded successfully. 
Resume will complete the remaining 2,000 in ~2 minutes.

IF YOU CONTINUE (Resume)
Remaining: Load 2,000 records → Verify counts → Mark complete
Estimated time: 2-3 minutes
Resume command: agent resume customer_sync_20240115 --from-checkpoint

ARTIFACTS
staging/extract_20240115.parquet    Raw CRM data (10,000 records)
staging/clean_20240115.parquet      Transformed data (9,847 records)
staging/checkpoint.json             Resume state (position 7847)
logs/sync_20240115.log             Full operation log
```

### Document Generation Handoff

```
HANDOFF: Report Generation - Q4_analysis_report
════════════════════════════════════════════════════════════

SITUATION
Generating quarterly analysis report (8 sections). Completed 5 sections;
failed on Market Analysis due to external data API timeout.

PROGRESS
✓ §1 Executive Summary         1,247 words    sections/01_executive.md
✓ §2 Financial Performance     2,891 words    sections/02_financial.md
✓ §3 Product Metrics           1,654 words    sections/03_product.md
✓ §4 Customer Analysis         2,103 words    sections/04_customer.md
✓ §5 Operations Review         1,432 words    sections/05_operations.md
✗ §6 Market Analysis           FAILED         [data API timeout]
⏸ §7 Competitive Landscape     Skipped        [depends on §6 data]
⏸ §8 Outlook & Recommendations Skipped        [depends on §6-7]

STATE
Preserved:
  - Sections 1-5 complete and formatted
  - Partial document: output/Q4_report_partial.docx (5 sections, 9,327 words)
  - Section source files in sections/ directory

Lost:
  - Market data fetch (API timed out, no cached response)

Uncertain:
  - None (clean failure point)

YOUR OPTIONS
1. Retry     Re-fetch market data, generate remaining sections
2. Skip      Finalize report with sections 1-5 only (note gaps)
3. Manual    Write sections 6-8 manually using the template structure
4. Abandon   Preserve partial work for later completion

RECOMMENDATION
Option 1 (Retry) if market data API is now responsive.
Option 3 (Manual) if you have the market data from another source.

IF YOU CONTINUE (Retry)
Remaining: Fetch market data → Generate §6-8 → Compile final document
Estimated time: 5-7 minutes
Retry command: agent retry Q4_analysis_report --from section_6

ARTIFACTS
output/Q4_report_partial.docx      Formatted report (§1-5)
sections/01_executive.md           Section 1 source
sections/02_financial.md           Section 2 source
sections/03_product.md             Section 3 source
sections/04_customer.md            Section 4 source
sections/05_operations.md          Section 5 source
templates/section_template.md      Template for manual sections
data/financial_data.json           Source data (§2)
data/product_metrics.json          Source data (§3)
```

### API Integration Handoff

```
HANDOFF: Multi-System Integration - order_fulfillment_sync
════════════════════════════════════════════════════════════

SITUATION
Syncing order #12847 across fulfillment systems. Successfully updated
inventory and shipping; payment capture failed due to card decline.

PROGRESS
✓ Inventory    Reserved 3 items in warehouse system
✓ Shipping     Created shipment label (tracking: 1Z999AA10123456784)
✗ Payment      Card declined (insufficient_funds)
⏸ Notification Email not sent (depends on payment success)
⏸ Complete     Order status not updated

STATE
Preserved:
  - Inventory reservation: 3 items held (reservation_id: INV-2024-98765)
  - Shipping label: Created and ready (tracking: 1Z999AA10123456784)
  
Lost:
  - None

Uncertain:
  - None (payment definitively declined, not ambiguous)

⚠️ IMPORTANT: Reservations expire in 24 hours
Current hold: 3× SKU-12345 in warehouse
Expiration: 2024-01-16T14:32:00Z
If not completed by then: Items return to available inventory

YOUR OPTIONS
1. Retry Payment    Attempt charge again (customer may have resolved)
2. Alternative Pay  Request different payment method from customer
3. Cancel Order     Release inventory, void shipping label
4. Hold for Manual  Keep reservations, handle payment manually

RECOMMENDATION
Option 2 (Alternative Pay)—card decline was 'insufficient_funds',
unlikely to resolve without customer action.

IF YOU CONTINUE (Alternative Pay)
Action needed: Contact customer for new payment method
Once received: agent resume order_fulfillment_sync --payment-method [new]
Deadline: Before reservation expiry (23h 47m remaining)

ARTIFACTS
logs/order_12847_sync.json         Full sync log with timestamps
receipts/shipping_label.pdf        UPS shipping label
receipts/inventory_hold.json       Reservation confirmation
```

### Batch Processing Handoff

```
HANDOFF: Batch Document Processing - invoice_batch_january
════════════════════════════════════════════════════════════

SITUATION
Processing 150 invoices for data extraction. Completed 127 successfully;
23 failed with various issues (corrupt files, unsupported formats).

PROGRESS
✓ Successful    127 invoices processed and extracted
✗ Failed         23 invoices with errors (see breakdown)
  └─ Corrupt PDF:     12 files
  └─ Password locked:  6 files  
  └─ Scan quality:     3 files
  └─ Unknown format:   2 files

STATE
Preserved:
  - 127 extracted datasets in output/extracted/
  - Original files unchanged in input/
  - Failure log with specific errors for each failed file

Lost:
  - Nothing (originals preserved)

YOUR OPTIONS
1. Finalize     Accept 127/150 (85%), export results
2. Remediate    Address failed files individually:
                - Corrupt: Obtain replacement files
                - Locked: Provide passwords
                - Quality: Manual data entry
                - Format: Convert to supported format
3. Manual       Process all 23 failed files manually
4. Escalate     Send failure report to source for file corrections

RECOMMENDATION
Option 1 (Finalize) for immediate results, then Option 2 for remediation.
85% success rate; remaining 23 can be addressed incrementally.

IF YOU CONTINUE (Finalize)
Will generate: Consolidated output with 127 records
Missing: 23 invoices flagged as unprocessed
Output format: output/january_invoices.csv + manifest

ARTIFACTS
output/extracted/                   127 individual extraction files
output/manifest.json               Processing summary and status
failed/                            23 failed files organized by error type
  └─ corrupt/                      12 corrupt PDFs
  └─ locked/                       6 password-protected files
  └─ quality/                      3 low-quality scans
  └─ format/                       2 unsupported formats
logs/batch_processing.log          Complete processing log
reports/failure_analysis.csv       Per-file failure reasons
```

## Handoff Principles

### Context Sufficiency Test

A handoff passes if the human can:
1. Understand what happened without asking follow-up questions
2. Find all relevant files without searching
3. Make an informed decision about next steps
4. Execute their chosen path without rediscovering context

### Artifact Clarity

Every artifact entry should specify:
- **Path**: Exact location
- **Contents**: What's in it (record count, format, completeness)
- **Status**: Ready to use, partial, requires processing

```
✓ output/data.csv          847 records, validated, ready for import
? staging/partial.csv      First 500 records only, needs remaining data  
⚠ temp/working.json        Intermediate state, not for direct use
```

### Decision Support

Options should be ordered by:
1. Most likely to succeed / most appropriate for situation
2. Lowest cost / effort
3. Preserves most completed work

Include "good if" guidance for non-obvious cases.

### Time Sensitivity

If any state is time-limited, surface prominently:

```
⚠️ TIME-SENSITIVE
Inventory hold expires: 2024-01-16T14:32:00Z (23h 47m)
API rate limit resets: 2024-01-15T15:00:00Z (28m)
Temporary credentials expire: 2024-01-15T16:00:00Z (1h 28m)
```

### Escalation Path

When agent cannot resolve, provide escalation information:

```
ESCALATION
If options above don't resolve the issue:
- Support ticket template: templates/support_request.md
- Relevant error codes: AUTH_EXPIRED, RATE_LIMIT_EXCEEDED
- Logs to attach: logs/sync_20240115.log
- Contact: platform-support@example.com
```
