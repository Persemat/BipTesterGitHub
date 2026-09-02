def render_paths(paths):
    """
    Stampa i percorsi in un formato human-readable per la verifica a terminale.
    """
    print(f"\n{'='*60}")
    print(f"📊 RISULTATI ESTRAZIONE: Trovati {len(paths)} percorsi univoci")
    print(f"{'='*60}")

    for i, path in enumerate(paths):
        print(f"\n🟢 Percorso {i + 1} (Lunghezza: {len(path)} step):")
        
        for step in path:
            target = step["target"]
            edge = step["edge_data"]
            
            if edge is None:
                azione = "ENTRY"
            else:
                c_type = edge.get("condition_type", "AUTO")
                if c_type == "KEYWORD_COMPARE":
                    azione = f"KEYWORD (ID: {edge.get('keywordId')})"
                elif c_type == "TIMEOUT":
                    azione = f"TIMEOUT ({edge.get('duration', 0)}s)"
                elif c_type == "FALLBACK":
                    azione = "FALLBACK"
                elif c_type == "INTENT":
                    azione = f"INTENT ({edge.get('intent_name')})"
                elif c_type == "EVALUATION":
                    azione = f"EVAL ({edge.get('condition')})"
                else:
                    azione = "Auto"
            
            loop_marker = " 🔄 [LOOP DETECTED - STOP]" if step.get("is_loop") else ""
            print(f"  {azione.ljust(25)} ➔  {target}{loop_marker}")
            
    print(f"\n{'='*60}\n")