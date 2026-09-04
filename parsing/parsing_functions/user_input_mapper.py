
def extract_common_input_logic(d_id,action):
    """
    Funzione Helper privata. 
    Estrae le logiche condivise da tutti i nodi di input: Fallback, Timeout e Repeat.
    Restituisce le transizioni e i dati base del contenuto.
    """
    fallback = action.get("fallback", {})
    repeat = action.get("repeat", {})
    timeout = action.get("timeout", {})
    timeout_fallback = action.get("timeoutFallback", {})

    transitions = []

    # ELaborazione fallback
    fallback_action = fallback.get("fallbackAction", "UNKNOWN")
    fallback_edge_data = {
        "condition_type" : "FALLBACK",
        "action" : fallback_action
    }

    fallback_messages = [msg.get("text", "") for msg in fallback.get("messages", []) if msg.get("text")]
    if fallback_messages:
        fallback_edge_data["messages_list"] = fallback_messages
        
    if fallback_action == "GO_TO_DIALOG":
        target_dialog = fallback.get("goToDialogId")
        if target_dialog:
            fallback_edge_data["target_dialog_id"] = target_dialog

            transitions.append({
                "target": f"{target_dialog}_1",
                "edge_data": fallback_edge_data
            })
    
    # Elaborazione timeout fallback
    if timeout.get("isEnabled", False) and timeout_fallback:    
        t_action = timeout_fallback.get("fallbackAction", "UNKNOWN")
        t_duration = timeout.get("durationSeconds", 0)

        timeout_edge_data = {
            # Non c'è nel JSON questa classificazione ma la uso per distiguere le tipologie di arco
            "condition_type": "TIMEOUT",
            "action": t_action,
            "duration": t_duration
        }

        # salvataggio messaggi di timeout fallback
        t_msgs = [msg.get("text", "") for msg in timeout_fallback.get("messages", []) if msg.get("text")]
        if t_msgs:
            timeout_edge_data["messages_list"] = t_msgs

        
        if t_action == "GO_TO_DIALOG":
            t_target_dialog = timeout_fallback.get("goToDialogId")
            if t_target_dialog:
                timeout_edge_data["target_dialog_id"] = t_target_dialog
                # FAI L'APPEND UNA SOLA VOLTA!
                transitions.append({
                    "target": f"{t_target_dialog}_1",
                    "edge_data": timeout_edge_data
                }) 
    
    repeat_count = repeat.get("count", 0)
    repeat_messages = [msg.get("text", "") for msg in repeat.get("messages", []) if msg.get("text")]

    common_content = {
        "repeat_count": repeat_count,
        "repeat_messages": repeat_messages,
        "timeout_enabled": timeout.get("isEnabled", False),
        "timeout_duration": timeout.get("durationSeconds", 0)
    }

    next_elem = action.get("nextElementId")
    next_combined_id = f"{d_id}_{next_elem}" if next_elem else None

    return transitions, common_content, next_combined_id

    


def map_process_user_input(d_id, e_id, element):
    """
    Sotto modulo di mapping per la ,acro categoria PROCESS_USER_INPUT.  
    Estare le logiche di smistamento e i fallback per preparare gli archi
    """
    action = element.get("action", {})
    transitions, content, _ = extract_common_input_logic(d_id, action)
    rules = action.get("rules", [])

    content["nlp_enabled"] = action.get("nlp_enabled", False)

    for rule in rules:
        target_id = rule.get("nextElementId")

        if not target_id:
            continue
        
        condition = rule.get("condition", {})
        condition_type = condition.get("type", "UNKNOWN")
        # Raccogliamo le informazioni della condizione
        edge_data = {"condition_type": condition_type}
        
        # Se è una Keyword
        if condition_type == "KEYWORD_COMPARE":
            edge_data["keywordId"] = condition.get("keywordId")
            
        
        edge = {
            "target": f"{d_id}_{target_id}",
            "edge_data": edge_data
        }
        transitions.append(edge)
    

    # Restituiamo il dizionario standardizzato
    return {
        "id": f"{d_id}_{e_id}",
        "dialog_id": d_id,
        "macro_type": "RECEIVE_INPUT",
        "specific_type": "PROCESS_USER_INPUT",  # È un nodo di smistamento logico
        "content": content,
        "transitions": transitions, # Passiamo l'array degli archi!
        "attributes_used": [],      # Non usa variabili nel testo
        "attributes_defined": [],   # (Per ora) non salva l'input dell'utente in variabili
    }


def map_get_attribute(d_id, e_id, element, attributes_dict = None):

    if attributes_dict is None:
        attributes_dict = {}

    action = element.get("action", {})
    
    transitions, content, next_combined_id = extract_common_input_logic(d_id, action)

    # Aggiunge la logica specifica del Get Attribute
    content["questions"] = [q.get("text", "") for q in action.get("questions", []) if q.get("text")]
    
    attr_defined = []
    attr_id = action.get("attributeId")

    data_type = "TEXT"

    if attr_id:
        str_attr_id = str(attr_id)
        attr_defined.append(str_attr_id)

        if str_attr_id in attributes_dict:
            data_type = attributes_dict[str_attr_id].get("type", "TEXT")
        
        

    return {
        "id": f"{d_id}_{e_id}",
        "dialog_id": d_id,
        "macro_type": "RECEIVE_INPUT",
        "specific_type": "GET_ATTRIBUTE",
        "content": content,
        "next_element": next_combined_id,
        "transitions": transitions, 
        "data_type" : data_type,
        "attributes_used": [],      
        "attributes_defined": attr_defined,
    }

def map_whatsapp_location(d_id, e_id, element):
    action = element.get("action", {})
    transitions, content, next_combined_id = extract_common_input_logic(d_id, action)
    
    body_text = action.get("body","")
    if body_text:
        content["body"] = [body_text]
    else:
        content["body"] = []
    
    attr_defined = []
    attr_id = action.get("attributeId")
    if attr_id:
        attr_defined.append(str(attr_id))

    return {
        "id": f"{d_id}_{e_id}",
        "dialog_id": d_id,
        "macro_type": "RECEIVE_INPUT",
        "specific_type": "WHATSAPP_LOCATION_REQUEST",
        "content": content,
        "next_element": next_combined_id,
        "transitions": transitions, 
        "attributes_used": [],      
        "attributes_defined": attr_defined
    }

def map_csat(d_id, e_id, element):
    action = element.get("action", {})

    transitions, content, next_combined_id = extract_common_input_logic(d_id, action)
    
    raw_question = action.get("scoringQuestion", "").strip()
    
    content["question"] = raw_question
    content["scale_type"] = action.get("scale", "SCORING_1_5")
    content["fallback"] = action.get("fallbackMessage", "")

    return {
        "id": f"{d_id}_{e_id}",
        "dialog_id": d_id,
        "macro_type": "RECEIVE_INPUT",
        "specific_type": "CSAT",
        "content": content,
        "next_element": next_combined_id,
        "transitions": transitions, 
        "attributes_used": [],      
        "attributes_defined": []
    }