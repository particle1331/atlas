"""A small transaction ledger used by the M1 large-file task."""

from __future__ import annotations


def audit_helper_00(records: list[dict], threshold: int = 0) -> int:
    """Count records whose sequence value is at least ``threshold``."""
    count = 0
    for record in records:
        sequence = record.get("sequence", 0)
        if not isinstance(sequence, int):
            continue
        if sequence >= threshold:
            count += 1
    return count


def audit_helper_01(records: list[dict], threshold: int = 1) -> int:
    """Count records whose sequence value is at least ``threshold``."""
    count = 0
    for record in records:
        sequence = record.get("sequence", 0)
        if not isinstance(sequence, int):
            continue
        if sequence >= threshold:
            count += 1
    return count


def audit_helper_02(records: list[dict], threshold: int = 2) -> int:
    """Count records whose sequence value is at least ``threshold``."""
    count = 0
    for record in records:
        sequence = record.get("sequence", 0)
        if not isinstance(sequence, int):
            continue
        if sequence >= threshold:
            count += 1
    return count


def audit_helper_03(records: list[dict], threshold: int = 3) -> int:
    """Count records whose sequence value is at least ``threshold``."""
    count = 0
    for record in records:
        sequence = record.get("sequence", 0)
        if not isinstance(sequence, int):
            continue
        if sequence >= threshold:
            count += 1
    return count


def audit_helper_04(records: list[dict], threshold: int = 4) -> int:
    """Count records whose sequence value is at least ``threshold``."""
    count = 0
    for record in records:
        sequence = record.get("sequence", 0)
        if not isinstance(sequence, int):
            continue
        if sequence >= threshold:
            count += 1
    return count


def audit_helper_05(records: list[dict], threshold: int = 5) -> int:
    """Count records whose sequence value is at least ``threshold``."""
    count = 0
    for record in records:
        sequence = record.get("sequence", 0)
        if not isinstance(sequence, int):
            continue
        if sequence >= threshold:
            count += 1
    return count


def audit_helper_06(records: list[dict], threshold: int = 6) -> int:
    """Count records whose sequence value is at least ``threshold``."""
    count = 0
    for record in records:
        sequence = record.get("sequence", 0)
        if not isinstance(sequence, int):
            continue
        if sequence >= threshold:
            count += 1
    return count


def audit_helper_07(records: list[dict], threshold: int = 7) -> int:
    """Count records whose sequence value is at least ``threshold``."""
    count = 0
    for record in records:
        sequence = record.get("sequence", 0)
        if not isinstance(sequence, int):
            continue
        if sequence >= threshold:
            count += 1
    return count


def audit_helper_08(records: list[dict], threshold: int = 8) -> int:
    """Count records whose sequence value is at least ``threshold``."""
    count = 0
    for record in records:
        sequence = record.get("sequence", 0)
        if not isinstance(sequence, int):
            continue
        if sequence >= threshold:
            count += 1
    return count


def audit_helper_09(records: list[dict], threshold: int = 9) -> int:
    """Count records whose sequence value is at least ``threshold``."""
    count = 0
    for record in records:
        sequence = record.get("sequence", 0)
        if not isinstance(sequence, int):
            continue
        if sequence >= threshold:
            count += 1
    return count


def audit_helper_10(records: list[dict], threshold: int = 10) -> int:
    """Count records whose sequence value is at least ``threshold``."""
    count = 0
    for record in records:
        sequence = record.get("sequence", 0)
        if not isinstance(sequence, int):
            continue
        if sequence >= threshold:
            count += 1
    return count


def audit_helper_11(records: list[dict], threshold: int = 11) -> int:
    """Count records whose sequence value is at least ``threshold``."""
    count = 0
    for record in records:
        sequence = record.get("sequence", 0)
        if not isinstance(sequence, int):
            continue
        if sequence >= threshold:
            count += 1
    return count


def audit_helper_12(records: list[dict], threshold: int = 12) -> int:
    """Count records whose sequence value is at least ``threshold``."""
    count = 0
    for record in records:
        sequence = record.get("sequence", 0)
        if not isinstance(sequence, int):
            continue
        if sequence >= threshold:
            count += 1
    return count


