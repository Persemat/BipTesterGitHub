"""
Full pytest suite for parsing/parser.py.

ChatbotParser is the orchestrator: it turns a raw Infobip chatbot export (JSON)
into a networkx.MultiDiGraph by dispatching each element to the mapper function
tested in test_parsing_functions.py, then wiring nodes together with edges
(resolving dialog-to-dialog jumps, enriching KEYWORD_COMPARE edges, applying
"Smart Pruning" to drop dead branches, and inlining sub-flow COMPONENTs).

Structure:
  - TestBuildKeyword / TestBuildIntent / TestBuildAttribute -> the three small
    lookup-table builders run at __init__ time.
  - TestIsUnfeasibleFallback  -> Smart Pruning (data-type-unfeasible FALLBACK).
  - TestProcessTransitions    -> the centralized edge-building method (pruning,
    prefix/GO_TO_DIALOG resolution, KEYWORD_COMPARE enrichment), unit-tested directly.
  - TestBuildEntryPointAndIntents -> USER_ENTRY -> first-dialog-element edges.
  - TestBuildNodesAndEdges    -> full element dispatch + auto-edges + COMPONENT handling.
  - TestInlineComponent       -> sub-flow inlining, including CLOSE_SESSION remapping
    (Smart Pruning Type 1 is exercised from TestBuildNodesAndEdges, since it's a
    side effect of _build_nodes_and_edges calling _inline_component).
  - TestProcessAllElementsIntegration -> a couple of small, whole-pipeline smoke tests.
"""

import networkx as nx
import pytest
from parsing.parser import ChatbotParser


# ---------------------------------------------------------------------------
# Small JSON builders to keep fixtures readable
# ---------------------------------------------------------------------------

def make_dialog(internal_id, elements, dialog_type="DEFAULT", intent_id=None, start_element_id=None, name=None):
    dialog = {"internalId": internal_id, "type": dialog_type, "elements": elements}
    if name is not None:
        dialog["name"] = name
    if intent_id is not None:
        dialog["intentId"] = intent_id
    if start_element_id is not None:
        dialog["startElementId"] = start_element_id
    return dialog


def send_message_element(elem_id, text="Hi", next_id=None):
    action = {"messages": [{"type": "TEXT", "message": text}]}
    if next_id:
        action["nextElementId"] = next_id
    return {"id": elem_id, "type": "SEND_MESSAGE", "action": action}


def close_session_element(elem_id):
    return {"id": elem_id, "type": "CLOSE_SESSION", "action": {}}


# ---------------------------------------------------------------------------
# _build_keyword / _build_intent / _build_attribute
# ---------------------------------------------------------------------------

class TestBuildKeyword:

    def test_keyword_with_name_and_synonyms(self):
        data = {"keywordRequests": [{"internalId": "K1", "name": "Yes", "synonyms": {"data": ["yeah", "yep"]}}]}
        parser = ChatbotParser(data, mock_data={})
        assert parser.keywords == {"K1": {"name": "Yes", "synonyms": ["yeah", "yep"]}}

    def test_keyword_without_name_gets_a_default(self):
        data = {"keywordRequests": [{"internalId": "K1"}]}
        parser = ChatbotParser(data, mock_data={})
        assert parser.keywords["K1"]["name"] == "Keyword_K1"
        assert parser.keywords["K1"]["synonyms"] == []

    def test_no_keyword_requests_gives_empty_dict(self):
        parser = ChatbotParser({}, mock_data={})
        assert parser.keywords == {}


class TestBuildIntent:

    def test_intent_with_name_and_phrases(self):
        data = {"intentRequests": [{"internalId": "I1", "name": "Greeting", "phrases": ["hi", "hello"]}]}
        parser = ChatbotParser(data, mock_data={})
        assert parser.intents == {"I1": {"name": "Greeting", "phrases": ["hi", "hello"]}}

    def test_intent_without_name_or_phrases_gets_defaults(self):
        data = {"intentRequests": [{"internalId": "I1"}]}
        parser = ChatbotParser(data, mock_data={})
        assert parser.intents["I1"] == {"name": "Unknown intent", "phrases": []}


