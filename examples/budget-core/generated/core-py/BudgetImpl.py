import sys
from typing import Callable, Any, TypeVar, NamedTuple
from math import floor
from itertools import count

import module_ as module_
import _dafny as _dafny
import System_ as System_

# Module: BudgetImpl

class default__:
    def  __init__(self):
        pass

    @staticmethod
    def ApplyDeposit(balance, amount):
        o: Outcome = Outcome.default()()
        if (amount) <= (0):
            o = Outcome_Rejected(balance, Reason_NonPositiveAmount())
        elif True:
            o = Outcome_Applied((balance) + (amount))
        return o

    @staticmethod
    def ApplyWithdraw(balance, amount):
        o: Outcome = Outcome.default()()
        if (amount) <= (0):
            o = Outcome_Rejected(balance, Reason_NonPositiveAmount())
        elif (amount) > (balance):
            o = Outcome_Rejected(balance, Reason_Overdraft())
        elif True:
            o = Outcome_Applied((balance) - (amount))
        return o

    @staticmethod
    def ApplyAll(start, txs):
        final: int = int(0)
        rejected: int = int(0)
        final = start
        rejected = 0
        d_0_i_: int
        d_0_i_ = 0
        while (d_0_i_) < (len(txs)):
            d_1_o_: Outcome = Outcome.default()()
            source0_ = (txs)[d_0_i_]
            with _dafny.label("match0"):
                if True:
                    if source0_.is_Deposit:
                        d_2_a_ = source0_.amount
                        out0_: Outcome
                        out0_ = default__.ApplyDeposit(final, d_2_a_)
                        d_1_o_ = out0_
                        raise _dafny.Break("match0")
                if True:
                    d_3_a_ = source0_.amount
                    out1_: Outcome
                    out1_ = default__.ApplyWithdraw(final, d_3_a_)
                    d_1_o_ = out1_
                pass
            if (d_1_o_).is_Rejected:
                rejected = (rejected) + (1)
            final = (d_1_o_).balance
            d_0_i_ = (d_0_i_) + (1)
        return final, rejected

    @staticmethod
    def Step(balance, tx):
        source0_ = tx
        if True:
            if source0_.is_Deposit:
                d_0_a_ = source0_.amount
                if (d_0_a_) > (0):
                    return (balance) + (d_0_a_)
                elif True:
                    return balance
        if True:
            d_1_a_ = source0_.amount
            if ((0) < (d_1_a_)) and ((d_1_a_) <= (balance)):
                return (balance) - (d_1_a_)
            elif True:
                return balance

    @staticmethod
    def IsRejected(balance, tx):
        source0_ = tx
        if True:
            if source0_.is_Deposit:
                d_0_a_ = source0_.amount
                return (d_0_a_) <= (0)
        if True:
            d_1_a_ = source0_.amount
            return ((d_1_a_) <= (0)) or ((d_1_a_) > (balance))

    @staticmethod
    def Replay(balance, txs):
        while True:
            with _dafny.label():
                if (len(txs)) == (0):
                    return balance
                elif True:
                    in0_ = default__.Step(balance, (txs)[0])
                    in1_ = _dafny.SeqWithoutIsStrInference((txs)[1::])
                    balance = in0_
                    txs = in1_
                    raise _dafny.TailCall()
                break

    @staticmethod
    def CountRejected(balance, txs):
        d_0___accumulator_ = 0
        while True:
            with _dafny.label():
                if (len(txs)) == (0):
                    return (0) + (d_0___accumulator_)
                elif True:
                    d_0___accumulator_ = (d_0___accumulator_) + ((1 if default__.IsRejected(balance, (txs)[0]) else 0))
                    in0_ = default__.Step(balance, (txs)[0])
                    in1_ = _dafny.SeqWithoutIsStrInference((txs)[1::])
                    balance = in0_
                    txs = in1_
                    raise _dafny.TailCall()
                break