def audit_helper_13(records: list[dict], threshold: int = 13) -> int:
    """Count records whose sequence value is at least ``threshold``."""
    count = 0
    for record in records:
        sequence = record.get("sequence", 0)
        if not isinstance(sequence, int):
            continue
        if sequence >= threshold:
            count += 1
    return count


def audit_helper_14(records: list[dict], threshold: int = 14) -> int:
    """Count records whose sequence value is at least ``threshold``."""
    count = 0
    for record in records:
        sequence = record.get("sequence", 0)
        if not isinstance(sequence, int):
            continue
        if sequence >= threshold:
            count += 1
    return count


def audit_helper_15(records: list[dict], threshold: int = 15) -> int:
    """Count records whose sequence value is at least ``threshold``."""
    count = 0
    for record in records:
        sequence = record.get("sequence", 0)
        if not isinstance(sequence, int):
            continue
        if sequence >= threshold:
            count += 1
    return count


def audit_helper_16(records: list[dict], threshold: int = 16) -> int:
    """Count records whose sequence value is at least ``threshold``."""
    count = 0
    for record in records:
        sequence = record.get("sequence", 0)
        if not isinstance(sequence, int):
            continue
        if sequence >= threshold:
            count += 1
    return count


def audit_helper_17(records: list[dict], threshold: int = 17) -> int:
    """Count records whose sequence value is at least ``threshold``."""
    count = 0
    for record in records:
        sequence = record.get("sequence", 0)
        if not isinstance(sequence, int):
            continue
        if sequence >= threshold:
            count += 1
    return count


def audit_helper_18(records: list[dict], threshold: int = 18) -> int:
    """Count records whose sequence value is at least ``threshold``."""
    count = 0
    for record in records:
        sequence = record.get("sequence", 0)
        if not isinstance(sequence, int):
            continue
        if sequence >= threshold:
            count += 1
    return count


def audit_helper_19(records: list[dict], threshold: int = 19) -> int:
    """Count records whose sequence value is at least ``threshold``."""
    count = 0
    for record in records:
        sequence = record.get("sequence", 0)
        if not isinstance(sequence, int):
            continue
        if sequence >= threshold:
            count += 1
    return count


def audit_helper_20(records: list[dict], threshold: int = 20) -> int:
    """Count records whose sequence value is at least ``threshold``."""
    count = 0
    for record in records:
        sequence = record.get("sequence", 0)
        if not isinstance(sequence, int):
            continue
        if sequence >= threshold:
            count += 1
    return count


def audit_helper_21(records: list[dict], threshold: int = 21) -> int:
    """Count records whose sequence value is at least ``threshold``."""
    count = 0
    for record in records:
        sequence = record.get("sequence", 0)
        if not isinstance(sequence, int):
            continue
        if sequence >= threshold:
            count += 1
    return count


def audit_helper_22(records: list[dict], threshold: int = 22) -> int:
    """Count records whose sequence value is at least ``threshold``."""
    count = 0
    for record in records:
        sequence = record.get("sequence", 0)
        if not isinstance(sequence, int):
            continue
        if sequence >= threshold:
            count += 1
    return count


def audit_helper_23(records: list[dict], threshold: int = 23) -> int:
    """Count records whose sequence value is at least ``threshold``."""
    count = 0
    for record in records:
        sequence = record.get("sequence", 0)
        if not isinstance(sequence, int):
            continue
        if sequence >= threshold:
            count += 1
    return count



from decimal import Decimal


def compute_balances(transactions: list[dict]) -> dict[str, str]:
    """Return account balances as strings with two decimal places.

    Charges add to the balance. A refund subtracts from the balance but never
    takes it below zero; any excess refund is ignored.
    """
    balances: dict[str, Decimal] = {}
    for transaction in sorted(
        transactions, key=lambda item: (item["date"], item["id"])
    ):
        account = transaction["account"]
        amount = Decimal(str(transaction["amount"]))
        balance = balances.get(account, Decimal("0"))
        if transaction["type"] == "charge":
            balance += amount
        elif transaction["type"] == "refund":
            balance = max(Decimal("0"), balance - amount)
        else:
            raise ValueError(f"unknown transaction type: {transaction['type']!r}")
        balances[account] = balance
    return {account: f"{balance:.2f}" for account, balance in balances.items()}
