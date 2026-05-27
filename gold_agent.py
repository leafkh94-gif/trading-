"""Simple launcher for the market analysis demo."""

from main import demonstrate_bot_with_sample_data, demonstrate_risk_management


def main() -> None:
    """Run the project demo entry points."""
    try:
        demonstrate_bot_with_sample_data()
        demonstrate_risk_management()
        print("\nAgent run completed successfully.")
    except KeyboardInterrupt:
        print("\nAgent run interrupted by user.")
    except Exception as exc:
        print(f"\nAgent run failed: {exc}")
        raise


if __name__ == "__main__":
    main()
