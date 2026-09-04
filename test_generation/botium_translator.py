import hashlib
import json
import re
from importlib.resources import path

from matplotlib.pyplot import step

class BotiumTranslator:
    def __init__(self, nodes_dict, mock_data=None):
        # Dictionary to store all discovered bursts: { "BURST_ID": ["phrase 1", "phrase 2"] }
        self.global_utterances = {}
        self.nodes = nodes_dict
        self.mock_data = mock_data or {}


    def extract_constraints_from_logic_tree(self, logic_tree):
        """
        Search recursively through the logic tree to extract attribute constraints.
        Returns a dictionary of constraints, e.g., {"130528": "Ficus"}.
        """
        constraints = {}
        if not logic_tree:
            return constraints

        node_type = logic_tree.get("type")

        # Caso Base: Abbiamo trovato la foglia con la condizione vera e propria!
        if node_type == "ATTRIBUTE_COMPARE":
            attr_id = str(logic_tree.get("attributeId"))
            operator = logic_tree.get("operator")
            value = logic_tree.get("value")

            # Per operatori di uguaglianza, salviamo esattamente il valore richiesto
            if operator in ["EQUAL", "CONTAINS", "STARTS_WITH", "ENDS_WITH"]:
                constraints[attr_id] = value
                
            # (Opzionale) Se hai operatori matematici in futuro, puoi gestirli qui
            elif operator in ["GREATER_THAN", "GREATER_OR_EQUAL"]:
                try: constraints[attr_id] = str(int(value) + 1)
                except: constraints[attr_id] = value
            elif operator in ["LESS_THAN", "LESS_OR_EQUAL"]:
                try: constraints[attr_id] = str(int(value) - 1)
                except: constraints[attr_id] = value

        # Caso Ricorsivo: È un blocco logico (AND/OR), dobbiamo scendere più a fondo
        elif node_type == "LOGICAL":
            for sub_cond in logic_tree.get("conditions", []):
                sub_constraints = self.extract_constraints_from_logic_tree(sub_cond)
                # Uniamo i vincoli trovati nei rami sottostanti
                constraints.update(sub_constraints)

        return constraints

    def pre_scan_path_constraints(self, path):
        """
        Search ahead through the path to collect future constraints.
        Returns a dictionary, e.g., {"130528": "Ficus"} specific to this test.
        """
        path_constraints = {}
        for step in path:
            edge = step["edge_data"]
            if edge and edge.get("condition_type") == "EVALUATION":
                logic_tree = edge.get("logic_tree", {})
                extracted = self.extract_constraints_from_logic_tree(logic_tree)
                path_constraints.update(extracted)
                
        return path_constraints

    def get_message(self, node_data, path_constraints=None):
        """Extracts the visible text from the bot's response node."""
        path_constraints = path_constraints or {}
        macro_type = node_data.get("macro_type")
        spec_type = node_data.get("specific_type")
        content = node_data.get("content", {})

        if macro_type == "SEND_MESSAGE":
            if spec_type == "TEXT":
                msgs = content.get("messages_list", [])
                if msgs:
                    msg = msgs[0]
                    for attr_id, value in path_constraints.items():
                        msg = re.sub(r'\{\{.*?\}\}', value, msg)

                    msg = re.sub(r'\{\{.*?\}\}', '', msg)
                return msg
            
            elif spec_type == "JSON":
                payload = content.get("payload", {})
                json_string = json.dumps(payload, separators=(',', ':'))
                
                for attr_id, val in path_constraints.items():
                    json_string = re.sub(r'\{\{.*?\}\}', val, json_string)
                    
                json_string = re.sub(r'\{\{.*?\}\}', '*', json_string)
                return json_string
                
        elif macro_type == "RECEIVE_INPUT":
            if spec_type == "CSAT":
                return content.get("question", "")
            elif spec_type == "GET_ATTRIBUTE":
                questions = content.get("questions", [])
                return questions[0] if questions else None
            elif spec_type == "WHATSAPP_LOCATION_REQUEST":
                body = content.get("body", [])
                return body[0] if body else None

        # ACTION, DELAY, or routing nodes do not produce visible text
        return None

    def get_user_input(self, edge_data, source_node_data, path_constraints):
        """Translates the graph edge into a textual #me input for Botium."""
        if not edge_data:
            return None
            
        c_type = edge_data.get("condition_type", "")

        if source_node_data:
            spec_type = source_node_data.get("specific_type")
            if c_type in ["AUTO", "[Auto]", "DEFAULT"] or edge_data.get("condition") == "[Auto]": 
        
                if spec_type == "GET_ATTRIBUTE":
                    attrs = source_node_data.get("attributes_defined", [])
                    if attrs:
                        attr_id = str(attrs[0])

                        if attr_id in path_constraints:
                            return path_constraints[attr_id]

                        elif attr_id in self.mock_data:
                            return self.mock_data[attr_id]

                        else:
                            return f"Generic_Value_For_Var_{attr_id}"
                    return "Generic_Text_Input"

        if c_type == "KEYWORD_COMPARE":
            synonyms = edge_data.get("synonyms", [])
            kw_name = edge_data.get("keyword_name")
            kw_id = str(edge_data.get("keywordId"))

            if synonyms:
                return synonyms[0]
            elif kw_name:
                return kw_name
            elif kw_id in self.mock_data:
                            return self.mock_data[kw_id]
            else:
            # Use the first available synonym, otherwise a placeholder
                return f"Keyword_{kw_id}"
            
        elif c_type == "INTENT":
            phrases = edge_data.get("phrases", [])
            return phrases[0] if phrases else "Hello"
            
        elif c_type == "FALLBACK":
            return "Test_Invalid_Input_For_Fallback"
            
        elif c_type == "DEFAULT":
            return "Any random string"
            
        elif c_type == "TIMEOUT":
            # Botium will wait silently. We use None to skip the #me statement.
            return None 

        # [Auto] edges and EVALUATION nodes do not require user input
        return None

    def translate_path(self, path, path_index):
        """
        Translates a single path into text for the .convo.txt file.
        """
        path_constraints = self.pre_scan_path_constraints(path)

        turns = []
        current_turn = {"user": None, "bot_responses": []}

        for step in path:
            edge = step["edge_data"]
            target_data = step["target_data"]
            source_data = self.nodes.get(step["source"]) if step["source"] else None

            user_action = self.get_user_input(edge, source_data, path_constraints)
            
            if user_action:
                if current_turn["bot_responses"] or current_turn["user"]:
                    turns.append(current_turn)
                current_turn = {"user": user_action, "bot_responses": []}

            bot_msg = self.get_message(target_data, path_constraints)
            if bot_msg:
                current_turn["bot_responses"].append(bot_msg)

        if current_turn["bot_responses"] or current_turn["user"]:
            turns.append(current_turn)

        convo_name = f"Test_Path_{path_index}"
        convo_lines = [f"{convo_name}\n"]

        for turn in turns:
            if turn["user"]:
                convo_lines.append(f"#me\n{turn['user']}\n")
                
            for response in turn["bot_responses"]:
                clean_response = response.strip()
                clean_response = re.sub(r' +', ' ', clean_response)

                raw_formatted = f"*{clean_response}*"
                clean_response = re.sub(r'\*+', '*', raw_formatted)

                convo_lines.append(f"#bot\n{clean_response}\n")

        return "\n".join(convo_lines)



    def generate_utterances_file(self):
        """Generates the content for the bursts.utterances.txt file."""
        lines = []
        for burst_name, phrases in self.global_utterances.items():
            lines.append(burst_name)
            for phrase in phrases:
                # Format the phrase with asterisks and clean up any redundant asterisks
                raw_formatted = f"*{phrase}*"
                clean_phrase = re.sub(r'\*+', '*', raw_formatted)
                lines.append(clean_phrase)
            lines.append("") 
            
        return "\n".join(lines)