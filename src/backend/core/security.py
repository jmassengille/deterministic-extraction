"""Security utilities for secret management and input validation."""

import os
import re
from pathlib import Path
from typing import Optional


def get_secret(secret_name: str, default: Optional[str] = None) -> Optional[str]:
    """
    Get secret from Docker secrets or environment variable.
    
    Args:
        secret_name: Name of the secret
        default: Default value if secret not found
        
    Returns:
        Secret value or default
    """
    # Try Docker secret first
    secret_file = Path(f'/run/secrets/{secret_name}')
    if secret_file.exists():
        try:
            return secret_file.read_text().strip()
        except Exception:
            pass
    
    # Try environment variable with _FILE suffix
    env_file_var = f"{secret_name.upper()}_FILE"
    if env_file_var in os.environ:
        try:
            file_path = Path(os.environ[env_file_var])
            if file_path.exists():
                return file_path.read_text().strip()
        except Exception:
            pass
    
    # Fall back to direct environment variable
    env_var = secret_name.upper()
    if env_var in os.environ:
        return os.environ[env_var]
    
    # Return default or raise error for required secrets
    if default is None and secret_name in ['openai_api_key', 'secret_key']:
        raise ValueError(f"Required secret '{secret_name}' not found")
    
    return default


class PathValidator:
    """Validate and sanitize file paths to prevent security issues."""
    
    @staticmethod
    def validate_pdf_path(path_str: str, base_dir: Optional[Path] = None) -> Path:
        """
        Validate and sanitize PDF file path.
        
        Args:
            path_str: Input path string
            base_dir: Base directory for validation (defaults to /app/data)
            
        Returns:
            Validated Path object
            
        Raises:
            ValueError: If path is invalid or unsafe
            FileNotFoundError: If file doesn't exist
        """
        if not path_str:
            raise ValueError("Path cannot be empty")
        
        # Remove null bytes and other dangerous characters
        clean_path = path_str.replace('\x00', '')
        clean_path = re.sub(r'[<>:"|?*]', '', clean_path)
        
        # Convert to Path and resolve
        try:
            file_path = Path(clean_path).resolve()
        except Exception as e:
            raise ValueError(f"Invalid path: {e}")
        
        # Set default base directory
        if base_dir is None:
            base_dir = Path('/app/data').resolve()
        else:
            base_dir = base_dir.resolve()
        
        # Check for path traversal
        try:
            file_path.relative_to(base_dir)
        except ValueError:
            raise ValueError(f"Path traversal detected: {path_str}")
        
        # Verify file exists and is a regular file
        if not file_path.exists():
            raise FileNotFoundError(f"File not found: {path_str}")
        
        if not file_path.is_file():
            raise ValueError(f"Not a regular file: {path_str}")
        
        # Check file extension
        if file_path.suffix.lower() != '.pdf':
            raise ValueError(f"File must be PDF, got: {file_path.suffix}")
        
        # Check file size (max 100MB)
        max_size = 100 * 1024 * 1024  # 100MB
        if file_path.stat().st_size > max_size:
            raise ValueError(f"File too large (max 100MB)")
        
        return file_path
    
    @staticmethod
    def validate_output_path(path_str: str, base_dir: Optional[Path] = None) -> Path:
        """
        Validate output path for MSF files.
        
        Args:
            path_str: Output path string
            base_dir: Base directory for validation
            
        Returns:
            Validated Path object
        """
        if not path_str:
            raise ValueError("Path cannot be empty")
        
        # Clean dangerous characters
        clean_path = path_str.replace('\x00', '')
        clean_path = re.sub(r'[<>:"|?*]', '', clean_path)
        
        # Convert to Path and resolve
        try:
            file_path = Path(clean_path).resolve()
        except Exception as e:
            raise ValueError(f"Invalid path: {e}")
        
        # Set default base directory
        if base_dir is None:
            base_dir = Path('/app/data/output').resolve()
        else:
            base_dir = base_dir.resolve()
        
        # Check for path traversal
        try:
            file_path.relative_to(base_dir)
        except ValueError:
            raise ValueError(f"Path traversal detected: {path_str}")
        
        # Ensure parent directory exists
        file_path.parent.mkdir(parents=True, exist_ok=True)
        
        # Check extension
        if file_path.suffix.lower() not in ['.msf', '.xml']:
            raise ValueError(f"Output must be MSF or XML file")
        
        return file_path