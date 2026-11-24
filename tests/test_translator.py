"""
Full pytest suite for test_generation/botium_translator.py (BotiumTranslator).

Structure:
  - TestCollectConditions            -> collect_conditions() (logic tree flattening)
  - TestSolveConditions              -> solve_conditions() / extract_constraints_from_logic_tree()
  - TestPreScanPathConstraints       -> pre_scan_path_constraints()
  - TestGetMessage                   -> get_message() (bot-side text extraction)
  - TestGetUserInput                 -> get_user_input() (#me text generation)
  - TestProcessPathLogicIntegration  -> _process_path_logic() / translate_path(), end to end
  - TestFormatBotiumScript           -> _format_botium_script() syntax rules
  - TestGetUtterancesFiles           -> get_utterances_files()

Fake `path` steps follow exactly the shape PathFinder.generate_paths() produces:
{"source": ..., "target": ..., "edge_data": {...}, "target_data": {...}}, so these tests
plug directly into the real pipeline shape instead of an invented one.

Two bugs found by actually running this code (not by inspection) are documented as
xfail(strict=True) tests instead of being silently skipped or deleted -- see
TestGetUserInput.test_missing_data_type_in_mock_registry_does_not_crash and
TestProcessPathLogicIntegration.test_csat_feedback_loop_does_not_crash.
"""

import pytest
from test_generation.botium_translator import BotiumTranslator


def make_translator(mock_data=None, attributes=None, nodes_dict=None):
    return BotiumTranslator(nodes_dict or {}, mock_data=mock_data, attributes=attributes)


# ---------------------------------------------------------------------------
# collect_conditions
# ---------------------------------------------------------------------------

class TestCollectConditions:

    def test_empty_logic_tree_returns_empty_list(self):
        translator = make_translator()
        assert translator.collect_conditions({}) == []
        assert translator.collect_conditions(None) == []

    def test_attribute_compare_leaf_is_a_single_tuple(self):
        translator = make_translator()
        tree = {"type": "ATTRIBUTE_COMPARE", "attributeId": 42, "operator": "EQUAL", "value": "Ficus"}
        # Arrange / Act
        result = translator.collect_conditions(tree)
        # Assert: attribute id is stringified
        assert result == [("42", "EQUAL", "Ficus")]

    def test_and_block_collects_every_branch(self):
        translator = make_translator()
        tree = {
            "type": "LOGICAL",
            "operator": "AND",
            "conditions": [
                {"type": "ATTRIBUTE_COMPARE", "attributeId": 1, "operator": "GREATER_THAN", "value": "5"},
                {"type": "ATTRIBUTE_COMPARE", "attributeId": 1, "operator": "LESS_THAN", "value": "10"},
            ],
        }
        result = translator.collect_conditions(tree)
        assert result == [("1", "GREATER_THAN", "5"), ("1", "LESS_THAN", "10")]

    def test_or_block_keeps_only_the_first_branch(self):
        # Arrange: by design, OR only explores its first branch (documented limitation
        # in the source -- see the TODO right above this code path)
        translator = make_translator()
        tree = {
            "type": "LOGICAL",
            "operator": "OR",
            "conditions": [
                {"type": "ATTRIBUTE_COMPARE", "attributeId": 1, "operator": "EQUAL", "value": "A"},
                {"type": "ATTRIBUTE_COMPARE", "attributeId": 2, "operator": "EQUAL", "value": "B"},
            ],
        }
        result = translator.collect_conditions(tree)
        assert result == [("1", "EQUAL", "A")]

    def test_or_block_with_no_conditions_returns_empty_list(self):
        translator = make_translator()
        tree = {"type": "LOGICAL", "operator": "OR", "conditions": []}
        assert translator.collect_conditions(tree) == []

    def test_unknown_node_type_returns_empty_list(self):
        translator = make_translator()
        assert translator.collect_conditions({"type": "SOMETHING_ELSE"}) == []

    def test_nested_and_of_and_is_fully_flattened(self):
        # Arrange: AND containing another AND -- recursion must flatten both levels
        translator = make_translator()
        tree = {
            "type": "LOGICAL", "operator": "AND",
            "conditions": [
                {"type": "ATTRIBUTE_COMPARE", "attributeId": 1, "operator": "EQUAL", "value": "A"},
                {
                    "type": "LOGICAL", "operator": "AND",
                    "conditions": [
                        {"type": "ATTRIBUTE_COMPARE", "attributeId": 2, "operator": "EQUAL", "value": "B"},
                    ],
                },
            ],
        }
        result = translator.collect_conditions(tree)
        assert result == [("1", "EQUAL", "A"), ("2", "EQUAL", "B")]


