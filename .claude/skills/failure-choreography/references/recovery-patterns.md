# Recovery Option Patterns

Implementation patterns for failure recovery options.

## Recovery Option Taxonomy

### Retry

Re-attempt the failed operation.

**When available**:
- Failure was potentially transient (network, timeout, rate limit)
- Operation is idempotent OR state is clean
- Retry budget not exhausted

**When unavailable**:
- Failure is deterministic (bad input, missing permissions)
- Operation has unknown side effects from first attempt
- Maximum retry attempts exceeded

**Implementation**:
```python
class RetryOption:
    def is_available(self, failure: FailureContext) -> bool:
        return (
            failure.is_transient_error() and
            failure.retry_count < failure.max_retries and
            (failure.operation.is_idempotent or failure.state_is_clean())
        )
    
    def describe(self, failure: FailureContext) -> str:
        return f"""
[Retry] Attempt again
        Target: {failure.operation.description}
        Attempts so far: {failure.retry_count}/{failure.max_retries}
        Good if: {self._suggest_when_appropriate(failure)}
        """
    
    def _suggest_when_appropriate(self, failure: FailureContext) -> str:
        if failure.error_type == "timeout":
            return "server was temporarily slow"
        if failure.error_type == "rate_limit":
            return f"waiting {failure.rate_limit_reset} for limit reset"
        if failure.error_type == "connection":
            return "network issue was temporary"
        return "the issue was temporary"
```

**Retry Intelligence**:
```python
class SmartRetry:
    """Intelligent retry with backoff and differentiation."""
    
    def __init__(self, max_attempts: int = 3, base_delay: float = 1.0):
        self.max_attempts = max_attempts
        self.base_delay = base_delay
    
    def should_retry(self, error: Exception, attempt: int) -> tuple[bool, float]:
        if attempt >= self.max_attempts:
            return False, 0
        
        # Differentiate error types
        if self._is_permanent_error(error):
            return False, 0
        
        if self._is_rate_limit(error):
            delay = self._extract_retry_after(error) or self._exponential_delay(attempt)
            return True, delay
        
        if self._is_transient_error(error):
            return True, self._exponential_delay(attempt)
        
        # Unknown errors: retry once with caution
        return attempt < 1, self.base_delay
    
    def _exponential_delay(self, attempt: int) -> float:
        return self.base_delay * (2 ** attempt) + random.uniform(0, 1)
```

### Rollback

Undo completed steps and restore starting state.

**When available**:
- All completed operations are reversible
- No irreversible external side effects occurred
- Rollback instructions exist for each step

**When unavailable**:
- Any step caused irreversible change (sent email, charged card, deleted data)
- External system state cannot be reverted
- Partial rollback would leave inconsistent state

**Implementation**:
```python
class RollbackOption:
    def is_available(self, failure: FailureContext) -> bool:
        return all(
            step.is_reversible for step in failure.completed_steps
        )
    
    def describe(self, failure: FailureContext) -> str:
        reversible = [s.name for s in failure.completed_steps if s.is_reversible]
        return f"""
[Rollback] Undo and restore starting state
           Will reverse: {', '.join(reversible)}
           Will preserve: original source files (unchanged)
           After rollback: system returns to pre-task state
           """
    
    def execute(self, failure: FailureContext) -> RollbackResult:
        # Reverse in LIFO order
        for step in reversed(failure.completed_steps):
            step.reverse()
        return RollbackResult(success=True, restored_state=failure.initial_state)
```

### Resume

Skip the failed step and continue with remaining work.

**When available**:
- Downstream steps don't strictly depend on failed step's output
- Partial completion is valuable
- User accepts gaps in final result

**When unavailable**:
- Failed step produces required input for all downstream steps
- Skipping would produce invalid/incomplete output
- Dependencies are not bypassable

**Implementation**:
```python
class ResumeOption:
    def is_available(self, failure: FailureContext) -> bool:
        failed_step = failure.failed_step
        remaining = failure.remaining_steps
        
        # Check if any remaining step hard-depends on failed step
        return not any(
            failed_step.id in step.hard_dependencies 
            for step in remaining
        )
    
    def describe(self, failure: FailureContext) -> str:
        skipped = failure.failed_step.name
        continuing = [s.name for s in failure.remaining_steps]
        impacts = self._assess_downstream_impact(failure)
        
        return f"""
[Resume] Skip failed step, continue with remaining
         Skips: {skipped}
         Continues with: {', '.join(continuing)}
         Impact: {impacts}
         """
    
    def _assess_downstream_impact(self, failure: FailureContext) -> str:
        soft_deps = [
            s.name for s in failure.remaining_steps
            if failure.failed_step.id in s.soft_dependencies
        ]
        if soft_deps:
            return f"{', '.join(soft_deps)} may have reduced functionality"
        return "No downstream impact expected"
```

