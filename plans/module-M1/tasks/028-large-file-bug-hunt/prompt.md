`ledger.py` is a large transaction-ledger module. `compute_balances(transactions)` should return a dict mapping each account to its balance as a string with exactly two decimal places.

Transactions are dicts with `id`, `date` (ISO date), `account`, `type` (`charge` or `refund`), and `amount` (a decimal string). Process transactions in date order, breaking ties by `id`. Charges add to the balance. A refund subtracts from the balance but never takes it below zero; any excess refund is ignored. Use exact decimal arithmetic.

The test suite in `test_ledger.py` currently fails. Fix `ledger.py` so all tests pass. Do not modify `test_ledger.py`.
