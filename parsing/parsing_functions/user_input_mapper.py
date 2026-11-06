from parsing.parsing_utils import extract_placeholders

def extract_common_input_logic(d_id, action):
    """
    Private helper function. 
    Extracts shared logic from all input nodes: Fallback, Timeout, and Repeat.
    Returns transitions and base content data.
    """
    fallback = action.get("fallback", {})
    repeat = action.get("repeat", {})
    timeout = action.get("timeout", {})
    timeout_fallback = action.get("timeoutFallback", {})

    transitions = []

    # Fallback processing
    fallback_action = fallback.get("fallbackAction", "UNKNOWN")
    fallback_edge_data = {
        "condition_type": "FALLBACK",
        "action": fallback_action
    }

    fallback_messages = [msg.get("text", "") for msg in fallback.get("messages", []) if msg.get("text")]
    if fallback_messages:
        fallback_edge_data["messages_list"] = fallback_messages
        
    if fallback_action == "GO_TO_DIALOG":
        target_dialog = fallback.get("goToDialogId")
        if target_dialog:
            fallback_edge_data["target_dialog_id"] = target_dialog
            transitions.append({
                "target": f"{target_dialog}_1",
                "edge_data": fallback_edge_data
            })
    
    # Timeout fallback processing
    if timeout.get("isEnabled", False) and timeout_fallback:    
        t_action = timeout_fallback.get("fallbackAction", "UNKNOWN")
        t_duration = timeout.get("durationSeconds", 0)

        timeout_edge_data = {
            # This classification is not in the JSON, but is used internally to distinguish edge types
            "condition_type": "TIMEOUT",
            "action": t_action,
            "duration": t_duration
        }

        # Save timeout fallback messages
        t_msgs = [msg.get("text", "") for msg in timeout_fallback.get("messages", []) if msg.get("text")]
        if t_msgs:
            timeout_edge_data["messages_list"] = t_msgs
        
        if t_action == "GO_TO_DIALOG":
            t_target_dialog = timeout_fallback.get("goToDialogId")
            if t_target_dialog:
                timeout_edge_data["target_dialog_id"] = t_target_dialog
                transitions.append({
                    "target": f"{t_target_dialog}_1",
                    "edge_data": timeout_edge_data
                }) 
    
    repeat_count = repeat.get("count", 0)
    repeat_messages = [msg.get("text", "") for msg in repeat.get("messages", []) if msg.get("text")]

    common_content = {
        "repeat_count": repeat_count,
        "repeat_messages": repeat_messages,
        "timeout_enabled": timeout.get("isEnabled", False),
        "timeout_duration": timeout.get("durationSeconds", 0)
    }

    next_elem = action.get("nextElementId")
    next_combined_id = f"{d_id}_{next_elem}" if next_elem else None

    return transitions, common_content, next_combined_id

def map_process_user_input(d_id, e_id, element):
    """
    Mapping submodule for the PROCESS_USER_INPUT macro category.  
    Extracts routing logic and fallbacks to prepare edge transitions.
    """
    action = element.get("action", {})
    transitions, content, _ = extract_common_input_logic(d_id, action)
    rules = action.get("rules", [])

    content["nlpEnabled"] = action.get("nlpEnabled", False)

    for rule in rules:
        target_id = rule.get("nextElementId")
        if not target_id:
            continue
        
        condition = rule.get("condition", {})
        condition_type = condition.get("type", "UNKNOWN")
        
        edge_data = {"condition_type": condition_type}
        
        # If it is a Keyword rule
        if condition_type == "KEYWORD_COMPARE":
            edge_data["keywordId"] = condition.get("keywordId")
            
        edge = {
            "target": f"{d_id}_{target_id}",
            "edge_data": edge_data
        }
        transitions.append(edge)
        
    # Extract dynamic variables from fallback/timeout/repeat messages
    attr_used = extract_placeholders(content)
    
    return {
        "id": f"{d_id}_{e_id}",
        "dialog_id": d_id,
        "macro_type": "RECEIVE_INPUT",
        "specific_type": "PROCESS_USER_INPUT",  # Logical routing node
        "content": content,
        "transitions": transitions, 
        "attributes_used": attr_used,       
        "attributes_defined": [],   
    }

def map_get_attribute(d_id, e_id, element, attributes_dict=None):
    """
    Maps the GET_ATTRIBUTE component used for requesting explicit variable input.
    """
    if attributes_dict is None:
        attributes_dict = {}

    action = element.get("action", {})
    transitions, content, next_combined_id = extract_common_input_logic(d_id, action)

    # Add specific Get Attribute logic
    content["questions"] = [q.get("text", "") for q in action.get("questions", []) if q.get("text")]

    # Extraction of attributes for regex validation and skip if attributes is filled value
    custom_validation = action.get("customValidation", False)
    content["validation_regex"] = action.get("customValidationRegex", "") if custom_validation else None
    content["skip_if_filled"] = action.get("skipIfAttributeFilled", False)
    
    attr_defined = []
    attr_id = action.get("attributeId")
    data_type = "TEXT"

    if attr_id:
        str_attr_id = str(attr_id)
        attr_defined.append(str_attr_id)

        if str_attr_id in attributes_dict:
            data_type = attributes_dict[str_attr_id].get("type", "TEXT")

    # Extract dynamic variables from questions and fallback/repeat messages
    attr_used = extract_placeholders(content)

    return {
        "id": f"{d_id}_{e_id}",
        "dialog_id": d_id,
        "macro_type": "RECEIVE_INPUT",
        "specific_type": "GET_ATTRIBUTE",
        "content": content,
        "next_element": next_combined_id,
        "transitions": transitions, 
        "data_type": data_type,
        "attributes_used": attr_used,       
        "attributes_defined": attr_defined,
    }

def map_csat(d_id, e_id, element):
    """
    Maps the CSAT (Customer Satisfaction) scoring component.
    Unlike standard input nodes, CSAT has a hardcoded lifecycle (1 retry limit),
    supports an optional secondary multi-turn feedback loop, and handles dynamic scales.
    """
    action = element.get("action", {})
    
    # Extracting all specific CSAT fields, including the optional feedback loop
    content = {
        "question": action.get("scoringQuestion", "").strip(),
        "scale_type": action.get("scale", "SCORING_1_5"),
        "fallback_message": action.get("fallbackMessage", ""),
        "feedback_question": action.get("feedbackQuestion", ""),
        "thank_you_message": action.get("thankYouMessage", ""),
        
        # Hardcoding the native Infobip CSAT lifecycle rules
        "repeat_count": 1,
        "repeat_messages": [] 
    }

    # Extract dynamic variables (e.g., {{username}}) from all text fields
    attr_used = extract_placeholders(content)

    next_elem = action.get("nextElementId")
    next_combined_id = f"{d_id}_{next_elem}" if next_elem else None

    return {
        "id": f"{d_id}_{e_id}",
        "dialog_id": d_id,
        "macro_type": "RECEIVE_INPUT",
        "specific_type": "CSAT",
        "content": content,
        "next_element": next_combined_id,
        "transitions": [], 
        "attributes_used": attr_used,      
        "attributes_defined": []
    }