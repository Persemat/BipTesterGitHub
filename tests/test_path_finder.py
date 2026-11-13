import pytest
import networkx as nx
from test_generation.path_finder import PathFinder

@pytest.fixture
def simple_graph():
    """
    Fixture (pre-condizione): Crea un MultiDiGraph 'giocattolo' piccolissimo.
    Struttura: USER_ENTRY --> Nodo_A --> Nodo_B (Foglia)
    """
    G = nx.MultiDiGraph()
    
    # Adding nodes with types
    G.add_node("USER_ENTRY", type="start")
    G.add_node("Node_A", type="normal")
    G.add_node("Node_B", type="end")
    
    # Adding edges to create a linear path
    G.add_edge("USER_ENTRY", "Node_A", key=0, condition_type="DEFAULT")
    G.add_edge("Node_A", "Node_B", key=0, condition_type="DEFAULT")
    
    # Exctract nodes and adjacency dictionaries for PathFinder
    nodes_dict = dict(G.nodes(data=True))
    adj_dict = dict(G.adj)
    
    # Return the initialized PathFinder and the graph
    return PathFinder(nodes_dict, adj_dict, G), G

def test_generate_paths_simple_linear(simple_graph):
    """Testa se il PathFinder riesce a trovare l'unico percorso possibile in un grafo lineare."""
    path_finder, _ = simple_graph
    
    paths = path_finder.generate_paths(start_node="USER_ENTRY")
    
    # Assert
    assert len(paths) == 1, "Ci dovrebbe essere esattamente 1 percorso"
    
    # The path should contain two steps: USER_ENTRY -> Node_A and Node_A -> Node_B
    step1 = paths[0][0]
    step2 = paths[0][1]
    
    assert step1["source"] == "USER_ENTRY"
    assert step1["target"] == "Node_A"
    
    assert step2["source"] == "Node_A"
    assert step2["target"] == "Node_B"


def test_get_escape_path_finds_leaf(simple_graph):
    """Test if the escape logic correctly identifies the path to the leaf node."""
    path_finder, G = simple_graph
    
    # PathFinder should know that Node_B is a leaf node
    path_finder.leaf_nodes = ["Node_B"]
    
    # Act: ask for the escape path from Node_A to the leaf Node_B
    escape_steps = path_finder.get_escape_path(start_node="Node_A")
    
    # Assert
    assert len(escape_steps) == 1, "La via di fuga da A a B è lunga 1 step"
    assert escape_steps[0]["source"] == "Node_A"
    assert escape_steps[0]["target"] == "Node_B"