# ---------------------------------------------------------------------------
# solve_conditions / extract_constraints_from_logic_tree
# ---------------------------------------------------------------------------

class TestSolveConditions:

    def test_single_condition_single_attribute(self):
        translator = make_translator(attributes={"1": {"type": "TEXT"}})
        constraints = translator.solve_conditions([("1", "EQUAL", "Ficus")])
        assert constraints == {"1": "Ficus"}

    def test_two_conditions_on_the_same_attribute_are_combined(self):
        # Arrange: x > 5 AND x < 10 on the same attribute, data_type NUMBER
        translator = make_translator(attributes={"1": {"type": "NUMBER"}})
        constraints = translator.solve_conditions([("1", "GREATER_THAN", "5"), ("1", "LESS_THAN", "10")])
        assert 5 < float(constraints["1"]) < 10

    def test_unknown_attribute_defaults_to_text_data_type(self):
        # Arrange: attribute "99" isn't declared in self.attributes at all
        translator = make_translator(attributes={})
        constraints = translator.solve_conditions([("99", "EQUAL", "hello")])
        assert constraints == {"99": "hello"}

    def test_mock_value_is_read_from_the_registry_valid_field(self):
        # Arrange: NOT_NULL_OPERATORS make solve_constraints fall back to mock_value,
        # so this is a clean way to check solve_conditions actually passes it through
        translator = make_translator(
            attributes={"1": {"type": "EMAIL"}},
            mock_data={"DATATYPE_MOCKS": {"EMAIL": {"valid": "mock@example.com", "invalid": None}}},
        )
        constraints = translator.solve_conditions([("1", "IS_NOT_NULL", None)])
        assert constraints == {"1": "mock@example.com"}

    def test_missing_registry_entry_does_not_crash(self):
        # Arrange: data_type "URL" has no entry in mock_registry at all -- solve_conditions
        # itself guards this with `.get(data_type, {})` (unlike get_user_input, see below)
        translator = make_translator(attributes={"1": {"type": "URL"}}, mock_data={"DATATYPE_MOCKS": {}})
        constraints = translator.solve_conditions([("1", "IS_NOT_NULL", None)])
        assert constraints == {"1": None}

    def test_extract_constraints_from_logic_tree_combines_collect_and_solve(self):
        translator = make_translator(attributes={"1": {"type": "TEXT"}})
        tree = {"type": "ATTRIBUTE_COMPARE", "attributeId": 1, "operator": "EQUAL", "value": "Rose"}
        assert translator.extract_constraints_from_logic_tree(tree) == {"1": "Rose"}


# ---------------------------------------------------------------------------
# get_message
# ---------------------------------------------------------------------------

