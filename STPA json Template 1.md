Odom, P. Wesley | Sandia National Laboratories

# Overview

This document contains the updated json template for collecting structured information on the control theoretic connections between components in a cyber-physical system.

# Basic

```
{
  "system_metadata": {
    "system_name": "<string: Name of the system being analyzed>",
    "netlist_source": "<string: Path or identifier of the KiCAD schematic/netlist file>",
    "analysis_date": "<ISO date: When this analysis was performed>"
  },
  
  "connection_pairs": {
    "<unique_connection_id>": {
      "endpoints": [
        "<string: component_name_1>",
        "<string: component_name_2>"
      ],
      "net_count": "<integer: Number of distinct nets connecting these two components in the netlist>",
      "net_names": [
        "<string: Net name from schematic>",
        "<string: Additional net names if multiple nets connect these components>"
      ]
    }
  },
  
  "components": {
    "<component_name>": {
      "component_id": "<string: KiCAD reference designator (e.g., U1, R5, BT1) from schematic>",
      "component_class": "<enum: controller | actuator | sensor | controlled_process | communication_channel | passive. Classify based on STPA role in the control structure>",
      "functional_description": "<string: Brief description of what this component does in the system context. Should be 1-2 sentences explaining its purpose>",
      "safety_critical": "<boolean: true if failure of this component could lead to system hazards or mission loss, false otherwise>",
      "connected_to": [
        "<string: component_name that this component has a netlist connection to>",
        "<string: additional connected component names>"
      ]
    }
  },
  
  "connection_details": {
    "<unique_connection_id>": {
      "endpoints": [
        "<string: component_name_1 - must match one of the components in connection_pairs>",
        "<string: component_name_2 - must match the other component in connection_pairs>"
      ],
      
      "physical_interface": "<string: Description of the physical connection type. Examples: 'direct_connection', 'I2C_bus', 'SPI_interface', 'GPIO_pins', 'power_rail', 'analog_signal', 'differential_pair'>",
      
      "control_actions": [
        {
          "from": "<string: component_name of the controlling component that initiates this action>",
          "to": "<string: component_name of the controlled component that receives and acts on this command>",
          "signal_name": "<string: The specific net name(s) from the schematic that carry this control action. Use the actual net label from the netlist>",
          "action_type": "<enum: enable | disable | set_mode | set_value | command | inhibit. Choose the type that best describes what control authority this signal provides>",
          "purpose": "<string: Human-readable description of WHY this control action exists. What system behavior does it enable? 1-2 sentences>",
          "timing_constraint": "<string: Description of timing requirements for this control action. Examples: 'continuous_regulation', 'polled_XXXms', 'event_driven', 'on_demand', 'periodic_XXHz', 'must_complete_within_XXms'>"
        }
      ],
      
      "feedback_signals": [
        {
          "from": "<string: component_name of the component providing state/measurement information>",
          "to": "<string: component_name of the component receiving this feedback to update its process model>",
          "signal_name": "<string: The specific net name(s) from the schematic that carry this feedback signal. Use the actual net label from the netlist>",
          "feedback_type": "<enum: measurement | status | acknowledgment | limit_flag. Choose based on what kind of information this feedback provides>",
          "informs": "<string: What piece of process model knowledge does this feedback provide? Examples: 'battery_voltage_level', 'switch_position_confirmation', 'temperature_reading', 'communication_success_flag'>",
          "update_rate": "<string: How frequently is this feedback updated? Examples: 'continuous_analog', 'polled_XXms', 'event_driven', 'on_state_change', 'sampled_XXkHz'>"
        }
      ],
      
      "source": [
        "<string: Citation of where this connection information was extracted from. Examples: 'schematic_netlist', 'component_datasheet_pageX', 'design_document_sectionY', 'requirements_doc_REQ-123'>"
      ],
      
      "notes": "<string: Optional field for additional context, ambiguities, assumptions made during analysis, or analyst commentary that doesn't fit other structured fields>"
    }
  },
  
  "graph_analysis": {
    "component_centrality": {
      "<component_name>": {
        "degree": "<float: Number of connections to this component normalized by total possible connections. Range 0-1>",
        "betweenness": "<float: How often this component lies on shortest paths between other components. Range 0-1. High values indicate critical bottleneck components>",
        "is_hub": "<boolean: true if this component has above-threshold connectivity (e.g., >5 connections), indicating it's a central coordination point>"
      }
    },
    
    "connection_criticality": {
      "<unique_connection_id>": {
        "control_signal_count": "<integer: Number of distinct control actions on this connection>",
        "feedback_signal_count": "<integer: Number of distinct feedback signals on this connection>",
        "is_bridge": "<boolean: true if removing this connection would disconnect the component graph, indicating critical path>",
        "connects_safety_critical": "<boolean: true if both endpoints are marked safety_critical=true>",
        "analysis_priority": "<enum: high | medium | low. Determined by combination of signal density, bridge status, and safety criticality>"
      }
    }
  }
}
```

