from html import escape

def _truncate_text(text, limit=100):
    """
    Helper function to truncate long text strings.
    Prevents Graphviz nodes from expanding beyond readable screen dimensions.
    """
    if not text:
        return ""
    return text[:limit] + "..." if len(text) > limit else text

def render_send_message_node(node_data, **kwargs):
    """
    Generates Graphviz HTML for SEND_MESSAGE macro nodes.
    Polymorphically renders different UI components (TEXT, IMAGE, BUTTON, LIST_PICKER, JSON)
    to visually represent the chatbot's outbound communication towards the user.
    """
    macro_type = node_data.get("macro_type", "SEND_MESSAGE")
    specific_type = node_data.get("specific_type", "UNKNOWN")
    content = node_data.get("content", {})

    # Initialize the HTML table structure with a specific background color (Light Green)
    html_str = '<<TABLE BORDER="0" CELLBORDER="1" CELLSPACING="0" CELLPADDING="5">'
    html_str += f'<TR><TD BGCOLOR="#E8F5E9"><B>{macro_type}</B><BR/><FONT POINT-SIZE="10">{specific_type}</FONT></TD></TR>'

    if specific_type == "TEXT":
        for msg in content.get("messages_list", []):
            # Use escape() to safely render special HTML characters (&, <, >)
            safe_msg = escape(str(msg))
            short_text = _truncate_text(safe_msg)
            html_str += f'<TR><TD>{short_text}</TD></TR>'

    elif specific_type == "IMAGE":
        safe_url = escape(content.get("url", ""))
        short_url = _truncate_text(safe_url)
        caption = escape(content.get("caption", ""))
        
        html_str += f'<TR><TD>{short_url}</TD></TR>'
        if caption:
            html_str += f'<TR><TD><I>Caption: {caption}</I></TD></TR>'
    
    elif specific_type == "BUTTON":
        if "header" in content:
            header_type = escape(content["header"].get("type", ""))
            html_str += f'<TR><TD BGCOLOR="#FFF9C4"><FONT POINT-SIZE="10">Header: {header_type}</FONT></TD></TR>'
        
        body = escape(content.get("body", ""))
        short_body = _truncate_text(body)
        html_str += f'<TR><TD>{short_body}</TD></TR>'
        
        for btn in content.get("buttons", []):
            safe_btn = escape(str(btn))
            html_str += f'<TR><TD BGCOLOR="#F5F5F5"><I> {safe_btn}</I></TD></TR>'
            
        if "footer" in content:
            safe_footer = escape(content["footer"])
            html_str += f'<TR><TD><FONT COLOR="gray" POINT-SIZE="10">Footer: {safe_footer}</FONT></TD></TR>'

    elif specific_type == "LIST_PICKER":
        if "header" in content: 
            safe_header = escape(content["header"])
            html_str += f'<TR><TD BGCOLOR="#FFF9C4"><FONT POINT-SIZE="10">Header: {safe_header}</FONT></TD></TR>'

        body = escape(content.get("body", ""))
        short_body = _truncate_text(body)
        html_str += f'<TR><TD>{short_body}</TD></TR>'

        menu_btn = escape(content.get("menu_button", ""))
        html_str += f'<TR><TD BGCOLOR="#F5F5F5"><I>Menu Button: {menu_btn}</I></TD></TR>'

        for opt in content.get("options", []):
            title = escape(opt.get("title", ""))
            postback = escape(opt.get("postback", ""))
            
            if "description" in opt:
                description = escape(opt.get("description", ""))
                html_str += f'<TR><TD><B>{title}</B> - {description} (Postback: {postback})</TD></TR>'
            else:
                html_str += f'<TR><TD><B>{title}</B> (Postback: {postback})</TD></TR>'
                
        if "footer" in content:
            safe_footer = escape(content["footer"])
            html_str += f'<TR><TD><FONT COLOR="gray" POINT-SIZE="10">Footer: {safe_footer}</FONT></TD></TR>'

    elif specific_type == "JSON":
        # Specific rendering for custom JSON components (e.g., dynamic carousels or custom API payloads)
        body = escape(content.get("body", "Custom JSON Component"))
        short_body = _truncate_text(body)
        html_str += f'<TR><TD>{short_body}</TD></TR>'
        
        # Extract options (if structured as dictionaries)
        options = content.get("options", [])
        # Extract buttons (if structured as a list of strings)
        buttons = content.get("buttons", [])
        
        if options:
            for opt in options:
                title = escape(opt.get("title", ""))
                payload = escape(opt.get("payload", ""))
                html_str += f'<TR><TD BGCOLOR="#E3F2FD"><I>[Btn] {title} ({payload})</I></TD></TR>'
        elif buttons:
            for btn in buttons:
                safe_btn = escape(str(btn))
                html_str += f'<TR><TD BGCOLOR="#E3F2FD"><I>[Btn] {safe_btn}</I></TD></TR>'
    
    html_str += '</TABLE>>'
    return html_str