class TestGetMessage:

    def test_send_message_text_single_message_no_placeholder(self):
        translator = make_translator()
        node = {"macro_type": "SEND_MESSAGE", "specific_type": "TEXT", "content": {"messages_list": ["Hello there!"]}}
        assert translator.get_message(node, "N1", {}, 0) == "Hello there!"

    def test_send_message_text_empty_messages_list_returns_none(self):
        translator = make_translator()
        node = {"macro_type": "SEND_MESSAGE", "specific_type": "TEXT", "content": {"messages_list": []}}
        assert translator.get_message(node, "N1", {}, 0) is None

    def test_send_message_text_placeholder_resolved_from_session_variables(self):
        translator = make_translator()
        node = {"macro_type": "SEND_MESSAGE", "specific_type": "TEXT", "content": {"messages_list": ["Thanks, {{name}}!"]}}
        assert translator.get_message(node, "N1", {"name": "Lorenzo"}, 0) == "Thanks, Lorenzo!"

    def test_send_message_text_unresolved_placeholder_becomes_wildcard(self):
        # Arrange: "session_id" is NOT in session_variables -- Botium can't match a
        # runtime-generated value, so it must become a loose wildcard instead
        translator = make_translator()
        node = {"macro_type": "SEND_MESSAGE", "specific_type": "TEXT", "content": {"messages_list": ["Session: {{session_id}}"]}}
        assert translator.get_message(node, "N1", {}, 0) == "Session: *"

    def test_session_value_containing_backslash_does_not_break_re_sub(self):
        # Regression test: a regex-generated mock value (or raw user data) containing
        # backslash sequences like "\d" must not be reinterpreted by re.sub as its own
        # escape/backreference syntax. This is exactly why the code uses a replacement
        # FUNCTION instead of a raw replacement string.
        translator = make_translator()
        node = {"macro_type": "SEND_MESSAGE", "specific_type": "TEXT", "content": {"messages_list": ["Code: {{code}}"]}}
        result = translator.get_message(node, "N1", {"code": r"\d\1\g<name>"}, 0)
        assert result == r"Code: \d\1\g<name>"

    def test_multiple_messages_with_placeholder_create_a_path_scoped_utterance(self):
        # Arrange: WITH a placeholder, the utterance name must include path_index so
        # different paths visiting the same node don't overwrite each other's utterance
        translator = make_translator()
        node = {
            "macro_type": "SEND_MESSAGE", "specific_type": "TEXT",
            "content": {"messages_list": ["Hi {{name}}!", "Hello {{name}}!"]},
        }
        result = translator.get_message(node, "N1", {"name": "Lorenzo"}, path_index=3)
        assert result == "UTT_NODE_N1_3"
        assert translator.global_utterances["UTT_NODE_N1_3"] == ["Hi Lorenzo!", "Hello Lorenzo!"]

    def test_multiple_messages_without_placeholder_create_a_shared_utterance(self):
        # Arrange: WITHOUT a placeholder, the same node always produces the same
        # variants regardless of path, so the utterance name is NOT path-scoped --
        # this is the fix for the utterance-overwriting bug, kept here as a
        # regression test from the translator's own perspective
        translator = make_translator()
        node = {"macro_type": "SEND_MESSAGE", "specific_type": "TEXT", "content": {"messages_list": ["Hi!", "Hello!"]}}
        result = translator.get_message(node, "N1", {}, path_index=3)
        assert result == "UTT_NODE_N1"

    def test_send_message_json_placeholder_and_wildcard(self):
        translator = make_translator()
        node = {
            "macro_type": "SEND_MESSAGE", "specific_type": "JSON",
            "content": {"payload": {"name": "{{name}}", "session": "{{session_id}}"}},
        }
        result = translator.get_message(node, "N1", {"name": "Lorenzo"}, 0)
        assert result == '{"name":"Lorenzo","session":"*"}'

    def test_receive_input_csat_returns_the_question(self):
        translator = make_translator()
        node = {"macro_type": "RECEIVE_INPUT", "specific_type": "CSAT", "content": {"question": "How did we do?"}}
        assert translator.get_message(node, "N1", {}, 0) == "How did we do?"

    def test_receive_input_get_attribute_single_question(self):
        translator = make_translator()
        node = {"macro_type": "RECEIVE_INPUT", "specific_type": "GET_ATTRIBUTE", "content": {"questions": ["What's your name?"]}}
        assert translator.get_message(node, "N1", {}, 0) == "What's your name?"

    def test_receive_input_get_attribute_multiple_questions_create_an_utterance(self):
        translator = make_translator()
        node = {
            "macro_type": "RECEIVE_INPUT", "specific_type": "GET_ATTRIBUTE",
            "content": {"questions": ["What's your name?", "May I have your name?"]},
        }
        result = translator.get_message(node, "N1", {}, path_index=2)
        assert result == "UTT_QUESTION_N1_2"
        assert translator.global_utterances["UTT_QUESTION_N1_2"] == ["What's your name?", "May I have your name?"]

    def test_receive_input_get_attribute_no_questions_returns_none(self):
        translator = make_translator()
        node = {"macro_type": "RECEIVE_INPUT", "specific_type": "GET_ATTRIBUTE", "content": {"questions": []}}
        assert translator.get_message(node, "N1", {}, 0) is None

    def test_action_node_returns_none(self):
        translator = make_translator()
        node = {"macro_type": "ACTION", "specific_type": "SET_ATTRIBUTE", "content": {}}
        assert translator.get_message(node, "N1", {}, 0) is None


# ---------------------------------------------------------------------------
# get_user_input
# ---------------------------------------------------------------------------

