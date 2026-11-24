"""
Full pytest suite for parsing/parsing_utils.py and parsing/parsing_functions/*.py.

These are the "mapper" functions: each takes one raw Infobip JSON element and
standardizes it into the {id, macro_type, specific_type, content, transitions, ...}
dict shape that ChatbotParser turns into graph nodes/edges. They're pure functions
(no shared state), so each is unit-tested directly on hand-built JSON fragments that
mirror the real Infobip export shape.

Structure:
  - TestExtractPlaceholders       -> parsing_utils.extract_placeholders()
  - TestExtractAttrsFromCondition -> parsing_utils.extract_attrs_from_condition()
  - TestExtractCodeAttributes     -> parsing_utils.extract_code_attributes()
  - TestMapSendMessage            -> send_message_mapper.map_send_message()
  - TestExtractCommonInputLogic   -> user_input_mapper.extract_common_input_logic()
  - TestMapProcessUserInput       -> user_input_mapper.map_process_user_input()
  - TestMapGetAttribute           -> user_input_mapper.map_get_attribute()
  - TestMapCsat                   -> user_input_mapper.map_csat()
  - TestMapGoToDialog             -> bot_actions_mapper.map_go_to_dialog()
  - TestMapDelay                  -> bot_actions_mapper.map_delay()
  - TestMapCloseSession           -> bot_actions_mapper.map_close_session()
  - TestMapEvaluateAttribute      -> bot_actions_mapper.map_evaluate_attribute()
  - TestMapCoding                 -> bot_actions_mapper.map_coding()
  - TestMapApiCall                -> bot_actions_mapper.map_api_call()
  - TestMapWebhook                -> bot_actions_mapper.map_webhook()
  - TestMapComponent              -> bot_actions_mapper.map_component()
"""

import pytest
from parsing.parsing_utils import extract_placeholders, extract_attrs_from_condition, extract_code_attributes
from parsing.parsing_functions.send_message_mapper import map_send_message
from parsing.parsing_functions.user_input_mapper import (
    extract_common_input_logic, map_process_user_input, map_get_attribute, map_csat,
)
from parsing.parsing_functions.bot_actions_mapper import (
    map_go_to_dialog, map_delay, map_close_session, map_evaluate_attribute,
    map_coding, map_api_call, map_webhook, map_component, map_authentication,
)


# ---------------------------------------------------------------------------
# extract_placeholders
# ---------------------------------------------------------------------------

class TestExtractPlaceholders:

    def test_single_placeholder_in_a_string(self):
        assert extract_placeholders("Hello {{name}}!") == ["name"]

    def test_no_placeholders_returns_empty_list(self):
        assert extract_placeholders("Hello there!") == []

    def test_multiple_distinct_placeholders_are_all_found(self):
        result = set(extract_placeholders("{{first}} {{second}}"))
        assert result == {"first", "second"}

    def test_duplicate_placeholders_are_deduplicated_when_reached_through_a_dict(self):
        # Dedup is applied by `list(set(found))`, but that line only runs in the
        # list/dict branches, AFTER collecting results from (possibly duplicated)
        # recursive calls. So wrapping the same string in a dict does deduplicate it.
        assert extract_placeholders({"msg": "{{name}} and {{name}} again"}) == ["name"]

    def test_BUG_duplicate_placeholders_in_a_bare_string_are_not_deduplicated(self):
        # The string branch is a *direct* `return re.findall(...)` with no call to
        # `list(set(...))` at all -- that dedup only happens in the list/dict branches.
        # So calling extract_placeholders() directly on a string with a repeated
        # placeholder (as map_send_message() does on e.g. a SEND_MESSAGE TEXT body)
        # returns the duplicate, unlike every other call path in this function.
        # This is a real, functioning characterization test (not a bug fix request):
        # it documents current behavior so a future dedup fix is a conscious, visible change.
        assert extract_placeholders("{{name}} and {{name}} again") == ["name", "name"]

    def test_recurses_into_nested_dicts_and_lists(self):
        data = {"messages_list": ["Hi {{name}}", {"nested": ["{{other}}"]}]}
        result = set(extract_placeholders(data))
        assert result == {"name", "other"}

    def test_non_string_non_list_non_dict_returns_empty_list(self):
        assert extract_placeholders(42) == []
        assert extract_placeholders(None) == []


# ---------------------------------------------------------------------------
# extract_attrs_from_condition
# ---------------------------------------------------------------------------

