import hashlib
import json
import re

from parsing.parsing_utils import extract_attrs_from_condition

def map_go_to_dialog(d_id, e_id, element):
    """
    Mapper for the GO_TO_DIALOG component.
    Represents an explicit jump to the beginning of another dialog.
    """
    action = element.get("action", {})
    target_dialog = action.get("dialogId")
    share_attribute_flag = action.get("shareAttributes", False)
    attribute_ids = action.get("attributeIds", [])

    shared_attrs_str = [str(attr) for attr in attribute_ids]
    transitions = []

    # Inject shared attributes into the transition to pass them to the next dialog
    if target_dialog:
        transitions.append({
            "target": f"{target_dialog}_1",
            "edge_data": {
                "action": "GO_TO_DIALOG",
                "target_dialog_id": target_dialog,
                "shared_attributes_ids": shared_attrs_str
            }
        })

    return {
        "id": f"{d_id}_{e_id}",
        "dialog_id": d_id,
        "element_id": e_id,
        "macro_type": "ACTION",
        "specific_type": "GO_TO_DIALOG",
        "content": {
            "target_dialog_id": target_dialog,
            "share_attributes": share_attribute_flag,
            "shared_attribute_ids": shared_attrs_str
        },
        "transitions": transitions,
        "attributes_used": shared_attrs_str,  
        "attributes_defined": []
    }

def map_delay(d_id, e_id, element):
    """
    Mapper for the DELAY component.
    Represents a time pause before proceeding to the next block.
    """
    action = element.get("action", {})
    delay_seconds = action.get("delayInSeconds", 0)
    
    next_elem = action.get("nextElementId")
    next_combined_id = f"{d_id}_{next_elem}" if next_elem else None

    return {
        "id": f"{d_id}_{e_id}",
        "dialog_id": d_id,
        "element_id": e_id,
        "macro_type": "ACTION",
        "specific_type": "DELAY",
        "content": {
            "delay_duration": delay_seconds
        },
        "next_element": next_combined_id,
        "transitions": [],
        "attributes_used": [],
        "attributes_defined": []
    }

def map_close_session(d_id, e_id, element):
    """
    Mapper for the CLOSE_SESSION component.
    Explicitly terminates the conversation.
    """
    return {
        "id": f"{d_id}_{e_id}",
        "dialog_id": d_id,
        "element_id": e_id,
        "macro_type": "ACTION",
        "specific_type": "CLOSE_SESSION",
        "content": {},
        "next_element": None,
        "transitions": [],
        "attributes_used": [],
        "attributes_defined": []
    }

def map_evaluate_attribute(d_id, e_id, element):
    """
    Mapper for the EVALUATE_ATTRIBUTE component.
    Forks the conversational flow based on logic tree variables.
    """
    action = element.get("action", {})
    transitions = []
    attrs_used = [] 

    rules = action.get("rules", [])
    for rule in rules:
        target_id = rule.get("nextElementId")
        if not target_id:
            continue

        rule_name = rule.get("name", "Condition")
        cond_obj = rule.get("condition", {})

        # Extract variables used for evaluation
        rule_attrs = extract_attrs_from_condition(cond_obj)
        attrs_used.extend(rule_attrs)

        edge_data = {
            "condition_type": "EVALUATION",
            "condition": rule_name,
            "logic_tree": cond_obj
        }
        transitions.append({
            "target": f"{d_id}_{target_id}",
            "edge_data": edge_data
        })

    # Default path (Else)
    else_elem = action.get("elseElementId")
    if else_elem:
        transitions.append({
            "target": f"{d_id}_{else_elem}",
            "edge_data": {
                "condition_type": "ELSE",
                "condition": "Else"
            }
        })

    return {
        "id": f"{d_id}_{e_id}",
        "dialog_id": d_id,
        "macro_type": "ACTION",
        "specific_type": "EVALUATE_ATTRIBUTE",
        "content": {},
        "transitions": transitions,
        "attributes_used": list(set(attrs_used)),
        "attributes_defined": []
    }

def map_api_call(d_id, e_id, element):
    """
    Mapper for the API_CALL component.
    Tracks external integrations and variables populated by the response.
    """
    action = element.get("action", {})
    
    content = {
        "url": action.get("url", ""),
        "method": action.get("method", "GET"),
        "timeout": action.get("timeoutSeconds", 0),
        "content_type": action.get("contentType", None)
    }
    
    attrs_defined = []
    
    # Status Code
    if action.get("responseCodeAttributeId"):
        attrs_defined.append(str(action.get("responseCodeAttributeId")))
        
    # Headers
    for h_attr in action.get("collectHeaderAttributes", []):
        if h_attr.get("attributeId"):
            attrs_defined.append(str(h_attr.get("attributeId")))
            
    # Body (JSONPath)
    for b_attr in action.get("collectAttributes", []):
        if b_attr.get("attributeId"):
            attrs_defined.append(str(b_attr.get("attributeId")))

    transitions = []
    fallback = action.get("fallback", {})
    if fallback:
        f_action = fallback.get("fallbackAction", "UNKNOWN")
        f_edge_data = {"condition_type": "FALLBACK", "action": f_action}
        
        f_msgs = [msg.get("text", "") for msg in fallback.get("messages", []) if msg.get("text")]
        if f_msgs: 
            f_edge_data["messages_list"] = f_msgs
            
        if f_action == "GO_TO_DIALOG":
            target_dialog = fallback.get("goToDialogId")
            if target_dialog:
                f_edge_data["target_dialog_id"] = target_dialog
                transitions.append({
                    "target": f"{target_dialog}_1",
                    "edge_data": f_edge_data
                })

    next_elem = action.get("nextElementId")
    next_combined_id = f"{d_id}_{next_elem}" if next_elem else None

    return {
        "id": f"{d_id}_{e_id}",
        "dialog_id": d_id,
        "macro_type": "ACTION",
        "specific_type": "API_CALL",
        "content": content,
        "next_element": next_combined_id,
        "transitions": transitions,
        "attributes_used": [], 
        "attributes_defined": list(set(attrs_defined)) 
    }