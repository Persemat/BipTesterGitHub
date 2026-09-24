def format_attr_list(attr_ids, attributes_dict):
    """
    Helper function to format variable IDs into human-readable strings with visual indicators.
    Uses defensive dictionary access to prevent KeyError exceptions if metadata is missing.
    """
    if not attr_ids:
        return ""
        
    formatted_list = []
    for a_id in attr_ids:
        if attributes_dict and str(a_id) in attributes_dict:
            attr = attributes_dict[str(a_id)]
            name = attr.get("name", f"Var_{a_id}")
            
            # Visual scope and security indicators
            scope_icon = "🌐" if attr.get("scope") == "GLOBAL" else ""
            security_icon = "🔒" if attr.get("sensitive", False) else ""
            agent_icon = "🎧" if attr.get("visible_to_agent", False) else ""
                
            formatted_list.append(f"{name} {scope_icon}{security_icon}{agent_icon}".strip())
        else:
            # Fallback for unregistered attributes
            formatted_list.append(f"ID:{a_id}")
            
    return ", ".join(formatted_list)