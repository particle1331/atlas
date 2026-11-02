from pathlib import Path


def main() -> None:
    rows = Path("sales.csv").read_text().strip().splitlines()[1:]
    total = 0.0
    # TODO: sum the amount column.
    Path("total.txt").write_text(f"{total:.2f}\n")


if __name__ == "__main__":
    main()
