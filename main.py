"""
Main entry point for the Trading Chart Analyzer application.
"""

import pandas as pd
from chart_analyzer import Analyzer, DataHandler


def main():
    """Main application entry point."""
    print("Trading Chart Analyzer")
    print("=" * 50)

    # Create sample data
    dates = pd.date_range('2024-01-01', periods=100)
    sample_data = pd.DataFrame({
        'open': [100 + i * 0.5 for i in range(100)],
        'high': [102 + i * 0.5 for i in range(100)],
        'low': [99 + i * 0.5 for i in range(100)],
        'close': [101 + i * 0.5 for i in range(100)],
        'volume': [1000000 + i * 1000 for i in range(100)],
    }, index=dates)

    # Initialize components
    analyzer = Analyzer()
    data_handler = DataHandler()

    # Clean and process data
    print("Processing data...")
    cleaned_data = data_handler.clean_data(sample_data)

    # Analyze data
    print("Analyzing chart...")
    results = analyzer.analyze(cleaned_data)

    # Display results
    print("\nAnalysis Complete!")
    print(f"Data points analyzed: {len(results['data'])}")
    print(f"Signals generated: {results['signals']}")

    print("\nIndicators calculated:")
    for indicator_name in results['indicators'].keys():
        print(f"  - {indicator_name}")


if __name__ == "__main__":
    main()

