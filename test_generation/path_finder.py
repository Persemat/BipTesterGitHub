import networkx as nx
from test_generation.utils.mock_registry import DATATYPE_MOCKS

class TestPathFinder:
    def __init__(self, g_nodes, g_adj, nx_graph):
        """
        Initializes the path finder with the NetworkX graph and its properties.
        """
        self.nodes = g_nodes
        self.adj = g_adj
        self.G = nx_graph
        self.all_test_paths = []

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
        This ensures tests don't hang indefinitely upon encountering an infinite loop.
        """
        if not self.leaf_nodes:
            return []

        shortest_path_nodes = None
        min_length = float('inf')

        # Iterate over all leaf nodes to find the globally shortest exit route
        for leaf in self.leaf_nodes:
            try:
                # Use NetworkX's built-in Dijkstra/BFS algorithm for unweighted shortest path
                path = nx.shortest_path(self.G, source=start_node, target=leaf)
                if len(path) < min_length:
                    min_length = len(path)
                    shortest_path_nodes = path
            except nx.NetworkXNoPath:
                # If a specific leaf is unreachable from this node, skip it
                continue

        # If no escape path is found or the path is trivial, return an empty list
        if not shortest_path_nodes or len(shortest_path_nodes) < 2:
            return []

        escape_steps = []
        # Convert the list of node IDs (e.g., ['A', 'B', 'C']) into standard step dictionaries
        for i in range(len(shortest_path_nodes) - 1):
            u = shortest_path_nodes[i]
            v = shortest_path_nodes[i+1]
            
            # Retrieve the specific edge attributes connecting 'u' to 'v'
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
        """
        Recursive Depth-First Search algorithm with backtracking, loop breaking, and pruning.
        """
        # 1. STOP CONDITION 1: Leaf Node (e.g., CLOSE_SESSION or end of flow)
        if current_node not in self.adj or not self.adj[current_node]:
            # Save a shallow copy of the current path to prevent reference mutation
            self.all_test_paths.append(list(current_path))
            return

        # 2. EXPLORE BRANCHES: Iterate over all outgoing edges from the current node
        for target_node, edges in self.adj[current_node].items():
            for edge_index, edge_data in edges.items():

                c_type = edge_data.get("condition_type", "")
                source_data = self.nodes.get(current_node, {})

                # --- SMART PRUNING VIA MOCK REGISTRY ---
                # Skip dynamically infeasible paths (e.g., FALLBACKs for fields that accept any input)
                if c_type == "FALLBACK" and source_data.get("specific_type") == "GET_ATTRIBUTE":
                    
                    data_type = source_data.get("data_type", "TEXT").lower()
                    mock_info = DATATYPE_MOCKS.get(data_type, DATATYPE_MOCKS["text"])
                    
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