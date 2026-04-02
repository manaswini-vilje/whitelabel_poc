#!/usr/bin/env python3
"""
Main entry point for document processing workflow.
Automatically converts documents to PL data and generates final allocation.
"""

import sys
from pathlib import Path

# Add src to path for package imports
project_root = Path(__file__).parent
src_path = project_root / "src"
if str(src_path) not in sys.path:
    sys.path.insert(0, str(src_path))

# Import after path is set
from pdf_to_json_converter import DocumentToJSONConverter, AllocationGenerator
from white_label import load_brand_config


def main():
    """Main workflow: Document -> PL Data -> Final Allocation."""
    if len(sys.argv) < 2:
        print("Usage: python main.py <document_file_path>")
        print("\nExample:")
        print("  python main.py document.pdf")
        print("  python main.py document.png")
        sys.exit(1)
    
    document_file = sys.argv[1]
    
    # Validate document file
    doc_path = Path(document_file)
    if not doc_path.exists():
        print(f"❌ Error: Document file not found: {document_file}")
        sys.exit(1)
    
    print("=" * 60)
    print("Document Processing Workflow")
    print("=" * 60)

    app_root = Path(__file__).parent
    brand_config = load_brand_config(project_root=app_root)
    print(f"Active brand: {brand_config.brand_id} ({brand_config.app_name})")
    
    # Setup paths
    runtime_root = brand_config.runtime_root(app_root)
    data_dir = brand_config.data_dir(app_root)
    outputs_dir = brand_config.outputs_dir(app_root)
    data_dir.mkdir(parents=True, exist_ok=True)
    outputs_dir.mkdir(parents=True, exist_ok=True)
    
    pl_data_path = data_dir / "pl_data.json"
    final_allocation_path = outputs_dir / f"{doc_path.stem}_output.json"
    custom_prompt = brand_config.prompt_overrides.get("document_extraction_prompt")
    print(f"Runtime root: {runtime_root}")
    
    try:
        # Step 1: Convert Document to PL Data
        print(f"\n[Step 1/2] Converting document to PL data...")
        print(f"  Input: {doc_path}")
        print(f"  Output: {pl_data_path}")
        
        converter = DocumentToJSONConverter()
        converter.convert_to_json(
            str(doc_path),
            str(pl_data_path),
            custom_prompt=custom_prompt
        )
        
        print(f"✓ PL data generated successfully!")
        
        # Step 2: Generate Final Allocation from PL Data
        print(f"\n[Step 2/2] Generating final allocation from PL data...")
        print(f"  PL Data: {pl_data_path}")
        print(f"  Output: {final_allocation_path}")
        
        final_allocation = AllocationGenerator.generate_po_allocation_from_pl(
            str(pl_data_path),
            str(final_allocation_path),
            priority=brand_config.allocation.priority,
            warehouse_id=brand_config.allocation.warehouse_id,
            supplier_country=brand_config.allocation.supplier_country
        )
        print(f"✓ Final allocation generated successfully!")
        
        print("\n" + "=" * 60)
        print("✓ Workflow completed successfully!")
        print("=" * 60)
        print(f"\nGenerated files:")
        print(f"  - {pl_data_path}")
        print(f"  - {final_allocation_path}")
        
    except KeyboardInterrupt:
        print("\n⚠️  Process interrupted by user")
        sys.exit(1)
    except Exception as e:
        print(f"\n❌ Error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
