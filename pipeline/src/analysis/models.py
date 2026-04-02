from enum import Enum
from typing import Optional
from pydantic import BaseModel, Field

class ComponentClass(str, Enum):
    controller = 'controller'
    actuator = 'actuator'
    sensor = 'sensor'
    controlled_process = 'controlled_process'
    communication_channel = 'communication_channel'
    passive = 'passive'

class SignalClassification(str, Enum):
    control_action = 'control_action'
    feedback_signal = 'feedback_signal'
    power = 'power'
    ground = 'ground'
    reference = 'reference'
    not_modeled = 'not_modeled'

class ActionType(str, Enum):
    enable = 'enable'
    disable = 'disable'
    set_mode = 'set_mode'
    set_value = 'set_value'
    command = 'command'
    inhibit = 'inhibit'

class FeedbackType(str, Enum):
    measurement = 'measurement'
    status = 'status'
    acknowledgment = 'acknowledgment'
    limit_flag = 'limit_flag'

class ExcludedComponent(BaseModel):
    component_id: str
    reason: str

class PlanningOutput(BaseModel):
    modeled_components: list[str]
    excluded_components: list[ExcludedComponent]
    connection_pairs_to_analyze: list[str]
    abstraction_notes: str

class TaskIOutput(BaseModel):
    component_class: ComponentClass
    functional_description: str
    safety_critical: bool

class SignalInfo(BaseModel):
    signal_name: str
    description: str
    driven_by: str
    received_by: str

class TaskIIOutput(BaseModel):
    physical_interface: str
    signals: list[SignalInfo]

class ClassifiedSignal(BaseModel):
    signal_name: str
    classification: SignalClassification
    reasoning: str

class TaskIIIOutput(BaseModel):
    classifications: list[ClassifiedSignal]

class ControlAction(BaseModel):
    from_component: str = Field(alias='from', serialization_alias='from')
    to_component: str = Field(alias='to', serialization_alias='to')
    signal_name: str
    action_type: ActionType
    purpose: str
    timing_constraint: str
    source: list[str] = Field(default_factory=list)
    model_config = {'populate_by_name': True}

class TaskIVOutput(BaseModel):
    control_actions: list[ControlAction]

class FeedbackSignal(BaseModel):
    from_component: str = Field(alias='from', serialization_alias='from')
    to_component: str = Field(alias='to', serialization_alias='to')
    signal_name: str
    feedback_type: FeedbackType
    informs: str
    update_rate: str
    source: list[str] = Field(default_factory=list)
    model_config = {'populate_by_name': True}

class TaskVOutput(BaseModel):
    feedback_signals: list[FeedbackSignal]