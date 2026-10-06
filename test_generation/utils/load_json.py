import json
import os

def _load_mock_registry():
    """
    Loads the mock data registry from the external JSON file 
    located in the root directory of the project.
    """
    # Current file directory: BipTester/test_generation/utils
    current_dir = os.path.dirname(os.path.abspath(__file__))
    
    # Parent directory: BipTester/test_generation
    parent_dir = os.path.dirname(current_dir)
    
    project_root = os.path.dirname(parent_dir)
    
    json_path = os.path.join(project_root, 'mock_registry.json')
    
    try:
        with open(json_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
            return data.get("DATATYPE_MOCKS", {})
    except FileNotFoundError:
        print(f"Warning: mock_registry.json file not found at {json_path}")
        return {}