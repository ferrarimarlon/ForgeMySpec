include "impl.dfy"

module BudgetTests {
  import opened BudgetImpl

  // @obligation deposit_exact
  method {:test} DepositAddsExactly() {
    var o := ApplyDeposit(10, 5);
    expect o == Applied(15);
  }

  // @obligation non_positive_rejected
  method {:test} NonPositiveAmountsAreRejected() {
    var d := ApplyDeposit(10, 0);
    expect d == Rejected(10, NonPositiveAmount);
    var w := ApplyWithdraw(10, -3);
    expect w == Rejected(10, NonPositiveAmount);
  }

  // @obligation withdraw_exact
  method {:test} WithdrawSubtractsExactly() {
    var o := ApplyWithdraw(10, 10);
    expect o == Applied(0);
    var p := ApplyWithdraw(10, 1);
    expect p == Applied(9);
  }

  // @obligation overdraft_rejected, never_negative
  method {:test} OverdraftIsRejected() {
    var o := ApplyWithdraw(10, 11);
    expect o == Rejected(10, Overdraft);
    expect o.balance >= 0;
  }

  // @obligation replay
  method {:test} ReplayAppliesInOrder() {
    var final, rejected := ApplyAll(0, [Deposit(10), Withdraw(4), Withdraw(7), Deposit(-1), Deposit(2)]);
    expect final == 8;
    expect rejected == 2;
    var empty, none := ApplyAll(3, []);
    expect empty == 3 && none == 0;
  }
}