class TestExtractAttrsFromCondition:

    def test_attribute_compare_leaf(self):
        cond = {"type": "ATTRIBUTE_COMPARE", "attributeId": 42}
        assert extract_attrs_from_condition(cond) == ["42"]

    def test_attribute_compare_without_attribute_id_is_skipped(self):
        cond = {"type": "ATTRIBUTE_COMPARE"}
        assert extract_attrs_from_condition(cond) == []

    def test_logical_block_recurses_into_every_sub_condition(self):
        cond = {
            "type": "LOGICAL",
            "conditions": [
                {"type": "ATTRIBUTE_COMPARE", "attributeId": 1},
                {"type": "ATTRIBUTE_COMPARE", "attributeId": 2},
            ],
        }
        assert extract_attrs_from_condition(cond) == ["1", "2"]

    def test_unknown_type_returns_empty_list(self):
        assert extract_attrs_from_condition({"type": "SOMETHING_ELSE"}) == []


# ---------------------------------------------------------------------------
# extract_code_attributes
# ---------------------------------------------------------------------------

class TestExtractCodeAttributes:

    def test_get_and_set_calls_with_double_quotes(self):
        code = 'var x = attributeApi.get("Foo"); attributeApi.set("Bar", x);'
        used, defined = extract_code_attributes(code)
        assert used == ["Foo"]
        assert defined == ["Bar"]

    def test_get_and_set_calls_with_single_quotes(self):
        code = "var x = attributeApi.get('Foo'); attributeApi.set('Bar', x);"
        used, defined = extract_code_attributes(code)
        assert used == ["Foo"]
        assert defined == ["Bar"]

    def test_no_calls_returns_two_empty_lists(self):
        assert extract_code_attributes("var x = 1;") == ([], [])

    def test_empty_or_non_string_input_returns_two_empty_lists(self):
        assert extract_code_attributes("") == ([], [])
        assert extract_code_attributes(None) == ([], [])

    def test_duplicate_calls_are_deduplicated(self):
        code = 'attributeApi.get("Foo"); attributeApi.get("Foo");'
        used, _ = extract_code_attributes(code)
        assert used == ["Foo"]


# ---------------------------------------------------------------------------
# map_send_message
# ---------------------------------------------------------------------------

