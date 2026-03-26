"""Tests for Pydantic data models."""

import pytest
from pydantic import ValidationError

from td_mcp.models import (
    OpFamily, Parameter, Connection, Operator, Network,
    PerformanceReport, CHOPRecipe, DAWMapping, Preset,
)


class TestOpFamily:
    def test_valid_families(self):
        for f in ("CHOP", "TOP", "SOP", "DAT", "COMP", "MAT"):
            assert OpFamily(f).value == f

    def test_invalid_family(self):
        with pytest.raises(ValueError):
            OpFamily("INVALID")


class TestParameter:
    def test_string_value(self):
        p = Parameter(name="file", value="/path/to/file")
        assert p.value == "/path/to/file"

    def test_float_value(self):
        p = Parameter(name="roughness", value=0.5)
        assert p.value == 0.5

    def test_bool_value(self):
        p = Parameter(name="active", value=True)
        assert p.value is True

    def test_defaults(self):
        p = Parameter(name="x", value=0)
        assert p.default is None
        assert p.mode == "constant"


class TestConnection:
    def test_basic(self):
        c = Connection(source_op="/a", target_op="/b")
        assert c.source_index == 0
        assert c.target_index == 0

    def test_with_indices(self):
        c = Connection(source_op="/a", source_index=1, target_op="/b", target_index=2)
        assert c.source_index == 1
        assert c.target_index == 2


class TestOperator:
    def test_minimal(self):
        op = Operator(path="/project1/noise1", name="noise1", family=OpFamily.CHOP, op_type="noisechop")
        assert op.parameters == []
        assert op.inputs == []
        assert op.outputs == []
        assert op.cook_time is None
        assert op.flags == {}

    def test_full(self):
        op = Operator(
            path="/project1/noise1",
            name="noise1",
            family="CHOP",
            op_type="noisechop",
            parameters=[Parameter(name="roughness", value=0.5)],
            inputs=["/project1/lfo1"],
            outputs=["/project1/math1"],
            cook_time=1.23,
            flags={"bypass": False, "display": True},
        )
        assert len(op.parameters) == 1
        assert op.cook_time == 1.23


class TestNetwork:
    def test_empty(self):
        n = Network(path="/project1")
        assert n.operators == []
        assert n.connections == []
        assert n.sub_networks == []


class TestPerformanceReport:
    def test_basic(self):
        r = PerformanceReport(total_ops=10, total_cook_time_ms=5.5)
        assert r.total_ops == 10
        assert r.hotspots == []


class TestCHOPRecipe:
    def test_basic(self):
        r = CHOPRecipe(
            name="test",
            description="A test recipe",
            category="test_cat",
            operators=[{"type": "noisechop", "params": {}}],
            connections=[(0, 0)],
        )
        assert r.name == "test"
        assert len(r.operators) == 1


class TestDAWMapping:
    def test_valid_osc(self):
        m = DAWMapping(
            source_type="osc",
            source_channel="/track/1/volume",
            target_op="/project1/geo1",
            target_par="ty",
        )
        assert m.range_min == 0.0
        assert m.range_max == 1.0
        assert m.curve == "linear"

    def test_valid_midi_cc(self):
        m = DAWMapping(
            source_type="midi_cc",
            source_channel="1",
            target_op="/project1/geo1",
            target_par="ty",
        )
        assert m.source_type == "midi_cc"

    def test_valid_midi_note(self):
        m = DAWMapping(
            source_type="midi_note",
            source_channel="60",
            target_op="/project1/geo1",
            target_par="ty",
        )
        assert m.source_type == "midi_note"

    def test_invalid_source_type_rejected(self):
        with pytest.raises(ValidationError):
            DAWMapping(
                source_type="websocket",
                source_channel="ch1",
                target_op="/project1/geo1",
                target_par="ty",
            )

    def test_invalid_source_type_empty(self):
        with pytest.raises(ValidationError):
            DAWMapping(
                source_type="",
                source_channel="ch1",
                target_op="/project1/geo1",
                target_par="ty",
            )

    def test_custom_range(self):
        m = DAWMapping(
            source_type="osc",
            source_channel="/x",
            target_op="/a",
            target_par="p",
            range_min=-1.0,
            range_max=2.0,
        )
        assert m.range_min == -1.0
        assert m.range_max == 2.0


class TestPreset:
    def test_minimal(self):
        p = Preset(name="init")
        assert p.description == ""
        assert p.mappings == []
        assert p.recipes == []
        assert p.parameters == {}

    def test_full(self):
        p = Preset(
            name="live_set_1",
            description="Main live preset",
            category="live",
            recipes=["audio_reactive_basic"],
            parameters={"/project1/noise1": {"roughness": 0.5}},
        )
        assert p.category == "live"
        assert len(p.recipes) == 1
