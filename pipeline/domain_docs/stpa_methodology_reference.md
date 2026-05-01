# STPA Methodology Reference — Control Structures, Control Actions, and Feedback

Source: Leveson, N.G. and Thomas, J.P., "STPA Handbook", MIT Partnership for Systems Approaches to Safety and Security (PSASS), March 2018. Chapter 2: How to Do a Basic STPA Analysis.

## What is STPA

STPA (System-Theoretic Process Analysis) is a hazard analysis technique based on systems theory. Unlike traditional methods that focus on component failures, STPA assumes accidents can also be caused by unsafe interactions of system components, none of which may have failed. Safety is treated as a dynamic control problem rather than a failure prevention problem.

## Core Concepts

### Losses

A loss involves something of value to stakeholders: loss of human life or injury, property damage, environmental pollution, loss of mission, loss of reputation, loss of sensitive information, or any other unacceptable consequence.

### Hazards

A hazard is a system state or set of conditions that, together with worst-case environmental conditions, will lead to a loss. Hazards are system-level states, NOT component-level causes. "Brake failure" is a cause, not a hazard. "Aircraft cannot decelerate sufficiently" is a hazard.

### Safety Constraints

A system-level constraint specifies conditions or behaviors that must be satisfied to prevent hazards. Derived by inverting hazards: if hazard is "aircraft violate minimum separation," constraint is "aircraft must satisfy minimum separation."

## The Hierarchical Control Structure

A hierarchical control structure is a system model composed of feedback control loops. It captures functional relationships and interactions. It is a FUNCTIONAL model, not a physical model — connections show information flow (commands, feedback), not physical wiring.

### Five Types of Elements

1. **Controllers**: Entities that make decisions and issue commands. Can be human (operators, pilots) or automated (MCU, FPGA, software). Controllers have:
   - A control algorithm: the decision-making process that determines what control actions to provide
   - A process model: internal beliefs about the state of the controlled process, used to make decisions. For humans this is called the "mental model."

2. **Control Actions**: Downward arrows in the control structure. Commands issued by a controller to influence the behavior of the controlled process. Examples: arm/disarm, engage/disengage, set mode, configure, enable/disable.

3. **Feedback**: Upward arrows in the control structure. Information sent from a controlled process (or sensors) back to the controller to update the controller's process model. Examples: wheel speed, weight-on-wheels status, fault indicators, temperature readings.

4. **Controlled Processes**: The physical or logical process being controlled. Examples: the wheel braking system, the power supply, the motor.

5. **Actuators and Sensors**: Mechanisms by which controllers act on controlled processes (actuators) and observe them (sensors). Usually abstracted away initially, added during scenario analysis.

### Key Rules

- The vertical axis indicates control authority: higher = more authority.
- ALL downward arrows are control actions (commands).
- ALL upward arrows are feedback.
- Just because a control action exists does not mean it will always be followed. Just because feedback exists does not mean it will always be accurate.
- The control structure models what CAN be sent, not what WILL happen in practice.

## How to Derive Feedback from Responsibilities

For each controller responsibility, ask:
1. What does the controller need to KNOW to fulfill this responsibility? (process model)
2. What FEEDBACK is needed to keep that knowledge accurate?

Example from aircraft wheel braking:

| Controller responsibility | Process model needed | Feedback required |
|---|---|---|
| Pulse brakes in case of skid (anti-skid) | Aircraft is skidding | Wheel speeds, inertial reference |
| Auto-engage brakes on landing | Aircraft has landed | Weight on wheels, throttle lever angle |
| Disable BSCU on malfunction | BSCU is malfunctioning | BSCU fault indicators |

## How to Identify Unsafe Control Actions (UCAs)

For each control action, consider four types of unsafe behavior:

1. **Not providing the control action leads to a hazard**: The controller does not issue a command when it should (e.g., brakes not applied when aircraft lands).

2. **Providing the control action leads to a hazard**: The controller issues a command when it should not (e.g., thrust reverser deployed in flight).

3. **Providing the control action too early, too late, or out of sequence**: Timing is wrong (e.g., deceleration after V1 point during takeoff).

4. **Control action stopped too soon or applied too long**: Duration is wrong (e.g., anti-skid pulses stop while aircraft is still skidding).

## How to Build a Control Structure — Step by Step

1. Start with an abstract control structure showing major subsystems needed to enforce constraints.
2. Identify controllers: who/what controls each subsystem? (human, automated, or both)
3. Assign responsibilities: what must each controller do to enforce safety constraints?
4. Define control actions: what commands must each controller be able to send?
5. Derive feedback: for each responsibility, what does the controller need to know, and what feedback provides that knowledge?
6. Iterate: refine by "zooming in" to add detail within subsystems.

## Abstraction Principles

- Group similar entities (e.g., "flight crew" instead of listing individual pilots).
- Begin with broad actions (e.g., "climb maneuver") and refine later (e.g., pitch, thrust).
- Abstact away actuators and sensors initially — add them during scenario analysis.
- Communication paths can be abstracted (what matters is that a command CAN be sent, not the physical mechanism).
- Start abstract, refine iteratively. STPA is most efficient when started early before design decisions are made.

## Common Mistakes

- Confusing hazards with component-level causes (e.g., "brake failure" is a cause, not a hazard).
- Making the control structure a physical wiring diagram instead of a functional model.
- Using vague labels like "Commands" and "Feedback" instead of specific action/signal names.
- Assuming the control structure implies obedience — it models capability, not guaranteed behavior.
- Including too many hazards (aim for 7-10 system-level, refine into sub-hazards if needed).
- Using "unsafe" in hazard definitions (recursive — specify what MAKES it unsafe).