class TestMapSendMessage:

    def test_text_message_single(self):
        element = {"action": {"messages": [{"type": "TEXT", "message": "Hello!"}], "nextElementId": "N2"}}
        result = map_send_message("D1", "N1", element)
        assert result["id"] == "D1_N1"
        assert result["macro_type"] == "SEND_MESSAGE"
        assert result["specific_type"] == "TEXT"
        assert result["content"] == {"messages_list": ["Hello!"]}
        assert result["next_element"] == "D1_N2"

    def test_text_message_multiple_variants_and_empty_text_is_filtered(self):
        element = {"action": {"messages": [
            {"type": "TEXT", "message": "Hi!"},
            {"type": "TEXT", "message": ""},
            {"type": "TEXT", "message": "Hello!"},
        ]}}
        result = map_send_message("D1", "N1", element)
        assert result["content"]["messages_list"] == ["Hi!", "Hello!"]

    def test_text_message_extracts_placeholders_as_attributes_used(self):
        element = {"action": {"messages": [{"type": "TEXT", "message": "Hi {{name}}!"}]}}
        result = map_send_message("D1", "N1", element)
        assert result["attributes_used"] == ["name"]

    def test_image_message(self):
        element = {"action": {"messages": [{"type": "IMAGE", "url": "http://x/img.png", "caption": "A cat"}]}}
        result = map_send_message("D1", "N1", element)
        assert result["specific_type"] == "IMAGE"
        assert result["content"] == {"url": "http://x/img.png", "caption": "A cat"}

    def test_button_message_with_text_header_and_footer(self):
        element = {"action": {"messages": [{
            "type": "BUTTON", "body": "Choose one", "footer": "Powered by Infobip",
            "buttons": [{"title": "Yes"}, {"title": "No"}],
            "header": {"type": "TEXT", "text": "Question"},
        }]}}
        result = map_send_message("D1", "N1", element)
        assert result["content"]["body"] == "Choose one"
        assert result["content"]["buttons"] == ["Yes", "No"]
        assert result["content"]["header"]["text"] == "Question"
        assert result["content"]["footer"] == "Powered by Infobip"

    def test_button_message_with_text_header_coincidentally_works(self):
        # NOTE: see the BUG test right below -- this one only passes because for a
        # TEXT header, the raw input dict and the normalized `header_data` dict
        # happen to share the same key names ("type", "text").
        element = {"action": {"messages": [{
            "type": "BUTTON", "body": "Question", "buttons": [],
            "header": {"type": "TEXT", "text": "Hi there"},
        }]}}
        result = map_send_message("D1", "N1", element)
        assert result["content"]["header"] == {"type": "TEXT", "text": "Hi there"}

    def test_button_message_with_document_header_should_be_normalized(self):
        # Expected/intended behavior: the mapper computes a normalized `header_data`
        # dict (lines ~42-52 of send_message_mapper.py) that turns the Infobip-specific
        # "documentUrl" field into a generic "url" field. This is what any downstream
        # consumer (e.g. BotiumTranslator) should be able to rely on.
        element = {"action": {"messages": [{
            "type": "BUTTON", "body": "File", "buttons": [],
            "header": {"type": "DOCUMENT", "documentUrl": "http://x/f.pdf", "filename": "f.pdf"},
        }]}}
        result = map_send_message("D1", "N1", element)
        assert result["content"]["header"]["url"] == "http://x/f.pdf"
        assert result["content"]["header"]["filename"] == "f.pdf"

    def test_list_picker_message_with_optional_description(self):
        element = {"action": {"messages": [{
            "type": "LIST_PICKER", "body": "Pick one", "header": "Menu", "footer": "", "button": "Open",
            "sections": [{"items": [
                {"title": "Pizza", "postback": "pizza", "description": "Tasty"},
                {"title": "Pasta", "postback": "pasta"},
            ]}],
        }]}}
        result = map_send_message("D1", "N1", element)
        options = result["content"]["options"]
        assert options[0] == {"title": "Pizza", "postback": "pizza", "description": "Tasty"}
        assert options[1] == {"title": "Pasta", "postback": "pasta"}  # no "description" key at all

    def test_json_message_with_valid_json_string_payload(self):
        element = {"action": {"messages": [{"type": "JSON", "json": '{"a": 1}'}]}}
        result = map_send_message("D1", "N1", element)
        assert result["content"]["payload"] == {"a": 1}

    def test_json_message_with_invalid_json_string_keeps_raw_payload(self):
        element = {"action": {"messages": [{"type": "JSON", "json": "{not valid json"}]}}
        result = map_send_message("D1", "N1", element)
        assert result["content"]["payload"] == "{not valid json"

    def test_json_message_with_already_a_dict_payload(self):
        element = {"action": {"messages": [{"type": "JSON", "json": {"a": 1}}]}}
        result = map_send_message("D1", "N1", element)
        assert result["content"]["payload"] == {"a": 1}

    def test_no_messages_falls_back_to_unknown_subtype(self):
        element = {"action": {"messages": []}}
        result = map_send_message("D1", "N1", element)
        assert result["specific_type"] == "UNKNOWN_SUBTYPE"
        assert result["content"] == {}

    def test_no_next_element_id_gives_none(self):
        element = {"action": {"messages": [{"type": "TEXT", "message": "Hi"}]}}
        result = map_send_message("D1", "N1", element)
        assert result["next_element"] is None


# ---------------------------------------------------------------------------
# extract_common_input_logic
# ---------------------------------------------------------------------------

