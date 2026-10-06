# parsing/parsing_utils.py

import json
import os
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

def extract_code_attributes(code_string):
    """
    Parses a JavaScript code string from an Infobip CODING node to extract
    attributes that are being read (used) or written (defined).
    
    Args:
        code_string (str): The raw JavaScript code.
        
    Returns:
        tuple: (list of used_attributes, list of defined_attributes)
    """
    if not isinstance(code_string, str) or not code_string:
        return [], []
        
    # Regex per catturare: attributeApi.get("NomeVar") o attributeApi.get('NomeVar')
    used = re.findall(r'attributeApi\.get\(\s*["\']([^"\']+)["\']\s*\)', code_string)
    
    # Regex per catturare: attributeApi.set("NomeVar", valore) o attributeApi.set('NomeVar', valore)
    defined = re.findall(r'attributeApi\.set\(\s*["\']([^"\']+)["\']\s*,', code_string)
    
    return list(set(used)), list(set(defined))

def load_components(mapping_file_path="chatbots/components_registry.json", components_dir="chatbots/components"):
    """
    Reads the user-defined mapping file and loads the corresponding 
    component JSON files into memory.
    Returns: A dictionary mapping component UUIDs to their parsed JSON data.
    """
    components_dict = {}
    
    # Check if the mapping file exists before attempting to read
    if not os.path.exists(mapping_file_path):
        print(f"[WARNING] Mapping file {mapping_file_path} not found. Components will be ignored.")
        return components_dict

    with open(mapping_file_path, 'r', encoding='utf-8') as f:
        mapping = json.load(f)

    # Iterate through the mapping and load each physical file
    for comp_uuid, filename in mapping.items():
        file_path = os.path.join(components_dir, filename)
        try:
            with open(file_path, 'r', encoding='utf-8') as comp_file:
                components_dict[comp_uuid] = json.load(comp_file)
                print(f"[LOADER] Component successfully loaded into memory: {filename}")
        except FileNotFoundError:
            print(f"[ERROR] The file {filename} does not exist in {components_dir}.")
            
    return components_dict