### Manual Takeover

Transfer control to human with all available context.

**When available**: Always. This is the universal fallback.

**Implementation**:
```python
class ManualOption:
    def is_available(self, failure: FailureContext) -> bool:
        return True  # Always available
    
    def describe(self, failure: FailureContext) -> str:
        artifacts = failure.available_artifacts
        remaining_steps = failure.remaining_steps
        
        return f"""
[Manual] Download results, complete manually
         Available now: {self._format_artifacts(artifacts)}
         You'll need to: {self._describe_remaining_work(remaining_steps)}
         """
    
    def _format_artifacts(self, artifacts: list[Artifact]) -> str:
        return '\n         '.join(
            f"- {a.path} ({a.description})" for a in artifacts
        )
    
    def _describe_remaining_work(self, steps: list[Step]) -> str:
        return ' → '.join(s.manual_instruction for s in steps)
```

### Abandon

Stop work, preserve what's done, clean up gracefully.

**When available**: Always. This is the graceful exit.

**Implementation**:
```python
class AbandonOption:
    def is_available(self, failure: FailureContext) -> bool:
        return True  # Always available
    
    def describe(self, failure: FailureContext) -> str:
        saved_location = failure.checkpoint_path
        completed_work = failure.completed_steps
        
        return f"""
[Abandon] Stop task, preserve completed work
          Saved to: {saved_location}
          Contains: {len(completed_work)} completed steps
          Can resume later: {'Yes' if failure.is_resumable else 'No'}
          """
    
    def execute(self, failure: FailureContext) -> AbandonResult:
        # Ensure final checkpoint is written
        failure.write_final_checkpoint()
        # Clean up any temporary resources
        failure.cleanup_temp_resources()
        # Return summary
        return AbandonResult(
            preserved_path=failure.checkpoint_path,
            manifest=failure.generate_manifest()
        )
```

## Recovery Menu Rendering

```python
def render_recovery_menu(failure: FailureContext) -> str:
    options = [
        RetryOption(),
        RollbackOption(),
        ResumeOption(),
        ManualOption(),
        AbandonOption()
    ]
    
    available = [opt for opt in options if opt.is_available(failure)]
    
    menu = "What would you like to do?\n\n"
    for i, opt in enumerate(available, 1):
        menu += opt.describe(failure) + "\n\n"
    
    if failure.has_recommendation:
        menu += f"RECOMMENDATION: {failure.recommendation}\n"
    
    return menu
```

## Conditional Option Display

Show options conditionally based on failure type:

```python
OPTION_AVAILABILITY = {
    "network_error": [RetryOption, ManualOption, AbandonOption],
    "rate_limit": [RetryOption, ManualOption, AbandonOption],  # with delay
    "auth_error": [ManualOption, AbandonOption],  # no retry without reauth
    "data_error": [ResumeOption, ManualOption, AbandonOption],  # skip bad data
    "unknown": [RetryOption, ManualOption, AbandonOption],  # cautious retry
}

def get_available_options(failure: FailureContext) -> list[RecoveryOption]:
    base_options = OPTION_AVAILABILITY.get(
        failure.error_category, 
        [ManualOption, AbandonOption]
    )
    return [opt() for opt in base_options if opt().is_available(failure)]
```

## Option Guidance

Each option should include "good if" guidance:

```
[Retry]     Good if: temporary network issue, service briefly overloaded
[Rollback]  Good if: want clean slate, will retry with different approach
[Resume]    Good if: partial result is valuable, failed step non-critical
[Manual]    Good if: need fine control, agent approach isn't working
[Abandon]   Good if: task no longer needed, will address later
```

## Recovery Recommendations

When appropriate, recommend an option:

```python
def generate_recommendation(failure: FailureContext) -> Optional[str]:
    # Strong recommendation cases
    if failure.is_transient and failure.retry_count == 0:
        return "Retry recommended—this appears to be a temporary issue."
    
    if failure.failed_step.is_optional and failure.remaining_steps:
        return "Resume recommended—failed step isn't critical to final result."
    
    if failure.has_significant_completed_work and not failure.is_recoverable:
        return "Manual takeover recommended—significant work completed, can finish manually."
    
    # No strong recommendation
    return None
```
