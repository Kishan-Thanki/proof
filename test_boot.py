from proof.core.compiler import load_and_compile_config


def main():
    print("Loading and compiling proof.yaml...")
    
    # This triggers PyYAML -> Pydantic -> fastjsonschema
    config = load_and_compile_config("scenarios/example.yaml")
    
    print("\nSuccessfully converted to Python Objects!")
    print("--- Accessing data using dot-notation ---")
    print(f"Global Base URL: {config.global_config.base_url}")
    
    scenario = config.scenarios[0]
    step = scenario.steps[0]
    
    print(f"\nScenario: '{scenario.name}' (runs every {scenario.interval_seconds}s)")
    print(f"Step 1: '{step.name}'")
    print(f"  -> Sending {step.request.method} to {step.request.path}")
    print(f"  -> Will extract variable: {step.extract}")
    
    print("\n--- Checking the Compiled JSON Schema ---")
    # This is the C/Python function pointer, NOT a dictionary!
    schema_func = step.expect.compiled_schema
    print(f"Memory Pointer : {schema_func}")
    print(f"Is it callable?: {callable(schema_func)}")

if __name__ == "__main__":
    main()
