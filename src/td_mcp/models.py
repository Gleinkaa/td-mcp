"""Data models for TouchDesigner operators, networks, and presets."""

from __future__ import annotations

from enum import Enum
from typing import Literal
from pydantic import BaseModel, Field


class OpFamily(str, Enum):
    """TouchDesigner operator families."""
    CHOP = "CHOP"
    TOP = "TOP"
    SOP = "SOP"
    DAT = "DAT"
    COMP = "COMP"
    MAT = "MAT"


class Parameter(BaseModel):
    """A single operator parameter."""
    name: str
    value: str | float | int | bool
    default: str | float | int | bool | None = None
    mode: str = "constant"  # constant, expression, export, bind


class Connection(BaseModel):
    """A wire between two operators."""
    source_op: str
    source_index: int = 0
    target_op: str
    target_index: int = 0


class Operator(BaseModel):
    """A TouchDesigner operator."""
    path: str
    name: str
    family: OpFamily
    op_type: str  # e.g. "audiofilein", "math", "noise"
    parameters: list[Parameter] = Field(default_factory=list)
    inputs: list[str] = Field(default_factory=list)
    outputs: list[str] = Field(default_factory=list)
    cook_time: float | None = None  # ms
    flags: dict[str, bool] = Field(default_factory=dict)  # display, render, bypass, etc.


class Network(BaseModel):
    """A network/container of operators."""
    path: str
    operators: list[Operator] = Field(default_factory=list)
    connections: list[Connection] = Field(default_factory=list)
    sub_networks: list[str] = Field(default_factory=list)


class PerformanceReport(BaseModel):
    """Performance analysis of a network."""
    total_ops: int
    total_cook_time_ms: float
    hotspots: list[Operator] = Field(default_factory=list)
    unused_ops: list[str] = Field(default_factory=list)
    disconnected_ops: list[str] = Field(default_factory=list)


class CHOPRecipe(BaseModel):
    """A reusable CHOP chain recipe."""
    name: str
    description: str
    category: str  # "audio_reactive", "lfo", "mapping", "filter"
    operators: list[dict] = Field(default_factory=list)  # op_type + params
    connections: list[tuple[int, int]] = Field(default_factory=list)  # index pairs


class DAWMapping(BaseModel):
    """A DAW-to-TD parameter mapping."""
    source_type: Literal["osc", "midi_cc", "midi_note"]
    source_channel: str  # OSC address or MIDI CC number
    target_op: str
    target_par: str
    range_min: float = 0.0
    range_max: float = 1.0
    curve: str = "linear"  # linear, exponential, logarithmic


class Preset(BaseModel):
    """A saved preset (snapshot of parameter states)."""
    name: str
    description: str = ""
    category: str = ""
    mappings: list[DAWMapping] = Field(default_factory=list)
    recipes: list[str] = Field(default_factory=list)  # recipe names
    parameters: dict[str, dict[str, str | float | int | bool]] = Field(default_factory=dict)