# Instructional

**Note:** This version of the json template has additional comment-style instructions that break the json syntax. I have found this to usually not be an issue when using target excerpts as instructional context for the LLM, especially when using pydantic and guided json to force model output compliance.

**Note:** Each element is either tagged with DET or LLM to distinguish between the information that should be found via deterministic scripts or information that will require an LLM. 

```
{
  "system_metadata": {
    "system_name": "<string: Name of the system being analyzed>", (DET)
    "netlist_source": "<string: Path or identifier of the KiCAD schematic/netlist file>", (DET)
    "analysis_date": "<ISO date: When this analysis was performed>" (DET)
  },
  
  "connection_pairs": { # this is the list of identified connection pairs at a given abstraction level
    "<unique_connection_id>": { # each pair has its own unique identifier
      "endpoints": [ (DET)
        "<string: component_name_1>", # not just component name, since there may be distinct duplicates of the same component, thus this should be a name+ID for cases when there are more than one of the same component serial at the target abstraction level
        "<string: component_name_2>"
      ],
      "net_count": "<integer: Number of distinct nets connecting these two components in the netlist>", (DET/LLM)
      "net_names": [ # Notional, if this can be reliably extracted/inferred
        "<string: Net name from schematic>", (DET)
        "<string: Additional net names if multiple nets connect these components>" (DET)
      ]
    }
  },
  
  "components": {
    "<component_name>": { (DET)
      "component_id": "<string: KiCAD reference designator (e.g., U1, R5, BT1) from schematic>", (DET)
      "component_class": "<enum: controller | actuator | sensor | controlled_process | communication_channel | passive. Classify based on STPA role in the control structure>", (LLM)
      "functional_description": "<string: Brief description of what this component does in the system context. Should be 1-2 sentences explaining its purpose>", (LLM)
      "safety_critical": "<boolean: true if failure of this component could lead to system hazards or mission loss, false otherwise>", (LLM)
      "connected_to": [
        "<string: component_name that this component has a netlist connection to>", (DET)
        "<string: additional connected component names>" (DET)
      ]
    }
  },
  
  "connection_details": {
    "<unique_connection_id>": { (DET)
      "endpoints": [ (DET)
        "<string: component_name_1 - must match one of the components in connection_pairs>",
        "<string: component_name_2 - must match the other component in connection_pairs>"
      ],
      
      "physical_interface": "<string: Description of the physical connection type. Examples: 'direct_connection', 'I2C_bus', 'SPI_interface', 'GPIO_pins', 'power_rail', 'analog_signal', 'differential_pair'>", (LLM)
      
      "control_actions": [ # Log each of these elements for each uniquely identified control action
        {
          "from": "<string: component_name of the controlling component that initiates this action>", (DET/LLM)
          "to": "<string: component_name of the controlled component that receives and acts on this command>", (DET/LLM)
          "signal_name": "<string: The specific net name(s) from the schematic that carry this control action. Use the actual net label from the netlist>", (DET/LLM)
          "action_type": "<enum: enable | disable | set_mode | set_value | command | inhibit. Choose the type that best describes what control authority this signal provides>", (LLM)
          "purpose": "<string: Human-readable description of WHY this control action exists. What system behavior does it enable? 1-2 sentences>", (LLM)
          "timing_constraint": "<string: Description of timing requirements for this control action. Examples: 'continuous_regulation', 'polled_XXXms', 'event_driven', 'on_demand', 'periodic_XHz', 'must_complete_within_XXms'>" (LLM)
        },
        {
        More control actions if/as found for a given pair
        }
      ],
      
      "feedback_signals": [ # Log each of these elements for each uniquely identified feedback signal
        {
          "from": "<string: component_name of the component providing state/measurement information>", (LLM)
          "to": "<string: component_name of the component receiving this feedback to update its process model>", (DET/LLM)
          "signal_name": "<string: The specific net name(s) from the schematic that carry this feedback signal. Use the actual net label from the netlist>", (LLM)
          "feedback_type": "<enum: measurement | status | acknowledgment | limit_flag. Choose based on what kind of information this feedback provides>", (LLM)
          "informs": "<string: What piece of process model knowledge does this feedback provide? Examples: 'battery_voltage_level', 'switch_position_confirmation', 'temperature_reading', 'communication_success_flag'>", (LLM)
          "update_rate": "<string: How frequently is this feedback updated? Examples: 'continuous_analog', 'polled_XXXms', 'event_driven', 'on_state_change', 'sampled_XkHz'>" (LLM)
        },
        {
        More feedback signals if/as found for a given pair
        }
      ],
      
      "source": [
        "<string: Citation of where this connection information was extracted from. Examples: 'schematic_netlist', 'component_datasheet_pageX', 'design_document_sectionY', 'requirements_doc_REQ-123'>" (DET) # shuold be mostly deterministic if the RAG pipeline retains source tracing and the LLM is instructed to specify which provided context document(s) it used in its answer
      ],
      
      "notes": "<string: Optional field for additional context, ambiguities, assumptions made during analysis, or analyst commentary that doesn't fit other structured fields>" (LLM)
    }
  },
  
  "graph_analysis": { # This is optional, but might be very useful as a way of identifying component abstraction groups when there is a high degree of interconnectivity. Everything in this graph analysis section should, in theory, be deterministic (DET)
    "component_centrality": { # notionally calculated based on density of interconnections within a component set (i.e., for a given set of components, the one with the highest number of connections to the most components in the set)
      "<component_name>": {
        "degree": "<float: Number of connections to this component normalized by total possible connections. Range 0-1>",
        "betweenness": "<float: How often this component lies on shortest paths between other components. Range 0-1. High values indicate critical bottleneck components>",
        "is_hub": "<boolean: true if this component has above-threshold connectivity (e.g., >5 connections), indicating it's a central coordination point>"
      }
    },
    
    "connection_criticality": { # What happens if this component has an error, or errors? (DET/LLM)
      "<unique_connection_id>": {
        "control_signal_count": "<integer: Number of distinct control actions on this connection>",
        "feedback_signal_count": "<integer: Number of distinct feedback signals on this connection>",
        "is_bridge": "<boolean: true if removing this connection would disconnect the component graph, indicating critical path>",
        "connects_safety_critical": "<boolean: true if both endpoints are marked safety_critical=true>",
        "analysis_priority": "<enum: high | medium | low. Determined by combination of signal density, bridge status, and safety criticality>" (LLM)
      }
    }
  }
}
```

