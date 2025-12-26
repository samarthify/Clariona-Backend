"""
Script to inspect Apify Twitter actor input schemas and supported fields
This performs a dry run by querying actor metadata, not running them
"""

import os
import json
from pathlib import Path
from dotenv import load_dotenv
from apify_client import ApifyClient

# Load environment variables
env_path = Path(__file__).parent.parent / "src" / "collectors" / '.env'
if not env_path.exists():
    env_path = Path(__file__).parent.parent / '.env'
load_dotenv(env_path)

# Actor IDs from the collector
ACTOR_CONFIGS = [
    {
        "id": "CJdippxWmn9uRfooo",  # Original actor ID
        "name": "Original Actor"
    },
    {
        "id": "nfp1fpt5gUlBwPcor",  # New actor ID
        "name": "New Actor"
    }
]

def inspect_actor_schema(client: ApifyClient, actor_id: str, actor_name: str):
    """Inspect an actor's input schema and return detailed information"""
    print(f"\n{'='*80}")
    print(f"Inspecting Actor: {actor_name} (ID: {actor_id})")
    print(f"{'='*80}\n")
    
    try:
        # Get actor details
        actor = client.actor(actor_id).get()
        print(f"Actor Name: {actor.get('name', 'N/A')}")
        print(f"Actor Username: {actor.get('username', 'N/A')}")
        print(f"Description: {actor.get('description', 'N/A')[:200]}...")
        print()
        
        # Get versions list
        versions_list = client.actor(actor_id).versions().list().items
        if versions_list:
            latest_version_info = versions_list[0]
            version_number = latest_version_info.get('versionNumber', 'N/A')
            print(f"Latest Version: {version_number}")
            
            # Try to get input schema from version
            try:
                version_detail = client.actor(actor_id).version(version_number).get()
                input_schema = version_detail.get('inputSchema', {})
                if input_schema:
                    print(f"Found input schema in version {version_number}")
            except Exception as ve:
                print(f"Could not get version detail: {ve}")
                input_schema = {}
        else:
            print("No versions found")
            input_schema = {}
        
        # Also check exampleRunInput which shows what fields the actor expects
        example_input = actor.get('exampleRunInput', {})
        if example_input:
            print(f"\nExample Run Input found with {len(example_input)} fields")
            print("This shows what fields the actor expects:")
        
        if not input_schema and example_input:
            # Use example input to infer schema structure
            print("\nUsing exampleRunInput to infer schema structure...")
            # Create a pseudo-schema from the example
            properties = {}
            for key, value in example_input.items():
                properties[key] = {
                    'type': type(value).__name__,
                    'example': value,
                    'description': f'Example value: {value}'
                }
            input_schema = {
                'type': 'object',
                'properties': properties
            }
            required_fields = []
            
        # Parse schema - schema might be directly the object or nested
        if not input_schema:
            print("ERROR: No input schema or example input found")
            print(f"\nActor keys: {list(actor.keys())}")
            if example_input:
                print(f"\nExample input fields: {list(example_input.keys())}")
            return None
            
        if isinstance(input_schema, dict):
            schema_type = input_schema.get('type', 'object')
            # Sometimes schema is a JSON schema, sometimes it's directly properties
            if 'properties' in input_schema:
                properties = input_schema.get('properties', {})
            elif '$schema' in input_schema or 'type' in input_schema:
                properties = input_schema.get('properties', {})
            else:
                # Maybe the schema itself is the properties
                properties = input_schema
                schema_type = 'object'
            required_fields = input_schema.get('required', [])
        else:
            print(f"Unexpected schema format: {type(input_schema)}")
            properties = {}
            required_fields = []
            schema_type = 'unknown'
        
        print(f"Schema Type: {schema_type}")
        print(f"Total Properties: {len(properties)}")
        print(f"Required Fields: {required_fields}")
        print()
        
        # Display all fields
        print("Supported Input Fields:")
        print("-" * 80)
        
        field_info = []
        for field_name, field_schema in properties.items():
            field_type = field_schema.get('type', 'unknown')
            description = field_schema.get('description', 'No description')
            default = field_schema.get('default', None)
            enum = field_schema.get('enum', None)
            is_required = field_name in required_fields
            
            field_info.append({
                'name': field_name,
                'type': field_type,
                'description': description,
                'default': default,
                'enum': enum,
                'required': is_required,
                'schema': field_schema
            })
            
            # Print formatted field info
            required_marker = " [REQUIRED]" if is_required else ""
            print(f"\n  Field: {field_name}{required_marker}")
            print(f"    Type: {field_type}")
            print(f"    Description: {description[:150] if description else 'N/A'}")
            if default is not None:
                print(f"    Default: {default}")
            if enum:
                print(f"    Allowed Values: {enum}")
        
        # Check specifically for date-related fields
        print("\n" + "-" * 80)
        print("Date-Related Fields:")
        date_fields = [f for f in field_info if any(keyword in f['name'].lower() 
                      for keyword in ['date', 'since', 'until', 'time', 'from', 'to'])]
        if date_fields:
            for field in date_fields:
                print(f"\n  • {field['name']} ({field['type']})")
                print(f"    {field['description']}")
                print(f"    Schema: {json.dumps(field['schema'], indent=6)}")
        else:
            print("  No date-related fields found")
        
        # Check for filter-related fields
        print("\n" + "-" * 80)
        print("Filter-Related Fields:")
        filter_fields = [f for f in field_info if any(keyword in f['name'].lower() 
                        for keyword in ['filter', 'include', 'min_', 'max_'])]
        if filter_fields:
            for field in filter_fields:
                print(f"\n  • {field['name']} ({field['type']})")
                print(f"    {field['description']}")
        else:
            print("  No filter-related fields found")
        
        # Check for searchTerms
        print("\n" + "-" * 80)
        print("Search-Related Fields:")
        search_fields = [f for f in field_info if any(keyword in f['name'].lower() 
                        for keyword in ['search', 'query', 'term', 'lang', 'language'])]
        if search_fields:
            for field in search_fields:
                print(f"\n  • {field['name']} ({field['type']})")
                print(f"    {field['description']}")
        else:
            print("  No search-related fields found")
        
        return {
            'actor_id': actor_id,
            'actor_name': actor_name,
            'schema': input_schema,
            'fields': field_info,
            'date_fields': date_fields,
            'filter_fields': filter_fields,
            'search_fields': search_fields
        }
        
    except Exception as e:
        print(f"ERROR: Error inspecting actor: {e}")
        import traceback
        traceback.print_exc()
        return None

