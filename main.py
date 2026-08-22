import json
import networkx as nx
# Assicurati che l'import corrisponda alla struttura delle tue cartelle
from parsing.parser import ChatbotParser 
from rendering.renderer import ChatbotRenderer

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



    print("Avvio motore grafico Graphviz...")
    graph = ChatbotRenderer(parser.G, parser.attributes)
    graph.render()
    graph.view("grafo prova")
if __name__ == "__main__":
    main()