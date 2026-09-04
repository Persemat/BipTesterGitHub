import networkx as nx
from  test_generation.utils.mock_registry import DATATYPE_MOCKS

class TestPathFinder:
    def __init__(self, g_nodes, g_adj, nx_graph):
        self.nodes = g_nodes
        self.adj = g_adj
        self.G = nx_graph
        self.all_test_paths = []

        # Identify leaf nodes (nodes with no outgoing edges)
        self.leaf_nodes = [n for n in self.G.nodes() if self.G.out_degree(n) == 0]

    def generate_paths(self, start_node="USER_ENTRY"):
        """
        Triggers the graph exploration.
        Returns a list of complete paths (each path is a list of steps).
        """
        print(f"\n[DFS] Starting exploration from root node: {start_node}...")
        
        # The initial step ("The entry point")
        initial_step = {
            "source": None,
            "target": start_node,
            "edge_data": None,
            "target_data": self.nodes.get(start_node, {})
        }
        
        # Set of visited nodes (initially contains only the starting node)
        visited = set([start_node])    
        # Start the recursive search
        self.dfs(current_node=start_node, current_path=[initial_step], visited=visited)
        
        unique_paths = []
        for path in self.all_test_paths:
            if path not in unique_paths:
                unique_paths.append(path)

        print(f"[DFS] Exploration completed! Found {len(unique_paths)} unique paths.")
        return unique_paths

    def get_escape_path(self, start_node):
        """Find the shortest path to a leaf node and convert it to valid steps."""
        if not self.leaf_nodes:
            return []

        shortest_path_nodes = None
        min_length = float('inf')

        # Find the shortest path to any leaf node
        for leaf in self.leaf_nodes:
            try:
                path = nx.shortest_path(self.G, source=start_node, target=leaf)
                if len(path) < min_length:
                    min_length = len(path)
                    shortest_path_nodes = path
            except nx.NetworkXNoPath:
                continue

        if not shortest_path_nodes or len(shortest_path_nodes) < 2:
            return []

        escape_steps = []
        # Convert the list of nodes (e.g., ['A', 'B', 'C']) to steps in the dictionary
        for i in range(len(shortest_path_nodes) - 1):
            u = shortest_path_nodes[i]
            v = shortest_path_nodes[i+1]
            
            # Retrieve the default edge between 'u' and 'v' from the adjacency matrix
            edge_data = {}
            if u in self.adj and v in self.adj[u]:
                first_edge_key = list(self.adj[u][v].keys())[0]
                edge_data = self.adj[u][v][first_edge_key]
                
            step = {
                "source": u,
                "target": v,
                "edge_data": edge_data,
                "target_data": self.nodes.get(v, {})
            }
            escape_steps.append(step)

        return escape_steps

    def dfs(self, current_node, current_path, visited):
        # 1. STOP CONDITION 1: Leaf Node (e.g., CLOSE_SESSION or no outgoing edges)
        if current_node not in self.adj or not self.adj[current_node]:
            # We must use list(current_path) to append a COPY, not a reference
            self.all_test_paths.append(list(current_path))
            return

        # 2. EXPLORE BRANCHES
        for target_node, edges in self.adj[current_node].items():
            for edge_index, edge_data in edges.items():

                c_type = edge_data.get("condition_type", "")
                source_data = self.nodes.get(current_node, {})

                # Skip invalid paths for GET_ATTRIBUTE nodes with no invalid mock data and no validation
                # --- PRUNING INTELLIGENTE CON MOCK REGISTRY ---
                if c_type == "FALLBACK" and source_data.get("specific_type") == "GET_ATTRIBUTE":
                    
                    # Ora source_data ha il data_type! Lo prendiamo e lo mettiamo in minuscolo
                    data_type = source_data.get("data_type", "TEXT").lower()
                    
                    # Recuperiamo le regole dal Registry
                    mock_info = DATATYPE_MOCKS.get(data_type, DATATYPE_MOCKS["text"])
                    
                    # Taglio dei rami morti
                    if mock_info["invalid"] is None:
                        print(f"[PRUNING] Ramo Fallback rimosso su '{current_node}' (Tipo '{data_type}' accetta tutto).")
                        continue 

                step = {
                    "source": current_node,
                    "target": target_node,
                    "edge_data": edge_data,
                    "target_data": self.nodes.get(target_node, {})
                }

                # 3. STOP CONDITION 2: Loop Detection (Fallback and circular timeouts)
                if target_node in visited:
                    step["is_loop"] = True
                    loop_path = list(current_path)
                    loop_path.append(step)
                    
                    self.all_test_paths.append(loop_path)
                    escape_route = self.get_escape_path(target_node)
                    if escape_route:
                        loop_path.extend(escape_route)
                        self.all_test_paths.append(loop_path)
                    # Use 'continue' to skip this specific branch, but keep checking other edges
                    continue

                # 4. DIVE DEEPER (Recursion)
                current_path.append(step)
                visited.add(target_node)

                # Recursive call
                self.dfs(target_node, current_path, visited)

                # 5. BACKTRACKING
                # Clean up the current path and visited set for the next iteration of the 'for' loop
                visited.remove(target_node)
                current_path.pop()