class TestExtractCommonInputLogic:

    def test_no_fallback_timeout_or_repeat_gives_minimal_content(self):
        transitions, content, next_id = extract_common_input_logic("D1", {})
        assert transitions == []
        assert content["repeat_count"] == 0
        assert content["timeout_enabled"] is False
        assert next_id is None

    def test_fallback_go_to_dialog_creates_a_transition(self):
        action = {"fallback": {"fallbackAction": "GO_TO_DIALOG", "goToDialogId": "D9", "messages": [{"text": "Sorry"}]}}
        transitions, content, _ = extract_common_input_logic("D1", action)
        assert transitions == [{
            "target": "D9_1",
            "edge_data": {
                "condition_type": "FALLBACK", "action": "GO_TO_DIALOG",
                "messages_list": ["Sorry"], "target_dialog_id": "D9",
            },
        }]

    def test_fallback_without_target_dialog_creates_no_transition(self):
        action = {"fallback": {"fallbackAction": "GO_TO_DIALOG"}}
        transitions, _, _ = extract_common_input_logic("D1", action)
        assert transitions == []

    def test_fallback_messages_with_empty_text_are_filtered_out(self):
        action = {"fallback": {"fallbackAction": "REPEAT", "messages": [{"text": ""}, {"text": "Try again"}]}}
        _, content, _ = extract_common_input_logic("D1", action)
        assert content["repeat_messages"] == []  # these are "fallback" messages, not "repeat" -- see below

    def test_timeout_fallback_only_applies_when_timeout_is_enabled(self):
        # Arrange: timeoutFallback IS configured, but timeout.isEnabled is False
        action = {
            "timeout": {"isEnabled": False, "durationSeconds": 30},
            "timeoutFallback": {"fallbackAction": "GO_TO_DIALOG", "goToDialogId": "D9"},
        }
        transitions, _, _ = extract_common_input_logic("D1", action)
        assert transitions == []

    def test_timeout_fallback_go_to_dialog_creates_a_transition_when_enabled(self):
        action = {
            "timeout": {"isEnabled": True, "durationSeconds": 30},
            "timeoutFallback": {"fallbackAction": "GO_TO_DIALOG", "goToDialogId": "D9", "messages": [{"text": "Still there?"}]},
        }
        transitions, content, _ = extract_common_input_logic("D1", action)
        assert transitions == [{
            "target": "D9_1",
            "edge_data": {
                "condition_type": "TIMEOUT", "action": "GO_TO_DIALOG", "duration": 30,
                "messages_list": ["Still there?"], "target_dialog_id": "D9",
            },
        }]
        assert content["timeout_enabled"] is True
        assert content["timeout_duration"] == 30

    def test_repeat_count_and_messages_are_collected(self):
        action = {"repeat": {"count": 3, "messages": [{"text": "Please repeat"}]}}
        _, content, _ = extract_common_input_logic("D1", action)
        assert content["repeat_count"] == 3
        assert content["repeat_messages"] == ["Please repeat"]

    def test_next_element_id_is_combined_with_dialog_id(self):
        _, _, next_id = extract_common_input_logic("D1", {"nextElementId": "N5"})
        assert next_id == "D1_N5"


# ---------------------------------------------------------------------------
# map_process_user_input
# ---------------------------------------------------------------------------

class TestMapProcessUserInput:

    def test_rules_become_edges(self):
        action = {"rules": [
            {"nextElementId": "N2", "condition": {"type": "INTENT"}},
            {"nextElementId": "N3", "condition": {"type": "DEFAULT"}},
        ]}
        element = {"action": action}
        result = map_process_user_input("D1", "N1", element)
        targets = {t["target"] for t in result["transitions"]}
        assert targets == {"D1_N2", "D1_N3"}

    def test_rule_without_next_element_id_is_skipped(self):
        action = {"rules": [{"condition": {"type": "DEFAULT"}}]}
        result = map_process_user_input("D1", "N1", {"action": action})
        assert result["transitions"] == []

    def test_keyword_compare_rule_carries_the_keyword_id(self):
        action = {"rules": [{"nextElementId": "N2", "condition": {"type": "KEYWORD_COMPARE", "keywordId": 7}}]}
        result = map_process_user_input("D1", "N1", {"action": action})
        assert result["transitions"][0]["edge_data"]["keywordId"] == 7

    def test_nlp_enabled_flag_is_read_from_the_action(self):
        result = map_process_user_input("D1", "N1", {"action": {"nlpEnabled": True}})
        assert result["content"]["nlpEnabled"] is True

    def test_nlp_enabled_defaults_to_false(self):
        result = map_process_user_input("D1", "N1", {"action": {}})
        assert result["content"]["nlpEnabled"] is False


# ---------------------------------------------------------------------------
# map_get_attribute
# ---------------------------------------------------------------------------

