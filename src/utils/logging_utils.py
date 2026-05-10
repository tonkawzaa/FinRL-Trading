import logging
import sys
from pathlib import Path
from typing import Union, Optional

def setup_logging(level: Union[int, str] = logging.INFO, log_file: Optional[Union[str, Path]] = None) -> None:
    """
    Configure application logging.
    
    Args:
        level: The logging level (e.g., logging.INFO, logging.DEBUG, or string 'INFO')
        log_file: Optional file path to write logs to.
    """
    if isinstance(level, str):
        level = getattr(logging, level.upper(), logging.INFO)
        
    handlers = [logging.StreamHandler(sys.stdout)]
    
    if log_file:
        log_path = Path(log_file)
        log_path.parent.mkdir(parents=True, exist_ok=True)
        handlers.append(logging.FileHandler(log_path))
        
    # Configure root logger
    logging.basicConfig(
        level=level,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        handlers=handlers
    )
