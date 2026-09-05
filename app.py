"""A small command-line Python application."""

import argparse


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="A friendly Python application.")
    parser.add_argument(
        "--name",
        default="world",
        help="Name to greet (default: world)",
    )
    return parser


def main() -> None:
    args = build_parser().parse_args()
    print(f"Hello, {args.name}!")


if __name__ == "__main__":
    main()