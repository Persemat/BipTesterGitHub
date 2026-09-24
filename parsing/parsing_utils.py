# parsing/parsing_utils.py

import re

def extract_placeholders(data):
    """
    Recursive function that explores dictionaries, lists, and strings
    to extract all placeholders in the format {{variable}}.
    
    Args:
        data: The data structure to inspect (dict, list, or str).
        
    Returns:
        list: A deduplicated list of placeholder strings found.
    """
    found = []

    # Base Case: It's a string, apply Regex
    if isinstance(data, str):
        return re.findall(r'\{\{(.*?)\}\}', data)
        
    # If it's a list: recursively explore each element
    elif isinstance(data, list):
        for item in data:
            found.extend(extract_placeholders(item))
            
    # If it's a dictionary: recursively explore each value
    elif isinstance(data, dict):
        for value in data.values():
            found.extend(extract_placeholders(value))

    # Return the list removing duplicates
    return list(set(found))


def extract_attrs_from_condition(condition_obj):
    """
    Recursive helper to find attribute IDs hidden inside EVALUATE_ATTRIBUTE logic trees.
    """
    found = []
    c_type = condition_obj.get("type")
    
    if c_type == "ATTRIBUTE_COMPARE":
        attr_id = condition_obj.get("attributeId")
        if attr_id:
            found.append(str(attr_id))
            
    elif c_type == "LOGICAL":
        for sub_cond in condition_obj.get("conditions", []):
            found.extend(extract_attrs_from_condition(sub_cond))
            
    return found