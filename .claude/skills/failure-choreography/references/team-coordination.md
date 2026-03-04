# Team Coordination Reference

Explicit handoff protocols between failure-choreography and sibling skills.

## Receiving from delegation-oversight

When delegation-oversight triggers a mid-task handoff to failure-choreography:

```yaml
handoff_from_delegation:
  trigger_type: uncertainty | stakes | conflict | user_intervention
  
  task_context:
    goal: "What user was trying to accomplish"
    progress: "Steps completed before handoff"
    current_step: "Where we are in the workflow"
  
  user_config:
    autonomy_level: "User's configured oversight preference"
    domain_trust: "Trust level in this specific domain"
  
  handoff_reason:
    type: "Why delegation-oversight triggered handoff"
    details: "Specific uncertainty, stakes threshold, or conflict"
```

**failure-choreography responsibility**: Generate handoff package appropriate to trigger type. If trigger was `uncertainty`, emphasize verification paths. If `stakes`, emphasize consequence clarity. If `conflict`, surface both agent reasoning and user's apparent intent.

## Receiving from approval-confirmation

When approval-confirmation hands off after timeout/rejection:

```yaml
handoff_from_approval:
  approval_context:
    original_trigger: "Why approval was requested"
    stakes_level: routine | notable | significant | critical
    proposed_action: "What the agent wanted to do"
  
  outcome:
    type: timeout | explicit_rejection | partial_approval
    time_elapsed: "How long user had"
    deadline: "What the deadline was"
  
  user_engagement:
    viewed: true | false
    edited: true | false
    partial_action: "Any modifications made before timeout"
  
  preserved_state:
    ready_artifacts: "What was prepared for approval"
    user_modifications: "Any changes user made"
```

**failure-choreography responsibility**: 
- For `timeout`: Preserve all state, frame as paused not failed, offer resume path
- For `explicit_rejection`: Acknowledge rejection, preserve artifacts, offer alternatives
- For `partial_approval`: Execute approved portion, surface what wasn't approved

## Handing off to trust-calibration

When failure involves agent error or requires trust repair:

```yaml
request_to_trust_calibration:
  failure_type: agent_error | unexpected_outcome | repeated_failure
  
  impact:
    user_harm: "What went wrong for the user"
    severity: minor | moderate | significant
  
  agent_state:
    cause_known: true | false
    correctable: true | false
    recurrence_risk: low | medium | high
  
  request:
    acknowledgment_level: "How much to apologize"
    expectation_reset: "What should change going forward"
```

**trust-calibration returns**: Calibrated failure acknowledgment language, confidence markers for future similar tasks, trust gradient adjustment recommendation.

## Handing off to ux-writing

After structuring failure response, request copy polish:

```yaml
request_to_ux_writing:
  context:
    failure_type: timeout | rejection | execution_error | partial_completion
    stakes_level: routine | notable | significant | critical
    user_emotional_state: frustrated | confused | cautious | neutral
    
  copy_needed:
    situation_summary:
      raw: "What happened (structured)"
      tone: "empathetic | matter-of-fact | serious"
      max_length: "1-3 sentences"
      
    state_descriptions:
      preserved: ["items to describe clearly"]
      lost: ["items to describe with recreation cost"]
      uncertain: ["items with verification steps"]
      
    option_labels:
      - name: "Retry"
        raw_description: "What retry does"
        tone: "confident | cautious"
      - name: "Manual"
        raw_description: "What manual takeover involves"
        tone: "helpful"
        
    error_explanation:
      L1_raw: "Technical summary"
      L2_raw: "Actionable detail"
      target_reading_level: "7th-8th grade"
      
  attribution:
    fault: agent | external | data | user | unknown
    tone_adjustment: "apologetic if agent fault"
```

**ux-writing returns**:
- Polished situation summaries at appropriate reading level
- Clear, non-blame state descriptions
- Action-oriented option labels and descriptions
- Tone-calibrated error explanations

## Integration Checkpoints

Before finalizing any failure response, verify:

1. **trust-calibration**: Are uncertainty markers calibrated? Is acknowledgment proportional to fault?
2. **ux-writing**: Is copy clear, non-blaming, at appropriate reading level?
3. **Back-reference**: Does response include enough context for user to understand without re-reading approval request?
