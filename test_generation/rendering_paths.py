def render_paths(paths):
    """
    Prints the extracted paths in a human-readable format for terminal verification.
    """
    print(f"\n{'='*60}")
    print(f"📊 EXTRACTION RESULTS: Found {len(paths)} unique paths")
    print(f"{'='*60}")

    for i, path in enumerate(paths):
        print(f"\n🟢 Path {i + 1} (Length: {len(path)} steps):")
        
        for step in path:
            target = step["target"]
            edge = step["edge_data"]
            
            if edge is None:
                action = "ENTRY"
            else:
                c_type = edge.get("condition_type", "AUTO")
                if c_type == "KEYWORD_COMPARE":
                    action = f"KEYWORD ({edge.get('keyword_name', 'No Name')})"
                elif c_type == "TIMEOUT":
                    action = f"TIMEOUT ({edge.get('duration', 0)}s)"
                elif c_type == "FALLBACK":
                    action = "FALLBACK"
                elif c_type == "INTENT":
                    action = f"INTENT ({edge.get('intent_name', 'Unknown')})"
                elif c_type == "EVALUATION":
                    action = f"EVAL ({edge.get('condition', 'Condition')})"
                else:
                    action = "AUTO"
            
            loop_marker = " 🔄 [LOOP DETECTED - STOP]" if step.get("is_loop") else ""
            print(f"  {action.ljust(25)} ➔  {target}{loop_marker}")
            
    print(f"\n{'='*60}\n")