class TestMapGetAttribute:

    def test_basic_fields_and_attribute_defined(self):
        action = {"attributeId": 42, "questions": [{"text": "What's your name?"}]}
        result = map_get_attribute("D1", "N1", {"action": action}, attributes_dict={})
        assert result["attributes_defined"] == ["42"]
        assert result["content"]["questions"] == ["What's your name?"]
        assert result["data_type"] == "TEXT"  # unknown to attributes_dict -> defaults to TEXT

    def test_data_type_is_looked_up_from_the_attributes_dict(self):
        action = {"attributeId": 42}
        attributes_dict = {"42": {"type": "EMAIL"}}
        result = map_get_attribute("D1", "N1", {"action": action}, attributes_dict=attributes_dict)
        assert result["data_type"] == "EMAIL"

    def test_no_attribute_id_means_nothing_is_defined(self):
        result = map_get_attribute("D1", "N1", {"action": {}}, attributes_dict={})
        assert result["attributes_defined"] == []

    def test_custom_validation_regex_is_kept_only_when_enabled(self):
        action = {"customValidation": True, "customValidationRegex": r"[A-Z]{3}"}
        result = map_get_attribute("D1", "N1", {"action": action}, attributes_dict={})
        assert result["content"]["validation_regex"] == r"[A-Z]{3}"

    def test_custom_validation_regex_is_none_when_disabled_even_if_present(self):
        action = {"customValidation": False, "customValidationRegex": r"[A-Z]{3}"}
        result = map_get_attribute("D1", "N1", {"action": action}, attributes_dict={})
        assert result["content"]["validation_regex"] is None

    def test_skip_if_filled_flag_is_read(self):
        result = map_get_attribute("D1", "N1", {"action": {"skipIfAttributeFilled": True}}, attributes_dict={})
        assert result["content"]["skip_if_filled"] is True

    def test_attributes_dict_defaults_to_empty_when_none_is_passed(self):
        # Arrange: attributes_dict=None is the function's own default
        result = map_get_attribute("D1", "N1", {"action": {"attributeId": 1}})
        assert result["data_type"] == "TEXT"


# ---------------------------------------------------------------------------
# map_csat
# ---------------------------------------------------------------------------

class TestMapCsat:

    def test_fields_are_extracted_and_lifecycle_is_hardcoded(self):
        action = {
            "scoringQuestion": " How did we do? ", "scale": "SCORING_1_10",
            "fallbackMessage": "Please answer 1-10", "feedbackQuestion": "Tell us more",
            "thankYouMessage": "Thanks!", "nextElementId": "N2",
        }
        result = map_csat("D1", "N1", {"action": action})
        assert result["content"]["question"] == "How did we do?"  # stripped
        assert result["content"]["scale_type"] == "SCORING_1_10"
        assert result["content"]["repeat_count"] == 1
        assert result["content"]["repeat_messages"] == []
        assert result["next_element"] == "D1_N2"
        assert result["transitions"] == []

    def test_defaults_when_fields_are_missing(self):
        result = map_csat("D1", "N1", {"action": {}})
        assert result["content"]["scale_type"] == "SCORING_1_5"
        assert result["content"]["question"] == ""


# ---------------------------------------------------------------------------
# map_go_to_dialog
# ---------------------------------------------------------------------------

class TestMapGoToDialog:

    def test_creates_a_transition_to_the_first_element_of_the_target_dialog(self):
        action = {"dialogId": "D9", "shareAttributes": True, "attributeIds": [1, 2]}
        result = map_go_to_dialog("D1", "N1", {"action": action})
        assert result["transitions"] == [{
            "target": "D9_1",
            "edge_data": {"action": "GO_TO_DIALOG", "target_dialog_id": "D9", "shared_attributes_ids": ["1", "2"]},
        }]
        assert result["content"]["share_attributes"] is True
        assert result["attributes_used"] == ["1", "2"]

    def test_no_target_dialog_means_no_transition(self):
        result = map_go_to_dialog("D1", "N1", {"action": {}})
        assert result["transitions"] == []
        assert result["content"]["target_dialog_id"] is None

    def test_share_attributes_defaults_to_false(self):
        result = map_go_to_dialog("D1", "N1", {"action": {"dialogId": "D9"}})
        assert result["content"]["share_attributes"] is False
        assert result["content"]["shared_attribute_ids"] == []


# ---------------------------------------------------------------------------
# map_delay
# ---------------------------------------------------------------------------

class TestMapDelay:

    def test_delay_duration_and_next_element_are_read(self):
        result = map_delay("D1", "N1", {"action": {"delayInSeconds": 5, "nextElementId": "N2"}})
        assert result["content"]["delay_duration"] == 5
        assert result["next_element"] == "D1_N2"

    def test_defaults_when_action_is_empty(self):
        result = map_delay("D1", "N1", {"action": {}})
        assert result["content"]["delay_duration"] == 0
        assert result["next_element"] is None


