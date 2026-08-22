import json
import re

def map_send_message(d_id, e_id, element):
    """
    Sotto modulo di mapping per la macro categoria SEND_MESSAGE.
    Prende l'elemento JSON grezzo e lo standardizza in un dizionario per il grafo.
    """
    # Navighiamo la struttura del JSON di infobip
    action = element.get("action", {})
    messages = action.get("messages", [])

    sub_type = "UNKNOWN_SUBTYPE"
    attr_used = []
    content = {}

    # Verifichiamo che la lista dei messggi non sia vuota
    if len(messages) > 0:
        sub_type = messages[0].get("type", "TEXT")
        
        # --- CARATTERIZZAZIONE PER SOTTOTIPO --- #

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
            menu_button = messages[0].get("button", "") # Siamo sicuri che ci serva? Ha solo scopo grafico, non influisce sul testing

           # Ciclo per estrazione di titolo, postback e eventualmente descrizione di ciascun item in section
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
                # Decodifichiamo se è una stringa, altrimenti lo teniamo così com'è
                payload = json.loads(raw_payload) if isinstance(raw_payload, str) else raw_payload
            except json.JSONDecodeError:
                payload = raw_payload

            # Inizializziamo il content di base per avere comunque traccia del payload originale
            content = {
                "raw_payload": raw_payload, 
                "payload": payload
            }

            # --- GESTIONE DEL CONTRATTO CUSTOM JSON ---
            if isinstance(payload, dict) and "custom_type" in payload:
                custom_type = payload.get("custom_type")
                custom_content = payload.get("content", {})
                
                # Sovrascriviamo il sub_type (es diventerà "CUSTOM_BUTTON_GROUP" o "CUSTOM_LIST_PICKER")
                # Questo aiuterà moltissimo in fase di generazione del test
                sub_type = f"CUSTOM_{custom_type}"
                
                # Estraiamo i dati in modo strutturato
                if custom_type in ["BUTTON", "LIST_PICKER"]:
                    content["body"] = custom_content.get("text", "")
                    content["options"] = custom_content.get("options", [])
                    
                    # Creiamo una lista piatta di soli titoli per renderla identica a come 
                    # gestisci i bottoni nativi di WhatsApp, facilitando la vita al test generator
                    content["buttons"] = [opt.get("title", "") for opt in custom_content.get("options", [])]

                if custom_type == "IMAGE":
                    content["url"] = custom_content.get("url", "No URL")
                    content["caption"] = custom_content.get("caption", "")

        # Applichiamo la Regex a tutti i valori del content per estrarre le variabili usate
        # La regex cerca pattern del tipo {{variabile}} e li estrae in una lista
        attr_used = extract_placeholders(content)


    # --- LOGICA NAVIGAZIONE GRAFO ( ARCHI ) --- 

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
        "attributes_defined": [],  # Un messaggio non scrive mai variabili nello stato del bot
        "attributes_used": attr_used  # Contiene le variabili estratte via Regex (es. ["shopName", "userDistance"])
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