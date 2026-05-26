"""
Trading Chart Analyzer Package

A comprehensive toolkit for analyzing trading charts and generating signals.
"""

from .analyzer import Analyzer
from .indicators import TechnicalIndicators
from .data_handler import DataHandler

__version__ = "0.1.0"
__author__ = "Trading Team"

__all__ = [
    "Analyzer",
    "TechnicalIndicators",
    "DataHandler",
]
