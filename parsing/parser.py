import networkx as nx

from parsing.parsing_functions.send_message_mapper import map_send_message
from parsing.parsing_functions.user_input_mapper import map_process_user_input
from parsing.parsing_functions.user_input_mapper import map_get_attribute
from parsing.parsing_functions.bot_actions_mapper import map_go_to_dialog
from parsing.parsing_functions.bot_actions_mapper import map_delay
from parsing.parsing_functions.bot_actions_mapper import map_close_session
from parsing.parsing_functions.bot_actions_mapper import map_evaluate_attribute
from parsing.parsing_functions.bot_actions_mapper import map_api_call
from parsing.parsing_functions.user_input_mapper import map_csat
from parsing.parsing_functions.bot_actions_mapper import map_webhook
from parsing.parsing_functions.bot_actions_mapper import map_authentication
from parsing.parsing_functions.bot_actions_mapper import map_coding
from parsing.parsing_functions.bot_actions_mapper import map_component
from test_generation.utils.load_json import _load_mock_registry

DATATYPE_MOCKS = _load_mock_registry()


class ChatbotParser:
    def __init__(self, json_data, component_jsons=None, mock_data=None):
        self.data = json_data
        self.keywords = self._build_keyword()
        self.intents = self._build_intent()
        self.start_element_map = {}
        self.attributes = self._build_attribute()
        self.components_jsons = component_jsons or {}
        self.mock_data = mock_data if mock_data is not None else DATATYPE_MOCKS

        # Build a map of starting elements for each dialog
        for dialog in self.data.get("dialogRequests", []):
            d_id = dialog["internalId"]
            start_elem = dialog.get("startElementId")
            
            if not start_elem:
                elements = dialog.get("elements", [])
                if elements:
                    start_elem = elements[0].get("id") 
                    
            if start_elem:
                self.start_element_map[d_id] = start_elem

        # Strategy Pattern: Maps Infobip JSON types to specific parsing functions
        self.dispatcher = {
            "SEND_MESSAGE": map_send_message,
            "PROCESS_USER_INPUT": map_process_user_input,
            "GET_ATTRIBUTE": map_get_attribute,
            "CSAT": map_csat,
            "GO_TO_DIALOG": map_go_to_dialog,
            "DELAY": map_delay,
            "CLOSE_SESSION": map_close_session,
            "EVALUATE_ATTRIBUTE": map_evaluate_attribute,
            "API_CALL": map_api_call,
            "WEBHOOK": map_webhook,
            "AUTHENTICATION": map_authentication,
            "CODING": map_coding,
            "COMPONENT": map_component
        }

    def _is_unfeasible_fallback(self, node_id, mapped_node, edge_data):
        """
        SMART PRUNING (Type 2 - Data-Type Unfeasible Fallback):
        Checks if a FALLBACK transition originates from a GET_ATTRIBUTE node
        whose data type accepts any input (i.e., 'invalid' mock is None).
        """
        if edge_data.get("condition_type") == "FALLBACK" and mapped_node.get("specific_type") == "GET_ATTRIBUTE":
            data_type = mapped_node.get("data_type", "TEXT").upper()
            default_mock = self.mock_data.get("TEXT", {"valid": "Generic_Text", "invalid": None})
            mock_info = self.mock_data.get(data_type, default_mock)
            
            if mock_info.get("invalid") is None:
                print(f"[SMART PRUNING] Dead fallback branch omitted on '{node_id}' (Type '{data_type}' accepts anything).")
                return True
        return False

    def _process_transitions(self, node_id, mapped_node, transitions, prefix=None, comp_start_map=None):
        """
        Unified method to process node transitions, apply Smart Pruning,
        resolve target IDs (with or without component prefixes), and enrich keyword edges.
        """
        comp_start_map = comp_start_map or {}
        
        for trans in transitions:
            target = trans.get("target")
            edge_data = trans.get("edge_data", {})
            
            if target:
                # SMART PRUNING (Type 2 - Data-Type Unfeasible Fallback)
                if self._is_unfeasible_fallback(node_id, mapped_node, edge_data):
                    continue

                if prefix:
                    if edge_data.get("action") == "GO_TO_DIALOG":
                        target_dialog_id = edge_data.get("target_dialog_id")
                        if target_dialog_id in comp_start_map:
                            target = comp_start_map[target_dialog_id]
                        elif target_dialog_id in self.start_element_map:
                            real_start = self.start_element_map[target_dialog_id]
                            target = f"{target_dialog_id}_{real_start}"
                    else:
                        target = f"{prefix}_{target}"
                else:
                    if edge_data.get("action") == "GO_TO_DIALOG":
                        target_dialog_id = edge_data.get("target_dialog_id")
                        if target_dialog_id:
                            real_start_elem = self.start_element_map.get(target_dialog_id)
                            if real_start_elem:
                                target = f"{target_dialog_id}_{real_start_elem}"

                if edge_data.get("condition_type") == "KEYWORD_COMPARE":
                    kw_id = edge_data.get("keywordId")
                    if kw_id in self.keywords:
                        kw_data = self.keywords[kw_id]
                        edge_data["keyword_name"] = kw_data["name"]
                        edge_data["synonyms"] = kw_data["synonyms"]

                self.G.add_edge(node_id, target, **edge_data)

    def map_unknown(self, d_id, e_id, element):
        print(f"Skipping or creating temporary map for unhandled element type: {element.get('type')}")
        action = element.get("action", {})
        next_elem = action.get("nextElementId")
        next_combined_id = f"{d_id}_{next_elem}" if next_elem else None

        return {
            "id": f"{d_id}_{e_id}",
            "dialog_id": d_id,             
            "macro_type": "UNKNOWN",          
            "specific_type": element.get("type", "UNKNOWN"),
            "content": {"body": "Unhandled Element"},
            "next_element": next_combined_id, 
            "attributes_used": [],
            "attributes_defined": []
        }

    def _inline_component(self, comp_json, parent_node_id, parent_next_element):
        comp_name = comp_json.get("botRequest", {}).get("name", "UnnamedComponent")
        prefix = f"COMP_{comp_name}"

        self.attributes.update(self._build_attribute(comp_json))
        
        comp_start_map = {}
        start_node_id = None
        for dialog in comp_json.get("dialogRequests", []):
            d_id = dialog["internalId"]
            start_elem = dialog.get("startElementId")
            if not start_elem and dialog.get("elements"):
                start_elem = dialog["elements"][0].get("id")
            if start_elem:
                comp_start_map[d_id] = f"{prefix}_{d_id}_{start_elem}"
                if dialog.get("type") == "DEFAULT" and not start_node_id:
                    start_node_id = comp_start_map[d_id]

        if not start_node_id:
            print(f"Error: No starting point found in component {comp_name}")
            return

        self.G.add_edge(parent_node_id, start_node_id, condition="[Enter Sub-Flow]")

        for dialog in comp_json.get("dialogRequests", []):
            d_id = dialog["internalId"]
            
            for element in dialog.get("elements", []):
                e_id = element["id"]
                elem_type = element["type"]
                
                mapping_function = self.dispatcher.get(elem_type, self.map_unknown)
                if mapping_function.__name__ == "map_get_attribute":
                    mapped_node = mapping_function(d_id, e_id, element, attributes_dict=self.attributes)
                else:
                    mapped_node = mapping_function(d_id, e_id, element)
                
                comp_node_id = f"{prefix}_{mapped_node.pop('id')}"
                mapped_node["dialog_name"] = f"[Component] {comp_name}"
                
                comp_next_element = mapped_node.pop("next_element", None)
                if comp_next_element:
                    comp_next_element = f"{prefix}_{comp_next_element}"
                
                comp_transitions = mapped_node.pop("transitions", [])

                if mapped_node.get("specific_type") == "CLOSE_SESSION":
                    mapped_node["macro_type"] = "ACTION"
                    mapped_node["specific_type"] = "COMPONENT_RETURN"
                    comp_next_element = parent_next_element

                self.G.add_node(comp_node_id, **mapped_node)

                if comp_next_element:
                    self.G.add_edge(comp_node_id, comp_next_element, condition="[Auto]")
                
                # Centralized transition processing for component internal nodes
                self._process_transitions(comp_node_id, mapped_node, comp_transitions, prefix=prefix, comp_start_map=comp_start_map)

    def process_all_elements(self):
        self.G = nx.MultiDiGraph()
        self._build_entry_point_and_intents()
        self._build_nodes_and_edges()

    def _build_entry_point_and_intents(self):
        self.G.add_node(
            "USER_ENTRY",
            dialog_id="GLOBAL",
            macro_type="USER_ENTRY",
            specific_type="INTENT_RECOGNITION",
            content={"description": "User opens WhatsApp or sends initial message"},
            dialog_name="Chat Start"
        )

        for dialog in self.data.get("dialogRequests", []):
            d_id = dialog["internalId"]
            start_elem = dialog.get("startElementId")
            
            if not start_elem:
                continue
                
            target_node = f"{d_id}_{start_elem}"
            intent_id = dialog.get("intentId")
            phrases = []
            intent_name = "Unknown"
            
            if intent_id and intent_id in self.intents:
                intent_data = self.intents[intent_id]
                phrases = intent_data.get("phrases", [])
                intent_name = intent_data.get("name", "Unknown")

            if dialog.get("type") == "DEFAULT":
                edge_data = {
                    "condition_type": "DEFAULT",
                    "condition": "[Any other input]",
                    "phrases": phrases
                }
                self.G.add_edge("USER_ENTRY", target_node, **edge_data)
            elif intent_id and phrases:
                edge_data = {
                    "condition_type": "INTENT",
                    "intent_name": intent_name,
                    "phrases": phrases
                }
                self.G.add_edge("USER_ENTRY", target_node, **edge_data)

    def _build_nodes_and_edges(self):
        for dialog in self.data.get("dialogRequests", []):
            dialog_id = dialog["internalId"]
            dialog_name = dialog.get("name", "Unnamed Dialog")

            for element in dialog.get("elements", []):
                element_id = element["id"]
                element_type = element["type"]

                mapping_function = self.dispatcher.get(element_type, self.map_unknown)
                if mapping_function.__name__ == "map_get_attribute":
                    mapped_node = mapping_function(dialog_id, element_id, element, attributes_dict=self.attributes)
                else:
                    mapped_node = mapping_function(dialog_id, element_id, element)

                mapped_node["dialog_name"] = dialog_name
                
                node_id = mapped_node.pop("id")
                next_element = mapped_node.pop("next_element", None)
                transitions = mapped_node.pop("transitions", [])
                
                self.G.add_node(node_id, **mapped_node)

                if mapped_node.get("specific_type") == "COMPONENT":
                    comp_id = mapped_node.get("content", {}).get("component_sender")
                    
                    if comp_id and comp_id in self.components_jsons:
                        comp_json_data = self.components_jsons[comp_id]
                        self._inline_component(comp_json_data, node_id, next_element)
                        
                        # SMART PRUNING (Type 1 - Component System Fallback)
                        next_element = None
                        transitions = []
                        print(f"[SMART PRUNING] Container-level system fallback omitted on component '{node_id}'.")
                    else:
                        print(f"[WARNING] JSON not found for component ID: {comp_id}")
                
                if next_element:
                    self.G.add_edge(node_id, next_element, condition="[Auto]")
                
                # Centralized transition processing for main graph nodes
                self._process_transitions(node_id, mapped_node, transitions)

    def _build_keyword(self):
        keywords = {}
        for kw in self.data.get("keywordRequests", []):
            kw_id = kw["internalId"]
            kw_name = kw.get("name", f"Keyword_{kw_id}")
            synonyms = kw.get("synonyms", {}).get("data", [])
            keywords[kw_id] = {"name": kw_name, "synonyms": synonyms}
        return keywords
    
    def _build_intent(self):
        intents = {}
        for intent in self.data.get("intentRequests", []):
            intent_id = intent["internalId"]
            training_phrases = intent.get("phrases", [])
            intents[intent_id] = {"name": intent.get("name", "Unknown intent"), "phrases": training_phrases}
        return intents

    def _build_attribute(self, json_source=None):
        if json_source is None:
            json_source = self.data
        attributes = {}
        for attr in json_source.get("attributeRequests", []):
            attr_id = str(attr["internalId"]) 
            attributes[attr_id] = {
                "name": attr.get("name", f"Var_{attr_id}"),
                "type": attr.get("dataType", "UNKNOWN"),
                "scope": attr.get("scope", "LOCAL"),
                "sensitive": attr.get("sensitive", False),
                "visible_to_agent": attr.get("visibleToAgent", False)
            }
        return attributes