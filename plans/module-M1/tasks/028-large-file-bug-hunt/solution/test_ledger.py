import unittest

from ledger import compute_balances


class TestLedger(unittest.TestCase):
    def test_charge_and_refund(self) -> None:
        transactions = [
            {"id": "a", "date": "2024-01-01", "account": "A", "type": "charge", "amount": "5.00"},
            {"id": "b", "date": "2024-01-02", "account": "A", "type": "refund", "amount": "2.00"},
        ]
        self.assertEqual(compute_balances(transactions), {"A": "3.00"})

    def test_refund_is_capped_at_balance(self) -> None:
        transactions = [
            {"id": "a", "date": "2024-01-01", "account": "A", "type": "charge", "amount": "5.00"},
            {"id": "b", "date": "2024-01-02", "account": "A", "type": "refund", "amount": "10.00"},
        ]
        self.assertEqual(compute_balances(transactions), {"A": "0.00"})

    def test_transactions_are_processed_by_date_not_id(self) -> None:
        transactions = [
            {"id": "z1", "date": "2024-01-01", "account": "A", "type": "charge", "amount": "5.00"},
            {"id": "a2", "date": "2024-01-02", "account": "A", "type": "refund", "amount": "10.00"},
            {"id": "m3", "date": "2024-01-03", "account": "A", "type": "charge", "amount": "10.00"},
        ]
        self.assertEqual(compute_balances(transactions), {"A": "10.00"})

    def test_multiple_accounts(self) -> None:
        transactions = [
            {"id": "a", "date": "2024-01-01", "account": "A", "type": "charge", "amount": "1.10"},
            {"id": "b", "date": "2024-01-01", "account": "B", "type": "charge", "amount": "2.20"},
            {"id": "c", "date": "2024-01-02", "account": "A", "type": "charge", "amount": "0.20"},
        ]
        self.assertEqual(compute_balances(transactions), {"A": "1.30", "B": "2.20"})


if __name__ == "__main__":
    unittest.main()
