from rendering_functions.utils import format_attr_list

def render_action_node(node_data, attributes_dict = None):
    """
    Renderizza i componenti del tipo chatbot actions:
    GO_TO_DIALOG, DELAY...
    
    """
    spec_type = node_data.get("specific_type", "UNKNOWN_ACTION")
    content = node_data.get("content", {})
    
    # Inizializziamo la tabella HTML
    html = '<<TABLE BORDER="0" CELLBORDER="1" CELLSPACING="0" CELLPADDING="5">'
    
    # Intestazione Colorata
    if spec_type == "CLOSE_SESSION":
        html += f'<TR><TD BGCOLOR="#C9CCD2"><B>END FLOW</B><BR/><FONT POINT-SIZE="10">Close Session</FONT></TD></TR>'
    else:
        html += f'<TR><TD BGCOLOR="#FFC080"><B>ACTION</B><BR/><FONT POINT-SIZE="10">{spec_type}</FONT></TD></TR>'
    
    # Corpo della tabella specifico
    if spec_type == "GO_TO_DIALOG":
        target = content.get("target_dialog_id", "Sconosciuto")
        html += f'<TR><TD>Jumps to dialog: <B>{target}</B></TD></TR>'
        
    elif spec_type == "DELAY":
        durata = content.get("delay_duration", 0)
        html += f'<TR><TD>Waits for: <B>{durata} sec</B></TD></TR>'
        
    elif spec_type == "API_CALL":
        method = content.get("method", "HTTP")
        html += f'<TR><TD><B>{method}</B> Request</TD></TR>'
        
        attrs_defined = node_data.get("attributes_defined", [])
        if attrs_defined:
            attrs_str = format_attr_list(attrs_defined, attributes_dict)
            html += f'<TR><TD BGCOLOR="#FFF9C4"><FONT POINT-SIZE="9"> Attributes defined: [{attrs_str}]</FONT></TD></TR>'
            
    elif spec_type == "EVALUATE_ATTRIBUTE":
        attrs_used = node_data.get("attributes_used", [])
        if attrs_used:
            attrs_str = format_attr_list(attrs_used, attributes_dict)
            html += f'<TR><TD BGCOLOR="#FFF9C4"><FONT POINT-SIZE="9"> Evaluates: [{attrs_str}]</FONT></TD></TR>'
        
    html += '</TABLE>>'
    return html