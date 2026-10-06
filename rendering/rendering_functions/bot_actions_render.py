from rendering.rendering_functions.utils import format_attr_list

def render_action_node(node_data, attributes_dict=None):
    """
    Generates Graphviz HTML for backend action nodes (e.g., GO_TO_DIALOG, DELAY, API_CALL).
    These nodes represent internal system operations that handle routing, data fetching, 
    or logic execution without directly prompting the user for input.
    """
    spec_type = node_data.get("specific_type", "UNKNOWN_ACTION")
    content = node_data.get("content", {})
    
    # Initialize the HTML table structure
    html = '<<TABLE BORDER="0" CELLBORDER="1" CELLSPACING="0" CELLPADDING="5">'
    
    # Dynamic header rendering based on action severity
    # CLOSE_SESSION is a terminal state, hence rendered with a distinct visual weight (gray)
    if spec_type == "CLOSE_SESSION":
        html += f'<TR><TD BGCOLOR="#C9CCD2"><B>END FLOW</B><BR/><FONT POINT-SIZE="10">Close Session</FONT></TD></TR>'
    else:
        # Standard backend actions (orange)
        html += f'<TR><TD BGCOLOR="#FFC080"><B>ACTION</B><BR/><FONT POINT-SIZE="10">{spec_type}</FONT></TD></TR>'
    
    # Specific payload rendering based on the action type
    if spec_type == "GO_TO_DIALOG":
        target = content.get("target_dialog_id", "Unknown")
        html += f'<TR><TD>Jumps to dialog: <B>{target}</B></TD></TR>'
        
    elif spec_type == "DELAY":
        duration_sec = content.get("delay_duration", 0)
        html += f'<TR><TD>Waits for: <B>{duration_sec} sec</B></TD></TR>'
        
    elif spec_type == "API_CALL":
        method = content.get("method", "HTTP")
        html += f'<TR><TD><B>{method}</B> Request</TD></TR>'
        
        # Display variables populated by the API response
        attrs_defined = node_data.get("attributes_defined", [])
        if attrs_defined:
            attrs_str = format_attr_list(attrs_defined, attributes_dict)
            html += f'<TR><TD BGCOLOR="#FFF9C4"><FONT POINT-SIZE="9"> Attributes defined: [{attrs_str}]</FONT></TD></TR>'
            
    elif spec_type == "EVALUATE_ATTRIBUTE":
        # Display variables evaluated during conditional routing
        attrs_used = node_data.get("attributes_used", [])
        if attrs_used:
            attrs_str = format_attr_list(attrs_used, attributes_dict)
            html += f'<TR><TD BGCOLOR="#FFF9C4"><FONT POINT-SIZE="9"> Evaluates: [{attrs_str}]</FONT></TD></TR>'

    elif spec_type == "CODING":
        lang = content.get("language", "JAVASCRIPT")
        html += f'<TR><TD>Executes <B>{lang}</B> script</TD></TR>'
        
        attrs_used = node_data.get("attributes_used", [])
        if attrs_used:
            attrs_str = format_attr_list(attrs_used, attributes_dict)
            html += f'<TR><TD BGCOLOR="#E8F5E9"><FONT POINT-SIZE="9"> Reads: [{attrs_str}]</FONT></TD></TR>'
            
        attrs_defined = node_data.get("attributes_defined", [])
        if attrs_defined:
            attrs_str = format_attr_list(attrs_defined, attributes_dict)
            html += f'<TR><TD BGCOLOR="#FFF9C4"><FONT POINT-SIZE="9"> Writes: [{attrs_str}]</FONT></TD></TR>'

    elif spec_type == "AUTHENTICATION":
        never_timeout = content.get("never_timeout", False)
        if never_timeout:
            html += f'<TR><TD>Timeout: <B>Never</B></TD></TR>'
        else:
            t_min = content.get("timeout_minutes", 0)
            html += f'<TR><TD>Timeout: <B>{t_min} min</B></TD></TR>'

    elif spec_type == "WEBHOOK":
        method = content.get("method", "GET")
        timeout_enabled = content.get("timeout_enabled", False)
        html += f'<TR><TD>Method: <B>{method}</B></TD></TR>'
        
        if timeout_enabled:
            timeout = content.get("timeout_duration", 0)
            html += f'<TR><TD><FONT POINT-SIZE="9">Timeout: {timeout}s</FONT></TD></TR>'

    elif spec_type == "COMPONENT":
        html += f'<TR><TD>Executes Sub-Flow</TD></TR>'
        
        attrs_used = node_data.get("attributes_used", [])
        if attrs_used:
            attrs_str = format_attr_list(attrs_used, attributes_dict)
            html += f'<TR><TD BGCOLOR="#E8F5E9"><FONT POINT-SIZE="9"> Inputs: [{attrs_str}]</FONT></TD></TR>'
            
        attrs_defined = node_data.get("attributes_defined", [])
        if attrs_defined:
            attrs_str = format_attr_list(attrs_defined, attributes_dict)
            html += f'<TR><TD BGCOLOR="#FFF9C4"><FONT POINT-SIZE="9"> Outputs: [{attrs_str}]</FONT></TD></TR>'
   
    html += '</TABLE>>'
    return html