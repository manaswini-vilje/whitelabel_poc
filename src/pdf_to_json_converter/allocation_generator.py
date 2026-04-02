"""
Allocation Generator Module
Generates PO allocation from PL data.
"""

import json
from pathlib import Path
from typing import Dict, Any
from datetime import datetime


class AllocationGenerator:
    """Generates PO allocation from PL data."""
    
    @staticmethod
    def load_json_file(file_path: str) -> Any:
        """Load JSON file."""
        with open(file_path, 'r', encoding='utf-8') as f:
            return json.load(f)
    
    @staticmethod
    def generate_po_allocation_from_pl(
        pl_file: str,
        output_file: str,
        priority: int = 3,
        warehouse_id: str = "NW",
        supplier_country: str = "SE"
    ) -> Dict[str, Any]:
        """
        Generate final allocation (PO format) from PL data only.
        Creates a single PO with all products and a generated temporary orderNr.
        
        Args:
            pl_file: Path to PL data JSON file
            output_file: Path to output final_allocation.json
            priority: Priority level for PO (default: 3)
            warehouse_id: Warehouse ID for all lines (default: "NW")
            supplier_country: Supplier country code (default: "SE")
            
        Returns:
            Single PO allocation dictionary
        """
        print(f"Loading PL data from: {pl_file}")
        pl_data = AllocationGenerator.load_json_file(pl_file)
        
        # Extract products and metadata from PL data
        if 'products' in pl_data:
            products = pl_data['products']
            metadata = pl_data.get('document_metadata', {})
        else:
            products = pl_data if isinstance(pl_data, list) else []
            metadata = {}
        
        print(f"Found {len(products)} products in PL data")
        
        # Extract supplier information
        seller = metadata.get('seller', {})
        date_of_issue = metadata.get('date_of_issue', '')
        
        # Get document number with fallbacks
        document_number = (
            metadata.get('packing_list_number') or 
            metadata.get('document_number') or 
            metadata.get('invoice_number') or 
            metadata.get('order_number') or
            f"TEMP-{datetime.now().strftime('%Y%m%d-%H%M%S')}"
        )
        
        # Build purchase order lines from all products
        purchase_order_lines = []
        line_counter = 10000
        
        for product in products:
            article = product.get('article', '')
            quantity = product.get('quantity', 0)
            
            if not article:
                continue
            
            purchase_order_lines.append({
                "line": line_counter,
                "itemId": article,
                "dateTime": date_of_issue,
                "quantity": quantity,
                "warehouseId": warehouse_id
            })
            
            line_counter += 10000
        
        # Build supplier info
        supplier = {
            "id": 0,  # Default ID, can be updated if supplier mapping exists
            "name": seller.get('name', ''),
            "address1": seller.get('address', ''),
            "city": "",  # Extract from address if needed
            "country": supplier_country,
            "mobileNo": seller.get('phone', ''),
            "email": "",  # Not in PL data
            "zipCode": ""  # Extract from address if needed
        }
        
        # Create single PO allocation
        po_allocation = {
            "orderType": "PO",
            "orderNr": document_number, 
            "supplier": supplier,
            "priority": priority,
            "purchaseOrderLines": purchase_order_lines
        }
        
        # Save to file
        output_path = Path(output_file)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        
        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(po_allocation, f, indent=4, ensure_ascii=False)
        
        print(f"\n✓ PO allocation saved to: {output_path}")
        print(f"  Total lines: {len(purchase_order_lines)}")
        total_quantity = sum(line['quantity'] for line in purchase_order_lines)
        print(f"  Total quantity: {total_quantity}")
        
        return po_allocation
