import graphviz
from rendering_functions.send_message_render import render_send_message_node
from rendering_functions.process_user_input_render import render_process_user_input_node
from rendering_functions.bot_actions_render import render_action_node
from rendering_functions.utils import format_attr_list

class ChatbotRenderer:
    def __init__(self, nx_graph, attributes_dict):
        """
        Il costruttore riceve l'oggetto (MultiDiGraph) di NetworkX
        """
        self.G = nx_graph
        self.attributes = attributes_dict
        self.dot = graphviz.Digraph(comment='Chatbot Flow', format='pdf')
        self.dot.attr(rankdir='TB')
        self.dot.attr('node', shape='plaintext', fontname='Helvetica')

        self.render_dispatcher = {
            "SEND_MESSAGE": render_send_message_node,
            "RECEIVE_INPUT": render_process_user_input_node,
            "ACTION": render_action_node
        }

    def render_unknown(self, node_data, attributes_dict):
        """Disegna un rettangolo rosso di base se il tipo di nodo è unknown"""
        macro_type = node_data.get("macro_type", "UNKNOWN")
        html = f'<<TABLE BORDER="0" CELLBORDER="1" CELLSPACING="0" CELLPADDING="5">'
        html += f'<TR><TD BGCOLOR="#FFCDD2"><B>{macro_type}</B></TD></TR>'
        html += f'<TR><TD>Nessuna regola di rendering definita</TD></TR>'
        html += '</TABLE>>'
        return html
    
    def render_entry_point(self, node_data, attributes_dict):
        """Renderizza il nodo fittizio di partenza"""
        macro_type = node_data.get("macro_type", "USER_ENTRY")
        html = '<<TABLE BORDER="0" CELLBORDER="1" CELLSPACING="0" CELLPADDING="8">'
        html += f'<TR><TD BGCOLOR="#80CBC4"><B> {macro_type} </B><BR/><FONT POINT-SIZE="10">WhatsApp Chat Opened</FONT></TD></TR>'
        html += '</TABLE>>'
        return html

    def render(self):
        """
        Scorre tutti i dati e fisicamente 'disegna' i nodi e le frecce sulla tela.
        """
        dialogs_info = {}
        for node_id, node_data in self.G.nodes(data=True):
            d_id = node_data.get('dialog_id')
            if d_id and d_id != "GLOBAL" and d_id not in dialogs_info:
                dialogs_info[d_id] = node_data.get('dialog_name', 'Senza Nome') 

        if self.G.has_node("USER_ENTRY"):
            node_data = self.G.nodes["USER_ENTRY"]
            html_label = self.render_entry_point(node_data,attributes_dict=None)
            self.dot.node("USER_ENTRY", label = html_label)
        
        # Disegno nodi
        for d_id, d_name in dialogs_info.items():
            with self.dot.subgraph(name=f'cluster_{d_id}') as c:
                c.attr(label=f'{d_name} - {d_id}', style='dashed', color='blue', fontname='Helvetica')
                
                for node_id, node_data in self.G.nodes(data=True):
                    if node_data.get('dialog_id') == d_id:
                        macro_type = node_data.get("macro_type", "UNKNOWN")
                        rendering_function = self.render_dispatcher.get(macro_type, self.render_unknown)
                        
                        html_label = rendering_function(node_data, attributes_dict = self.attributes)
                        c.node(node_id, label=html_label)
            
        # Disegno archi
        for u, v, edge_data in self.G.edges(data=True):
            
            label = ""
            line_color = "gray"
            text_color = "gray"
            line_style = "solid"
            
            action = edge_data.get("action")
            c_type = edge_data.get("condition_type")

            #  Regole grafiche per gli archi NLP e DEFAULT
            if c_type == "INTENT":
                intent_name = edge_data.get("intent_name", "Unknown Intent")
                label = f"NLP Match:\n[{intent_name}]"
                line_color = "dodgerblue"
                text_color = "dodgerblue"
                line_style = "bold"
            
            elif c_type == "DEFAULT":
                label = "Default Dialog"
                line_style = "dashed"

            # Go to dialog
            elif action == "GO_TO_DIALOG":
                line_style = "dashed"
                line_color = "gray"
                text_color = "gray"
                
                if c_type == "FALLBACK":
                    label = "Fallback"
                elif c_type == "TIMEOUT":
                    duration = edge_data.get("duration", 0)
                    label = f"Timeout: {duration}s"
                else:
                    label = "Change dialog"

            # Keyword
            elif c_type == "KEYWORD_COMPARE":
                synonyms = edge_data.get("synonyms", [])
                if synonyms:
                    label = f"User input:\n[{' | '.join(synonyms)}]"
                else:
                    label = f"Keyword ID:\n{edge_data.get('keywordId')}"

            # (Auto)
            elif "condition" in edge_data:
                label = str(edge_data.get("condition", "[Auto]"))

            else:
                label = "Unknown Edge"


            self.dot.edge(
                u, v, 
                label=label, 
                color=line_color, 
                fontcolor=text_color, 
                style=line_style, 
                fontsize='10'
            )

    def view(self, filename='chatbot_graph'):
        print("Rendering del PDF in corso...")
        self.dot.render(filename, view=True)