class TestBuildAttribute:

    def test_attribute_fields_and_defaults(self):
        data = {"attributeRequests": [{"internalId": 42, "name": "Email", "dataType": "EMAIL", "sensitive": True}]}
        parser = ChatbotParser(data, mock_data={})
        assert parser.attributes["42"] == {
            "name": "Email", "type": "EMAIL", "scope": "LOCAL", "sensitive": True, "visible_to_agent": False,
        }

    def test_attribute_id_is_cast_to_a_string_key(self):
        data = {"attributeRequests": [{"internalId": 42}]}
        parser = ChatbotParser(data, mock_data={})
        assert "42" in parser.attributes
        assert 42 not in parser.attributes

    def test_can_build_attributes_from_an_external_json_source(self):
        # Used by _inline_component() to merge a sub-flow's own attributes in.
        parser = ChatbotParser({}, mock_data={})
        other_json = {"attributeRequests": [{"internalId": 7, "name": "CompAttr"}]}
        result = parser._build_attribute(other_json)
        assert result["7"]["name"] == "CompAttr"


# ---------------------------------------------------------------------------
# _is_unfeasible_fallback (Smart Pruning Type 2)
# ---------------------------------------------------------------------------

class TestIsUnfeasibleFallback:

    MOCKS = {"TEXT": {"valid": "Generic_Text", "invalid": None}, "EMAIL": {"valid": "a@b.com", "invalid": "not-an-email"}}

    def test_fallback_from_get_attribute_with_an_unconstrained_type_is_unfeasible(self):
        parser = ChatbotParser({}, mock_data=self.MOCKS)
        mapped_node = {"specific_type": "GET_ATTRIBUTE", "data_type": "TEXT"}
        edge_data = {"condition_type": "FALLBACK"}
        assert parser._is_unfeasible_fallback("N1", mapped_node, edge_data) is True

    def test_fallback_from_get_attribute_with_a_constrained_type_is_feasible(self):
        parser = ChatbotParser({}, mock_data=self.MOCKS)
        mapped_node = {"specific_type": "GET_ATTRIBUTE", "data_type": "EMAIL"}
        edge_data = {"condition_type": "FALLBACK"}
        assert parser._is_unfeasible_fallback("N1", mapped_node, edge_data) is False

    def test_fallback_from_a_non_get_attribute_node_is_never_pruned(self):
        parser = ChatbotParser({}, mock_data=self.MOCKS)
        mapped_node = {"specific_type": "SEND_MESSAGE"}
        edge_data = {"condition_type": "FALLBACK"}
        assert parser._is_unfeasible_fallback("N1", mapped_node, edge_data) is False

    def test_non_fallback_edges_are_never_pruned(self):
        parser = ChatbotParser({}, mock_data=self.MOCKS)
        mapped_node = {"specific_type": "GET_ATTRIBUTE", "data_type": "TEXT"}
        edge_data = {"condition_type": "DEFAULT"}
        assert parser._is_unfeasible_fallback("N1", mapped_node, edge_data) is False

    def test_unknown_data_type_falls_back_to_the_text_entry_in_the_registry(self):
        parser = ChatbotParser({}, mock_data=self.MOCKS)
        mapped_node = {"specific_type": "GET_ATTRIBUTE", "data_type": "SOME_UNKNOWN_TYPE"}
        edge_data = {"condition_type": "FALLBACK"}
        # TEXT's "invalid" is None, so an unknown type (falling back to TEXT) is also unfeasible.
        assert parser._is_unfeasible_fallback("N1", mapped_node, edge_data) is True

    def test_unknown_data_type_with_no_text_entry_in_registry_defaults_to_unconstrained(self):
        parser = ChatbotParser({}, mock_data={})  # registry has no "TEXT" key either
        mapped_node = {"specific_type": "GET_ATTRIBUTE", "data_type": "SOME_UNKNOWN_TYPE"}
        edge_data = {"condition_type": "FALLBACK"}
        # default_mock = {"valid": "Generic_Text", "invalid": None} -> still unfeasible.
        assert parser._is_unfeasible_fallback("N1", mapped_node, edge_data) is True

    def test_missing_data_type_defaults_to_text(self):
        parser = ChatbotParser({}, mock_data=self.MOCKS)
        mapped_node = {"specific_type": "GET_ATTRIBUTE"}  # no "data_type" key at all
        edge_data = {"condition_type": "FALLBACK"}
        assert parser._is_unfeasible_fallback("N1", mapped_node, edge_data) is True


# ---------------------------------------------------------------------------
# _process_transitions
# ---------------------------------------------------------------------------

