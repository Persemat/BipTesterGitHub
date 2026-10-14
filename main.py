"""
Main execution module for the Automated Chatbot Testing Tool.

This script orchestrates the entire pipeline:
1. Loads the Infobip chatbot graph export (JSON).
2. Parses the JSON into a NetworkX directed graph.
3. Generates all possible conversational paths using a Depth-First Search (DFS) algorithm.
4. Translates the paths into Botium-compatible test cases (.convo.txt and .utterances.txt).
5. Renders a visual representation of the chatbot graph using Graphviz.
"""

import json
import os
import networkx as nx
import shutil
from test_generation.rendering_paths import render_paths
from parsing.parser import ChatbotParser 
from rendering.renderer import ChatbotRenderer
from test_generation.path_finder import TestPathFinder
from test_generation.botium_translator import BotiumTranslator
from parsing.parsing_utils import load_components
from test_generation.utils.load_json import _load_mock_registry


def main():
    """
    Entry point of the application. 
    Executes the parsing, path generation, translation, and rendering phases sequentially.
    """
    # 1. Load the JSON export from Infobip
    print("Reading JSON file...")
    try:
        with open('chatbots/GreenHub_OpenChannel_Simple.json', 'r', encoding='utf-8') as f:
            json_data = json.load(f)
    except FileNotFoundError:
        print("Error: Could not find the file GreenHub_OpenChannel_Simple.json!")
        return

    comp_dict = load_components(
        mapping_file_path = "chatbots/component_registry.json",
        components_dir = "chatbots/components"
    )

    # Initialize Parser and process nodes
    parser = ChatbotParser(json_data, component_jsons=comp_dict)
    #Trigger the parsing process to build the graph and extract attributes
    parser.process_all_elements()

    # Print Graph verification metrics
    print("=" * 50)
    print(f"TOTAL NODES CREATED: {parser.G.number_of_nodes()}")
    print(f"TOTAL EDGES CREATED: {parser.G.number_of_edges()}")
    print("=" * 50)

    print("\n--- NODE CONTENT SAMPLE ---")
    if parser.G.has_node("943568_2"):
        node_data = parser.G.nodes["943568_2"]
        print(json.dumps(node_data, indent=4))
    """
    print("\n--- EDGES AND TRANSITIONS ---")
    for u, v, data in parser.G.edges(data=True):
        print(f"Edge from [{u}] to [{v}] with data: {data}")
    """

    # Print Graph memory structures for debugging
    print("\n" + "=" * 60)
    print(" NODES REGISTRY (G.nodes)")
    print("=" * 60)
    nodes = dict(parser.G.nodes(data=True))
    print(json.dumps(nodes, indent=4, ensure_ascii=False))

    print("\n" + "=" * 60)
    print(" ADJACENCY DICTIONARY (G.adj / Edges)")
    print("=" * 60)
    # Extract exact O(1) routing structure
    adjacency_dict = nx.to_dict_of_dicts(parser.G)
    print(json.dumps(adjacency_dict, indent=4, ensure_ascii=False))
    
    # 3. Path Generation
    print("\nStarting Botium test generation engine...")
    nodes_dict = dict(parser.G.nodes(data=True))
    adj_dict = dict(parser.G.adj)

    path_finder = TestPathFinder(nodes_dict, adj_dict, parser.G)
    paths_found = path_finder.generate_paths(start_node="USER_ENTRY")
    """
    print(f"\n{'=' * 50}")
    print(f" TOTAL PATHS GENERATED: {len(paths_found)}")
    print(f"{'=' * 50}")
    
    # Print the paths to the terminal for observability
    render_paths(paths_found)
    """
    # 4. Botium Translation

    DATATYPE_MOCKS = _load_mock_registry()

    translator = BotiumTranslator(nodes_dict, mock_data=DATATYPE_MOCKS, attributes=parser.attributes)

    # Output directory management
    output_folder = os.path.join("botium", "spec", "generated_tests")
    if os.path.exists(output_folder):
        shutil.rmtree(output_folder) # Clean previous test suite
    os.makedirs(output_folder, exist_ok=True)

    # Write Botium .convo.txt files
    for i, path in enumerate(paths_found, start=1):
        convo_text = translator.translate_path(path, i)
        file_path = os.path.join(output_folder, f"Test_Path_{i}.convo.txt")
        with open(file_path, 'w', encoding='utf-8') as f:
            f.write(convo_text)

    utterances_folder = os.path.join(output_folder, "utterances")
    os.makedirs(utterances_folder, exist_ok=True)

    # Write Botium .utterances.txt file
    utterances_files = translator.get_utterances_files()

    for filename, content in utterances_files.items():
        file_path = os.path.join(utterances_folder, filename)
        with open(file_path, 'w', encoding='utf-8', newline='\n') as f:
            f.write(content)

    

    print(f"✅ Generation completed! Created {len(paths_found)} .convo.txt files and 1 .utterances.txt file.")

    # 5. Graph Rendering
    print("Starting Graphviz rendering engine...")
    graph = ChatbotRenderer(parser.G, parser.attributes)
    graph.render()
    graph.view("grafo prova")

if __name__ == "__main__":
    main()