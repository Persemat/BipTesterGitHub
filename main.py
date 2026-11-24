"""
Main execution module for the Automated Chatbot Testing Tool.

This script orchestrates the entire pipeline:
1. Loads the Infobip chatbot graph export (JSON) dynamically via CLI.
2. Parses the JSON into a NetworkX directed graph.
3. Generates all possible conversational paths using a Depth-First Search (DFS) algorithm.
4. Translates the paths into Botium-compatible test cases (.convo.txt and .utterances.txt).
5. Renders a visual representation of the chatbot graph using Graphviz (optional).
"""

import argparse
import json
import os
import sys
import networkx as nx
import shutil
import logging
from dotenv import load_dotenv
from test_generation.rendering_paths import render_paths
from parsing.parser import ChatbotParser 
from rendering.renderer import ChatbotRenderer
from test_generation.path_finder import PathFinder
from test_generation.botium_translator import BotiumTranslator
from parsing.parsing_utils import load_components
from test_generation.utils.load_json import _load_mock_registry

def main():
    load_dotenv()  # Load environment variables from .env file
    # 1. Configure CLI arguments
    parser = argparse.ArgumentParser(
        description="Infobip Chatbot Test Generator - Orchestrates parsing, path generation, and Botium translation."
    )
    
    # Required argument: The chatbot JSON file
    parser.add_argument(
        "-b", "--bot", 
        type=str, 
        required=True, 
        help="Path to the JSON file exported from Infobip (e.g., chatbots/GreenHub_OpenChannel_Simple.json)"
    )
    
    # Optional argument: Output directory
    parser.add_argument(
        "-o", "--output", 
        type=str, 
        default=os.getenv("BOTIUM_TEST_DIR", os.path.join("botium", "spec", "generated_tests")),
        help="Directory where generated Botium tests will be saved"
    )
    
    # Optional argument: Skip Graphviz rendering (useful for CI/CD or fast generation)
    parser.add_argument(
        "--no-render", 
        action="store_true", 
        help="Disable Graphviz rendering of the chatbot graph"
    )

    args = parser.parse_args()

    # Configure basic logger to replace some print statements (keeps output clean)
    logging.basicConfig(level=logging.INFO, format='%(message)s')

    # 2. Load the JSON export from Infobip
    logging.info(f"Reading JSON file: {args.bot}...")
    try:
        with open(args.bot, 'r', encoding='utf-8') as f:
            json_data = json.load(f)
    except FileNotFoundError:
        logging.error(f"❌ Error: Could not find the file {args.bot}!")
        sys.exit(1)

    # Load component registry and component JSONs
    comp_dict = load_components(
        mapping_file_path="chatbots/component_registry.json",
        components_dir="chatbots/components"
    )

    # 3. Initialize Parser and process nodes
    chatbot_parser = ChatbotParser(json_data, component_jsons=comp_dict)
    chatbot_parser.process_all_elements()
    
    # 4. Path Generation
    logging.info("\nStarting Botium test generation engine...")
    nodes_dict = dict(chatbot_parser.G.nodes(data=True))
    adj_dict = dict(chatbot_parser.G.adj)

    path_finder = PathFinder(nodes_dict, adj_dict, chatbot_parser.G)
    paths_found = path_finder.generate_paths(start_node="USER_ENTRY")
   
    # 5. Botium Translation
    DATATYPE_MOCKS = _load_mock_registry()
    translator = BotiumTranslator(nodes_dict, mock_data=DATATYPE_MOCKS, attributes=chatbot_parser.attributes)

    # Output directory management
    output_folder = args.output
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

    logging.info(f"✅ Generation completed! Created {len(paths_found)} .convo.txt files and {len(utterances_files)} .utterances file(s) in '{output_folder}'.")

    if translator.unknown_nodes_report:
        logging.warning("\n" + "!" * 60)
        logging.warning("⚠️  ACTION REQUIRED: UNHANDLED NODES DETECTED")
        logging.warning("The following test files contain placeholders ('TODO_REPLACE_UNKNOWN_NODE_...')")
        logging.warning("that MUST be manually edited before running E2E tests:")
        for p_idx, n_id, s_type in translator.unknown_nodes_report:
            logging.warning(f"  - Test_Path_{p_idx}.convo.txt -> Node ID: {n_id} (Type: {s_type})")
        logging.warning("!" * 60 + "\n")

    # 6. Graph Rendering
    if not args.no_render:
        logging.info("Starting Graphviz rendering engine...")
        graph = ChatbotRenderer(chatbot_parser.G, chatbot_parser.attributes)
        graph.render()
        graph.view("chatbot_graph")
    else:
        logging.info("⏭️ Graph rendering skipped (--no-render).")

if __name__ == "__main__":
    main()