class TestProcessTransitions:

    def make_parser(self, data=None, mock_data=None):
        parser = ChatbotParser(data or {}, mock_data=mock_data if mock_data is not None else {})
        parser.G = nx.MultiDiGraph()
        return parser

    def test_a_plain_transition_becomes_an_edge_with_its_edge_data(self):
        parser = self.make_parser()
        transitions = [{"target": "D1_N2", "edge_data": {"condition_type": "DEFAULT"}}]
        parser._process_transitions("D1_N1", {"specific_type": "SEND_MESSAGE"}, transitions)
        assert parser.G.has_edge("D1_N1", "D1_N2")
        edge_data = list(parser.G.get_edge_data("D1_N1", "D1_N2").values())[0]
        assert edge_data["condition_type"] == "DEFAULT"

    def test_unfeasible_fallback_is_pruned_and_no_edge_is_added(self):
        mocks = {"TEXT": {"valid": "x", "invalid": None}}
        parser = self.make_parser(mock_data=mocks)
        mapped_node = {"specific_type": "GET_ATTRIBUTE", "data_type": "TEXT"}
        transitions = [{"target": "D1_N2", "edge_data": {"condition_type": "FALLBACK"}}]
        parser._process_transitions("D1_N1", mapped_node, transitions)
        assert parser.G.number_of_edges() == 0

    def test_transition_without_a_target_is_skipped_silently(self):
        parser = self.make_parser()
        transitions = [{"edge_data": {"condition_type": "DEFAULT"}}]  # no "target" key
        parser._process_transitions("D1_N1", {}, transitions)
        assert parser.G.number_of_edges() == 0

    def test_keyword_compare_edge_is_enriched_with_name_and_synonyms(self):
        data = {"keywordRequests": [{"internalId": "K1", "name": "Yes", "synonyms": {"data": ["yeah"]}}]}
        parser = self.make_parser(data=data)
        transitions = [{"target": "D1_N2", "edge_data": {"condition_type": "KEYWORD_COMPARE", "keywordId": "K1"}}]
        parser._process_transitions("D1_N1", {}, transitions)
        edge_data = list(parser.G.get_edge_data("D1_N1", "D1_N2").values())[0]
        assert edge_data["keyword_name"] == "Yes"
        assert edge_data["synonyms"] == ["yeah"]

    def test_keyword_compare_with_an_unknown_keyword_id_is_left_unenriched(self):
        parser = self.make_parser()
        transitions = [{"target": "D1_N2", "edge_data": {"condition_type": "KEYWORD_COMPARE", "keywordId": "UNKNOWN"}}]
        parser._process_transitions("D1_N1", {}, transitions)
        edge_data = list(parser.G.get_edge_data("D1_N1", "D1_N2").values())[0]
        assert "keyword_name" not in edge_data

    def test_go_to_dialog_without_prefix_resolves_through_start_element_map(self):
        parser = self.make_parser()
        parser.start_element_map = {"D9": "N1"}
        transitions = [{"target": "D9_1", "edge_data": {"action": "GO_TO_DIALOG", "target_dialog_id": "D9"}}]
        parser._process_transitions("D1_N1", {}, transitions)
        assert parser.G.has_edge("D1_N1", "D9_N1")
        assert not parser.G.has_edge("D1_N1", "D9_1")

    def test_go_to_dialog_without_prefix_and_unknown_target_dialog_keeps_the_placeholder_target(self):
        parser = self.make_parser()
        parser.start_element_map = {}  # D9 is unknown
        transitions = [{"target": "D9_1", "edge_data": {"action": "GO_TO_DIALOG", "target_dialog_id": "D9"}}]
        parser._process_transitions("D1_N1", {}, transitions)
        assert parser.G.has_edge("D1_N1", "D9_1")

    def test_with_prefix_a_normal_transition_target_is_prefixed(self):
        parser = self.make_parser()
        transitions = [{"target": "D1_N2", "edge_data": {"condition_type": "DEFAULT"}}]
        parser._process_transitions("COMP_X_D1_N1", {}, transitions, prefix="COMP_X")
        assert parser.G.has_edge("COMP_X_D1_N1", "COMP_X_D1_N2")

    def test_with_prefix_go_to_dialog_resolves_through_the_component_start_map_first(self):
        parser = self.make_parser()
        parser.start_element_map = {"D9": "OUTSIDE_START"}  # should NOT be used: comp_start_map wins
        comp_start_map = {"D9": "COMP_X_D9_INSIDE_START"}
        transitions = [{"target": "D9_1", "edge_data": {"action": "GO_TO_DIALOG", "target_dialog_id": "D9"}}]
        parser._process_transitions("COMP_X_D1_N1", {}, transitions, prefix="COMP_X", comp_start_map=comp_start_map)
        assert parser.G.has_edge("COMP_X_D1_N1", "COMP_X_D9_INSIDE_START")

    def test_with_prefix_go_to_dialog_falls_back_to_the_outer_start_element_map(self):
        # Target dialog is outside the component (e.g. the sub-flow jumps back to the main flow).
        parser = self.make_parser()
        parser.start_element_map = {"D_MAIN": "N1"}
        transitions = [{"target": "D_MAIN_1", "edge_data": {"action": "GO_TO_DIALOG", "target_dialog_id": "D_MAIN"}}]
        parser._process_transitions("COMP_X_D1_N1", {}, transitions, prefix="COMP_X", comp_start_map={})
        assert parser.G.has_edge("COMP_X_D1_N1", "D_MAIN_N1")


