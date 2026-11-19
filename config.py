from pathlib import Path

class Config:
    # Corrected Bank Details
    BANK_ACCOUNT = "3004895036"
    BANK_BRANCH = "Totalai Branch Buner"
    BRANCH_CODE = "5187"
    
    # Directory settings
    BASE_DIR = Path(__file__).parent
    OUTPUT_DIR = BASE_DIR / "Generated_Challans"

CONFIG = Config()