class TestGetUserInput:

    def test_no_edge_data_returns_none(self):
        translator = make_translator()
        assert translator.get_user_input(None, {"specific_type": "CSAT"}, {}) is None

    @pytest.mark.parametrize("c_type", ["AUTO", "[Auto]", "DEFAULT", "Enter Sub-Flow", "EVALUATION"])
    def test_csat_node_with_auto_like_edge_returns_default_score(self, c_type):
        translator = make_translator()
        edge = {"condition_type": c_type}
        source = {"specific_type": "CSAT"}
        assert translator.get_user_input(edge, source, {}) == "4"

    def test_get_attribute_uses_a_constraint_already_resolved_earlier_in_the_path(self):
        # Arrange: path_constraints already has a value for this attribute (e.g. from
        # a later EVALUATION edge pre-scanned by pre_scan_path_constraints) -- it must
        # take priority over regex/mock generation
        translator = make_translator()
        edge = {"condition_type": "AUTO"}
        source = {"specific_type": "GET_ATTRIBUTE", "attributes_defined": [130528], "data_type": "TEXT", "content": {}}
        result = translator.get_user_input(edge, source, path_constraints={"130528": "Ficus"})
        assert result == "Ficus"

    def test_get_attribute_uses_regex_when_no_constraint_is_known(self):
        translator = make_translator()
        edge = {"condition_type": "AUTO"}
        source = {
            "specific_type": "GET_ATTRIBUTE", "attributes_defined": [1], "data_type": "TEXT",
            "content": {"validation_regex": r"[A-Z]{3}"},
        }
        result = translator.get_user_input(edge, source, path_constraints={})
        assert isinstance(result, str) and result != ""

    def test_get_attribute_falls_back_to_generic_text_if_regex_generation_raises(self, monkeypatch):
        # Arrange: force rstr.xeger to fail, exactly as a malformed pattern would do
        import test_generation.botium_translator as module

        def boom(pattern):
            raise ValueError("boom")

        monkeypatch.setattr(module.rstr, "xeger", boom)
        translator = make_translator()
        edge = {"condition_type": "AUTO"}
        source = {
            "specific_type": "GET_ATTRIBUTE", "attributes_defined": [7], "data_type": "TEXT",
            "content": {"validation_regex": r"(unbalanced"},
        }
        result = translator.get_user_input(edge, source, path_constraints={})
        assert result == "Generic_Text_7"

    def test_get_attribute_uses_mock_registry_valid_value_when_data_type_is_known(self):
        translator = make_translator(mock_data={"DATATYPE_MOCKS": {"EMAIL": {"valid": "mock@example.com", "invalid": None}}})
        edge = {"condition_type": "AUTO"}
        source = {"specific_type": "GET_ATTRIBUTE", "attributes_defined": [1], "data_type": "EMAIL", "content": {}}
        result = translator.get_user_input(edge, source, path_constraints={})
        assert result == "mock@example.com"

    def test_get_attribute_falls_back_to_generic_text_if_mock_value_is_falsy(self):
        # Arrange: data_type is known but its "valid" mock is None (e.g. a type that
        # "accepts anything") -- `mock_value or f"Generic_Text_{attr_id}"` must kick in
        translator = make_translator(mock_data={"DATATYPE_MOCKS": {"JSON": {"valid": None, "invalid": None}}})
        edge = {"condition_type": "AUTO"}
        source = {"specific_type": "GET_ATTRIBUTE", "attributes_defined": [9], "data_type": "JSON", "content": {}}
        result = translator.get_user_input(edge, source, path_constraints={})
        assert result == "Generic_Text_9"

    @pytest.mark.xfail(
        reason="BUG: self.mock_registry.get(data_type).get('valid', {}) has no default "
               "for the outer .get() -- if data_type isn't a key in the registry at all, "
               ".get(data_type) returns None and .get('valid', {}) on None raises "
               "AttributeError, instead of falling back to a generic placeholder like "
               "the sibling call in solve_conditions() already does (.get(data_type, {})).",
        strict=True,
    )
    def test_missing_data_type_in_mock_registry_does_not_crash(self):
        translator = make_translator(mock_data={"DATATYPE_MOCKS": {}})  # "CUSTOM_TYPE" not registered
        edge = {"condition_type": "AUTO"}
        source = {"specific_type": "GET_ATTRIBUTE", "attributes_defined": [5], "data_type": "CUSTOM_TYPE", "content": {}}
        result = translator.get_user_input(edge, source, path_constraints={})
        assert result == "Generic_Text_5"

    def test_missing_data_type_in_mock_registry_currently_crashes(self):
        # Characterization test proving the bug above exists today -- delete this once
        # the xfail test starts passing.
        translator = make_translator(mock_data={"DATATYPE_MOCKS": {}})
        edge = {"condition_type": "AUTO"}
        source = {"specific_type": "GET_ATTRIBUTE", "attributes_defined": [5], "data_type": "CUSTOM_TYPE", "content": {}}
        with pytest.raises(AttributeError):
            translator.get_user_input(edge, source, path_constraints={})

    def test_keyword_compare_prefers_the_first_synonym(self):
        translator = make_translator()
        edge = {"condition_type": "KEYWORD_COMPARE", "synonyms": ["yes", "yep"], "keyword_name": "Yes", "keywordId": 1}
        assert translator.get_user_input(edge, None, {}) == "yes"

    def test_keyword_compare_falls_back_to_keyword_name(self):
        translator = make_translator()
        edge = {"condition_type": "KEYWORD_COMPARE", "synonyms": [], "keyword_name": "Yes", "keywordId": 1}
        assert translator.get_user_input(edge, None, {}) == "Yes"

    def test_keyword_compare_falls_back_to_a_placeholder(self):
        translator = make_translator()
        edge = {"condition_type": "KEYWORD_COMPARE", "synonyms": [], "keyword_name": None, "keywordId": 42}
        assert translator.get_user_input(edge, None, {}) == "Keyword_42"

    def test_intent_uses_the_first_phrase(self):
        translator = make_translator()
        edge = {"condition_type": "INTENT", "phrases": ["I want a pizza", "pizza please"]}
        assert translator.get_user_input(edge, None, {}) == "I want a pizza"

    def test_intent_without_phrases_falls_back_to_hello(self):
        translator = make_translator()
        edge = {"condition_type": "INTENT", "phrases": []}
        assert translator.get_user_input(edge, None, {}) == "Hello"

    def test_fallback_returns_an_invalid_marker_input(self):
        translator = make_translator()
        edge = {"condition_type": "FALLBACK"}
        assert translator.get_user_input(edge, None, {}) == "INVALID_INPUT_!@#_123"

    def test_default_uses_the_first_phrase(self):
        translator = make_translator()
        edge = {"condition_type": "DEFAULT", "phrases": ["ok"]}
        assert translator.get_user_input(edge, None, {}) == "ok"

    def test_default_without_phrases_falls_back_to_the_literal_default(self):
        translator = make_translator()
        edge = {"condition_type": "DEFAULT", "phrases": []}
        assert translator.get_user_input(edge, None, {}) == "default"

    def test_timeout_converts_duration_to_a_pause_command_in_milliseconds(self):
        translator = make_translator()
        edge = {"condition_type": "TIMEOUT", "duration": 15}
        assert translator.get_user_input(edge, None, {}) == "PAUSE 15000"

    def test_timeout_defaults_to_twenty_seconds_when_duration_is_missing(self):
        translator = make_translator()
        edge = {"condition_type": "TIMEOUT"}
        assert translator.get_user_input(edge, None, {}) == "PAUSE 20000"

    def test_unrecognized_condition_type_returns_none(self):
        translator = make_translator()
        edge = {"condition_type": "SOMETHING_UNEXPECTED"}
        assert translator.get_user_input(edge, None, {}) is None


