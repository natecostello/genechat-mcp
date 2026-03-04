# State Preservation Patterns

Checkpoint strategies and state communication by task type.

## Checkpoint Architecture

### Core Principle: Persist Before Proceed

```
Wrong:  step1() → step2() → step3() → checkpoint()
Right:  step1() → checkpoint() → step2() → checkpoint() → step3() → checkpoint()
```

A failure during step N should never lose step N-1's results.

### Checkpoint Granularity

Match checkpoint frequency to recovery cost:

| Recovery Cost | Checkpoint Frequency | Example |
|---------------|---------------------|---------|
| **Low** (<1 min to redo) | End of task only | Simple file rename |
| **Medium** (1-10 min) | After each major step | Document section completion |
| **High** (>10 min or irreversible) | After each operation | Database migrations, API calls |
| **Critical** (data loss risk) | Before AND after | Financial transactions |

### Checkpoint Content

Each checkpoint must capture:

```python
@dataclass
class Checkpoint:
    task_id: str
    step_index: int
    step_name: str
    timestamp: datetime
    
    # What was accomplished
    completed_operations: list[str]
    artifacts_created: dict[str, Path]
    
    # How to resume
    next_step: str
    resume_context: dict  # Parameters needed for next step
    
    # What external state was modified
    external_mutations: list[ExternalMutation]
```

## State Categories

### Preserved State

State that survives failure and can be reused.

**Identification criteria**:
- Written to persistent storage before failure
- No dependencies on failed operation's output
- Format is self-contained (no dangling references)

**Communication pattern**:
```
PRESERVED
─────────────────────────────────────────────────
✓ Downloaded source files         input/raw/
✓ Extracted data (847 records)    staging/extract.csv
✓ Applied transformations         staging/transformed.csv
✓ Task configuration              config/task_params.json

These files are complete and ready for reuse.
```

### Lost State

State that was not persisted before failure.

**Identification criteria**:
- Only existed in memory
- Dependent on operation that failed mid-execution
- Written to temp storage that was cleaned up

**Communication pattern**:
```
LOST
─────────────────────────────────────────────────
✗ API response data               (connection dropped before response)
✗ Computed similarity scores      (in-memory only, not checkpointed)
✗ Temp working files             (cleaned up on process exit)

Must be recomputed on retry.
Estimated time to recreate: ~3 minutes
```

### Uncertain State

State where persistence is unknown—the dangerous category.

**Identification criteria**:
- External system was contacted but response not received
- Transaction was initiated but not confirmed
- Write operation started but completion unknown

**Communication pattern**:
```
UNCERTAIN
─────────────────────────────────────────────────
? Database transaction            Connection lost after COMMIT sent
                                  May have committed—check db directly
                                  Verify: SELECT * FROM orders WHERE id='abc123'

? Email notification              SMTP accepted message, no delivery confirm
                                  May have been sent—check recipient or logs

? Webhook registration            POST succeeded, response not parsed
                                  Check: https://api.example.com/webhooks
```

**Verification guidance**: Always include HOW to verify uncertain state.

## Task-Specific Patterns

### Data Pipeline Checkpoints

```python
class PipelineCheckpoint:
    """Checkpoint for ETL-style pipelines."""
    
    def after_extract(self, data_path: Path, record_count: int):
        return {
            "stage": "extract",
            "artifact": str(data_path),
            "records": record_count,
            "resume_from": "transform"
        }
    
    def after_transform(self, data_path: Path, transformations: list[str]):
        return {
            "stage": "transform", 
            "artifact": str(data_path),
            "applied": transformations,
            "resume_from": "validate"
        }
```

### Document Generation Checkpoints

```python
class DocumentCheckpoint:
    """Checkpoint for multi-section document generation."""
    
    def after_section(self, section_id: str, content_path: Path, 
                      word_count: int, dependencies_met: list[str]):
        return {
            "section": section_id,
            "content": str(content_path),
            "words": word_count,
            "dependencies": dependencies_met,
            "can_compile": self._check_compilable()
        }
```

### API Integration Checkpoints

```python
class IntegrationCheckpoint:
    """Checkpoint for multi-system API operations."""
    
    def after_api_call(self, system: str, operation: str,
                       response_summary: dict, side_effects: list[str]):
        return {
            "system": system,
            "operation": operation,
            "response": response_summary,
            "mutations": side_effects,  # What external state changed
            "idempotent": self._is_safe_to_retry(operation)
        }
```

## State Recovery Patterns

### Clean Recovery (all state known)

```
Recovery Analysis
─────────────────────────────────────────────────
Preserved: 4 artifacts (extract, transform, validate, config)
Lost: 0 (failure occurred at clean boundary)
Uncertain: 0

Recovery path: Resume from 'load' step with existing artifacts.
No verification needed.
```

### Partial Recovery (some state uncertain)

```
Recovery Analysis
─────────────────────────────────────────────────
Preserved: 3 artifacts
Lost: 1 (API enrichment data)
Uncertain: 1 (database write)

BEFORE RESUMING, VERIFY:
1. Check if database write committed:
   SELECT COUNT(*) FROM imports WHERE batch_id='xyz'
   Expected: 847 if committed, 0 if not

2. If committed: Resume from 'notify' step
   If not: Resume from 'load' step (will reprocess)
```

### Dirty Recovery (external state unknown)

```
Recovery Analysis
─────────────────────────────────────────────────
Preserved: Local artifacts intact
Lost: None
Uncertain: External system state

CRITICAL: Verify before ANY retry
─────────────────────────────────────────────────
Payment API state unknown. Possible scenarios:
1. Charge never processed (safe to retry)
2. Charge processed, response lost (DO NOT retry)
3. Charge partially processed (requires manual intervention)

VERIFICATION REQUIRED:
Check Stripe dashboard for charge matching:
  - Amount: $147.50
  - Customer: cust_abc123
  - Timestamp: ~14:32 UTC

If no matching charge: Safe to retry
If charge exists: Mark as complete, do not retry
If unclear: Contact support before proceeding
```

## Idempotency Markers

For operations that might be retried, track idempotency:

```python
class IdempotentOperation:
    """Track operations to prevent duplicate execution."""
    
    def __init__(self, operation_id: str):
        self.operation_id = operation_id
        self.idempotency_key = f"{operation_id}_{uuid4()}"
    
    def mark_started(self):
        """Call before operation. Stores intent."""
        self._persist_intent(self.idempotency_key, "started")
    
    def mark_completed(self, result_summary: dict):
        """Call after operation. Stores result."""
        self._persist_intent(self.idempotency_key, "completed", result_summary)
    
    def safe_to_retry(self) -> bool:
        """Check if retry would cause duplicate."""
        status = self._get_status(self.idempotency_key)
        return status != "completed"
```

## Communication Template

```
STATE ASSESSMENT
════════════════════════════════════════════════════════════

PRESERVED (ready for reuse)
────────────────────────────────────────────────────────────
[list artifacts with paths and descriptions]

LOST (must be recreated)
────────────────────────────────────────────────────────────
[list what was lost and recreation cost]

UNCERTAIN (verify before proceeding)
────────────────────────────────────────────────────────────
[list uncertain state with verification instructions]

RECOVERY RECOMMENDATION
────────────────────────────────────────────────────────────
[state recommended path based on above]
```