# ---------------------------------------------------------------------------
# _build_entry_point_and_intents
# ---------------------------------------------------------------------------

class TestBuildEntryPointAndIntents:

    def test_user_entry_node_is_always_created(self):
        parser = ChatbotParser({}, mock_data={})
        parser.process_all_elements()
        assert parser.G.has_node("USER_ENTRY")
        assert parser.G.nodes["USER_ENTRY"]["macro_type"] == "USER_ENTRY"

    def test_default_dialog_gets_a_default_edge_from_user_entry(self):
        data = {"dialogRequests": [make_dialog("D1", [send_message_element("N1")], dialog_type="DEFAULT", start_element_id="N1")]}
        parser = ChatbotParser(data, mock_data={})
        parser.process_all_elements()
        assert parser.G.has_edge("USER_ENTRY", "D1_N1")
        edge_data = list(parser.G.get_edge_data("USER_ENTRY", "D1_N1").values())[0]
        assert edge_data["condition_type"] == "DEFAULT"

    def test_intent_dialog_with_phrases_gets_an_intent_edge(self):
        data = {
            "intentRequests": [{"internalId": "I1", "name": "Greeting", "phrases": ["hi"]}],
            "dialogRequests": [make_dialog("D1", [send_message_element("N1")], dialog_type="INTENT", intent_id="I1", start_element_id="N1")],
        }
        parser = ChatbotParser(data, mock_data={})
        parser.process_all_elements()
        assert parser.G.has_edge("USER_ENTRY", "D1_N1")
        edge_data = list(parser.G.get_edge_data("USER_ENTRY", "D1_N1").values())[0]
        assert edge_data["condition_type"] == "INTENT"
        assert edge_data["intent_name"] == "Greeting"

    def test_intent_dialog_whose_intent_has_no_phrases_gets_no_edge(self):
        data = {
            "intentRequests": [{"internalId": "I1", "name": "Greeting", "phrases": []}],
            "dialogRequests": [make_dialog("D1", [send_message_element("N1")], dialog_type="INTENT", intent_id="I1", start_element_id="N1")],
        }
        parser = ChatbotParser(data, mock_data={})
        parser.process_all_elements()
        assert not parser.G.has_edge("USER_ENTRY", "D1_N1")

    def test_dialog_without_a_start_element_is_skipped_entirely(self):
        data = {"dialogRequests": [make_dialog("D1", [send_message_element("N1")], dialog_type="DEFAULT")]}  # no start_element_id
        parser = ChatbotParser(data, mock_data={})
        # Should not raise, and should simply produce no USER_ENTRY edge for D1.
        parser.process_all_elements()
        assert parser.G.out_degree("USER_ENTRY") == 0


# ---------------------------------------------------------------------------
# _build_nodes_and_edges
# ---------------------------------------------------------------------------

