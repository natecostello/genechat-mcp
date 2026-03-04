# Partial Success Surfacing Patterns

Format-specific patterns for making completed work visible after partial failure.

## Data Processing Tasks

### ETL/Pipeline Failures

```
Pipeline: source → extract → transform → validate → load
Failed at: load (step 5 of 5)

COMPLETED WORK
──────────────────────────────────────────────────
extract     847 records from source.csv      → staging/raw.parquet
transform   Applied 3 transformations        → staging/transformed.parquet
validate    812 passed, 35 flagged           → staging/valid.parquet
                                             → staging/flagged.csv

ARTIFACTS READY FOR MANUAL LOAD
staging/valid.parquet (812 records, schema-compliant)

VALIDATION REPORT
staging/flagged.csv contains 35 records with issues:
- 23: missing required field 'customer_id'
- 12: date format non-conformant
```

### Batch Processing Failures

Use completion matrix for batch operations:

```
Batch: 50 documents

STATUS BREAKDOWN
✓ Completed:  34 (68%)
✗ Failed:      3 (6%)
⏸ Skipped:   13 (26%)  [stopped after failure threshold]

COMPLETED (34 files)
output/processed/doc_001.json through doc_034.json

FAILED (3 files)
├── doc_035.pdf  →  Corrupt: unreadable page 7
├── doc_041.pdf  →  Password protected
└── doc_048.pdf  →  Unsupported encoding (JBIG2)

SKIPPED (13 files)
input/pending/doc_036-040.pdf, doc_042-047.pdf, doc_049-050.pdf
(Not attempted—batch halted at failure threshold)
```

## Document Generation Tasks

### Multi-section Document Failure

```
Document: Annual Report (8 sections)

COMPLETED SECTIONS
────────────────────────────────────────────────────
§1  Executive Summary     ✓  Complete    → sections/01_executive.md
§2  Financial Overview    ✓  Complete    → sections/02_financial.md
§3  Market Analysis       ✓  Complete    → sections/03_market.md
§4  Product Roadmap       ✗  FAILED      [API timeout fetching roadmap data]
§5  Team & Hiring         ⏸  Skipped     [depends on §4 resource data]
§6  Risk Assessment       ⏸  Skipped
§7  Appendix A           ⏸  Skipped
§8  Appendix B           ⏸  Skipped

PARTIAL DOCUMENT AVAILABLE
output/annual_report_partial.docx
Contains: Sections 1-3 fully formatted
Missing: Sections 4-8 (placeholders inserted)

REUSABLE CONTENT
sections/01_executive.md  (1,247 words, reviewed)
sections/02_financial.md  (2,103 words, charts embedded)
sections/03_market.md     (1,891 words, data current as of fetch time)
```

## API Integration Tasks

### Multi-endpoint Failures

```
Integration: Sync customer data across 4 systems

SYSTEM STATUS
──────────────────────────────────────────────────
CRM (Salesforce)      ✓  Synced 1,247 contacts
Billing (Stripe)      ✓  Synced 892 payment methods  
Support (Zendesk)     ✗  FAILED: Rate limit exceeded
Analytics (Mixpanel)  ⏸  Not attempted

COMPLETED SYNCS (preserved)
- Salesforce: All contact records updated
  Audit log: logs/salesforce_sync_20240115.json
- Stripe: Payment methods linked to contacts
  Audit log: logs/stripe_sync_20240115.json

FAILED SYNC (Zendesk)
- 847 of 1,247 tickets synced before rate limit
- Partial progress: logs/zendesk_partial.json
- Resume token: zendesk_cursor_8a7f3c2d

RECOMMENDED RECOVERY
Wait 15 minutes (rate limit reset), then resume Zendesk sync.
Mixpanel sync can proceed independently.
```

## File Transformation Tasks

### Media Processing Failures

```
Task: Convert 20 videos to web format

CONVERSION STATUS
──────────────────────────────────────────────────
✓ Completed:  12 videos
✗ Failed:      1 video
⏸ Queued:     7 videos

COMPLETED (ready for use)
output/web/
├── video_01_720p.mp4  (142 MB → 47 MB, -67%)
├── video_02_720p.mp4  (98 MB → 31 MB, -68%)
...
└── video_12_720p.mp4  (203 MB → 71 MB, -65%)

FAILED
video_13.mov
  Error: Codec 'prores_ks' not supported for web transcode
  Original preserved: input/video_13.mov
  Suggestion: Re-export source as H.264 or provide alternate

QUEUED (not started)
input/video_14.mov through input/video_20.mov
```

## Manifest File Specification

Every partial success should generate a machine-readable manifest:

```json
{
  "task_id": "batch-process-20240115-143022",
  "task_type": "document_processing",
  "started_at": "2024-01-15T14:30:22Z",
  "failed_at": "2024-01-15T14:45:17Z",
  "status": "partial_failure",
  
  "progress": {
    "total_items": 50,
    "completed": 34,
    "failed": 3,
    "skipped": 13
  },
  
  "completed_artifacts": [
    {
      "item_id": "doc_001",
      "input": "input/doc_001.pdf",
      "output": "output/doc_001.json",
      "status": "success"
    }
  ],
  
  "failed_items": [
    {
      "item_id": "doc_035",
      "input": "input/doc_035.pdf",
      "error_code": "PDF_CORRUPT",
      "error_message": "Unreadable page 7",
      "recoverable": false
    }
  ],
  
  "resume_state": {
    "next_item": "doc_036",
    "checkpoint_path": "state/checkpoint_34.json",
    "resume_command": "agent resume batch-process-20240115-143022"
  }
}
```

## Display Principles

1. **Concrete counts**: "34 of 50" not "most"
2. **File locations**: Exact paths, not descriptions
3. **Reusability signals**: Can this output be used as-is?
4. **Dependency clarity**: Why were items skipped?
5. **Resume path**: How to continue if desired
