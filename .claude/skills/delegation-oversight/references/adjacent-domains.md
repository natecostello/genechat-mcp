# Adjacent Domain Lessons

Delegation and oversight patterns from fields that have solved similar problems.

## Pair Programming

**Relevance**: Two agents collaborating on same artifact, dynamic role switching.

### Driver/Navigator Model
- **Driver**: Hands on keyboard, tactical focus
- **Navigator**: Strategic oversight, catches errors, thinks ahead

**Lesson**: Roles should be explicit and switchable. "I'm driving now" / "Can you take over?" is normal operation.

### Ping-Pong Pattern
- One person writes test, other implements
- Continuous handoff at small granularity

**Lesson**: Frequent, low-cost handoffs build shared context better than infrequent, heavy handoffs.

### Verbal Protocol
- Navigator speaks intention before driver acts
- Driver voices implementation as it happens

**Lesson**: Narration builds shared understanding. Agents should explain what they're about to do, not just do it.

## Aviation (Crew Resource Management)

**Relevance**: High-stakes decisions, automation handoffs, error management.

### Sterile Cockpit Rule
Below 10,000 feet (high-risk phases), only task-essential communication.

**Lesson**: During critical operations, reduce noise. Checkpoints should be selective, not continuous.

### Challenge-Response Protocol
- Pilot announces action: "Gear down"
- Copilot confirms: "Gear down, three green"

**Lesson**: Bidirectional confirmation prevents misunderstanding. Agent says what it will do, human confirms understanding.

### Automation Mode Confusion
Many accidents stem from pilots not knowing what the autopilot is doing or about to do.

**Lesson**: Agent state must be visible. User should always be able to answer "What is it doing? What will it do next?"

### Escalation Gradient
- PIC (Pilot in Command) has final authority
- But questioning is not just permitted—it's required

**Lesson**: Agents should escalate concerns even if user has given instructions. "You said X, but I notice Y—still proceed?"

## Surgery (Surgical Checklists)

**Relevance**: Multi-step procedures, handoffs, error prevention.

### The Checklist Manifesto
Before critical actions, explicit verification with entire team.

**Lesson**: High-stakes checkpoints benefit from structured protocol, not ad hoc confirmation.

### Time Out
Complete stop before incision. Everyone confirms patient, procedure, site.

**Lesson**: Some checkpoints should be blocking. Can't proceed until confirmed.

### Handoff at Shift Change
- Outgoing team briefs incoming team
- Incoming team asks clarifying questions
- Both confirm shared understanding

**Lesson**: Handoff is bidirectional. Receiver must confirm understanding, not just receive.

## Military Command & Control

**Relevance**: Delegation under uncertainty, command authority, rules of engagement.

### Commander's Intent
"This is what I want to achieve" vs. specific orders.

**Lesson**: Delegate by goal, not by step. Agent should understand *why* so it can adapt when situation changes.

### Rules of Engagement
Explicit boundaries on autonomous action. "You may engage if X, must escalate if Y."

**Lesson**: Autonomy boundaries should be explicit and situation-aware, not global.

### OODA Loop (Observe, Orient, Decide, Act)
Decision cycle that can operate faster inside adversary's cycle.

**Lesson**: Latency matters. Checkpoints that add too much delay may defeat the purpose of delegation.

### Mission Command
Subordinates empowered to act within intent when communication breaks down.

**Lesson**: Design for graceful degradation. What should agent do if it can't reach user?

## Healthcare Shift Handoffs

**Relevance**: Context transfer, patient continuity, information loss prevention.

### SBAR Protocol
Situation, Background, Assessment, Recommendation.

**Lesson**: Structured handoff reduces information loss. Don't rely on unstructured "let me tell you what happened."

### Bedside Handoff
Handoff occurs in presence of patient (when possible).

**Lesson**: Handoffs can include the artifact itself. "Here's the document, let me walk you through what's done and what's pending."

### Read-Back
Receiver restates key information, sender confirms.

**Lesson**: Verbal confirmation is not enough. Receiver must demonstrate understanding.

## Air Traffic Control

**Relevance**: Multiple agents, handoffs, spatial awareness.

### Sector Handoff
Controller explicitly transfers responsibility for aircraft.
- Both controllers must confirm
- There is no ambiguity about who is responsible

**Lesson**: Responsibility must be explicit. "You have control" / "I have control" with no gap.

### Position and Altitude Readback
Pilot reads back clearance, controller confirms.

**Lesson**: Critical information requires bidirectional confirmation.

### Conflict Detection
Automated systems flag potential conflicts, human decides.

**Lesson**: Automation surfaces risk; human has authority. Agent recommends, human approves.

## Summary: Cross-Domain Principles

| Principle | Sources | Application |
|-----------|---------|-------------|
| Explicit role transfer | Aviation, ATC | "I have control" / "You have control" |
| Bidirectional confirmation | Aviation, Healthcare | Agent states plan, human confirms understanding |
| Structured handoff | Healthcare, Military | SBAR or similar protocol |
| Goal-based delegation | Military | Commander's intent, not step-by-step |
| Selective checkpoints | Aviation | Sterile cockpit—checkpoint on critical phases |
| Receiver confirms understanding | Surgery, Healthcare | Read-back, question asking |
| Automation state visibility | Aviation | User always knows what agent is doing |
| Graceful degradation | Military | Design for when communication fails |