# ---------------------------------------------------------------------------
# map_close_session
# ---------------------------------------------------------------------------

class TestMapCloseSession:

    def test_is_a_terminal_node_with_no_transitions_or_content(self):
        result = map_close_session("D1", "N1", {"action": {}})
        assert result["specific_type"] == "CLOSE_SESSION"
        assert result["content"] == {}
        assert result["next_element"] is None
        assert result["transitions"] == []


# ---------------------------------------------------------------------------
# map_evaluate_attribute
# ---------------------------------------------------------------------------

class TestMapEvaluateAttribute:

    def test_each_rule_with_a_next_element_becomes_an_evaluation_edge(self):
        action = {"rules": [
            {"nextElementId": "N2", "name": "Rule A", "condition": {"type": "ATTRIBUTE_COMPARE", "attributeId": 1}},
        ]}
        result = map_evaluate_attribute("D1", "N1", {"action": action})
        assert result["transitions"] == [{
            "target": "D1_N2",
            "edge_data": {"condition_type": "EVALUATION", "condition": "Rule A", "logic_tree": action["rules"][0]["condition"]},
        }]
        assert result["attributes_used"] == ["1"]

    def test_rule_without_next_element_id_is_skipped(self):
        action = {"rules": [{"name": "Rule A", "condition": {}}]}
        result = map_evaluate_attribute("D1", "N1", {"action": action})
        assert result["transitions"] == []

    def test_rule_name_defaults_to_condition(self):
        action = {"rules": [{"nextElementId": "N2", "condition": {}}]}
        result = map_evaluate_attribute("D1", "N1", {"action": action})
        assert result["transitions"][0]["edge_data"]["condition"] == "Condition"

    def test_else_element_creates_a_final_else_transition(self):
        action = {"rules": [], "elseElementId": "N9"}
        result = map_evaluate_attribute("D1", "N1", {"action": action})
        assert result["transitions"] == [{"target": "D1_N9", "edge_data": {"condition_type": "ELSE", "condition": "Else"}}]

    def test_attributes_used_is_deduplicated_across_rules(self):
        action = {"rules": [
            {"nextElementId": "N2", "condition": {"type": "ATTRIBUTE_COMPARE", "attributeId": 1}},
            {"nextElementId": "N3", "condition": {"type": "ATTRIBUTE_COMPARE", "attributeId": 1}},
        ]}
        result = map_evaluate_attribute("D1", "N1", {"action": action})
        assert result["attributes_used"] == ["1"]


# ---------------------------------------------------------------------------
# map_coding
# ---------------------------------------------------------------------------

class TestMapCoding:

    def test_extracts_attributes_used_and_defined_from_the_code_string(self):
        code = 'var x = attributeApi.get("In"); attributeApi.set("Out", x);'
        result = map_coding("D1", "N1", {"action": {"code": code, "nextElementId": "N2"}})
        assert result["attributes_used"] == ["In"]
        assert result["attributes_defined"] == ["Out"]
        assert result["content"]["code"] == code
        assert result["next_element"] == "D1_N2"

    def test_language_defaults_to_javascript(self):
        result = map_coding("D1", "N1", {"action": {}})
        assert result["content"]["language"] == "JAVASCRIPT"
        assert result["attributes_used"] == []
        assert result["attributes_defined"] == []


# ---------------------------------------------------------------------------
# map_authentication
# ---------------------------------------------------------------------------

class TestMapAuthentication:

    def test_passes_through_timeout_fields(self):
        action = {"timeoutInMinutes": 15, "neverTimeout": True, "nextElementId": "N2"}
        result = map_authentication("D1", "N1", {"action": action})
        assert result["content"] == {"timeout_minutes": 15, "never_timeout": True}
        assert result["next_element"] == "D1_N2"

    def test_defaults_when_action_is_empty(self):
        result = map_authentication("D1", "N1", {"action": {}})
        assert result["content"] == {"timeout_minutes": 0, "never_timeout": False}


# ---------------------------------------------------------------------------
# map_api_call
# ---------------------------------------------------------------------------

