import networkx as nx

from parsing.parsing_functions.send_message_mapper import map_send_message
from parsing.parsing_functions.user_input_mapper import map_process_user_input
from parsing.parsing_functions.user_input_mapper import map_get_attribute
from parsing.parsing_functions.user_input_mapper import map_whatsapp_location
from parsing.parsing_functions.bot_actions_mapper import map_go_to_dialog
from parsing.parsing_functions.bot_actions_mapper import map_delay
from parsing.parsing_functions.bot_actions_mapper import map_close_session
from parsing.parsing_functions.bot_actions_mapper import map_evaluate_attribute
from parsing.parsing_functions.bot_actions_mapper import map_api_call
from parsing.parsing_functions.user_input_mapper import map_csat


class ChatbotParser:
    def __init__(self, json_data):
        self.data = json_data
        self.keywords = self.build_keyword()
        self.intents = self.build_intent()
        self.start_element_map = {}
        self.attributes = self.build_attribute()

        for dialog in self.data.get("dialogRequests", []):
             d_id = dialog["internalId"]
             start_elem = dialog.get("startElementId")
             if start_elem:
                  self.start_element_map[d_id] = start_elem

        self.dispatcher = {
            "SEND_MESSAGE": map_send_message,
            "PROCESS_USER_INPUT": map_process_user_input,
            "GET_ATTRIBUTE" : map_get_attribute,
            "WHATSAPP_LOCATION_REQUEST": map_whatsapp_location,
            "CSAT": map_csat,
            "GO_TO_DIALOG" : map_go_to_dialog,
            "DELAY" : map_delay,
            "CLOSE_SESSION" : map_close_session,
            "EVALUATE_ATTRIBUTE" : map_evaluate_attribute,
            "API_CALL" : map_api_call
        }

    #Salvatggio default
    def map_unknown(self, d_id, e_id, element):
        """
        Viene chiamata se il tipo non esiste nel dispatcher
        """
        print(f"Salto o mappa temporanea per elemento di tipo: {element.get('type')}")
        
        action = element.get("action", {})
        next_elem = action.get("nextElementId")
        next_combined_id = f"{d_id}_{next_elem}" if next_elem else None

        return {
            "id": f"{d_id}_{e_id}",
            "dialog_id": d_id,             
            "macro_type": "UNKNOWN",          
            "specific_type": element.get("type", "UNKNOWN"),
            "content": {"body": "Elemento non gestito"},
            "next_element": next_combined_id, #
            "attributes_used": []
        }

    def process_all_elements(self):
        self.G = nx.MultiDiGraph()

        self.G.add_node(
            "USER_ENTRY",
            dialog_id = "GLOBAL",
            macro_type = "USER_ENTRY",
            specific_type = "INTENT_RECOGNITION",
            content={"description": "L'utente apre WhatsApp o scrive un messaggio iniziale"},
            dialog_name="Chat Start"
            )

        # Rami NLP e default
        for dialog in self.data.get("dialogRequests", []):
            d_id = dialog["internalId"]
            start_elem = dialog.get("startElementId")
            
            if not start_elem:
                continue
                
            target_node = f"{d_id}_{start_elem}"

            # Controllo se è il dialogo di Default (Nessun match NLP)
            if dialog.get("type") == "DEFAULT":
                self.G.add_edge("USER_ENTRY", target_node, condition_type="DEFAULT", condition="[Any other input]")

            # Controllo se il dialogo ha un Intent associato (Match NLP)
            intent_id = dialog.get("intentId")
            if intent_id and intent_id in self.intents:
                intent_data = self.intents[intent_id]
                edge_data = {
                    "condition_type": "INTENT",
                    "intent_name": intent_data["name"],
                    "phrases": intent_data["phrases"]
                }
                self.G.add_edge("USER_ENTRY", target_node, **edge_data)

        # ciclo normale sui nodi del grafo
        for dialog in self.data.get("dialogRequests", []):
            dialog_id = dialog["internalId"]
            dialog_name = dialog.get("name", "Unnamed Dialog")

        # Iteriamo per ogni Element all'interno del Dialog 
        # e estraiamo id e tipo del nodo
            for element in dialog.get("elements",[]):
                element_id = element["id"]
                element_type = element["type"]

                # qui avviene la chiamata alla funzione di mapping associata nel dispatcher, e se non la trova chiama self.map_unknown
                mapping_function = self.dispatcher.get(element_type, self.map_unknown)
                mapped_node = mapping_function(dialog_id, element_id, element)
                mapped_node["dialog_name"] = dialog_name
                
                # Separazione dati e creazione nodo
                node_id = mapped_node.pop("id")
                # Estrazione collegamenti e rimozione dal dizionario
                next_element = mapped_node.pop("next_element", None)
                transitions = mapped_node.pop("transitions", [])

                
                self.G.add_node(node_id, **mapped_node)

                if next_element:
                    self.G.add_edge(node_id, next_element, condition = "[Auto]")
                
                if transitions:
                    for trans in transitions:
                        target = trans.get("target")
                        edge_data = trans.get("edge_data", {})
                        
                        
                        if target:
                            if edge_data.get("action") == "GO_TO_DIALOG":
                                target_dialog_id = edge_data.get("target_dialog_id")

                                if target_dialog_id:
                                    real_start_elem = self.start_element_map.get(target_dialog_id)

                                    if real_start_elem:
                                        target = f"{target_dialog_id}_{real_start_elem}"
                        
                            if edge_data.get("condition_type") == "KEYWORD_COMPARE":
                                kw_id = edge_data.get("keywordId")
                                if kw_id in self.keywords:
                                    edge_data["synonyms"] = self.keywords[kw_id]
                        
                            self.G.add_edge(node_id, target, **edge_data)


    def build_keyword(self):
        keywords = {}

        keyword_list = self.data.get("keywordRequests", [])

        for kw in keyword_list:
            kw_id = kw["internalId"]
            synonyms = kw.get("synonyms", {}).get("data",[])

            keywords[kw_id] = synonyms

        return keywords
    
    def build_intent(self):
        intents = {}

        intent_list = self.data.get("intentRequests", [])

        for intent in intent_list:
            intent_id = intent["internalId"]

            training_phrases = intent.get("phrases", [])

            intents[intent_id] = {
                "name" : intent.get("name", "Unknown intent"),
                "phrases" : training_phrases
            }

        return intents

    def build_attribute(self):
        """
        Estrae tutti gli attributi dal JSON e crea un dizionario di facile consultazione.
        La chiave è l'internalId, il valore è un dizionario con i metadati.
        """
        attributes = {}
        attribute_list = self.data.get("attributeRequests", [])
        
        for attr in attribute_list:
            attr_id = str(attr["internalId"]) # Convertiamo in stringa per uniformità con i mapper
            
            attributes[attr_id] = {
                "name": attr.get("name", f"Var_{attr_id}"),
                "type": attr.get("dataType", "UNKNOWN"),
                "scope": attr.get("scope", "LOCAL"),
                "sensitive": attr.get("sensitive", False),
                "visible_to_agent": attr.get("visibleToAgent", False)
            }
            
        return attributes
