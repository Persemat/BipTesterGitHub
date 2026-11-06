import networkx as nx


class PathFinder:
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
        
        initial_step = {
            "source": None,
            "target": start_node,
            "edge_data": None,
            "target_data": self.nodes.get(start_node, {})
        }
        
        visited = set([start_node])    
        
        self.dfs(current_node=start_node, current_path=[initial_step], visited=visited)
        
        unique_paths = []
        for path in self.all_test_paths:
            if path not in unique_paths:
                unique_paths.append(path)

        print(f"[DFS] Exploration completed! Found {len(unique_paths)} unique paths.")
        return unique_paths

    def get_escape_path(self, start_node):
        """
        Calculates the shortest valid route from a looped node to a leaf node.
        Prefer already visited edges without mutating the graph.

        When a cycle is detected during DFS, the test cannot simply stop mid-conversation,
        otherwise the chatbot session would remain open and corrupt subsequent Botium tests.
        This method finds an escape route to properly terminate the conversation, strongly
        preferring already visited edges so unvisited branches are saved for their own dedicated tests.
        """
        if not self.leaf_nodes:
            return []

        # Define a custom edge weight function that prioritizes already visited edges
        def edge_weight(u, v, edges_dict):
            return min(
                1 if (u, v, k) in self.global_visited_edges else 1000
                for k in edges_dict
            )
        
        shortest_path_nodes = None
        min_cost = float('inf')

        # Find the shortest path to any leaf node
        for leaf in self.leaf_nodes:
            try:
                cost = nx.shortest_path_length(self.G, source=start_node, target=leaf, weight=edge_weight)
                if cost < min_cost:
                    min_cost = cost
                    shortest_path_nodes = nx.shortest_path(self.G, source=start_node, target=leaf, weight=edge_weight)
            except nx.NetworkXNoPath:
                continue
                

        if not shortest_path_nodes or len(shortest_path_nodes) < 2:
            return []

        # Build the escape steps based on the shortest path found
        escape_steps = []
        
        for i in range(len(shortest_path_nodes) - 1):
            u, v = shortest_path_nodes[i], shortest_path_nodes[i + 1]
            
            # Take the first visited edge if available, otherwise take the first edge
            parallel_edges = self.G[u][v]
            best_key = min(parallel_edges, key=lambda k: 1 if (u, v, k) in self.global_visited_edges else 1000)
            
            escape_steps.append({
                "source": u,
                "target": v,
                "edge_data": parallel_edges[best_key],
                "target_data": self.nodes.get(v, {})
            })

        return escape_steps
    
    def dfs(self, current_node, current_path, visited):
        """
        Recursive Depth-First Search algorithm with backtracking and loop breaking.
        Assumes unfeasible edges have already been pruned by the parser.
        """
        if current_node not in self.adj or not self.adj[current_node]:
            self.all_test_paths.append(list(current_path))
            return

        unvisited_edges = []
        for target_node, edges in self.adj[current_node].items():
            for edge_index, edge_data in edges.items():
                edge_sig = (current_node, target_node, edge_index)
                if edge_sig not in self.global_visited_edges:
                    unvisited_edges.append((target_node, edge_index, edge_data, edge_sig))

        if not unvisited_edges:
            escape_route = self.get_escape_path(current_node)
            if escape_route:
                self.all_test_paths.append(list(current_path) + escape_route)
            else:
                self.all_test_paths.append(list(current_path))
            return

        for target_node, edge_index, edge_data, edge_sig in unvisited_edges:
            self.global_visited_edges.add(edge_sig)

            step = {
                "source": current_node,
                "target": target_node,
                "edge_data": edge_data,
                "target_data": self.nodes.get(target_node, {})
            }

            if target_node in visited:
                step["is_loop"] = True
                loop_path = list(current_path)
                loop_path.append(step)
                
                escape_route = self.get_escape_path(target_node)
                if escape_route:
                    loop_path.extend(escape_route)
                
                self.all_test_paths.append(loop_path)
                continue

            current_path.append(step)
            visited.add(target_node)

            self.dfs(target_node, current_path, visited)

            visited.remove(target_node)
            current_path.pop()