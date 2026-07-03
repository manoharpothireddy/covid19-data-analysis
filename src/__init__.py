"""
src/__init__.py
===============
Package initialiser for the COVID-19 pipeline source modules.

Exposes the four main entry-point functions at the package level so
run.py can import them with a single line:

    from src.data_collection import download_owid_data
    from src.data_cleaning    import run_cleaning_pipeline
    from src.analysis         import run_analysis_pipeline
    from src.database         import run_database_pipeline
"""

from src.data_collection import download_owid_data
from src.data_cleaning   import run_cleaning_pipeline
from src.analysis        import run_analysis_pipeline
from src.database        import run_database_pipeline

__all__ = [
    "download_owid_data",
    "run_cleaning_pipeline",
    "run_analysis_pipeline",
    "run_database_pipeline",
]
