import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent

class Config:
    SECRET_KEY = os.getenv("SECRET_KEY", "dev-secret-key-sc6113-dapp")
    SQLALCHEMY_DATABASE_URI = os.getenv("DATABASE_URL", f"sqlite:///{BASE_DIR / 'scf_dapp.db'}")
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    
    # Upload folder for invoice PDFs
    UPLOAD_FOLDER = os.getenv("UPLOAD_FOLDER", str(BASE_DIR / "uploads"))
    MAX_CONTENT_LENGTH = 16 * 1024 * 1024  # 16 MB max limit
    ALLOWED_EXTENSIONS = {"pdf"}

    # Blockchain
    WEB3_PROVIDER_URI = os.getenv("WEB3_PROVIDER_URI", "https://rpc.sepolia.org")
    CHAIN_ID = int(os.getenv("CHAIN_ID", 11155111))

    # Contract Addresses (Defaults to zero addresses until deployed)
    ROLE_MANAGER_ADDRESS = os.getenv("ROLE_MANAGER_ADDRESS", "0x0000000000000000000000000000000000000000")
    INVOICE_REGISTRY_ADDRESS = os.getenv("INVOICE_REGISTRY_ADDRESS", "0x0000000000000000000000000000000000000000")
    RECEIVABLE_TOKEN_ADDRESS = os.getenv("RECEIVABLE_TOKEN_ADDRESS", "0x0000000000000000000000000000000000000000")
    FINANCING_POOL_ADDRESS = os.getenv("FINANCING_POOL_ADDRESS", "0x0000000000000000000000000000000000000000")
    MOCK_STABLECOIN_ADDRESS = os.getenv("MOCK_STABLECOIN_ADDRESS", "0x0000000000000000000000000000000000000000")
