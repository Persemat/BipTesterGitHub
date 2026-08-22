from rendering_functions.utils import format_attr_list

def render_process_user_input(content):
    """Rendering specifico per il Router logico"""
    nlp = content.get("nlp_enabled", False)
    return f'<TR><TD>NLP Enabled: {nlp}</TD></TR>'


def render_get_attribute(content):
    """Rendering specifico per la richiesta di attributi generici"""
    questions = content.get("questions", [])
    if questions:
        questions_clenead = str(questions[0]).replace('"', '&quot;').replace('<', '&lt;').replace('>', '&gt;')
        return f'<TR><TD><FONT POINT-SIZE="10"><I>&quot;{questions_clenead}&quot;</I></FONT></TD></TR>'
    return ''


def render_whatsapp_location(content):
    """Rendering specifico per la richiesta di posizione WhatsApp"""
    body = content.get("body", [])
    if body:
        # Legge correttamente dalla chiave "body" senza trucchi!
        body_cleaned = str(body[0]).replace('"', '&quot;').replace('<', '&lt;').replace('>', '&gt;')
        return f'<TR><TD><FONT POINT-SIZE="10"><I>&quot;{body_cleaned}&quot;</I></FONT></TD></TR>'
    return ''


def render_process_user_input_node(node_data, attributes_dict=None):
    """
    Funzione principale associata a RECEIVE_INPUT.
    Funge da controllore e smista il rendering alle sotto-funzioni specifiche.
    """
    spec_type = node_data.get("specific_type", "UNKNOWN_INPUT")
    content = node_data.get("content", {})
    repeats = content.get("repeat_count", 0)
    repeat_msgs = content.get("repeat_messages", [])
    
    # Inizio tabella HTML comune
    html = '<<TABLE BORDER="0" CELLBORDER="1" CELLSPACING="0" CELLPADDING="5">'
    
    # Intestazione comune a tutti
    html += f'<TR><TD BGCOLOR="#FFFF80"><B>RECEIVE_INPUT</B><BR/><FONT POINT-SIZE="10">{spec_type}</FONT></TD></TR>'
    
    # Chiamiamo la funzione dedicata al blocco specifico
    if spec_type == "PROCESS_USER_INPUT":
        html += render_process_user_input(content)
    elif spec_type == "GET_ATTRIBUTE":
        html += render_get_attribute(content)
    elif spec_type == "WHATSAPP_LOCATION_REQUEST":
        html += render_whatsapp_location(content)

    # Informazioni sulle variabili salvate (comune a Get Attribute e Location)
    attrs_defined = node_data.get("attributes_defined", [])
    if attrs_defined:
        attrs_str = format_attr_list(attrs_defined, attributes_dict)
        html += f'<TR><TD BGCOLOR="#FFF9C4"><FONT POINT-SIZE="9"> Attributes defined: [{attrs_str}]</FONT></TD></TR>'

    # Sezione ripetizioni in caso di errore (comune)
    if repeats > 0:
        html += f'<TR><TD BGCOLOR="#FFF9C4"><FONT POINT-SIZE="10">Max Repeats: {repeats}</FONT></TD></TR>'
        if repeat_msgs:
            html += '<TR><TD BGCOLOR="#FFF9C4"><FONT POINT-SIZE="10">Repeat Messages:'
            for msg in repeat_msgs:
                safe_msg = str(msg).replace('"', '&quot;').replace('<', '&lt;').replace('>', '&gt;')
                html += f'<BR/>&#8226; {safe_msg}'
            html += '</FONT></TD></TR>'
            
    html += '</TABLE>>'
    return html