import os
import sys
from pathlib import Path
import socket

sys.path.insert(0, os.path.abspath('..'))
import googlemaps_extras

ROOT = Path('.')
DATA_DIR = Path('tests/data')