class TestMapApiCall:

    def test_collects_attributes_defined_from_status_header_and_body(self):
        action = {
            "responseCodeAttributeId": 1,
            "collectHeaderAttributes": [{"attributeId": 2}],
            "collectAttributes": [{"attributeId": 3}, {"attributeId": None}],
        }
        result = map_api_call("D1", "N1", {"action": action})
        assert sorted(result["attributes_defined"]) == ["1", "2", "3"]

    def test_attributes_defined_is_deduplicated(self):
        action = {"responseCodeAttributeId": 1, "collectHeaderAttributes": [{"attributeId": 1}]}
        result = map_api_call("D1", "N1", {"action": action})
        assert result["attributes_defined"] == ["1"]

    def test_fallback_go_to_dialog_creates_a_transition(self):
        action = {"fallback": {"fallbackAction": "GO_TO_DIALOG", "goToDialogId": "D9", "messages": [{"text": "API failed"}]}}
        result = map_api_call("D1", "N1", {"action": action})
        assert result["transitions"] == [{
            "target": "D9_1",
            "edge_data": {
                "condition_type": "FALLBACK", "action": "GO_TO_DIALOG",
                "messages_list": ["API failed"], "target_dialog_id": "D9",
            },
        }]

    def test_fallback_with_a_non_go_to_dialog_action_creates_no_transition(self):
        action = {"fallback": {"fallbackAction": "REPEAT"}}
        result = map_api_call("D1", "N1", {"action": action})
        assert result["transitions"] == []

    def test_content_defaults(self):
        result = map_api_call("D1", "N1", {"action": {}})
        assert result["content"] == {"url": "", "method": "GET", "timeout": 0, "content_type": None}


# ---------------------------------------------------------------------------
# map_webhook
# ---------------------------------------------------------------------------

class TestMapWebhook:

    def test_timeout_fields_and_method_are_read(self):
        action = {"method": "POST", "timeout": {"isEnabled": True, "durationSeconds": 20}}
        result = map_webhook("D1", "N1", {"action": action})
        assert result["content"] == {"method": "POST", "timeout_enabled": True, "timeout_duration": 20}

    def test_timeout_duration_defaults_to_10(self):
        result = map_webhook("D1", "N1", {"action": {}})
        assert result["content"]["timeout_duration"] == 10
        assert result["content"]["timeout_enabled"] is False

    def test_timeout_fallback_go_to_dialog_creates_a_transition(self):
        action = {"timeoutFallback": {"fallbackAction": "GO_TO_DIALOG", "goToDialogId": "D9", "messages": [{"text": "Timed out"}]}}
        result = map_webhook("D1", "N1", {"action": action})
        assert result["transitions"] == [{
            "target": "D9_1",
            "edge_data": {
                "condition_type": "TIMEOUT_FALLBACK", "action": "GO_TO_DIALOG",
                "messages_list": ["Timed out"], "target_dialog_id": "D9",
            },
        }]

    def test_timeout_fallback_with_a_non_go_to_dialog_action_creates_no_transition(self):
        action = {"timeoutFallback": {"fallbackAction": "UNKNOWN"}}
        result = map_webhook("D1", "N1", {"action": action})
        assert result["transitions"] == []


# ---------------------------------------------------------------------------
# map_component
# ---------------------------------------------------------------------------

class TestMapComponent:

    def test_extracts_input_and_output_attributes(self):
        action = {
            "componentSender": "Sender1",
            "inputAttributes": [{"attributeId": 1}],
            "outputAttributes": [{"attributeId": 2}, {"attributeId": None}],
        }
        result = map_component("D1", "N1", {"action": action})
        assert result["attributes_used"] == ["1"]
        assert result["attributes_defined"] == ["2"]
        assert result["content"]["component_sender"] == "Sender1"

    def test_fallback_go_to_dialog_creates_a_transition(self):
        action = {"fallback": {"fallbackAction": "GO_TO_DIALOG", "goToDialogId": "D9"}}
        result = map_component("D1", "N1", {"action": action})
        assert result["transitions"] == [{
            "target": "D9_1",
            "edge_data": {"condition_type": "COMPONENT_FALLBACK", "action": "GO_TO_DIALOG", "target_dialog_id": "D9"},
        }]

    def test_fallback_with_a_non_go_to_dialog_action_creates_no_transition(self):
        action = {"fallback": {"fallbackAction": "RETRY"}}
        result = map_component("D1", "N1", {"action": action})
        assert result["transitions"] == []

    def test_no_attributes_or_fallback_gives_empty_lists(self):
        result = map_component("D1", "N1", {"action": {}})
        assert result["attributes_used"] == []
        assert result["attributes_defined"] == []
        assert result["transitions"] == []