# Recommended Segmentation
These are some recommended segmentation strategies based on model intelligence levels
## Smaller models
- OpenAI's gpt-oss-20b
- Meta's Llama 3 70B
- Nvidia's Nemotron 3 Nano 30B

For these less intelligent models I would simple have it answer one item at a time from the json template. The part that might make a material difference is the order in which you serve these up to the model, since you can include previous determinations as context for future determinations when it makes sense. Although this will require more LLM calls, these small models are usually so fast that they can churn through a lot of calls very quickly, especially since the number of tokens that have to generate is also less. 

**Note:** In reference to ordering and context bolstering, an example of where you would want to use a previous field (or previous fields) as context for a new field would be `safety_critical` , which would likely benefit from having the component class and functional descriptions as context.

**Note:** See Tasks III and IV for medium models for special processing information that also applies to smaller models.
## Medium Models
- OpenAI's gpt-oss-120b

**Note:** I haven't tested any of the other models that are around 100B parameters, but I assume some of the Chinese models would fall into this category

**Task I:** `component_class` , `functional_description`, `safety_critical`

**Task II:** `physical_interface`

**Task III:** Interim step to determine what the signals between two components are, or can be. Use LLM, documentation, and schematics to help answer this as completely as possible. It might be only one signal or it could be many.