class Reason:
    @_dafny.classproperty
    def AllSingletonConstructors(cls):
        return [Reason_Overdraft(), Reason_NonPositiveAmount()]
    @classmethod
    def default(cls, ):
        return lambda: Reason_Overdraft()
    def __ne__(self, __o: object) -> bool:
        return not self.__eq__(__o)
    @property
    def is_Overdraft(self) -> bool:
        return isinstance(self, Reason_Overdraft)
    @property
    def is_NonPositiveAmount(self) -> bool:
        return isinstance(self, Reason_NonPositiveAmount)

class Reason_Overdraft(Reason, NamedTuple('Overdraft', [])):
    def __dafnystr__(self) -> str:
        return f'BudgetImpl.Reason.Overdraft'
    def __eq__(self, __o: object) -> bool:
        return isinstance(__o, Reason_Overdraft)
    def __hash__(self) -> int:
        return super().__hash__()

class Reason_NonPositiveAmount(Reason, NamedTuple('NonPositiveAmount', [])):
    def __dafnystr__(self) -> str:
        return f'BudgetImpl.Reason.NonPositiveAmount'
    def __eq__(self, __o: object) -> bool:
        return isinstance(__o, Reason_NonPositiveAmount)
    def __hash__(self) -> int:
        return super().__hash__()


class Outcome:
    @classmethod
    def default(cls, ):
        return lambda: Outcome_Applied(int(0))
    def __ne__(self, __o: object) -> bool:
        return not self.__eq__(__o)
    @property
    def is_Applied(self) -> bool:
        return isinstance(self, Outcome_Applied)
    @property
    def is_Rejected(self) -> bool:
        return isinstance(self, Outcome_Rejected)

class Outcome_Applied(Outcome, NamedTuple('Applied', [('balance', Any)])):
    def __dafnystr__(self) -> str:
        return f'BudgetImpl.Outcome.Applied({_dafny.string_of(self.balance)})'
    def __eq__(self, __o: object) -> bool:
        return isinstance(__o, Outcome_Applied) and self.balance == __o.balance
    def __hash__(self) -> int:
        return super().__hash__()

class Outcome_Rejected(Outcome, NamedTuple('Rejected', [('balance', Any), ('reason', Any)])):
    def __dafnystr__(self) -> str:
        return f'BudgetImpl.Outcome.Rejected({_dafny.string_of(self.balance)}, {_dafny.string_of(self.reason)})'
    def __eq__(self, __o: object) -> bool:
        return isinstance(__o, Outcome_Rejected) and self.balance == __o.balance and self.reason == __o.reason
    def __hash__(self) -> int:
        return super().__hash__()


class Tx:
    @classmethod
    def default(cls, ):
        return lambda: Tx_Deposit(int(0))
    def __ne__(self, __o: object) -> bool:
        return not self.__eq__(__o)
    @property
    def is_Deposit(self) -> bool:
        return isinstance(self, Tx_Deposit)
    @property
    def is_Withdraw(self) -> bool:
        return isinstance(self, Tx_Withdraw)

class Tx_Deposit(Tx, NamedTuple('Deposit', [('amount', Any)])):
    def __dafnystr__(self) -> str:
        return f'BudgetImpl.Tx.Deposit({_dafny.string_of(self.amount)})'
    def __eq__(self, __o: object) -> bool:
        return isinstance(__o, Tx_Deposit) and self.amount == __o.amount
    def __hash__(self) -> int:
        return super().__hash__()

class Tx_Withdraw(Tx, NamedTuple('Withdraw', [('amount', Any)])):
    def __dafnystr__(self) -> str:
        return f'BudgetImpl.Tx.Withdraw({_dafny.string_of(self.amount)})'
    def __eq__(self, __o: object) -> bool:
        return isinstance(__o, Tx_Withdraw) and self.amount == __o.amount
    def __hash__(self) -> int:
        return super().__hash__()

