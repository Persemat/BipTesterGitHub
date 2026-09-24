import graphviz
from rendering.rendering_functions.send_message_render import render_send_message_node
from rendering.rendering_functions.process_user_input_render import render_process_user_input_node
from rendering.rendering_functions.bot_actions_render import render_action_node
from rendering.rendering_functions.utils import format_attr_list

class ChatbotRenderer:
    """
    Core rendering engine that translates a NetworkX graph representing the chatbot logic
    into a visual Graphviz architecture diagram.
    """
    
    def __init__(self, nx_graph, attributes_dict):
        """
        Initializes the renderer with the generated MultiDiGraph and global attributes.
        """
        self.G = nx_graph
        self.attributes = attributes_dict
        
        # Initialize the Graphviz canvas
        self.dot = graphviz.Digraph(comment='Chatbot Architecture Flow', format='pdf')
        self.dot.attr(rankdir='TB')  # Top-to-Bottom layout
        self.dot.attr('node', shape='plaintext', fontname='Helvetica')

        # Dispatcher map for node rendering polymorphism
        self.render_dispatcher = {
            "SEND_MESSAGE": render_send_message_node,
            "RECEIVE_INPUT": render_process_user_input_node,
            "ACTION": render_action_node
        }

    def render_unknown(self, node_data, attributes_dict):
        """
        Fallback renderer for uncategorized or unsupported node types.
        Renders a red alert box to highlight parsing gaps.
        """
        macro_type = node_data.get("macro_type", "UNKNOWN")
        html = f'<<TABLE BORDER="0" CELLBORDER="1" CELLSPACING="0" CELLPADDING="5">'
        html += f'<TR><TD BGCOLOR="#FFCDD2"><B>{macro_type}</B></TD></TR>'
        html += f'<TR><TD>No rendering rule defined</TD></TR>'
        html += '</TABLE>>'
        return html
    
    def render_entry_point(self, node_data, attributes_dict=None):
        """
        Renders the artificial entry point node indicating the start of the session.
        """
        macro_type = node_data.get("macro_type", "USER_ENTRY")
        html = '<<TABLE BORDER="0" CELLBORDER="1" CELLSPACING="0" CELLPADDING="8">'
        html += f'<TR><TD BGCOLOR="#80CBC4"><B> {macro_type} </B><BR/><FONT POINT-SIZE="10">Session Opened</FONT></TD></TR>'
        html += '</TABLE>>'
        return html

    def _get_edge_formatting(self, edge_data):
        """
        Extracts styling properties (color, style, labels) for an edge 
        based on its logical condition and routing action.
        """
        label = ""
        line_color = "gray"
        text_color = "gray"
        line_style = "solid"
        
        action = edge_data.get("action")
        c_type = edge_data.get("condition_type")

        # NLP and Intent Matching
        if c_type == "INTENT":
            intent_name = edge_data.get("intent_name", "Unknown Intent")
            label = f"NLP Match:\n[{intent_name}]"
            line_color = "dodgerblue"
            text_color = "dodgerblue"
            line_style = "bold"
            
        elif c_type == "DEFAULT":
            label = "Default Dialog"
            line_style = "dashed"

        # Hardcoded Routing Actions
        elif action == "GO_TO_DIALOG":
            line_style = "dashed"
            
            if c_type == "FALLBACK":
                label = "Fallback Trigger"
            elif c_type == "TIMEOUT":
                duration = edge_data.get("duration", 0)
                label = f"Timeout: {duration}s"
            else:
                label = "Change dialog"

        # Explicit User Interactions
        elif c_type == "KEYWORD_COMPARE":
            synonyms = edge_data.get("synonyms", [])
            if synonyms:
                label = f"User input:\n[{' | '.join(synonyms)}]"
            else:
                label = f"Keyword ID:\n{edge_data.get('keywordId')}"

        # Automatic transitions
        elif "condition" in edge_data:
            label = str(edge_data.get("condition", "[Auto]"))

        else:
            label = "Unknown Edge"

        return label, line_color, text_color, line_style

    def render(self):
        """
        Traverses the NetworkX graph and orchestrates the physical drawing on the Graphviz canvas.
        Groups nodes by Dialog ID using Graphviz Clusters for logical separation.
        """
        # 1. Map dialog names for clustering
        dialogs_info = {}
        for node_id, node_data in self.G.nodes(data=True):
            d_id = node_data.get('dialog_id')
            if d_id and d_id != "GLOBAL" and d_id not in dialogs_info:
                dialogs_info[d_id] = node_data.get('dialog_name', 'Unnamed Dialog') 

        # 2. Render the Entry Point
        if self.G.has_node("USER_ENTRY"):
            node_data = self.G.nodes["USER_ENTRY"]
            html_label = self.render_entry_point(node_data)
            self.dot.node("USER_ENTRY", label=html_label)
        
        # 3. Render Nodes Grouped by Subgraph (Clusters)
        for d_id, d_name in dialogs_info.items():
            with self.dot.subgraph(name=f'cluster_{d_id}') as c:
                c.attr(label=f'{d_name} - {d_id}', style='dashed', color='blue', fontname='Helvetica')
                
                for node_id, node_data in self.G.nodes(data=True):
                    if node_data.get('dialog_id') == d_id:
                        macro_type = node_data.get("macro_type", "UNKNOWN")
                        # Dispatch rendering to the appropriate module
                        rendering_function = self.render_dispatcher.get(macro_type, self.render_unknown)
                        
                        html_label = rendering_function(node_data, attributes_dict=self.attributes)
                        c.node(node_id, label=html_label)
            
        # 4. Render Edges (Transitions)
        for u, v, edge_data in self.G.edges(data=True):
            label, line_color, text_color, line_style = self._get_edge_formatting(edge_data)

            self.dot.edge(
                u, v, 
                label=label, 
                color=line_color, 
                fontcolor=text_color, 
                style=line_style, 
                fontsize='10'
            )

    def view(self, filename='chatbot_architecture'):
        """
        Compiles the dot file and opens the generated PDF viewer.
        """
        print(f"Rendering PDF: {filename}.pdf...")
        self.dot.render(filename, view=True)