**Task IV:** FOR EACH of the identified signals in Task III, determine whether the signal is control or feedback. 

Key distinction is that a `control action` directly influences what the other component is doing whereas the `feedback signal` merely informs/updates that internal process model of the other component (i.e., what the other component understands about the state of the system or environment). For example, an electric signal that directly causes another component to turn on is a `control action`, whereas, a `feedback signal` might be notification of environment temperature (in this case, the receiving component merely accounts for the signal and may, or may not, change its behavior in response). Here is some high level guidance that you can use with the LLM to help it decipher the difference:

> **Control Action Detection**
> Look for evidence that component A **commands or controls** component B:
> - Datasheet language: "enable pin", "control signal", "command register", "mode select"
> - Signal naming conventions: *_EN, _CTRL, _CMD, _SEL suffixes*
> - Design doc language: "activates", "enables", "disables", "sets", "configures"
> - Direction: Typically from controller (MCU, FPGA) TO actuator (switch, driver)
> 
> 	**action_type mapping:**
> 	- "enable/disable" → binary on/off control
> 	- "set_mode" → multi-state selection (e.g., mode A/B/C)
> 	- "set_value" → continuous/scalar control (e.g., voltage, frequency)
> 	- "command" → discrete instructions over a bus (e.g., I2C writes)
> 	- "inhibit" → safety override, preventing action
>
> **Feedback Signal Detection**
> Look for evidence that component B **informs or reports to** component A:
> - Datasheet language: "status output", "measurement pin", "flag", "alert", "sense"
> - Signal naming conventions: *_SENSE, _MON, _ALERT, _STATUS, _FB suffixes*
> - Design doc language: "monitors", "measures", "reports", "detects", "indicates"
> - Direction: Typically TO controller (MCU, FPGA) FROM sensor/actuator
> 
> 	**feedback_type mapping:**
> 	- "measurement" → quantitative readings (voltage, current, temperature)
> 	- "status" → qualitative state (on/off, mode A/B, ready/busy)
> 	- "acknowledgment" → confirmation of command receipt/execution
> 	- "limit_flag" → threshold crossing alerts (overvoltage, undertemp)

**Task V:** FOR EACH identified `control action` in Task IV:
	**Task Va:** `from`, `to`, `signal_name`
	**Task Vb:** `action_type`, `purpose`
	**Task Vc:** `timing_constraints`

**Task VI:** FOR EACH identified `feedback signal` in Task IV:
	**Task Va:** `from`, `to`, `signal_name`
	**Task Vb:** `feedback_type`, `informs`
	**Task Vc:** `update_rate`

**Task VII:** `notes` 
	- It might be worth collecting these along the way during the preceding tasks and then either compiling them directly or using a clean-up LLM call to make it coherent.
## Frontier
Most frontier models included in this segmentation
- OpenAI ChatGPT 5.2
- Anthropic Sonnet 4.5
- Google Gemini 3 (fast or thinking/Pro)
- Moonshot Kimi K2.5 (great cost for the intelligence)

**Task I:**  `component_class` , `functional_description`, `safety_critical`, `physical_interface`

**Task II:** Interim step to determine what the signals between two components are, or can be. Use LLM, documentation, and schematics to help answer this as completely as possible. It might be only one signal or it could be many.

**Task III:** FOR EACH of the identified signals in Task III, determine whether the signal is control or feedback. (Refer to medium size model instruction for more details on this part)

**Task IV:** FOR EACH identified `control action` in Task III:
	- `from`
	- `to`
	- `signal_name`
	- `action_type`
	- `purpose`
	- `timing_constraints`

**Task V:** FOR EACH identified `feedback signal` in Task III:
	- `from`
	- `to`
	- `signal_name`
	- `feedback_type`
	- `informs`
	- `update_rate`

**Note:** All components under Tasks IV and V can usually be handled in a single LLM call

**Task VI:** `notes` 
	- It might be worth collecting these along the way during the preceding tasks and then either compiling them directly or using a clean-up LLM call to make it coherent.