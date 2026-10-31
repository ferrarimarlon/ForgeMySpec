// @target replay
// Planted error: Forgets to count rejected transactions during replay.
include "contract.dfy"

module BudgetImpl refines BudgetCore {
  method ApplyDeposit(balance: int, amount: int) returns (o: Outcome)
  {
    if amount <= 0 {
      o := Rejected(balance, NonPositiveAmount);
    } else {
      o := Applied(balance + amount);
    }
  }

  method ApplyWithdraw(balance: int, amount: int) returns (o: Outcome)
  {
    if amount <= 0 {
      o := Rejected(balance, NonPositiveAmount);
    } else if amount > balance {
      o := Rejected(balance, Overdraft);
    } else {
      o := Applied(balance - amount);
    }
  }

  method ApplyAll(start: int, txs: seq<Tx>) returns (final: int, rejected: nat)
  {
    final := start;
    rejected := 0;
    var i := 0;
    while i < |txs|
      invariant 0 <= i <= |txs|
      invariant final >= 0
      invariant Replay(final, txs[i..]) == Replay(start, txs)
      invariant rejected + CountRejected(final, txs[i..]) == CountRejected(start, txs)
    {
      assert txs[i..][1..] == txs[i + 1..];
      var o: Outcome;
      match txs[i] {
        case Deposit(a) => o := ApplyDeposit(final, a);
        case Withdraw(a) => o := ApplyWithdraw(final, a);
      }
      final := o.balance;
      i := i + 1;
    }
  }
}
