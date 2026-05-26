"""
Data handling and processing module.
"""

import pandas as pd
import numpy as np


class DataHandler:
    """Class for handling and processing trading data."""

    @staticmethod
    def clean_data(data: pd.DataFrame) -> pd.DataFrame:
        """
        Clean and validate trading data.

        Args:
            data: Raw trading data DataFrame

        Returns:
            Cleaned DataFrame with OHLCV columns
        """
        df = data.copy()

        # Normalize column names to lowercase
        df.columns = df.columns.str.lower()

        # Handle missing values
        df = df.ffill().bfill()

        # Remove duplicates
        df = df[~df.index.duplicated(keep='first')]

        # Ensure required columns exist
        required_cols = ['open', 'high', 'low', 'close', 'volume']
        if not all(col in df.columns for col in required_cols):
            raise ValueError(f"Data must contain columns: {required_cols}")

        # Convert to numeric types
        for col in required_cols:
            df[col] = pd.to_numeric(df[col], errors='coerce')

        return df

    @staticmethod
    def resample_data(data: pd.DataFrame, timeframe: str) -> pd.DataFrame:
        """
        Resample data to a different timeframe.

        Args:
            data: Trading data DataFrame with datetime index
            timeframe: Target timeframe (e.g., '1H', '1D', '5T')

        Returns:
            Resampled DataFrame
        """
        if not isinstance(data.index, pd.DatetimeIndex):
            raise ValueError("DataFrame index must be DatetimeIndex")

        agg_dict = {
            'open': 'first',
            'high': 'max',
            'low': 'min',
            'close': 'last',
            'volume': 'sum',
        }

        return data.resample(timeframe).agg(agg_dict)

    @staticmethod
    def normalize_data(data: pd.DataFrame, columns: list = None) -> pd.DataFrame:
        """
        Normalize data to 0-1 range.

        Args:
            data: Trading data DataFrame
            columns: Columns to normalize (default: all numeric columns)

        Returns:
            Normalized DataFrame
        """
        df = data.copy()

        if columns is None:
            columns = df.select_dtypes(include=[np.number]).columns

        for col in columns:
            min_val = df[col].min()
            max_val = df[col].max()
            df[col] = (df[col] - min_val) / (max_val - min_val)

        return df

    @staticmethod
    def split_data(data: pd.DataFrame, train_ratio: float = 0.8) -> tuple:
        """
        Split data into training and testing sets.

        Args:
            data: Trading data DataFrame
            train_ratio: Ratio for training data (default: 0.8)

        Returns:
            Tuple of (train_data, test_data)
        """
        split_idx = int(len(data) * train_ratio)
        return data.iloc[:split_idx], data.iloc[split_idx:]
