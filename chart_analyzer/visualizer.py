"""
Chart visualization module.
"""

import matplotlib.pyplot as plt
import pandas as pd


class Visualizer:
    """Class for visualizing trading data and analysis results."""

    def __init__(self, figsize: tuple = (14, 8)):
        """
        Initialize the visualizer.

        Args:
            figsize: Figure size as (width, height)
        """
        self.figsize = figsize

    def plot_candlestick(self, data: pd.DataFrame, title: str = "Candlestick Chart") -> None:
        """
        Plot candlestick chart.

        Args:
            data: DataFrame with OHLC data
            title: Chart title
        """
        fig, ax = plt.subplots(figsize=self.figsize)

        for idx, row in data.iterrows():
            color = 'green' if row['close'] >= row['open'] else 'red'
            
            # High-Low line
            ax.plot([idx, idx], [row['low'], row['high']], color=color, linewidth=1)
            
            # Open-Close rectangle
            height = abs(row['close'] - row['open'])
            bottom = min(row['open'], row['close'])
            ax.add_patch(plt.Rectangle((idx - 0.3, bottom), 0.6, height,
                                      facecolor=color, edgecolor=color))

        ax.set_title(title, fontsize=14, fontweight='bold')
        ax.set_xlabel("Date")
        ax.set_ylabel("Price")
        ax.grid(True, alpha=0.3)
        plt.tight_layout()
        plt.show()

    def plot_indicators(self, data: pd.DataFrame, indicators: dict, title: str = "Indicators") -> None:
        """
        Plot price with indicators.

        Args:
            data: DataFrame with price data
            indicators: Dictionary of indicators to plot
            title: Chart title
        """
        fig, ax = plt.subplots(figsize=self.figsize)

        ax.plot(data.index, data['close'], label='Close', linewidth=2)

        for name, indicator in indicators.items():
            ax.plot(data.index, indicator, label=name, alpha=0.7)

        ax.set_title(title, fontsize=14, fontweight='bold')
        ax.set_xlabel("Date")
        ax.set_ylabel("Price")
        ax.legend()
        ax.grid(True, alpha=0.3)
        plt.tight_layout()
        plt.show()

    def plot_rsi(self, rsi: pd.Series, title: str = "RSI (14)") -> None:
        """
        Plot RSI indicator.

        Args:
            rsi: RSI series
            title: Chart title
        """
        fig, ax = plt.subplots(figsize=self.figsize)

        ax.plot(rsi.index, rsi, label='RSI', linewidth=2, color='purple')
        ax.axhline(y=70, color='r', linestyle='--', alpha=0.5, label='Overbought (70)')
        ax.axhline(y=30, color='g', linestyle='--', alpha=0.5, label='Oversold (30)')

        ax.set_title(title, fontsize=14, fontweight='bold')
        ax.set_xlabel("Date")
        ax.set_ylabel("RSI")
        ax.set_ylim([0, 100])
        ax.legend()
        ax.grid(True, alpha=0.3)
        plt.tight_layout()
        plt.show()