class TestBuildNodesAndEdges:

    def test_send_message_node_is_created_with_an_auto_edge_to_next(self):
        data = {"dialogRequests": [make_dialog("D1", [
            send_message_element("N1", text="Hi", next_id="N2"),
            send_message_element("N2", text="Bye"),
        ])]}
        parser = ChatbotParser(data, mock_data={})
        parser.process_all_elements()
        assert parser.G.has_node("D1_N1")
        assert parser.G.nodes["D1_N1"]["macro_type"] == "SEND_MESSAGE"
        assert parser.G.has_edge("D1_N1", "D1_N2")
        edge_data = list(parser.G.get_edge_data("D1_N1", "D1_N2").values())[0]
        assert edge_data["condition"] == "[Auto]"

    def test_unhandled_element_type_falls_back_to_map_unknown(self):
        data = {"dialogRequests": [make_dialog("D1", [{"id": "N1", "type": "SOME_FUTURE_TYPE", "action": {}}])]}
        parser = ChatbotParser(data, mock_data={})
        parser.process_all_elements()
        assert parser.G.nodes["D1_N1"]["macro_type"] == "UNKNOWN"
        assert parser.G.nodes["D1_N1"]["specific_type"] == "SOME_FUTURE_TYPE"

    def test_get_attribute_node_resolves_its_data_type_from_the_attributes_table(self):
        data = {
            "attributeRequests": [{"internalId": 1, "name": "Email", "dataType": "EMAIL"}],
            "dialogRequests": [make_dialog("D1", [{
                "id": "N1", "type": "GET_ATTRIBUTE", "action": {"attributeId": 1, "questions": [{"text": "Your email?"}]},
            }])],
        }
        parser = ChatbotParser(data, mock_data={})
        parser.process_all_elements()
        assert parser.G.nodes["D1_N1"]["data_type"] == "EMAIL"

    def test_component_node_with_a_known_component_json_is_inlined_and_pruned(self):
        comp_json = {
            "botRequest": {"name": "SubFlow"},
            "dialogRequests": [make_dialog("CD1", [close_session_element("CN1")], dialog_type="DEFAULT", start_element_id="CN1")],
        }
        data = {"dialogRequests": [make_dialog("D1", [
            {"id": "N1", "type": "COMPONENT", "action": {"componentSender": "COMP1", "nextElementId": "N2"}},
            send_message_element("N2", text="After component"),
        ])]}
        parser = ChatbotParser(data, component_jsons={"COMP1": comp_json}, mock_data={})
        parser.process_all_elements()
        # Smart Pruning Type 1: the container-level [Auto] edge to N2 is NOT added directly from N1...
        assert not parser.G.has_edge("D1_N1", "D1_N2")
        # ...instead the sub-flow was entered...
        assert parser.G.has_edge("D1_N1", "COMP_SubFlow_CD1_CN1")
        entry_edge = list(parser.G.get_edge_data("D1_N1", "COMP_SubFlow_CD1_CN1").values())[0]
        assert entry_edge["condition"] == "[Enter Sub-Flow]"
        # ...and the component's CLOSE_SESSION was remapped to continue to the parent's next element.
        assert parser.G.has_edge("COMP_SubFlow_CD1_CN1", "D1_N2")
        return_edge = list(parser.G.get_edge_data("COMP_SubFlow_CD1_CN1", "D1_N2").values())[0]
        assert return_edge["condition"] == "[Auto]"
        assert parser.G.nodes["COMP_SubFlow_CD1_CN1"]["specific_type"] == "COMPONENT_RETURN"

    def test_component_node_with_an_unknown_component_json_falls_back_to_normal_auto_edge(self):
        # comp_id is not in components_jsons -> a [WARNING] is printed, but the COMPONENT
        # node's own next_element/transitions are NOT cleared, so it behaves like a plain node.
        data = {"dialogRequests": [make_dialog("D1", [
            {"id": "N1", "type": "COMPONENT", "action": {"componentSender": "MISSING_COMP", "nextElementId": "N2"}},
            send_message_element("N2"),
        ])]}
        parser = ChatbotParser(data, component_jsons={}, mock_data={})
        parser.process_all_elements()
        assert parser.G.has_edge("D1_N1", "D1_N2")


# ---------------------------------------------------------------------------
# _inline_component
# ---------------------------------------------------------------------------