# ---------------------------------------------------------------------------
# translate_path / _process_path_logic (integration)
# ---------------------------------------------------------------------------

class PathBuilder:
    """
    Builds a fake `path` exactly in the shape PathFinder.generate_paths() produces,
    AND the matching `nodes_dict` to hand to BotiumTranslator's constructor.

    This matters because _process_path_logic() resolves `source_data` via
    `self.nodes.get(step["source"])` (the translator's own global nodes_dict), which is
    a SEPARATE lookup from `step["target_data"]` (filled in directly by PathFinder from
    the same nodes_dict). Passing a step's target_data without also registering that
    node in the translator's nodes_dict silently breaks every source_data-dependent
    branch (session variable updates, skip_if_filled, CSAT, FALLBACK, WEBHOOK) --
    exactly the mistake the first draft of these tests made, caught by actually running
    them against the real code instead of assuming the fixture was right.
    """

    def __init__(self):
        self.nodes = {"USER_ENTRY": {}}
        self.edges = []

    def add(self, source, target, edge_data, target_data):
        self.nodes[target] = target_data
        self.edges.append({"source": source, "target": target, "edge_data": edge_data, "target_data": target_data})
        return self

    def path(self):
        return [{"source": None, "target": "USER_ENTRY", "edge_data": None, "target_data": {}}] + self.edges


