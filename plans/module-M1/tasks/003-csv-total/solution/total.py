import csv
from pathlib import Path


def main() -> None:
    with Path("sales.csv").open(newline="") as handle:
        rows = list(csv.DictReader(handle))
    total = sum(float(row["amount"]) for row in rows)
    Path("total.txt").write_text(f"{total:.2f}\n")


if __name__ == "__main__":
    main()
