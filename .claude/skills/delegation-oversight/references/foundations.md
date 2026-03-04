# Research Foundations

## Levels of Automation (Sheridan & Verplank, 1978; Parasuraman et al., 2000)

The canonical 10-level framework remains foundational:

1. Human does everything
2. Computer offers alternatives
3. Computer narrows selection
4. Computer suggests one alternative
5. Computer executes if human approves
6. Computer allows human limited time to veto
7. Computer executes, then informs human
8. Computer executes, informs human only if asked
9. Computer executes, informs human only if it decides to
10. Computer does everything autonomously

**Key insight**: Levels can vary by *task stage* within a single interaction. An agent might operate at Level 10 for information gathering, Level 5 for decision selection, and Level 7 for routine execution.

**Design implication**: Don't configure a global automation level—configure per task stage or per domain.

## Trust in Automation (Lee & See, 2004)

Trust has three bases:
- **Performance**: Does it work reliably?
- **Process**: Do I understand how it works?
- **Purpose**: Does it share my goals?

Trust should be:
- **Calibrated**: Match actual system capabilities
- **Domain-specific**: Trust in scheduling ≠ trust in financial decisions
- **Dynamic**: Adjust based on experience

**Design implication**: Build and display trust per capability, not globally. Track record should be granular.

## Alarm Fatigue Literature

**ICU monitoring studies** (Sendelbach & Funk, 2013; Drew et al., 2014):
- False positive rates: 72-99%
- Response degradation: Alarm response rates drop to 20-30% with high false positive rates
- Habituation is rapid: meaningful signal degrades within days of high-frequency false alarms

**Design implication**: Checkpoint precision matters more than frequency. A few high-precision interruptions build trust; many low-precision interruptions train users to ignore the system entirely.

## Situation Awareness and Handoffs (Endsley, 1995)

Three levels of situation awareness:
1. **Perception**: What elements are present?
2. **Comprehension**: What do they mean together?
3. **Projection**: What will happen next?

Handoff failures typically occur at Level 2: recipient receives raw data (perception) but lacks the mental model to comprehend its meaning.

**Design implication**: Handoff documents must serialize comprehension, not just perception. Include the "so what" interpretation, not just raw state.

## SBAR (Healthcare Handoff Protocol)

**S**ituation: What's happening right now (1-2 sentences)
**B**ackground: Relevant context and history
**A**ssessment: What I think is going on / why this matters
**R**ecommendation: What I think should happen next

Originally from nursing handoffs. Success factors:
- Standardized structure reduces cognitive load
- Both parties confirm shared understanding
- Assessment/Recommendation force sender to synthesize, not dump

**Adaptation for AI handoffs**: Add "Options" between Assessment and Recommendation—AI should surface choice space, not just its top recommendation.

## Return-of-Control Problems (Automation Complacency)

**Complacency research** (Parasuraman & Manzey, 2010):
- Humans become less vigilant when automation is reliable
- When automation fails, humans are slow to detect and respond
- "Automation surprises" occur when human must suddenly take over with degraded situation awareness

**The inverse problem for agentic systems**: We want humans to intervene *routinely*, not just on failure. System must support planned intervention without treating it as system failure.

**Design implication**: Re-delegation should be a first-class workflow, not error recovery.
