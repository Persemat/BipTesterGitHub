import networkx as nx

from test_generation.utils.load_json import _load_mock_registry

DATATYPE_MOCKS = _load_mock_registry()

class TestPathFinder:
    def __init__(self, g_nodes, g_adj, nx_graph):
        """
        Initializes the path finder with the NetworkX graph and its properties.
        """
        self.nodes = g_nodes
        self.adj = g_adj
        self.G = nx_graph
        self.all_test_paths = []
        self.global_visited_edges = set()

        # Identify leaf nodes (nodes with no outgoing edges, representing the end of a conversation)
        self.leaf_nodes = [n for n in self.G.nodes() if self.G.out_degree(n) == 0]

    def generate_paths(self, start_node="USER_ENTRY"):
        """
        Triggers the graph exploration using Depth-First Search (DFS).
        Returns a list of complete and unique conversational paths (each path is a list of steps).
        """
        print(f"\n[DFS] Starting exploration from root node: {start_node}...")
        
        # Define the initial step representing the entry point of the chatbot
        initial_step = {
            "source": None,
            "target": start_node,
            "edge_data": None,
            "target_data": self.nodes.get(start_node, {})
        }
        
        # Initialize the set of visited nodes to prevent immediate loops
        visited = set([start_node])    
        
        # Start the recursive DFS exploration
        self.dfs(current_node=start_node, current_path=[initial_step], visited=visited)
        
        # Deduplicate paths to ensure the test suite contains only unique scenarios
        unique_paths = []
        for path in self.all_test_paths:
            if path not in unique_paths:
                unique_paths.append(path)

        print(f"[DFS] Exploration completed! Found {len(unique_paths)} unique paths.")
        return unique_paths

    def get_escape_path(self, start_node):
        """
        Calculates the shortest valid route from a looped node to a leaf node.
        Uses a weighted Dijkstra approach to prefer already visited edges,
        preventing the escape route from consuming unvisited test paths.
        """
        if not self.leaf_nodes:
            return []

        # 1. Dynamic weight assignment (Cost 1 = already visited, Cost 1000 = unexplored)
        for u, v, key, data in self.G.edges(keys=True, data=True):
            # Signature of the edge: node pair and edge key that uniquely identifies it in a MultiDiGraph
            edge_sig = (u, v, key)
            if edge_sig in self.global_visited_edges:
                self.G[u][v][key]['weight'] = 1     
            else:
                self.G[u][v][key]['weight'] = 1000  

        shortest_path_nodes = None
        min_length = float('inf')

        # 2. Search for the minimum cost path (Weighted Dijkstra) to any leaf node
        for leaf in self.leaf_nodes:
            try:
                # NetworkX automatically uses Dijkstra when weight='weight' is specified
                path = nx.shortest_path(self.G, source=start_node, target=leaf, weight='weight')
                
                # Calculate the actual total cost of this path on the MultiDiGraph
                path_cost = 0
                for i in range(len(path) - 1):
                    u = path[i]
                    v = path[i+1]
                    # Get the weight of the cheapest edge between u and v
                    min_edge_weight = min(self.G[u][v][k].get('weight', 1000) for k in self.G[u][v])
                    path_cost += min_edge_weight
                
                if path_cost < min_length:
                    min_length = path_cost
                    shortest_path_nodes = path
            except nx.NetworkXNoPath:
                continue

        if not shortest_path_nodes or len(shortest_path_nodes) < 2:
            return []

        escape_steps = []
        
        # 3. Step-by-step path reconstruction
        for i in range(len(shortest_path_nodes) - 1):
            u = shortest_path_nodes[i]
            v = shortest_path_nodes[i+1]
            
            best_edge_key = None
            best_weight = float('inf')
            edge_data = {}
            
            # Ensure extraction of the exact edge with the lowest weight
            if u in self.adj and v in self.adj[u]:
                for key, data in self.adj[u][v].items():
                    w = data.get('weight', 1000)
                    if w < best_weight:
                        best_weight = w
                        best_edge_key = key
                
                edge_data = self.adj[u][v][best_edge_key]
                
            step = {
                "source": u,
                "target": v,
                "edge_data": edge_data,
                "target_data": self.nodes.get(v, {})
            }
            escape_steps.append(step)

        return escape_steps
    
    def dfs(self, current_node, current_path, visited):
        """
        Recursive Depth-First Search algorithm with backtracking, loop breaking, and pruning.
        """
        # 1. STOP CONDITION 1: Leaf Node (e.g., CLOSE_SESSION or end of flow)
        if current_node not in self.adj or not self.adj[current_node]:
            # Save a shallow copy of the current path to prevent reference mutation
            self.all_test_paths.append(list(current_path))
            return

        # Identify unvisited edges from the current node to avoid redundant exploration
        unvisited_edges = []
        for target_node, edges in self.adj[current_node].items():
            for edge_index, edge_data in edges.items():
                edge_sig = (current_node, target_node, edge_index)
                if edge_sig not in self.global_visited_edges:
                    unvisited_edges.append((target_node, edge_index, edge_data, edge_sig))

        # If all outgoing edges have been visited, attempt to find an escape route to a leaf node
        if not unvisited_edges:
            escape_route = self.get_escape_path(current_node)
            if escape_route:
                self.all_test_paths.append(list(current_path) + escape_route)
            else:
                self.all_test_paths.append(list(current_path))
            return

        # 2. EXPLORE BRANCHES: Iterate over all outgoing edges from the current node
        for target_node, edge_index, edge_data, edge_sig in unvisited_edges:
                
                self.global_visited_edges.add(edge_sig)

                c_type = edge_data.get("condition_type", "")
                source_data = self.nodes.get(current_node, {})

                # --- SMART PRUNING VIA MOCK REGISTRY ---
                # Skip dynamically infeasible paths (e.g., FALLBACKs for fields that accept any input)
                if c_type == "FALLBACK" and source_data.get("specific_type") == "GET_ATTRIBUTE":
                    
                    data_type = source_data.get("data_type", "TEXT").lower()
                    
                    default_mock = DATATYPE_MOCKS.get("text", {"valid": "Generic_Text", "invalid": None})
                    mock_info = DATATYPE_MOCKS.get(data_type, default_mock)
                    
                    # Cut the dead branch if no invalid mock data exists for this data type
                    if mock_info["invalid"] is None:
                        print(f"[PRUNING] Dead fallback branch removed on '{current_node}' (Type '{data_type}' accepts anything).")
                        continue 

                step = {
                    "source": current_node,
                    "target": target_node,
                    "edge_data": edge_data,
                    "target_data": self.nodes.get(target_node, {})
                }

                # 3. STOP CONDITION 2: Loop Detection (Prevents infinite recursion)
                if target_node in visited:
                    step["is_loop"] = True
                    loop_path = list(current_path)
                    loop_path.append(step)
                    
                    # Save the path that successfully triggered the loop
                    self.all_test_paths.append(loop_path)
                    
                    # Attempt to force an exit to gracefully terminate the test case
                    escape_route = self.get_escape_path(target_node)
                    if escape_route:
                        loop_path.extend(escape_route)
                        self.all_test_paths.append(loop_path)
                        
                    # Stop descending into this specific branch, but continue exploring siblings
                    continue

                # 4. DIVE DEEPER: Prepare state for the next recursive depth
                current_path.append(step)
                visited.add(target_node)

                # Execute recursive call on the target node
                self.dfs(target_node, current_path, visited)

                # 5. BACKTRACKING: Restore state before checking the next sibling edge
                visited.remove(target_node)
                current_path.pop()