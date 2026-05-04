# Hardware Component STPA Role Classification Reference

This reference maps common hardware component types to their typical STPA control structure roles. Use this as a starting point for Task I (component classification). The actual role depends on the system context — a component may serve a different role than its "typical" classification in specific circuits.

## STPA Component Classes

| Class | Definition | Role in control structure |
|---|---|---|
| controller | Makes decisions, issues commands based on internal logic or process model | Top of control hierarchy, sends control actions downward |
| actuator | Receives commands and acts on the physical process | Middle layer, translates control actions into physical effects |
| sensor | Measures physical quantities and reports to controllers | Provides feedback upward to controllers |
| controlled_process | The physical process or load being controlled | Bottom of hierarchy, the thing being acted upon |
| communication_channel | Carries signals between other components without making decisions | Connects layers, may translate or buffer signals |
| passive | Support component with no active role in control or feedback | Not modeled in STPA control structure |

---

## Microcontrollers and Processors

| Component type | Typical STPA role | Reasoning |
|---|---|---|
| MCU (microcontroller, e.g., STM32, ATmega, PIC) | **controller** | Contains control algorithms, makes decisions, sends commands to peripherals, reads sensor feedback. Central to most control structures. |
| MPU (microprocessor, e.g., ARM Cortex-A) | **controller** | Same as MCU but typically runs higher-level control logic, operating systems. |
| DSP (digital signal processor) | **controller** | Processes sensor data and generates control outputs. Common in motor control, audio, RF. |
| FPGA / CPLD | **controller** | Implements control logic in hardware. Role depends on what's programmed — usually controller, sometimes communication_channel if used as a bus bridge. |

## Power Components

| Component type | Typical STPA role | Reasoning |
|---|---|---|
| Voltage regulator (LDO, buck, boost, e.g., TPS62A01, LM1117) | **actuator** | Receives enable/control signal, acts on power domain by regulating voltage. The enable pin is the control action input. Some regulators have feedback pins (power-good, PGOOD) making them also a feedback source. |
| Power MOSFET (e.g., FDN537N, IRF540) | **actuator** | Receives gate signal (control action) from a controller, switches current to a load. Acts as an electronic switch in the power path. |
| Motor driver / H-bridge (e.g., DRV8833, L298N) | **actuator** | Receives direction and PWM commands, drives motor current. Translates digital control into physical motion. |
| Power supply module (DC-DC converter) | **actuator** | Converts and regulates power. When it has an enable pin or soft-start control, it's an actuator receiving commands. When it's always-on with no control input, it may be passive infrastructure. |
| Battery / power source | **controlled_process** | The energy source being managed. A battery management system (BMS) is the controller; the battery is the controlled process. |
| Fuse / circuit breaker | **passive** or **actuator** | Usually passive (fixed protection). A resettable electronic fuse with a trip/enable input is an actuator. |
| Power supervision IC (e.g., TPS3808, MAX6369) | **sensor** or **controller** | Monitors voltage levels and asserts reset/fault signals. If it only monitors and reports, it's a sensor. If it makes decisions (e.g., watchdog timer that resets the MCU), it has controller aspects — classify as controller. |

## Analog Sensing Components

| Component type | Typical STPA role | Reasoning |
|---|---|---|
| ADC (analog-to-digital converter) | **sensor** | Converts analog physical measurements to digital values readable by a controller. Primary feedback path component. |
| DAC (digital-to-analog converter) | **actuator** | Converts digital commands from a controller into analog signals that drive actuators or set reference voltages. |
| Operational amplifier (op-amp) | **sensor** or **passive** | When used in a measurement circuit (e.g., current sense amplifier, instrumentation amplifier), it's part of the sensor chain. When used as a simple buffer or filter, it's passive. |
| Temperature sensor (e.g., TMP36, LM35, NTC thermistor) | **sensor** | Measures temperature and provides analog or digital feedback to a controller. |
| Current sense resistor + amplifier (e.g., INA219) | **sensor** | Measures current flow and reports to controller. Critical feedback component in power management. |
| Voltage divider (resistive) | **sensor** | Scales a voltage for measurement by an ADC. Part of the feedback path, but often classified as passive since it has no active role. Context-dependent. |
| Accelerometer / gyroscope / IMU (e.g., MPU6050, BMI160) | **sensor** | Measures motion/orientation and reports to controller via I2C/SPI. |
| Photodetector / light sensor (e.g., TSL2561) | **sensor** | Measures light intensity and reports to controller. |
| Pressure sensor (e.g., BMP280) | **sensor** | Measures pressure/altitude and reports to controller. |
| GPS receiver (e.g., u-blox NEO) | **sensor** | Provides position/velocity/time feedback to the navigation controller. |