def main():
    # Get API token
    api_token = os.getenv("APIFY_API_TOKEN")
    if not api_token:
        print("ERROR: APIFY_API_TOKEN not found in environment variables")
        print(f"   Checked paths: {env_path}")
        return
    
    # Initialize client
    client = ApifyClient(api_token)
    
    print("=" * 80)
    print("TWITTER ACTOR SCHEMA INSPECTION (DRY RUN)")
    print("=" * 80)
    
    results = []
    for actor_config in ACTOR_CONFIGS:
        result = inspect_actor_schema(
            client, 
            actor_config['id'], 
            actor_config['name']
        )
        if result:
            results.append(result)
    
    # Summary
    print("\n" + "=" * 80)
    print("SUMMARY")
    print("=" * 80)
    for result in results:
        print(f"\n{result['actor_name']} ({result['actor_id']}):")
        print(f"  Total fields: {len(result['fields'])}")
        print(f"  Date fields: {len(result['date_fields'])}")
        print(f"  Filter fields: {len(result['filter_fields'])}")
        print(f"  Search fields: {len(result['search_fields'])}")
        
        if result['date_fields']:
            print(f"  Date field names: {[f['name'] for f in result['date_fields']]}")
    
    # Save detailed results to JSON
    output_file = Path(__file__).parent.parent / "data" / "processed" / "twitter_actor_schemas.json"
    output_file.parent.mkdir(parents=True, exist_ok=True)
    
    with open(output_file, 'w') as f:
        json.dump(results, f, indent=2, default=str)
    
    print(f"\nSUCCESS: Detailed results saved to: {output_file}")

if __name__ == "__main__":
    main()