class TestProcessPathLogicIntegration:
    """
    End-to-end tests of translate_path(): a full fake `path` (the same shape PathFinder
    returns) goes in, a Botium .convo.txt string comes out. These exercise
    pre_scan_path_constraints, get_user_input, get_message and the two formatting
    methods together, the same way the real pipeline chains them.
    """

    def test_simple_intent_and_reply(self):
        # Arrange: USER_ENTRY -> (INTENT "ciao") -> GREET (SEND_MESSAGE "Welcome!")
        builder = PathBuilder().add(
            "USER_ENTRY", "GREET",
            {"condition_type": "INTENT", "phrases": ["ciao"]},
            {"macro_type": "SEND_MESSAGE", "specific_type": "TEXT", "content": {"messages_list": ["Welcome!"]}},
        )
        translator = make_translator(nodes_dict=builder.nodes)
        # Act
        script = translator.translate_path(builder.path(), path_index=1)
        # Assert
        assert "#me\nciao\n" in script
        assert "#bot\n*Welcome!*\n" in script
        assert script.startswith("Test_Path_1\n")

    def test_get_attribute_answer_is_echoed_back_via_session_variable(self):
        # Arrange: GET_ATTRIBUTE node asks a question, the user answers (mock/generic,
        # since no path_constraint is pre-resolved here), and the NEXT bot message
        # echoes it back via {{attribute_id}} -- the Session Tracker end to end
        builder = (
            PathBuilder()
            .add("USER_ENTRY", "ASK", {"condition_type": "INTENT", "phrases": ["hi"]}, {
                "macro_type": "RECEIVE_INPUT", "specific_type": "GET_ATTRIBUTE",
                "content": {"questions": ["What plant do you have?"]},
                "attributes_defined": [130528], "data_type": "TEXT",
            })
            .add("ASK", "THANK", {"condition_type": "AUTO"}, {
                "macro_type": "SEND_MESSAGE", "specific_type": "TEXT",
                "content": {"messages_list": ["Great, a {{130528}}!"]},
            })
        )
        translator = make_translator(
            nodes_dict=builder.nodes,
            attributes={"130528": {"type": "TEXT", "name": "plant_name"}},
            mock_data={"DATATYPE_MOCKS": {"TEXT": {"valid": "Generic_Value", "invalid": None}}},
        )
        script = translator.translate_path(builder.path(), path_index=2)
        assert "#bot\n*What plant do you have?*\n" in script
        assert "#bot\n*Great, a " in script
        assert "{{130528}}" not in script  # the placeholder WAS substituted, not left literal

    def test_fallback_repeat_cycle_creates_an_utterance_and_repeats_the_turn(self):
        # Arrange: a GET_ATTRIBUTE node with 2 configured retries and 2 fallback-repeat
        # message variants -- the repeat cycle must run exactly repeat_count times
        ask_node = {
            "macro_type": "RECEIVE_INPUT", "specific_type": "GET_ATTRIBUTE",
            "content": {
                "questions": ["Your email?"],
                "repeat_count": 2,
                "repeat_messages": ["Sorry, that's not valid", "Please try again"],
            },
            "attributes_defined": [1], "data_type": "EMAIL",
        }
        builder = (
            PathBuilder()
            .add("USER_ENTRY", "ASK", {"condition_type": "INTENT", "phrases": ["hi"]}, ask_node)
            .add("ASK", "ASK", {"condition_type": "FALLBACK"}, ask_node)
        )
        translator = make_translator(nodes_dict=builder.nodes)
        script = translator.translate_path(builder.path(), path_index=5)
        # Assert: the two fallback messages became a path-scoped utterance, referenced twice
        utt_name = "UTT_REPEAT_ASK_5"
        assert translator.global_utterances[utt_name] == ["Sorry, that's not valid", "Please try again"]
        assert script.count(f"#bot\n{utt_name}\n") == 2

    def test_timeout_edge_emits_a_bare_pause_line_without_the_me_tag(self):
        # Arrange
        builder = PathBuilder().add("USER_ENTRY", "USER_ENTRY", {"condition_type": "TIMEOUT", "duration": 5}, {})
        translator = make_translator(nodes_dict=builder.nodes)
        script = translator.translate_path(builder.path(), path_index=0)
        # Assert: PAUSE must be a standalone line, never wrapped in "#me"
        assert "PAUSE 5000\n" in script
        assert "#me\nPAUSE 5000" not in script

    def test_skip_if_filled_source_node_produces_no_user_turn_when_already_known(self):
        # Arrange: the attribute was already collected by an earlier GET_ATTRIBUTE
        # step; this second one has skip_if_filled=True and must be silently skipped
        # (no question displayed for it)
        builder = (
            PathBuilder()
            .add("USER_ENTRY", "ASK1", {"condition_type": "INTENT", "phrases": ["hi"]}, {
                "macro_type": "RECEIVE_INPUT", "specific_type": "GET_ATTRIBUTE",
                "content": {"questions": ["What plant?"]}, "attributes_defined": [1], "data_type": "TEXT",
            })
            .add("ASK1", "ASK2", {"condition_type": "AUTO"}, {
                "macro_type": "RECEIVE_INPUT", "specific_type": "GET_ATTRIBUTE",
                "content": {"questions": ["What plant (again)?"], "skip_if_filled": True},
                "attributes_defined": [1], "data_type": "TEXT",
            })
            .add("ASK2", "END", {"condition_type": "AUTO"}, {
                "macro_type": "SEND_MESSAGE", "specific_type": "TEXT", "content": {"messages_list": ["Bye!"]},
            })
        )
        translator = make_translator(
            nodes_dict=builder.nodes,
            attributes={"1": {"type": "TEXT", "name": "plant_name"}},
            mock_data={"DATATYPE_MOCKS": {"TEXT": {"valid": "Generic_Value", "invalid": None}}},
        )
        script = translator.translate_path(builder.path(), path_index=0)
        assert "What plant (again)?" not in script

    def test_webhook_source_injects_a_waitforbot_line(self):
        # Arrange
        builder = (
            PathBuilder()
            .add("USER_ENTRY", "WH", {"condition_type": "INTENT", "phrases": ["go"]},
                 {"specific_type": "WEBHOOK", "content": {"timeout_duration": 8}})
            .add("WH", "END", {"condition_type": "AUTO"},
                 {"macro_type": "SEND_MESSAGE", "specific_type": "TEXT", "content": {"messages_list": ["Done!"]}})
        )
        translator = make_translator(nodes_dict=builder.nodes)
        script = translator.translate_path(builder.path(), path_index=0)
        # Assert: (8 + 2) * 1000 ms, passed through _format_botium_script unmodified
        assert "WAITFORBOT 10000\n" in script

    @pytest.mark.xfail(
        reason="BUG: self.mock_registry.valid_value(...) is called on line ~345, but "
               "self.mock_registry is a plain dict (built in __init__ from the JSON mock "
               "registry) which has no such method -- AttributeError on every CSAT node "
               "whose AUTO/[Auto]/DEFAULT exit edge has a feedback_question configured.",
        strict=True,
    )
    def test_csat_feedback_loop_does_not_crash(self):
        builder = (
            PathBuilder()
            .add("USER_ENTRY", "CSAT1", {"condition_type": "INTENT", "phrases": ["feedback"]}, {
                "specific_type": "CSAT",
                "content": {"feedback_question": "Tell us more", "thank_you_message": "Thanks!"},
            })
            .add("CSAT1", "END", {"condition_type": "AUTO"},
                 {"macro_type": "SEND_MESSAGE", "specific_type": "TEXT", "content": {"messages_list": ["Bye!"]}})
        )
        translator = make_translator(nodes_dict=builder.nodes)
        script = translator.translate_path(builder.path(), path_index=0)
        assert "Tell us more" in script
        assert "Thanks!" in script

    def test_csat_feedback_loop_currently_crashes(self):
        # Characterization test proving the bug above exists today -- delete this once
        # the xfail test starts passing.
        builder = (
            PathBuilder()
            .add("USER_ENTRY", "CSAT1", {"condition_type": "INTENT", "phrases": ["feedback"]}, {
                "specific_type": "CSAT",
                "content": {"feedback_question": "Tell us more", "thank_you_message": "Thanks!"},
            })
            .add("CSAT1", "END", {"condition_type": "AUTO"},
                 {"macro_type": "SEND_MESSAGE", "specific_type": "TEXT", "content": {"messages_list": ["Bye!"]}})
        )
        translator = make_translator(nodes_dict=builder.nodes)
        with pytest.raises(AttributeError):
            translator.translate_path(builder.path(), path_index=0)