## Digital Logic and Interface Components

| Component type | Typical STPA role | Reasoning |
|---|---|---|
| Logic gate (AND, OR, NAND, e.g., SN74LVC1G08) | **communication_channel** or **passive** | Usually performs signal conditioning or simple combinational logic. If it gates an enable signal (e.g., AND gate that combines two enable conditions), it's part of the control action path — classify as communication_channel. If it's just a buffer, passive. |
| Level shifter / voltage translator (e.g., TXB0108) | **communication_channel** | Translates signals between voltage domains. Does not make decisions — purely passes signals through. |
| Bus transceiver (e.g., SN65HVD230 for CAN) | **communication_channel** | Converts logic-level signals to bus-level signals and vice versa. Part of the communication path, not a decision-maker. |
| Multiplexer / demultiplexer (e.g., CD74HC4051) | **communication_channel** or **actuator** | Selects which signal path is active. If controlled by an MCU's select lines, the select signal is a control action and the mux is an actuator (it routes signals based on commands). If it's part of a fixed routing scheme, it's a communication channel. |
| Optocoupler / isolator (e.g., PC817, Si8600) | **communication_channel** | Provides galvanic isolation while passing signals. Pure signal path component. |
| Latch / flip-flop (e.g., SN74LVC1G74) | **communication_channel** or **controller** | If it stores state that affects downstream behavior (e.g., a set-reset latch in a safety interlock), it has controller aspects. If it's just synchronizing a signal, it's a communication channel. |

## Communication Interface Components

| Component type | Typical STPA role | Reasoning |
|---|---|---|
| UART transceiver (e.g., MAX3232) | **communication_channel** | Converts UART logic levels to RS-232 levels. Pure signal path. |
| SPI flash / EEPROM (e.g., W25Q128, AT24C256) | **controlled_process** | Stores data on command from a controller. The controller writes/reads via SPI/I2C; the memory is the controlled process (its state is being managed). |
| Radio transceiver (e.g., nRF24L01, SX1276) | **communication_channel** | Transmits and receives data wirelessly. The radio module doesn't make control decisions — it passes data between controllers. |
| Ethernet PHY (e.g., KSZ8081) | **communication_channel** | Physical layer interface for Ethernet. Pure signal path. |
| USB controller / hub | **communication_channel** | Manages USB communication. May have some controller aspects (protocol handling) but primarily a communication path. |

## Passive and Support Components

| Component type | Typical STPA role | Reasoning |
|---|---|---|
| Resistor (pull-up, pull-down, current-limiting) | **passive** | Sets electrical conditions. Does not actively participate in control. Exception: a current-sense resistor in a feedback path is part of the sensor chain. |
| Capacitor (decoupling, filtering, bulk) | **passive** | Filters noise, stores charge. Does not participate in control. |
| Inductor (filter, choke) | **passive** | Filters current, stores energy. Does not participate in control. Exception: inductor in a DC-DC converter is part of the actuator's energy conversion mechanism but is not independently modeled. |
| Crystal / oscillator | **passive** | Provides clock reference. Not a control or feedback element. |
| Connector (header, socket, terminal) | **passive** | Physical interface point. Not modeled in STPA. |
| LED (indicator) | **actuator** or **passive** | If the LED state is a meaningful feedback path to a human operator (e.g., power LED, fault LED), it's an actuator that the controller drives to communicate status. If decorative or non-safety-relevant, passive. |
| Test point / mounting hole | **passive** | Not modeled. |

---

## Context-Dependent Classification Guidelines

1. **When a component has multiple roles:** Classify by its PRIMARY role in the specific control loop being analyzed. A voltage regulator is an actuator in the power control loop, but its PGOOD output makes it a sensor in the power monitoring loop. For STPA, capture both roles in the connection details — the component can appear in multiple control actions and feedback signals.

2. **When unsure between controller and actuator:** Ask: "Does this component make DECISIONS or just execute commands?" A MOSFET executes — it's an actuator. An MCU decides — it's a controller. A watchdog timer both monitors (sensor) and acts autonomously (controller) — classify as controller because it makes an independent decision to reset.

3. **When unsure between sensor and passive:** Ask: "Does the output of this component feed into a controller's process model?" If yes, it's part of the sensor/feedback path. A voltage divider whose output goes to an ADC input is functionally a sensor. A voltage divider that just sets a bias point is passive.

4. **When unsure about communication_channel vs actuator:** Ask: "Does this component change what signal is sent based on a control input, or does it just pass signals through?" A level shifter passes signals through — communication_channel. A multiplexer selects which signal based on a control input — has actuator characteristics.

5. **Default to the more active classification when in doubt.** It's better to analyze a component as a potential control point than to dismiss it as passive and miss a hazard scenario.
