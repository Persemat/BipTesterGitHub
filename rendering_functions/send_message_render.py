from html import escape

def render_send_message_node(node_data, **kwargs):
    """
    Costruisce l'etichetta HTML per un nodo di tipo SEND_MESSAGE
    """
    macro_type = node_data.get("macro_type", "SEND_MESSAGE")
    specific_type = node_data.get("specific_type", "UNKNOWN")
    content = node_data.get("content", {})

    # Cambiato il nome variabile da 'html' a 'html_str' per evitare conflitti
    html_str = '<<TABLE BORDER="0" CELLBORDER="1" CELLSPACING="0" CELLPADDING="5">'
    html_str += f'<TR><TD BGCOLOR="#E8F5E9"><B>{macro_type}</B><BR/><FONT POINT-SIZE="10">{specific_type}</FONT></TD></TR>'

    if specific_type == "TEXT":
        for msg in content.get("messages_list", []):
            # Usiamo escape() per rendere sicuri i caratteri speciali come & < >
            safe_msg = escape(msg)
            short_text = safe_msg[:100] + "..." if len(safe_msg) > 100 else safe_msg
            html_str += f'<TR><TD>{short_text}</TD></TR>'

    elif specific_type == "IMAGE":
        safe_url = escape(content.get("url", ""))
        short_url = safe_url[:100] + "..." if len(safe_url) > 100 else safe_url
        caption = escape(content.get("caption", ""))
        
        html_str += f'<TR><TD> {short_url} </TD></TR>'
        if caption:
            html_str += f'<TR><TD><I>Caption: {caption}</I></TD></TR>'
    
    elif specific_type == "BUTTON":
        if "header" in content:
            h_type = escape(content["header"].get("type", ""))
            html_str += f'<TR><TD BGCOLOR="#FFF9C4"><FONT POINT-SIZE="10">Header: {h_type}</FONT></TD></TR>'
        
        body = escape(content.get("body", ""))
        body_corto = body[:100] + "..." if len(body) > 100 else body
        html_str += f'<TR><TD>{body_corto}</TD></TR>'
        
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

        body = escape(content.get("body",""))
        short_body = body[:100] + "..." if len(body) > 100 else body
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
            html_str += f'<TR><TD><FONT COLOR="gray" POINT-SIZE="10"> Footer: {safe_footer}</FONT></TD></TR>'
    
    html_str += '</TABLE>>'
    return html_str