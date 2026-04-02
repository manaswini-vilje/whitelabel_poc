"""
Document to JSON Converter Package
Converts documents to JSON format using GPT-4 and generates allocation data.
"""

from .pdf_converter import DocumentToJSONConverter
from .allocation_generator import AllocationGenerator

__version__ = "1.0.0"
__all__ = ["DocumentToJSONConverter", "AllocationGenerator"]

# Backward compatibility
PDFToJSONConverter = DocumentToJSONConverter
