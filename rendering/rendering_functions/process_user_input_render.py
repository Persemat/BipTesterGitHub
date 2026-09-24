from rendering.rendering_functions.utils import format_attr_list

def _escape_html(text):
    """
    Helper function to sanitize text for Graphviz HTML labels.
    Prevents parsing errors by escaping illegal characters.
    """
    if not text:
        return ""
    return str(text).replace('"', '&quot;').replace('<', '&lt;').replace('>', '&gt;')

def render_process_user_input(content):
    """
    Generates Graphviz HTML for the logical Router node (PROCESS_USER_INPUT).
    """
    nlp = content.get("nlp_enabled", False)
    return f'<TR><TD>NLP Enabled: {nlp}</TD></TR>'

def render_get_attribute(content):
    """
    Generates Graphviz HTML for generic attribute request nodes.
    Displays the question prompted to the user.
    """
    questions = content.get("questions", [])
    if questions:
        questions_cleaned = _escape_html(questions[0])
        return f'<TR><TD><FONT POINT-SIZE="10"><I>&quot;{questions_cleaned}&quot;</I></FONT></TD></TR>'
    return ''

def render_whatsapp_location(content):
    """
    Generates Graphviz HTML for WhatsApp Location request nodes.
    Displays the request body.
    """
    body = content.get("body", [])
    if body:
        # Reads directly from the "body" key to extract the prompt
        body_cleaned = _escape_html(body[0])
        return f'<TR><TD><FONT POINT-SIZE="10"><I>&quot;{body_cleaned}&quot;</I></FONT></TD></TR>'
    return ''

def render_csat_survey(content):
    """
    Generates Graphviz HTML for Customer Satisfaction (CSAT) survey nodes.
    Displays the survey question, scale type, and optional fallback messages.
    """
    question = content.get("question", "")
    html = ''
    
    if question:
        question_cleaned = _escape_html(question)
        # Truncate string to prevent gigantism in the Graphviz rendered nodes
        short_question = question_cleaned[:100] + "..." if len(question_cleaned) > 100 else question_cleaned
        html += f'<TR><TD><FONT POINT-SIZE="10"><B>Question:</B> <I>&quot;{short_question}&quot;</I></FONT></TD></TR>'
    
    scale_type = content.get("scale_type", "UNKNOWN")
    html += f'<TR><TD BGCOLOR="#F5F5F5"><FONT POINT-SIZE="10">Scale: {scale_type}</FONT></TD></TR>'
    
    fallback = content.get("fallback")
    if fallback:
        fallback_cleaned = _escape_html(fallback)
        html += f'<TR><TD><FONT COLOR="gray" POINT-SIZE="10">Fallback: {fallback_cleaned}</FONT></TD></TR>'
        
    return html

def render_process_user_input_node(node_data, attributes_dict=None):
    """
    Main dispatcher function for the RECEIVE_INPUT macro type.
    Acts as a controller, routing the rendering process to specific sub-functions
    based on the 'specific_type' metadata, and appends common configuration fields.
    """
    spec_type = node_data.get("specific_type", "UNKNOWN_INPUT")
    content = node_data.get("content", {})
    repeats = content.get("repeat_count", 0)
    repeat_msgs = content.get("repeat_messages", [])
    
    # Initialize the common HTML table structure
    html = '<<TABLE BORDER="0" CELLBORDER="1" CELLSPACING="0" CELLPADDING="5">'
    
    # Common header for all RECEIVE_INPUT nodes
    html += f'<TR><TD BGCOLOR="#FFFF80"><B>RECEIVE_INPUT</B><BR/><FONT POINT-SIZE="10">{spec_type}</FONT></TD></TR>'
    
    # Dispatcher: Call the dedicated renderer based on the specific node type
    if spec_type == "PROCESS_USER_INPUT":
        html += render_process_user_input(content)
    elif spec_type == "GET_ATTRIBUTE":
        html += render_get_attribute(content)
    elif spec_type == "WHATSAPP_LOCATION_REQUEST":
        html += render_whatsapp_location(content)
    elif spec_type == "CSAT":
        html += render_csat_survey(content)

    # Render target variables (common to Get Attribute and Location nodes)
    attrs_defined = node_data.get("attributes_defined", [])
    if attrs_defined:
        attrs_str = format_attr_list(attrs_defined, attributes_dict)
        html += f'<TR><TD BGCOLOR="#FFF9C4"><FONT POINT-SIZE="9"> Attributes defined: [{attrs_str}]</FONT></TD></TR>'

    # Render error handling and repeat cycles (common to all input nodes)
    if repeats > 0:
        html += f'<TR><TD BGCOLOR="#FFF9C4"><FONT POINT-SIZE="10">Max Repeats: {repeats}</FONT></TD></TR>'
        if repeat_msgs:
            html += '<TR><TD BGCOLOR="#FFF9C4"><FONT POINT-SIZE="10">Repeat Messages:'
            for msg in repeat_msgs:
                safe_msg = _escape_html(msg)
                html += f'<BR/>&#8226; {safe_msg}'
            html += '</FONT></TD></TR>'
            
    # Close the HTML table
    html += '</TABLE>>'
    return html