# ---------------------------------------------------------------------------
# _format_botium_script
# ---------------------------------------------------------------------------

class TestFormatBotiumScript:

    def test_bot_response_is_wrapped_in_wildcards(self):
        translator = make_translator()
        script = translator._format_botium_script([{"user": "hi", "bot_responses": ["Hello there"]}], path_index=0)
        assert "#bot\n*Hello there*\n" in script

    def test_utterance_reference_is_not_wrapped_in_wildcards(self):
        translator = make_translator()
        script = translator._format_botium_script([{"user": "hi", "bot_responses": ["UTT_NODE_1"]}], path_index=0)
        assert "#bot\nUTT_NODE_1\n" in script

    def test_waitforbot_passes_through_unwrapped(self):
        translator = make_translator()
        script = translator._format_botium_script([{"user": None, "bot_responses": ["WAITFORBOT 5000"]}], path_index=0)
        assert "WAITFORBOT 5000\n" in script
        assert "*WAITFORBOT" not in script

    def test_pause_command_has_no_me_tag(self):
        translator = make_translator()
        script = translator._format_botium_script([{"user": "PAUSE 1000", "bot_responses": []}], path_index=0)
        assert "PAUSE 1000\n" in script
        assert "#me" not in script

    def test_newlines_inside_a_response_become_a_wildcard(self):
        translator = make_translator()
        script = translator._format_botium_script([{"user": None, "bot_responses": ["Line one\nLine two"]}], path_index=0)
        assert "#bot\n*Line one*Line two*\n" in script

    def test_convo_name_uses_the_path_index(self):
        translator = make_translator()
        script = translator._format_botium_script([], path_index=7)
        assert script.startswith("Test_Path_7\n")


