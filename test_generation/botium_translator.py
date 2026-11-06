import json
import re
import rstr
from importlib.resources import path
from test_generation.utils.costraints_solver import solve_conjunction

class BotiumTranslator:
    def __init__(self, nodes_dict, mock_data=None, attributes=None):
        # Dictionary to store all discovered bursts: { "BURST_ID": ["phrase 1", "phrase 2"] }
        self.global_utterances = {}
        self.nodes = nodes_dict
        raw_mock = mock_data or {}
        self.mock_registry = raw_mock.get("DATATYPE_MOCKS", raw_mock)
        self.attributes = attributes or {}

    def collect_conditions(self, logic_tree):
        """
        Flattens a logic tree into the list of (attribute_id, operator, target_value) that
        must hold for the tree to be true. AND keeps every branch; OR keeps the first one.
        """
        if not logic_tree:
            return []

        node_type = logic_tree.get("type")

        # Base Case: We found the leaf with the actual condition
        if node_type == "ATTRIBUTE_COMPARE":
            return [(
                str(logic_tree.get("attributeId")),
                logic_tree.get("operator"),
                logic_tree.get("value"),
            )]

        # Recursive Case: It's a logical block (AND/OR), dive deeper
        if node_type == "LOGICAL":
            operator = logic_tree.get("operator")
            conditions = logic_tree.get("conditions", [])

            if operator == "AND":
                collected = []
                for sub_cond in conditions:
                    collected.extend(self.collect_conditions(sub_cond))
                return collected

            if operator == "OR" and conditions:
                # For OR, we can choose the first valid branch to satisfy the condition
                #TODO: Multiple OR branches could be explored for more comprehensive test coverage
                return self.collect_conditions(conditions[0])

        return []

    def solve_conditions(self, conditions):
        """
        Turns (attribute_id, operator, target_value) conditions into one value per attribute.
        Conditions on the same attribute are solved together, so the value satisfies all of them.
        Returns a dictionary of constraints, e.g., {"130528": "Ficus"}.
        """
        conditions_by_attribute = {}
        for attr_id, operator, target_value in conditions:
            conditions_by_attribute.setdefault(attr_id, []).append((operator, target_value))

        constraints = {}
        for attr_id, attribute_conditions in conditions_by_attribute.items():
            data_type = self.attributes.get(attr_id, {}).get("type", "TEXT")
            mock_value = self.mock_registry.get(data_type, {}).get("valid", None)

            # Use the constraint solver to generate a valid value for this attribute
            constraints[attr_id] = solve_conjunction(attribute_conditions, data_type, mock_value)

        return constraints

    def extract_constraints_from_logic_tree(self, logic_tree):
        """
        Extracts attribute constraints from a logic tree.
        Returns a dictionary of constraints, e.g., {"130528": "Ficus"}.
        """
        return self.solve_conditions(self.collect_conditions(logic_tree))

    def pre_scan_path_constraints(self, path):
        """
        Search ahead through the path to collect future constraints.
        Returns a dictionary, e.g., {"130528": "Ficus"} specific to this test.
        Every EVALUATION edge of the path contributes: when two of them constrain the same
        attribute, the value is chosen to satisfy both.
        """
        conditions = []
        for step in path:
            edge = step["edge_data"]
            if edge and edge.get("condition_type") == "EVALUATION":
                conditions.extend(self.collect_conditions(edge.get("logic_tree", {})))

        return self.solve_conditions(conditions)

    def get_message(self, node_data, node_id, session_variables=None):
        """Extracts the visible text from the bot's response node."""
        session_variables = session_variables or {}
        macro_type = node_data.get("macro_type")
        spec_type = node_data.get("specific_type")
        content = node_data.get("content", {})

        if macro_type == "SEND_MESSAGE":
            if spec_type == "TEXT":
                msgs = content.get("messages_list", [])
                if not msgs:
                    return None

                # Clean the messages by replacing attribute placeholders with actual values from path_constraints
                cleaned_msgs = []
                for msg in msgs:
                    temp_msg = msg
                    # 1. Replace variables if their current runtime value is known in the session
                    for key, value in session_variables.items():
                        pattern = r'\{\{\s*' + re.escape(str(key)) + r'\s*\}\}'
                        # A replacement function (not a raw string) sidesteps re.sub's own
                        # backreference syntax: a session value containing "\d", "\1" or "\g<x>"
                        # (e.g. mock data for a vCard or a value generated from a regex) would
                        # otherwise crash re.sub or get silently reinterpreted as an escape.
                        temp_msg = re.sub(pattern, lambda _match, v=value: str(v), temp_msg)

                    # Convert remaining (unknown) variables to a wildcard '*' for Botium loose matching
                    temp_msg = re.sub(r'\{\{.*?\}\}', '*', temp_msg)
                    cleaned_msgs.append(temp_msg)

                # If there's only one message, return it as a standard text string; if multiple, create an Utterance reference
                if len(cleaned_msgs) == 1:
                    return cleaned_msgs[0]
                else:
                    utt_name = f"UTT_NODE_{node_id}"
                    self.global_utterances[utt_name] = cleaned_msgs
                    return utt_name
            
            elif spec_type == "JSON":
                payload = content.get("payload", {})
                json_string = json.dumps(payload, separators=(',', ':'))
                
                for attr_id, val in session_variables.items():
                    # Find and replace the specific attribute placeholder with its corresponding value
                    pattern = r'\{\{\s*' + re.escape(str(attr_id)) + r'\s*\}\}'
                    # See the TEXT branch above: a replacement function avoids re.sub
                    # reinterpreting backslashes inside `val` as its own escape syntax.
                    json_string = re.sub(pattern, lambda _match, v=val: str(v), json_string)

                json_string = re.sub(r'\{\{.*?\}\}', '*', json_string)
                return json_string
                
        elif macro_type == "RECEIVE_INPUT":
            if spec_type == "CSAT":
                return content.get("question", "")
            elif spec_type == "GET_ATTRIBUTE":
                questions = content.get("questions", [])
                if not questions:
                    return None
                
                # Clean the questions by replacing attribute placeholders with session_variables
                cleaned_questions = []
                for q in questions:
                    temp_q = q
                    for attr_id, value in session_variables.items():
                        # Find and replace the specific attribute placeholder with its corresponding value
                        pattern = r'\{\{\s*' + re.escape(str(attr_id)) + r'\s*\}\}'
                        # See get_message's TEXT branch: a replacement function avoids re.sub
                        # reinterpreting backslashes inside `value` as its own escape syntax.
                        temp_q = re.sub(pattern, lambda _match, v=value: str(v), temp_q)

                    temp_q = re.sub(r'\{\{.*?\}\}', '*', temp_q)
                    cleaned_questions.append(temp_q)

                # Generate an utterance if there are multiple variants for the question
                if len(cleaned_questions) == 1:
                    return cleaned_questions[0]
                else:
                    utt_name = f"UTT_QUESTION_{node_id}"
                    self.global_utterances[utt_name] = cleaned_questions
                    return utt_name

        # ACTION, DELAY, or routing nodes do not produce visible text
        return None

    def get_user_input(self, edge_data, source_node_data, path_constraints):
        """Translates the graph edge into a textual #me input for Botium dynamically."""
        if not edge_data:
            return None
            
        c_type = edge_data.get("condition_type", "")

        if source_node_data:
            spec_type = source_node_data.get("specific_type")
            
            # Handling component-specific default inputs to prevent validation errors
            if c_type in ["AUTO", "[Auto]", "DEFAULT", "Enter Sub-Flow", "EVALUATION"] or edge_data.get("condition") == "[Auto]": 

                
                    if spec_type == "CSAT":
                        return "4"  # Default valid CSAT score
        
                    if spec_type == "GET_ATTRIBUTE":
                        attrs = source_node_data.get("attributes_defined", [])
                        data_type = source_node_data.get("data_type", "TEXT")
                        content = source_node_data.get("content", {})
                        regex_pattern = content.get("validation_regex")

                        if attrs:
                            attr_id = str(attrs[0])
                        
                            # Check if a specific constraint was extracted earlier in the path; if so, use it
                            if attr_id in path_constraints:
                                return path_constraints[attr_id]

                            if regex_pattern:
                                try:
                                    return rstr.xeger(regex_pattern)
                                except Exception as e:
                                    print(f"Error generating string from regex '{regex_pattern}': {e}")
                                    return f"Generic_Text_{attr_id}"
                            
                            # Retrieve the valid mock value for this data type from the mock registry
                            mock_value = self.mock_registry.get(data_type).get("valid", None)
                            
                            # If no specific mock value exists, return a generic placeholder for the attribute
                            return mock_value or f"Generic_Text_{attr_id}"

        if c_type == "KEYWORD_COMPARE":
            synonyms = edge_data.get("synonyms", [])
            kw_name = edge_data.get("keyword_name")
            kw_id = str(edge_data.get("keywordId"))

            if synonyms:
                return synonyms[0]
            elif kw_name:
                return kw_name
            else:
                # Use the first available synonym, otherwise a placeholder
                return f"Keyword_{kw_id}"
            
        elif c_type == "INTENT":
            phrases = edge_data.get("phrases", [])
            return phrases[0] if phrases else "Hello"
            
        elif c_type == "FALLBACK":
            # Invalid input to trigger fallback even if regex validation is present
            return "INVALID_INPUT_!@#_123"
            
        elif c_type == "DEFAULT":
            phrases = edge_data.get("phrases", [])
            if phrases:
                return phrases[0]
            else:
                return "default"
            
        elif c_type == "TIMEOUT":
            # Retrieve the configured timeout duration from the parser's edge metadata.
            # The parser saves it as "duration" in the edge_data dictionary.
            timeout_seconds = edge_data.get("duration", 20) 
            
            # Convert to milliseconds for Botium's #pause command
            timeout_ms = timeout_seconds * 1000
            
            return f"PAUSE {timeout_ms}"

        # [Auto] edges and EVALUATION nodes do not require user input
        return None

    def translate_path(self, path, path_index):
        """
        Translates a graph path into a Botium script.
        Acts as the main orchestrator, delegating logic extraction and text formatting.
        """
        # 1. Pre-calculate path constraints for deterministic routing
        path_constraints = self.pre_scan_path_constraints(path)
        
        # 2. Logic Extraction: Process the path and build conversational turns
        turns = self._process_path_logic(path, path_constraints)
        
        # 3. Syntax Formatting: Convert logical turns into Botium syntax rules
        return self._format_botium_script(turns, path_index)

    def _process_path_logic(self, path, path_constraints):
        """
        Iterates through the path, handling turn-taking, CSAT loops, and error/timeout injections.
        Returns a structured list of conversational turns.
        """
        turns = []
        current_turn = {"user": None, "bot_responses": []}

        # Session Tracker: Maintain a dictionary of session variables to simulate stateful interactions
        session_variables = {}

        for step in path:
            edge = step["edge_data"]
            target_data = step["target_data"]
            source_data = self.nodes.get(step["source"]) if step["source"] else None

            source_skipped = False
            if source_data and source_data.get("specific_type") == "GET_ATTRIBUTE":
                if source_data.get("content", {}).get("skip_if_filled"):
                    attrs = source_data.get("attributes_defined", [])
                    if attrs and str(attrs[0]) in session_variables:
                        source_skipped = True

            if source_skipped:
                user_action = None
            else:
                user_action = self.get_user_input(edge, source_data, path_constraints)
            
           # SESSION TRACKER UPDATE: If the user just typed an input for an attribute, 
            # save it in the short-term memory so the bot can print it later.
            if user_action and source_data and source_data.get("specific_type") == "GET_ATTRIBUTE":
                attrs = source_data.get("attributes_defined", [])
                if attrs:
                    attr_id = str(attrs[0])
                    attr_name = self.attributes.get(attr_id, {}).get("name")
                    if attr_name:
                        session_variables[attr_name] = user_action
                    session_variables[attr_id] = user_action

            # Turn-taking management: close the current turn if a new user action occurs
            if user_action:
                if current_turn["bot_responses"] or current_turn["user"]:
                    turns.append(current_turn)
                current_turn = {"user": user_action, "bot_responses": []}

            # --- NATIVE CSAT MULTI-TURN MANAGEMENT ---
            # Check if the user successfully exits a CSAT node
            if source_data and source_data.get("specific_type") == "CSAT" and edge and edge.get("condition_type") in ["AUTO", "[Auto]", "DEFAULT"]:
                csat_content = source_data.get("content", {})
                feedback_q = csat_content.get("feedback_question")
                thank_you = csat_content.get("thank_you_message")
                
                # 1. Feedback Loop: Simulate user providing textual feedback
                if feedback_q:
                    current_turn["bot_responses"].append(feedback_q)
                    turns.append(current_turn)
                    
                    # Fetch the dynamic mock data for the feedback loop
                    mock_feedback_text = self.mock_registry.valid_value("csat_feedback", default="Great support, thank you!")
                    current_turn = {"user": mock_feedback_text, "bot_responses": []}
                
                # 2. Closure: Append thank you message to close the CSAT lifecycle
                if thank_you:
                    current_turn["bot_responses"].append(thank_you)

            # --- ERROR AND TIMEOUT INJECTION ---
            # Handle courtesy repeat messages, fallback messages, and timeouts
            if edge:
                c_type = edge.get("condition_type", "")
                
                if c_type == "FALLBACK":
                    # Retrieve fallback data extracted from the parser
                    source_content = source_data.get("content", {}) if source_data else {}
                    repeat_count = source_content.get("repeat_count", 0)
                    repeat_msgs = source_content.get("repeat_messages", [])
                    fallback_msgs = edge.get("messages_list", [])

                    # CSAT uses 'fallback_message' instead of the standard list
                    csat_fallback = source_content.get("fallback_message")
                    if csat_fallback and not repeat_msgs:
                        repeat_msgs = [csat_fallback]
                    
                    # 1. REPEAT CYCLE (User makes consecutive mistakes)
                    for _ in range(repeat_count):
                        if repeat_msgs:    
                            # If multiple variants exist, create an Utterance reference
                            if len(repeat_msgs) > 1:
                                utt_name = f"UTT_REPEAT_{step['source']}"
                                self.global_utterances[utt_name] = repeat_msgs
                                current_turn["bot_responses"].append(utt_name)
                            else:
                                current_turn["bot_responses"].append(repeat_msgs[0])
                        
                        turns.append(current_turn)
                        # Prepare input for the next incorrect attempt
                        current_turn = {"user": user_action, "bot_responses": []}
                    
                    # 2. DEFINITIVE FALLBACK (Attempts exhausted)
                    if fallback_msgs:
                        if len(fallback_msgs) > 1:
                            utt_name = f"UTT_FALLBACK_{step['source']}"
                            self.global_utterances[utt_name] = fallback_msgs
                            current_turn["bot_responses"].append(utt_name)
                        else:
                            current_turn["bot_responses"].append(fallback_msgs[0])

                elif c_type == "TIMEOUT":
                    timeout_msgs = edge.get("messages_list", [])
                    if timeout_msgs:
                        if len(timeout_msgs) > 1:
                            utt_name = f"UTT_TIMEOUT_{step['source']}"
                            self.global_utterances[utt_name] = timeout_msgs
                            current_turn["bot_responses"].append(utt_name)
                        else:
                            current_turn["bot_responses"].append(timeout_msgs[0])
                            
            target_skipped = False
            if target_data and target_data.get("specific_type") == "GET_ATTRIBUTE":
                if target_data.get("content", {}).get("skip_if_filled"):
                    attrs = target_data.get("attributes_defined", [])
                    if attrs and str(attrs[0]) in session_variables:
                        target_skipped = True

            # If the next node is skipped due to a filled attribute, we don't want to generate a bot message for it. Otherwise, fetch the bot's response from the target node.
            if target_skipped:
                bot_msg = None
            else:
                target_node_id = step.get("target", "UNKNOWN")
                bot_msg = self.get_message(target_data, target_node_id, session_variables)

            # Handle special cases like Webhook nodes that require a wait time before the bot responds
            if source_data and source_data.get("specific_type") == "WEBHOOK":
                timeout_sec = source_data.get("content", {}).get("timeout_duration", 10)
                timeout_ms = (timeout_sec + 2) * 1000 
                current_turn["bot_responses"].append(f"WAITFORBOT {timeout_ms}")

            if bot_msg:
                current_turn["bot_responses"].append(bot_msg)

        # Close the last pending turn after the loop finishes
        if current_turn["bot_responses"] or current_turn["user"]:
            turns.append(current_turn)
            
        return turns

    def _format_botium_script(self, turns, path_index):
        """
        Takes the logical turns and formats them strictly according to Botium's syntax rules.
        Handles Markdown stripping, wildcard insertion, and system labels mapping.
        """
        convo_name = f"Test_Path_{path_index}"
        convo_lines = [f"{convo_name}\n"]

        for turn in turns:
            if turn["user"]:
                user_text = str(turn["user"]).strip()
                
                # System commands handling: print standalone without the #me tag
                if user_text.startswith("PAUSE"):
                    convo_lines.append(f"{user_text}\n")
                else:
                    convo_lines.append(f"#me\n{user_text}\n")
                        
            responses = turn["bot_responses"]
            
            for response in responses:
                # System label references remain plain text to allow Utterance expansion
                if response.startswith("UTT_"):
                    convo_lines.append(f"#bot\n{response}\n")
                elif response.startswith("WAITFORBOT"):
                    convo_lines.append(f"{response}\n")
                else:
                    # Clean the response text to ensure it doesn't have unwanted newlines or excessive spaces
                    clean_response = re.sub(r'[\r\n]+', '*', response)
                    clean_response = re.sub(r' +', ' ', clean_response).strip()

                    # Remove any leading or trailing wildcards that may have been introduced during cleaning
                    clean_response = re.sub(r'\s+\*', '*', clean_response)
                    clean_response = re.sub(r'\*\s+', '*', clean_response)
                    
                    # Wrap standard text in wildcards for resilient pattern matching
                    raw_formatted = f"*{clean_response}*"
                    clean_response = re.sub(r'\*+', '*', raw_formatted)

                    convo_lines.append(f"#bot\n{clean_response}\n")
        
        return "\n".join(convo_lines)

    def get_utterances_files(self):
        """
        Generates individual utterance files to completely bypass Botium's block-parsing bugs.
        Returns a dictionary mapping filenames to their textual content.
        """
        files_dict = {}
        
        for utt_name, phrases in self.global_utterances.items():
            clean_name = utt_name.strip()
            # La prima riga è il nome dell'etichetta
            lines = [clean_name]
            
            for phrase in phrases:
                # Pulizia degli a capo e aggiunta wildcards
                clean_phrase = re.sub(r'[\r\n]+', ' ', phrase).strip()
                lines.append(f"*{clean_phrase}*")
            
            # Creiamo un file dedicato per ogni etichetta
            file_name = f"{clean_name}.utterances.txt"
            files_dict[file_name] = "\n".join(lines) + "\n"
            
        return files_dict
