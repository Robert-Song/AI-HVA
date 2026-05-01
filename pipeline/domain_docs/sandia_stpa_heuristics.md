# Sandia STPA Heuristics — Signal Classification and Task Guidance

Source: Odom, P. Wesley, Sandia National Laboratories. STPA JSON Template, Recommended Segmentation section.

## Control Action vs Feedback Signal — Classification Heuristics

The key distinction in STPA is between control actions and feedback signals. A control action directly influences what the receiving component is doing. A feedback signal merely informs or updates the receiving component's internal process model about the state of the system or environment.

### Control Action Detection

Look for evidence that component A commands or controls component B.

**Datasheet language indicators:**
- "enable pin"
- "control signal"
- "command register"
- "mode select"
- "shutdown pin"
- "inhibit input"
- "output enable"

**Signal naming conventions (suffixes):**
- _EN (enable)
- _CTRL (control)
- _CMD (command)
- _SEL (select)
- _RST (reset)
- _SHDN (shutdown)
- _INH (inhibit)

**Design document language:**
- "activates"
- "enables"
- "disables"
- "sets"
- "configures"
- "commands"
- "inhibits"

**Direction pattern:** Typically FROM controller (MCU, FPGA, logic IC) TO actuator (switch, driver, regulator, MOSFET).

### Control Action Type Mapping

| action_type | Description | Examples |
|---|---|---|
| enable | Binary on/off control — turns something on | EN pin high activates a voltage regulator |
| disable | Binary on/off control — turns something off | SHDN pin low disables a power supply |
| set_mode | Multi-state selection (mode A/B/C) | Mode select pins choosing between standby/active/sleep |
| set_value | Continuous or scalar control (voltage, frequency, duty cycle) | DAC output setting a reference voltage, PWM duty cycle |
| command | Discrete instructions over a bus (I2C writes, SPI commands) | Writing to a configuration register via I2C |
| inhibit | Safety override that prevents action | Hardware interlock that prevents firing, watchdog timeout |

### Feedback Signal Detection

Look for evidence that component B informs or reports to component A.

**Datasheet language indicators:**
- "status output"
- "measurement pin"
- "flag"
- "alert"
- "sense"
- "monitor output"
- "fault indicator"
- "ready signal"
- "power good"

**Signal naming conventions (suffixes):**
- _SENSE (sense)
- _MON (monitor)
- _ALERT (alert)
- _STATUS (status)
- _FB (feedback)
- _PG (power good)
- _FAULT (fault)
- _FLAG (flag)
- _RDY (ready)

**Design document language:**
- "monitors"
- "measures"
- "reports"
- "detects"
- "indicates"
- "senses"
- "flags"

**Direction pattern:** Typically TO controller (MCU, FPGA) FROM sensor, actuator, or monitored process.

### Feedback Signal Type Mapping

| feedback_type | Description | Examples |
|---|---|---|
| measurement | Quantitative readings — a number representing a physical quantity | Voltage level from ADC, current sense resistor output, temperature reading |
| status | Qualitative state — discrete states like on/off, ready/busy | Power-good flag, ready signal, mode indicator |
| acknowledgment | Confirmation that a command was received or executed | I2C ACK bit, SPI response frame, busy-then-ready transition |
| limit_flag | Threshold crossing alert — something exceeded a boundary | Overvoltage flag, overtemperature alert, undervoltage lockout, fault pin |

## Ambiguous Signals — How to Decide

Some signals can be interpreted as either control or feedback depending on context. Guidelines:

1. **Power rails (VCC, GND, VBAT):** Neither control nor feedback in the STPA sense. Classify as "power" or "ground." Exception: a switched power rail controlled by an enable pin IS a control action (the enable pin is the control action, the power delivery is the controlled process).

2. **Clock signals (CLK, OSC):** Usually classify as "reference" — they provide timing but don't carry control or feedback information. Exception: a clock enable/disable IS a control action.

3. **Bidirectional data lines (SDA on I2C, MISO/MOSI on SPI):** These carry BOTH control and feedback. Decompose: the write operations (master to slave) are control actions, the read operations (slave to master) are feedback signals. Each direction is a separate signal for STPA purposes.

4. **Interrupt lines (INT, IRQ):** Usually feedback — the peripheral is informing the controller that something happened. But check: if the interrupt line can also be used to wake a sleeping controller, it has a control aspect too.

5. **Reset lines (RST, RESET):** Usually control actions — one component forces another to restart. But an external watchdog timer's reset output is also a safety interlock (inhibit type).

## Timing Constraint Heuristics

When determining timing constraints for control actions:

1. **Check switching characteristics in the datasheet**: turn-on delay, turn-off delay, propagation delay, rise/fall times give you the physical timing floor.
2. **Check protocol specs**: I2C clock rates (100kHz/400kHz/1MHz), SPI clock rates, UART baud rates define the communication timing.
3. **Check application requirements**: how fast must the system respond? A safety interlock may need microsecond response; a temperature monitoring loop may poll every second.
4. **Common timing patterns:**
   - "continuous_regulation" — analog control loop, always active
   - "polled_Xms" — digital polling at a fixed interval
   - "event_driven" — triggered by an interrupt or state change
   - "on_demand" — activated by user or system request
   - "periodic_XHz" — regular periodic signal (PWM, clock)
   - "must_complete_within_Xms" — hard real-time deadline

## Update Rate Heuristics for Feedback Signals

1. **Analog feedback (voltage divider, current sense):** "continuous_analog" — always available, limited by ADC sampling rate if digitized.
2. **Polled digital (I2C/SPI register read):** "polled_Xms" — depends on the controller's polling interval.
3. **Interrupt-driven digital (alert pin, fault flag):** "event_driven" — updates only when state changes.
4. **Periodic digital (encoder, tachometer):** "sampled_XkHz" — regular sampling at a known rate.