class TestInlineComponent:

    def test_no_default_dialog_in_component_prints_error_and_adds_no_edge(self, capsys):
        comp_json = {"botRequest": {"name": "Broken"}, "dialogRequests": [make_dialog("CD1", [close_session_element("CN1")], dialog_type="INTENT", start_element_id="CN1")]}
        parser = ChatbotParser({}, mock_data={})
        parser.G = nx.MultiDiGraph()
        parser._inline_component(comp_json, "PARENT_NODE", "PARENT_NEXT")
        assert parser.G.number_of_edges() == 0
        assert "Error: No starting point found" in capsys.readouterr().out

    def test_component_attributes_are_merged_into_the_parser_attributes_table(self):
        comp_json = {
            "botRequest": {"name": "SubFlow"},
            "attributeRequests": [{"internalId": 99, "name": "CompOnlyAttr"}],
            "dialogRequests": [make_dialog("CD1", [close_session_element("CN1")], dialog_type="DEFAULT", start_element_id="CN1")],
        }
        parser = ChatbotParser({}, mock_data={})
        parser.G = nx.MultiDiGraph()
        parser._inline_component(comp_json, "PARENT_NODE", "PARENT_NEXT")
        assert "99" in parser.attributes
        assert parser.attributes["99"]["name"] == "CompOnlyAttr"

    def test_go_to_dialog_inside_a_component_pointing_to_another_internal_dialog(self):
        comp_json = {
            "botRequest": {"name": "SubFlow"},
            "dialogRequests": [
                make_dialog("CD1", [{"id": "CN1", "type": "GO_TO_DIALOG", "action": {"dialogId": "CD2"}}], dialog_type="DEFAULT", start_element_id="CN1"),
                make_dialog("CD2", [close_session_element("CN2")], dialog_type="OTHER", start_element_id="CN2"),
            ],
        }
        parser = ChatbotParser({}, mock_data={})
        parser.G = nx.MultiDiGraph()
        parser._inline_component(comp_json, "PARENT_NODE", "PARENT_NEXT")
        # CD2's start element, inside the SAME component, is resolved via comp_start_map.
        assert parser.G.has_edge("COMP_SubFlow_CD1_CN1", "COMP_SubFlow_CD2_CN2")


# ---------------------------------------------------------------------------
# process_all_elements -- small whole-pipeline smoke tests
# ---------------------------------------------------------------------------

class TestProcessAllElementsIntegration:

    def test_keyword_compare_is_enriched_end_to_end_through_process_user_input(self):
        data = {
            "keywordRequests": [{"internalId": "K1", "name": "Yes", "synonyms": {"data": ["yeah", "sure"]}}],
            "dialogRequests": [make_dialog("D1", [
                {"id": "N1", "type": "PROCESS_USER_INPUT", "action": {"rules": [
                    {"nextElementId": "N2", "condition": {"type": "KEYWORD_COMPARE", "keywordId": "K1"}},
                ]}},
                send_message_element("N2"),
            ])],
        }
        parser = ChatbotParser(data, mock_data={})
        parser.process_all_elements()
        edge_data = list(parser.G.get_edge_data("D1_N1", "D1_N2").values())[0]
        assert edge_data["keyword_name"] == "Yes"
        assert edge_data["synonyms"] == ["yeah", "sure"]

    def test_unconstrained_get_attribute_fallback_is_pruned_end_to_end(self):
        mocks = {"TEXT": {"valid": "Generic_Text", "invalid": None}}
        data = {"dialogRequests": [make_dialog("D1", [
            {
                "id": "N1", "type": "GET_ATTRIBUTE",
                "action": {
                    "attributeId": 1, "questions": [{"text": "Name?"}],
                    "fallback": {"fallbackAction": "REPEAT", "messages": [{"text": "Try again"}]},
                },
            },
        ])]}
        parser = ChatbotParser(data, mock_data=mocks)
        parser.process_all_elements()
        # The FALLBACK transition built by extract_common_input_logic() targets the
        # node itself (REPEAT has no goToDialogId), but since data_type TEXT accepts
        # anything, Smart Pruning Type 2 should drop it regardless of its target.
        assert parser.G.out_degree("D1_N1") == 0

    def test_go_to_dialog_across_dialogs_resolves_to_the_targets_real_start_element(self):
        data = {"dialogRequests": [
            make_dialog("D1", [{"id": "N1", "type": "GO_TO_DIALOG", "action": {"dialogId": "D2"}}], start_element_id="N1"),
            make_dialog("D2", [send_message_element("N5")], start_element_id="N5"),
        ]}
        parser = ChatbotParser(data, mock_data={})
        parser.process_all_elements()
        assert parser.G.has_edge("D1_N1", "D2_N5")
