import json
import re

def map_send_message(d_id, e_id, element):
    """
    Sotto modulo di mapping per la macro categoria SEND_MESSAGE.
    Prende l'elemento JSON grezzo e lo standardizza in un dizionario per il grafo.
    """

    action = element.get("action", {})
    messages = action.get("messages", [])

    sub_type = "UNKNOWN_SUBTYPE"
    attr_used = []
    content = {}

    # Verify if the list of messages is not empty 
    if len(messages) > 0:
        sub_type = messages[0].get("type", "TEXT")

        # --- Extraction of content based on the subtype ---

        if sub_type == "TEXT":
            messages_list = []
            for msg in messages:
                text = msg.get("message", "")
                if text:
                    messages_list.append(text)
            content = {"messages_list" : messages_list}
            

        elif sub_type == "IMAGE":
            content = {
            "url" : messages[0].get("url", "No URL"),
            "caption" : messages[0].get("caption", "")
            }

        elif sub_type == "BUTTON":
            buttons = messages[0].get("buttons", [])
            header = messages[0].get("header", {})
            footer = messages[0].get("footer", "")
            
            if header:
                header_type = header.get("type", "UNKNOWN")
                header_data = {
                    "type": header_type
                    }
                if header_type == "TEXT":
                    header_data["text"] = header.get("text", "")
                if header_type == "IMAGE":
                    header_data["url"] = header.get("url", "")
                if header_type == "DOCUMENT":
                    header_data["url"] = header.get("documentUrl", "")
                    header_data["filename"] = header.get("filename", "")
                if header_type == "VIDEO":
                    header_data["url"] = header.get("url", "")
            
            content = {
            "body": messages[0].get("body", ""),
            "buttons": [b.get("title", "") for b in buttons]
            }

            if header:
                content["header"] = header
            if footer:
                content["footer"] = footer
        

        elif sub_type == "LIST_PICKER":
            header = messages[0].get("header", "")
            footer = messages[0].get("footer", "")
            body = messages[0].get("body", "")
            menu_button = messages[0].get("button", "") # Only for the rendering

           # Title and descrpiton extraction cicle 
            options_data = []
            for section in messages[0].get("sections",[]):
                for item in section.get("items", []):
                    single_item = {
                        "title": item.get("title", ""),
                        "postback": item.get("postback", "")
                    }
                    if "description" in item:
                        single_item["description"] = item.get("description", "")
                    
                    options_data.append(single_item)

            content = {
            "body" : body,
            "menu_button" : menu_button,
            "options" : options_data
            }

            if header:
                content["header"] = header
            if footer:
                content["footer"] = footer

        elif sub_type == "JSON":
            raw_payload = messages[0].get("json", "")

            try:
                # Decoding if it is a string, otherwise keep it as is (dict)
                payload = json.loads(raw_payload) if isinstance(raw_payload, str) else raw_payload
            except json.JSONDecodeError:
                payload = raw_payload

            # If the payload is a dictionary, we can extract the custom_type and content for further processing
            content = {
                "raw_payload": raw_payload, 
                "payload": payload
            }
            
        # Applichiamo la Regex a tutti i valori del content per estrarre le variabili usate
        # La regex cerca pattern del tipo {{variabile}} e li estrae in una lista
        attr_used = extract_placeholders(content)


    # --- GRAPH SEARCH LOGIC (EDGES) --- 

    next_elem = action.get("nextElementId")
    next_combined_id = f"{d_id}_{next_elem}" if next_elem else None 

    return{
        "id": f"{d_id}_{e_id}",
        "dialog_id": d_id,
        "element_id": e_id,
        "macro_type": "SEND_MESSAGE",
        "specific_type": sub_type,
        "content": content,
        "next_element": next_combined_id,
        "attributes_defined": [],  
        "attributes_used": attr_used  
    }

def extract_placeholders(data):
    """
    Funzione ricorsiva che esplora dizionari, liste e stringhe
    per estrarre tutti i placeholder nel formato {{variabile}}.
    """
    trovati = []

    # Caso Base: È una stringa, applichiamo la Regex
    if isinstance(data, str):
        return re.findall(r'\{\{(.*?)\}\}', data)
        
    # Se è una lista: esploriamo ogni elemento ricorsivamente
    elif isinstance(data, list):
        for item in data:
            trovati.extend(extract_placeholders(item))
            
    # Se è un dizionario: esploriamo ogni valore ricorsivamente
    elif isinstance(data, dict):
        for value in data.values():
            trovati.extend(extract_placeholders(value))

    # Restituiamo la lista rimuovendo i duplicati
    return list(set(trovati))