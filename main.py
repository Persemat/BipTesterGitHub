import json
import os
import networkx as nx
import shutil
# Assicurati che l'import corrisponda alla struttura delle tue cartelle
from parsing.parser import ChatbotParser 
from rendering.renderer import ChatbotRenderer
from test_generation import path_finder
from test_generation.path_finder import TestPathFinder
from test_generation.rendering_paths import render_paths
from test_generation.botium_translator import BotiumTranslator

def main():
    # Caricamento file json
    print("Lettura del file JSON in corso...")
    try:
        with open('chatbots/GreenHub_OpenChannel.json', 'r', encoding='utf-8') as f:
            json_data = json.load(f)
    except FileNotFoundError:
        print("Errore: Impossibile trovare il file GreenHub_OpenChannel.json!")
        return

    # Inizializzazione Parser
    print("Inizializzazione del Parser...")
    parser = ChatbotParser(json_data)

    # Estrazione dei nodi
    print("Estrazione dei nodi in corso...\n")
    parser.process_all_elements()

    # Stampe verifica grafo
    print("="*50)
    print(f"TOTALE NODI CREATI: {parser.G.number_of_nodes()}")
    print(f"TOTALE ARCHI CREATI : {parser.G.number_of_edges()}")
    print("="*50)

    print("\n--- CONTENUTO DI UN NODO ---")
    if parser.G.has_node("943568_2"):
        dati_nodo = parser.G.nodes["943568_2"]
        print(json.dumps(dati_nodo, indent=4))
    
    print("\n--- ELENCO ARCHI E TRANSIZIONI ---")
    for u, v, data in parser.G.edges(data=True):
        print(f"Arco da [{u}] a [{v}] con dati: {data}")

    #STAMPA DEI NODI E DEGLI ARCHI IN MEMORIA (G.nodes e G.adj) PER VERIFICA
    print("\n" + "="*60)
    print(" L'ANAGRAFE DEI NODI (G.nodes)")
    print("="*60)
    # Convertiamo i nodi in un dizionario Python standard per stamparli bene
    nodes = dict(parser.G.nodes(data=True))
    print(json.dumps(nodes, indent=4, ensure_ascii=False))

    print("\n" + "="*60)
    print("IL DIZIONARIO DI ADIACENZA (G.adj / Archi)")
    print("="*60)
    # Questa funzione estrae l'esatta struttura di routing $O(1)$
    adjacency_dict = nx.to_dict_of_dicts(parser.G)
    print(json.dumps(adjacency_dict, indent=4, ensure_ascii=False))

    print("\n Avvio motore generazione test Botium...")

    nodes_dict = dict(parser.G.nodes(data=True))
    adj_dict = dict(parser.G.adj)

    path_finder = TestPathFinder(nodes_dict, adj_dict, parser.G)
    paths_found = path_finder.generate_paths(start_node="USER_ENTRY")

    print(f"\n{'='*50}")
    print(f" TOTAL PATHS GENERATED: {len(paths_found)}")
    print(f"{'='*50}")
    
    for i, path in enumerate(paths_found, start=1):
        print(f"\n--- Test Path {i} ---")
        
        for step in path:
            source = step.get('source')
            target = step.get('target')
            edge = step.get('edge_data')
            
            # Estraiamo il tipo di condizione per rendere la stampa parlante
            if edge:
                condition = edge.get('condition_type', 'UNKNOWN')
                # Dettaglio extra per le keyword testuali
                if condition == "KEYWORD_COMPARE":
                    condition += f" ({edge.get('keyword_name', '')})"
            else:
                condition = "START"
                
            # Identifica se il passo è il trigger del fallback e avvia la recovery
            is_loop = step.get('is_loop', False)
            loop_marker = " [LOOP DETECTED! -> Avvio Recovery verso la foglia]" if is_loop else ""
            
            print(f"  {source} --[{condition}]--> {target}{loop_marker}")
            
    print(f"\n{'='*50}\n")

    test_configuration = {
    "CSAT_DEFAULT": "4",
    "LOCATION_DEFAULT": "Lat: 45.46, Long: 9.19"
    }

    translator = BotiumTranslator(nodes_dict, mock_data = test_configuration)

    output_folder = os.path.join("botium", "spec", "generated_tests")
    os.makedirs(output_folder, exist_ok=True)

    if os.path.exists(output_folder):
        shutil.rmtree(output_folder)
    os.makedirs(output_folder, exist_ok=True)

    for i, path in enumerate(paths_found, start = 1):
        convo_text = translator.translate_path(path, i )
        file_path = os.path.join(output_folder, f"Test_Path_{i}.convo.txt")
        with open(file_path, 'w', encoding='utf-8') as f:
            f.write(convo_text)

    utterances_content = translator.generate_utterances_file()
    utterances_path = os.path.join(output_folder, "bursts.utterances.txt")
    with open(utterances_path, "w", encoding="utf-8") as f:
        f.write(utterances_content)

    print(f"✅ Generazione completata! Creati {len(paths_found)} file .convo.txt e 1 file .utterances.txt.")

    print("Avvio motore grafico Graphviz...")
    graph = ChatbotRenderer(parser.G, parser.attributes)
    graph.render()
    graph.view("grafo prova")
if __name__ == "__main__":
    main()