# ---------------------------------------------------------------------------
# get_utterances_files
# ---------------------------------------------------------------------------

class TestGetUtterancesFiles:

    def test_no_utterances_returns_empty_dict(self):
        translator = make_translator()
        assert translator.get_utterances_files() == {}

    def test_each_utterance_becomes_its_own_file_with_wildcard_wrapped_phrases(self):
        translator = make_translator()
        translator.global_utterances["UTT_NODE_1"] = ["Hi!", "Hello!"]
        files = translator.get_utterances_files()
        assert set(files.keys()) == {"UTT_NODE_1.utterances.txt"}
        content = files["UTT_NODE_1.utterances.txt"]
        assert content == "UTT_NODE_1\n*Hi!*\n*Hello!*\n"

    def test_newlines_inside_a_phrase_are_flattened(self):
        translator = make_translator()
        translator.global_utterances["UTT_NODE_2"] = ["Line one\nLine two"]
        files = translator.get_utterances_files()
        assert files["UTT_NODE_2.utterances.txt"] == "UTT_NODE_2\n*Line one Line two*\n"


# ---------------------------------------------------------------------------
# pre_scan_path_constraints
# ---------------------------------------------------------------------------

class TestPreScanPathConstraints:

    def test_empty_path_returns_empty_constraints(self):
        translator = make_translator()
        assert translator.pre_scan_path_constraints([]) == {}

    def test_non_evaluation_edges_are_ignored(self):
        translator = make_translator()
        path = [{"source": "A", "target": "B", "edge_data": {"condition_type": "DEFAULT"}, "target_data": {}}]
        assert translator.pre_scan_path_constraints(path) == {}

    def test_single_evaluation_edge_contributes_its_constraint(self):
        translator = make_translator(attributes={"1": {"type": "TEXT"}})
        path = [{
            "source": "A", "target": "B",
            "edge_data": {
                "condition_type": "EVALUATION",
                "logic_tree": {"type": "ATTRIBUTE_COMPARE", "attributeId": 1, "operator": "EQUAL", "value": "Ficus"},
            },
            "target_data": {},
        }]
        assert translator.pre_scan_path_constraints(path) == {"1": "Ficus"}

    def test_two_evaluation_edges_on_the_same_attribute_are_combined(self):
        # Arrange: two separate EVALUATION edges further down the path both constrain
        # attribute "1" -- the value must satisfy both at once, exactly like
        # solve_conjunction does for a single logic tree with an AND
        translator = make_translator(attributes={"1": {"type": "NUMBER"}})
        path = [
            {
                "source": "A", "target": "B",
                "edge_data": {
                    "condition_type": "EVALUATION",
                    "logic_tree": {"type": "ATTRIBUTE_COMPARE", "attributeId": 1, "operator": "GREATER_THAN", "value": "5"},
                },
                "target_data": {},
            },
            {
                "source": "B", "target": "C",
                "edge_data": {
                    "condition_type": "EVALUATION",
                    "logic_tree": {"type": "ATTRIBUTE_COMPARE", "attributeId": 1, "operator": "LESS_THAN", "value": "10"},
                },
                "target_data": {},
            },
        ]
        constraints = translator.pre_scan_path_constraints(path)
        assert 5 < float(constraints["1"]) < 10
