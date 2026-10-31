// Contract for the budget ledger core. Approved by the user and locked in
// contract.lock: impl.dfy refines this module and cannot weaken it.
abstract module BudgetCore {
  datatype Reason = Overdraft | NonPositiveAmount
  datatype Outcome = Applied(balance: int) | Rejected(balance: int, reason: Reason)
  datatype Tx = Deposit(amount: int) | Withdraw(amount: int)

  function Step(balance: int, tx: Tx): int
  {
    match tx
    case Deposit(a) => if a > 0 then balance + a else balance
    case Withdraw(a) => if 0 < a <= balance then balance - a else balance
  }

  function IsRejected(balance: int, tx: Tx): bool
  {
    match tx
    case Deposit(a) => a <= 0
    case Withdraw(a) => a <= 0 || a > balance
  }

  function Replay(balance: int, txs: seq<Tx>): int
    decreases |txs|
  {
    if |txs| == 0 then balance else Replay(Step(balance, txs[0]), txs[1..])
  }

  function CountRejected(balance: int, txs: seq<Tx>): nat
    decreases |txs|
  {
    if |txs| == 0 then 0
    else (if IsRejected(balance, txs[0]) then 1 else 0) + CountRejected(Step(balance, txs[0]), txs[1..])
  }

  method ApplyDeposit(balance: int, amount: int) returns (o: Outcome)
    requires balance >= 0
    // @obligation deposit_exact
    ensures amount > 0 ==> o == Applied(balance + amount)
    // @obligation non_positive_rejected
    ensures amount <= 0 ==> o == Rejected(balance, NonPositiveAmount)

  method ApplyWithdraw(balance: int, amount: int) returns (o: Outcome)
    requires balance >= 0
    // @obligation withdraw_exact
    ensures 0 < amount <= balance ==> o == Applied(balance - amount)
    // @obligation overdraft_rejected
    ensures amount > balance && amount > 0 ==> o == Rejected(balance, Overdraft)
    // @obligation non_positive_rejected
    ensures amount <= 0 ==> o == Rejected(balance, NonPositiveAmount)
    // @obligation never_negative
    ensures o.balance >= 0

  method ApplyAll(start: int, txs: seq<Tx>) returns (final: int, rejected: nat)
    requires start >= 0
    // @obligation replay
    ensures final == Replay(start, txs)
    ensures rejected == CountRejected(start, txs)
    // @obligation never_negative
    ensures final >= 0
}
