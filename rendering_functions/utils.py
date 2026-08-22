# File: rendering_functions/utils.py

def format_attr_list(attr_ids, attributes_dict):
    """Funzione helper per formattare gli ID in nomi con icone"""
    if not attr_ids:
        return ""
        
    formatted_list = []
    for a_id in attr_ids:
        
        if attributes_dict and str(a_id) in attributes_dict:
            attr = attributes_dict[str(a_id)]
            name = attr["name"]
            
            scope_icon = "🌐" if attr["scope"] == "GLOBAL" else ""
            security_icon = "🔒" if attr["sensitive"] else ""
            agent_icon = "🎧" if attr["visible_to_agent"] else ""
                
            formatted_list.append(f"{name} {scope_icon}{security_icon}{agent_icon}")
        else:
            formatted_list.append(f"ID:{a_id}")
            
    return ", ".join(formatted_list)