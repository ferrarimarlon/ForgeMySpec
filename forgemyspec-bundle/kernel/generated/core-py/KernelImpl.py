import sys
from typing import Callable, Any, TypeVar, NamedTuple
from math import floor
from itertools import count

import module_ as module_
import _dafny as _dafny
import System_ as System_

# Module: KernelImpl

class default__:
    def  __init__(self):
        pass

    @staticmethod
    def ClassifyObligation(kind, failures, survivors, testsOk, blocked):
        s: Status = Status.default()()
        r: ObligationReason = ObligationReason.default()()
        if (failures) > (0):
            rhs0_ = Status_Leaking()
            rhs1_ = ObligationReason_ByFailure()
            s = rhs0_
            r = rhs1_
        elif (kind) == (Kind_BoundaryObligation()):
            if testsOk:
                rhs2_ = Status_Fragile()
                rhs3_ = ObligationReason_ByBoundary()
                s = rhs2_
                r = rhs3_
            elif True:
                rhs4_ = Status_Leaking()
                rhs5_ = ObligationReason_ByFailure()
                s = rhs4_
                r = rhs5_
        elif (survivors) > (0):
            rhs6_ = Status_Fragile()
            rhs7_ = ObligationReason_ByMutant()
            s = rhs6_
            r = rhs7_
        elif (blocked) or (not(testsOk)):
            rhs8_ = Status_Fragile()
            rhs9_ = ObligationReason_ByBlock()
            s = rhs8_
            r = rhs9_
        elif True:
            rhs10_ = Status_Proven()
            rhs11_ = ObligationReason_ByProof()
            s = rhs10_
            r = rhs11_
        return s, r

    @staticmethod
    def RequirementStatus(phase, gate, coverage):
        s: Status = Status.default()()
        r: RequirementReason = RequirementReason.default()()
        if (phase) != (Phase_Locked()):
            rhs0_ = Status_Leaking()
            rhs1_ = RequirementReason_NotApproved()
            s = rhs0_
            r = rhs1_
            return s, r
        if (gate) == (GateState_NoGate()):
            rhs2_ = Status_Leaking()
            rhs3_ = RequirementReason_GateMissing()
            s = rhs2_
            r = rhs3_
            return s, r
        if (gate) == (GateState_Stale()):
            rhs4_ = Status_Leaking()
            rhs5_ = RequirementReason_GateStale()
            s = rhs4_
            r = rhs5_
            return s, r
        if (len(coverage)) == (0):
            rhs6_ = Status_Leaking()
            rhs7_ = RequirementReason_Uncovered()
            s = rhs6_
            r = rhs7_
            return s, r
        d_0_idx_: int
        d_0_idx_ = 0
        d_1_i_: int
        d_1_i_ = 1
        while (d_1_i_) < (len(coverage)):
            if (default__.Rank((coverage)[d_1_i_])) < (default__.Rank((coverage)[d_0_idx_])):
                d_0_idx_ = d_1_i_
            d_1_i_ = (d_1_i_) + (1)
        s = (coverage)[d_0_idx_]
        r = RequirementReason_ByObligation(d_0_idx_)
        return s, r

    @staticmethod
    def DecideEdit(c, formal, phase, changesFormal, coveringApproved):
        d: Decision = Decision.default()()
        source0_ = c
        with _dafny.label("match0"):
            if True:
                if source0_.is_OutsideProject:
                    d = Decision_Allow()
                    raise _dafny.Break("match0")
            if True:
                if source0_.is_Protected:
                    d = Decision_Deny(Reason_RProtected())
                    raise _dafny.Break("match0")
            if True:
                if source0_.is_Allowed:
                    d = Decision_Allow()
                    raise _dafny.Break("match0")
            if True:
                if source0_.is_BundleDoc:
                    d = Decision_Allow()
                    raise _dafny.Break("match0")
            if True:
                if source0_.is_NotCovered:
                    d = Decision_Deny(Reason_ROutsideSpec())
                    raise _dafny.Break("match0")
            if True:
                if source0_.is_ScopeCovered:
                    if coveringApproved:
                        d = Decision_Allow()
                    elif True:
                        d = Decision_Deny(Reason_RNotApproved())
                    raise _dafny.Break("match0")
            if True:
                if source0_.is_BundleSpec:
                    if ((phase) == (Phase_Draft())) or ((phase) == (Phase_SpecInvalid())):
                        d = Decision_Allow()
                    elif not(formal):
                        d = Decision_Deny(Reason_RSpecLocked())
                    elif changesFormal:
                        d = Decision_Deny(Reason_RFormalLocked())
                    elif True:
                        d = Decision_Allow()
                    raise _dafny.Break("match0")
            if True:
                if source0_.is_BundleContract:
                    source1_ = phase
                    with _dafny.label("match1"):
                        if True:
                            if source1_.is_Draft:
                                d = Decision_Allow()
                                raise _dafny.Break("match1")
                        if True:
                            if source1_.is_Locked:
                                d = Decision_Deny(Reason_RContractLocked())
                                raise _dafny.Break("match1")
                        if True:
                            if source1_.is_LockInvalid:
                                d = Decision_Deny(Reason_RContractLocked())
                                raise _dafny.Break("match1")
                        if True:
                            d = Decision_Deny(Reason_RSpecInvalid())
                        pass
                    raise _dafny.Break("match0")
            if True:
                source2_ = phase
                with _dafny.label("match2"):
                    if True:
                        if source2_.is_Locked:
                            d = Decision_Allow()
                            raise _dafny.Break("match2")
                    if True:
                        if source2_.is_Draft:
                            if formal:
                                d = Decision_Deny(Reason_RImplWithoutLock())
                            elif True:
                                d = Decision_Deny(Reason_RNotApproved())
                            raise _dafny.Break("match2")
                    if True:
                        if source2_.is_LockInvalid:
                            d = Decision_Deny(Reason_RLockInvalid())
                            raise _dafny.Break("match2")
                    if True:
                        d = Decision_Deny(Reason_RSpecInvalid())
                    pass
            pass
        return d

    @staticmethod
    def DecideApproval(terminal, typedCode, contentMatches, used):
        a: ApprovalDecision = ApprovalDecision.default()()
        if terminal:
            a = ApprovalDecision_Approved()
        elif not(typedCode):
            a = ApprovalDecision_Refused(ApprovalReason_RNoTypedCode())
        elif not(contentMatches):
            a = ApprovalDecision_Refused(ApprovalReason_RContentChanged())
        elif used:
            a = ApprovalDecision_Refused(ApprovalReason_RAlreadyUsed())
        elif True:
            a = ApprovalDecision_Approved()
        return a

    @staticmethod
    def Coverage(hypotheses, phrases, refsH, refsP):
        missingH: _dafny.Seq = _dafny.Seq({})
        missingP: _dafny.Seq = _dafny.Seq({})
        out0_: _dafny.Seq
        out0_ = default__.Missing(hypotheses, refsH)
        missingH = out0_
        out1_: _dafny.Seq
        out1_ = default__.Missing(phrases, refsP)
        missingP = out1_
        return missingH, missingP

    @staticmethod
    def Missing(xs, refs):
        r: _dafny.Seq = _dafny.Seq({})
        r = _dafny.SeqWithoutIsStrInference([])
        d_0_i_: int
        d_0_i_ = 0
        while (d_0_i_) < (len(xs)):
            d_1_covered_: bool
            out0_: bool
            out0_ = default__.Covered((xs)[d_0_i_], refs)
            d_1_covered_ = out0_
            if not(d_1_covered_):
                r = (r) + (_dafny.SeqWithoutIsStrInference([(xs)[d_0_i_]]))
            d_0_i_ = (d_0_i_) + (1)
        return r

    @staticmethod
    def Covered(x, refs):
        b: bool = False
        b = False
        d_0_k_: int
        d_0_k_ = 0
        while (d_0_k_) < (len(refs)):
            if (x) in ((refs)[d_0_k_]):
                b = True
            d_0_k_ = (d_0_k_) + (1)
        return b

    @staticmethod
    def Rank(s):
        source0_ = s
        if True:
            if source0_.is_Leaking:
                return 0
        if True:
            if source0_.is_Fragile:
                return 1
        if True:
            return 2


class Status:
    @_dafny.classproperty
    def AllSingletonConstructors(cls):
        return [Status_Leaking(), Status_Fragile(), Status_Proven()]
    @classmethod
    def default(cls, ):
        return lambda: Status_Leaking()
    def __ne__(self, __o: object) -> bool:
        return not self.__eq__(__o)
    @property
    def is_Leaking(self) -> bool:
        return isinstance(self, Status_Leaking)
    @property
    def is_Fragile(self) -> bool:
        return isinstance(self, Status_Fragile)
    @property
    def is_Proven(self) -> bool:
        return isinstance(self, Status_Proven)

class Status_Leaking(Status, NamedTuple('Leaking', [])):
    def __dafnystr__(self) -> str:
        return f'KernelImpl.Status.Leaking'
    def __eq__(self, __o: object) -> bool:
        return isinstance(__o, Status_Leaking)
    def __hash__(self) -> int:
        return super().__hash__()

class Status_Fragile(Status, NamedTuple('Fragile', [])):
    def __dafnystr__(self) -> str:
        return f'KernelImpl.Status.Fragile'
    def __eq__(self, __o: object) -> bool:
        return isinstance(__o, Status_Fragile)
    def __hash__(self) -> int:
        return super().__hash__()

class Status_Proven(Status, NamedTuple('Proven', [])):
    def __dafnystr__(self) -> str:
        return f'KernelImpl.Status.Proven'
    def __eq__(self, __o: object) -> bool:
        return isinstance(__o, Status_Proven)
    def __hash__(self) -> int:
        return super().__hash__()


class Kind:
    @_dafny.classproperty
    def AllSingletonConstructors(cls):
        return [Kind_DafnyObligation(), Kind_BoundaryObligation()]
    @classmethod
    def default(cls, ):
        return lambda: Kind_DafnyObligation()
    def __ne__(self, __o: object) -> bool:
        return not self.__eq__(__o)
    @property
    def is_DafnyObligation(self) -> bool:
        return isinstance(self, Kind_DafnyObligation)
    @property
    def is_BoundaryObligation(self) -> bool:
        return isinstance(self, Kind_BoundaryObligation)

class Kind_DafnyObligation(Kind, NamedTuple('DafnyObligation', [])):
    def __dafnystr__(self) -> str:
        return f'KernelImpl.Kind.DafnyObligation'
    def __eq__(self, __o: object) -> bool:
        return isinstance(__o, Kind_DafnyObligation)
    def __hash__(self) -> int:
        return super().__hash__()

class Kind_BoundaryObligation(Kind, NamedTuple('BoundaryObligation', [])):
    def __dafnystr__(self) -> str:
        return f'KernelImpl.Kind.BoundaryObligation'
    def __eq__(self, __o: object) -> bool:
        return isinstance(__o, Kind_BoundaryObligation)
    def __hash__(self) -> int:
        return super().__hash__()


class ObligationReason:
    @_dafny.classproperty
    def AllSingletonConstructors(cls):
        return [ObligationReason_ByProof(), ObligationReason_ByBoundary(), ObligationReason_ByMutant(), ObligationReason_ByBlock(), ObligationReason_ByFailure()]
    @classmethod
    def default(cls, ):
        return lambda: ObligationReason_ByProof()
    def __ne__(self, __o: object) -> bool:
        return not self.__eq__(__o)
    @property
    def is_ByProof(self) -> bool:
        return isinstance(self, ObligationReason_ByProof)
    @property
    def is_ByBoundary(self) -> bool:
        return isinstance(self, ObligationReason_ByBoundary)
    @property
    def is_ByMutant(self) -> bool:
        return isinstance(self, ObligationReason_ByMutant)
    @property
    def is_ByBlock(self) -> bool:
        return isinstance(self, ObligationReason_ByBlock)
    @property
    def is_ByFailure(self) -> bool:
        return isinstance(self, ObligationReason_ByFailure)

class ObligationReason_ByProof(ObligationReason, NamedTuple('ByProof', [])):
    def __dafnystr__(self) -> str:
        return f'KernelImpl.ObligationReason.ByProof'
    def __eq__(self, __o: object) -> bool:
        return isinstance(__o, ObligationReason_ByProof)
    def __hash__(self) -> int:
        return super().__hash__()

class ObligationReason_ByBoundary(ObligationReason, NamedTuple('ByBoundary', [])):
    def __dafnystr__(self) -> str:
        return f'KernelImpl.ObligationReason.ByBoundary'
    def __eq__(self, __o: object) -> bool:
        return isinstance(__o, ObligationReason_ByBoundary)
    def __hash__(self) -> int:
        return super().__hash__()

class ObligationReason_ByMutant(ObligationReason, NamedTuple('ByMutant', [])):
    def __dafnystr__(self) -> str:
        return f'KernelImpl.ObligationReason.ByMutant'
    def __eq__(self, __o: object) -> bool:
        return isinstance(__o, ObligationReason_ByMutant)
    def __hash__(self) -> int:
        return super().__hash__()

class ObligationReason_ByBlock(ObligationReason, NamedTuple('ByBlock', [])):
    def __dafnystr__(self) -> str:
        return f'KernelImpl.ObligationReason.ByBlock'
    def __eq__(self, __o: object) -> bool:
        return isinstance(__o, ObligationReason_ByBlock)
    def __hash__(self) -> int:
        return super().__hash__()

class ObligationReason_ByFailure(ObligationReason, NamedTuple('ByFailure', [])):
    def __dafnystr__(self) -> str:
        return f'KernelImpl.ObligationReason.ByFailure'
    def __eq__(self, __o: object) -> bool:
        return isinstance(__o, ObligationReason_ByFailure)
    def __hash__(self) -> int:
        return super().__hash__()


class Phase:
    @_dafny.classproperty
    def AllSingletonConstructors(cls):
        return [Phase_Draft(), Phase_Locked(), Phase_LockInvalid(), Phase_SpecInvalid()]
    @classmethod
    def default(cls, ):
        return lambda: Phase_Draft()
    def __ne__(self, __o: object) -> bool:
        return not self.__eq__(__o)
    @property
    def is_Draft(self) -> bool:
        return isinstance(self, Phase_Draft)
    @property
    def is_Locked(self) -> bool:
        return isinstance(self, Phase_Locked)
    @property
    def is_LockInvalid(self) -> bool:
        return isinstance(self, Phase_LockInvalid)
    @property
    def is_SpecInvalid(self) -> bool:
        return isinstance(self, Phase_SpecInvalid)

class Phase_Draft(Phase, NamedTuple('Draft', [])):
    def __dafnystr__(self) -> str:
        return f'KernelImpl.Phase.Draft'
    def __eq__(self, __o: object) -> bool:
        return isinstance(__o, Phase_Draft)
    def __hash__(self) -> int:
        return super().__hash__()

class Phase_Locked(Phase, NamedTuple('Locked', [])):
    def __dafnystr__(self) -> str:
        return f'KernelImpl.Phase.Locked'
    def __eq__(self, __o: object) -> bool:
        return isinstance(__o, Phase_Locked)
    def __hash__(self) -> int:
        return super().__hash__()

class Phase_LockInvalid(Phase, NamedTuple('LockInvalid', [])):
    def __dafnystr__(self) -> str:
        return f'KernelImpl.Phase.LockInvalid'
    def __eq__(self, __o: object) -> bool:
        return isinstance(__o, Phase_LockInvalid)
    def __hash__(self) -> int:
        return super().__hash__()

class Phase_SpecInvalid(Phase, NamedTuple('SpecInvalid', [])):
    def __dafnystr__(self) -> str:
        return f'KernelImpl.Phase.SpecInvalid'
    def __eq__(self, __o: object) -> bool:
        return isinstance(__o, Phase_SpecInvalid)
    def __hash__(self) -> int:
        return super().__hash__()


class GateState:
    @_dafny.classproperty
    def AllSingletonConstructors(cls):
        return [GateState_NoGate(), GateState_Stale(), GateState_Current()]
    @classmethod
    def default(cls, ):
        return lambda: GateState_NoGate()
    def __ne__(self, __o: object) -> bool:
        return not self.__eq__(__o)
    @property
    def is_NoGate(self) -> bool:
        return isinstance(self, GateState_NoGate)
    @property
    def is_Stale(self) -> bool:
        return isinstance(self, GateState_Stale)
    @property
    def is_Current(self) -> bool:
        return isinstance(self, GateState_Current)

class GateState_NoGate(GateState, NamedTuple('NoGate', [])):
    def __dafnystr__(self) -> str:
        return f'KernelImpl.GateState.NoGate'
    def __eq__(self, __o: object) -> bool:
        return isinstance(__o, GateState_NoGate)
    def __hash__(self) -> int:
        return super().__hash__()

class GateState_Stale(GateState, NamedTuple('Stale', [])):
    def __dafnystr__(self) -> str:
        return f'KernelImpl.GateState.Stale'
    def __eq__(self, __o: object) -> bool:
        return isinstance(__o, GateState_Stale)
    def __hash__(self) -> int:
        return super().__hash__()

class GateState_Current(GateState, NamedTuple('Current', [])):
    def __dafnystr__(self) -> str:
        return f'KernelImpl.GateState.Current'
    def __eq__(self, __o: object) -> bool:
        return isinstance(__o, GateState_Current)
    def __hash__(self) -> int:
        return super().__hash__()


class RequirementReason:
    @classmethod
    def default(cls, ):
        return lambda: RequirementReason_NotApproved()
    def __ne__(self, __o: object) -> bool:
        return not self.__eq__(__o)
    @property
    def is_NotApproved(self) -> bool:
        return isinstance(self, RequirementReason_NotApproved)
    @property
    def is_GateMissing(self) -> bool:
        return isinstance(self, RequirementReason_GateMissing)
    @property
    def is_GateStale(self) -> bool:
        return isinstance(self, RequirementReason_GateStale)
    @property
    def is_Uncovered(self) -> bool:
        return isinstance(self, RequirementReason_Uncovered)
    @property
    def is_ByObligation(self) -> bool:
        return isinstance(self, RequirementReason_ByObligation)

class RequirementReason_NotApproved(RequirementReason, NamedTuple('NotApproved', [])):
    def __dafnystr__(self) -> str:
        return f'KernelImpl.RequirementReason.NotApproved'
    def __eq__(self, __o: object) -> bool:
        return isinstance(__o, RequirementReason_NotApproved)
    def __hash__(self) -> int:
        return super().__hash__()

class RequirementReason_GateMissing(RequirementReason, NamedTuple('GateMissing', [])):
    def __dafnystr__(self) -> str:
        return f'KernelImpl.RequirementReason.GateMissing'
    def __eq__(self, __o: object) -> bool:
        return isinstance(__o, RequirementReason_GateMissing)
    def __hash__(self) -> int:
        return super().__hash__()

class RequirementReason_GateStale(RequirementReason, NamedTuple('GateStale', [])):
    def __dafnystr__(self) -> str:
        return f'KernelImpl.RequirementReason.GateStale'
    def __eq__(self, __o: object) -> bool:
        return isinstance(__o, RequirementReason_GateStale)
    def __hash__(self) -> int:
        return super().__hash__()

class RequirementReason_Uncovered(RequirementReason, NamedTuple('Uncovered', [])):
    def __dafnystr__(self) -> str:
        return f'KernelImpl.RequirementReason.Uncovered'
    def __eq__(self, __o: object) -> bool:
        return isinstance(__o, RequirementReason_Uncovered)
    def __hash__(self) -> int:
        return super().__hash__()

class RequirementReason_ByObligation(RequirementReason, NamedTuple('ByObligation', [('index', Any)])):
    def __dafnystr__(self) -> str:
        return f'KernelImpl.RequirementReason.ByObligation({_dafny.string_of(self.index)})'
    def __eq__(self, __o: object) -> bool:
        return isinstance(__o, RequirementReason_ByObligation) and self.index == __o.index
    def __hash__(self) -> int:
        return super().__hash__()


class Category:
    @_dafny.classproperty
    def AllSingletonConstructors(cls):
        return [Category_OutsideProject(), Category_Protected(), Category_Allowed(), Category_BundleSpec(), Category_BundleContract(), Category_BundleImpl(), Category_BundleDoc(), Category_ScopeCovered(), Category_NotCovered()]
    @classmethod
    def default(cls, ):
        return lambda: Category_OutsideProject()
    def __ne__(self, __o: object) -> bool:
        return not self.__eq__(__o)
    @property
    def is_OutsideProject(self) -> bool:
        return isinstance(self, Category_OutsideProject)
    @property
    def is_Protected(self) -> bool:
        return isinstance(self, Category_Protected)
    @property
    def is_Allowed(self) -> bool:
        return isinstance(self, Category_Allowed)
    @property
    def is_BundleSpec(self) -> bool:
        return isinstance(self, Category_BundleSpec)
    @property
    def is_BundleContract(self) -> bool:
        return isinstance(self, Category_BundleContract)
    @property
    def is_BundleImpl(self) -> bool:
        return isinstance(self, Category_BundleImpl)
    @property
    def is_BundleDoc(self) -> bool:
        return isinstance(self, Category_BundleDoc)
    @property
    def is_ScopeCovered(self) -> bool:
        return isinstance(self, Category_ScopeCovered)
    @property
    def is_NotCovered(self) -> bool:
        return isinstance(self, Category_NotCovered)

class Category_OutsideProject(Category, NamedTuple('OutsideProject', [])):
    def __dafnystr__(self) -> str:
        return f'KernelImpl.Category.OutsideProject'
    def __eq__(self, __o: object) -> bool:
        return isinstance(__o, Category_OutsideProject)
    def __hash__(self) -> int:
        return super().__hash__()

class Category_Protected(Category, NamedTuple('Protected', [])):
    def __dafnystr__(self) -> str:
        return f'KernelImpl.Category.Protected'
    def __eq__(self, __o: object) -> bool:
        return isinstance(__o, Category_Protected)
    def __hash__(self) -> int:
        return super().__hash__()

class Category_Allowed(Category, NamedTuple('Allowed', [])):
    def __dafnystr__(self) -> str:
        return f'KernelImpl.Category.Allowed'
    def __eq__(self, __o: object) -> bool:
        return isinstance(__o, Category_Allowed)
    def __hash__(self) -> int:
        return super().__hash__()

class Category_BundleSpec(Category, NamedTuple('BundleSpec', [])):
    def __dafnystr__(self) -> str:
        return f'KernelImpl.Category.BundleSpec'
    def __eq__(self, __o: object) -> bool:
        return isinstance(__o, Category_BundleSpec)
    def __hash__(self) -> int:
        return super().__hash__()

class Category_BundleContract(Category, NamedTuple('BundleContract', [])):
    def __dafnystr__(self) -> str:
        return f'KernelImpl.Category.BundleContract'
    def __eq__(self, __o: object) -> bool:
        return isinstance(__o, Category_BundleContract)
    def __hash__(self) -> int:
        return super().__hash__()

class Category_BundleImpl(Category, NamedTuple('BundleImpl', [])):
    def __dafnystr__(self) -> str:
        return f'KernelImpl.Category.BundleImpl'
    def __eq__(self, __o: object) -> bool:
        return isinstance(__o, Category_BundleImpl)
    def __hash__(self) -> int:
        return super().__hash__()

class Category_BundleDoc(Category, NamedTuple('BundleDoc', [])):
    def __dafnystr__(self) -> str:
        return f'KernelImpl.Category.BundleDoc'
    def __eq__(self, __o: object) -> bool:
        return isinstance(__o, Category_BundleDoc)
    def __hash__(self) -> int:
        return super().__hash__()

class Category_ScopeCovered(Category, NamedTuple('ScopeCovered', [])):
    def __dafnystr__(self) -> str:
        return f'KernelImpl.Category.ScopeCovered'
    def __eq__(self, __o: object) -> bool:
        return isinstance(__o, Category_ScopeCovered)
    def __hash__(self) -> int:
        return super().__hash__()

class Category_NotCovered(Category, NamedTuple('NotCovered', [])):
    def __dafnystr__(self) -> str:
        return f'KernelImpl.Category.NotCovered'
    def __eq__(self, __o: object) -> bool:
        return isinstance(__o, Category_NotCovered)
    def __hash__(self) -> int:
        return super().__hash__()


class Reason:
    @_dafny.classproperty
    def AllSingletonConstructors(cls):
        return [Reason_RProtected(), Reason_ROutsideSpec(), Reason_RNotApproved(), Reason_RContractLocked(), Reason_RFormalLocked(), Reason_RSpecLocked(), Reason_RImplWithoutLock(), Reason_RLockInvalid(), Reason_RSpecInvalid()]
    @classmethod
    def default(cls, ):
        return lambda: Reason_RProtected()
    def __ne__(self, __o: object) -> bool:
        return not self.__eq__(__o)
    @property
    def is_RProtected(self) -> bool:
        return isinstance(self, Reason_RProtected)
    @property
    def is_ROutsideSpec(self) -> bool:
        return isinstance(self, Reason_ROutsideSpec)
    @property
    def is_RNotApproved(self) -> bool:
        return isinstance(self, Reason_RNotApproved)
    @property
    def is_RContractLocked(self) -> bool:
        return isinstance(self, Reason_RContractLocked)
    @property
    def is_RFormalLocked(self) -> bool:
        return isinstance(self, Reason_RFormalLocked)
    @property
    def is_RSpecLocked(self) -> bool:
        return isinstance(self, Reason_RSpecLocked)
    @property
    def is_RImplWithoutLock(self) -> bool:
        return isinstance(self, Reason_RImplWithoutLock)
    @property
    def is_RLockInvalid(self) -> bool:
        return isinstance(self, Reason_RLockInvalid)
    @property
    def is_RSpecInvalid(self) -> bool:
        return isinstance(self, Reason_RSpecInvalid)

class Reason_RProtected(Reason, NamedTuple('RProtected', [])):
    def __dafnystr__(self) -> str:
        return f'KernelImpl.Reason.RProtected'
    def __eq__(self, __o: object) -> bool:
        return isinstance(__o, Reason_RProtected)
    def __hash__(self) -> int:
        return super().__hash__()

class Reason_ROutsideSpec(Reason, NamedTuple('ROutsideSpec', [])):
    def __dafnystr__(self) -> str:
        return f'KernelImpl.Reason.ROutsideSpec'
    def __eq__(self, __o: object) -> bool:
        return isinstance(__o, Reason_ROutsideSpec)
    def __hash__(self) -> int:
        return super().__hash__()

class Reason_RNotApproved(Reason, NamedTuple('RNotApproved', [])):
    def __dafnystr__(self) -> str:
        return f'KernelImpl.Reason.RNotApproved'
    def __eq__(self, __o: object) -> bool:
        return isinstance(__o, Reason_RNotApproved)
    def __hash__(self) -> int:
        return super().__hash__()

class Reason_RContractLocked(Reason, NamedTuple('RContractLocked', [])):
    def __dafnystr__(self) -> str:
        return f'KernelImpl.Reason.RContractLocked'
    def __eq__(self, __o: object) -> bool:
        return isinstance(__o, Reason_RContractLocked)
    def __hash__(self) -> int:
        return super().__hash__()

class Reason_RFormalLocked(Reason, NamedTuple('RFormalLocked', [])):
    def __dafnystr__(self) -> str:
        return f'KernelImpl.Reason.RFormalLocked'
    def __eq__(self, __o: object) -> bool:
        return isinstance(__o, Reason_RFormalLocked)
    def __hash__(self) -> int:
        return super().__hash__()

class Reason_RSpecLocked(Reason, NamedTuple('RSpecLocked', [])):
    def __dafnystr__(self) -> str:
        return f'KernelImpl.Reason.RSpecLocked'
    def __eq__(self, __o: object) -> bool:
        return isinstance(__o, Reason_RSpecLocked)
    def __hash__(self) -> int:
        return super().__hash__()

class Reason_RImplWithoutLock(Reason, NamedTuple('RImplWithoutLock', [])):
    def __dafnystr__(self) -> str:
        return f'KernelImpl.Reason.RImplWithoutLock'
    def __eq__(self, __o: object) -> bool:
        return isinstance(__o, Reason_RImplWithoutLock)
    def __hash__(self) -> int:
        return super().__hash__()

class Reason_RLockInvalid(Reason, NamedTuple('RLockInvalid', [])):
    def __dafnystr__(self) -> str:
        return f'KernelImpl.Reason.RLockInvalid'
    def __eq__(self, __o: object) -> bool:
        return isinstance(__o, Reason_RLockInvalid)
    def __hash__(self) -> int:
        return super().__hash__()

class Reason_RSpecInvalid(Reason, NamedTuple('RSpecInvalid', [])):
    def __dafnystr__(self) -> str:
        return f'KernelImpl.Reason.RSpecInvalid'
    def __eq__(self, __o: object) -> bool:
        return isinstance(__o, Reason_RSpecInvalid)
    def __hash__(self) -> int:
        return super().__hash__()


class Decision:
    @classmethod
    def default(cls, ):
        return lambda: Decision_Allow()
    def __ne__(self, __o: object) -> bool:
        return not self.__eq__(__o)
    @property
    def is_Allow(self) -> bool:
        return isinstance(self, Decision_Allow)
    @property
    def is_Deny(self) -> bool:
        return isinstance(self, Decision_Deny)

class Decision_Allow(Decision, NamedTuple('Allow', [])):
    def __dafnystr__(self) -> str:
        return f'KernelImpl.Decision.Allow'
    def __eq__(self, __o: object) -> bool:
        return isinstance(__o, Decision_Allow)
    def __hash__(self) -> int:
        return super().__hash__()

class Decision_Deny(Decision, NamedTuple('Deny', [('reason', Any)])):
    def __dafnystr__(self) -> str:
        return f'KernelImpl.Decision.Deny({_dafny.string_of(self.reason)})'
    def __eq__(self, __o: object) -> bool:
        return isinstance(__o, Decision_Deny) and self.reason == __o.reason
    def __hash__(self) -> int:
        return super().__hash__()


class ApprovalReason:
    @_dafny.classproperty
    def AllSingletonConstructors(cls):
        return [ApprovalReason_RNoTypedCode(), ApprovalReason_RContentChanged(), ApprovalReason_RAlreadyUsed()]
    @classmethod
    def default(cls, ):
        return lambda: ApprovalReason_RNoTypedCode()
    def __ne__(self, __o: object) -> bool:
        return not self.__eq__(__o)
    @property
    def is_RNoTypedCode(self) -> bool:
        return isinstance(self, ApprovalReason_RNoTypedCode)
    @property
    def is_RContentChanged(self) -> bool:
        return isinstance(self, ApprovalReason_RContentChanged)
    @property
    def is_RAlreadyUsed(self) -> bool:
        return isinstance(self, ApprovalReason_RAlreadyUsed)

class ApprovalReason_RNoTypedCode(ApprovalReason, NamedTuple('RNoTypedCode', [])):
    def __dafnystr__(self) -> str:
        return f'KernelImpl.ApprovalReason.RNoTypedCode'
    def __eq__(self, __o: object) -> bool:
        return isinstance(__o, ApprovalReason_RNoTypedCode)
    def __hash__(self) -> int:
        return super().__hash__()

class ApprovalReason_RContentChanged(ApprovalReason, NamedTuple('RContentChanged', [])):
    def __dafnystr__(self) -> str:
        return f'KernelImpl.ApprovalReason.RContentChanged'
    def __eq__(self, __o: object) -> bool:
        return isinstance(__o, ApprovalReason_RContentChanged)
    def __hash__(self) -> int:
        return super().__hash__()

class ApprovalReason_RAlreadyUsed(ApprovalReason, NamedTuple('RAlreadyUsed', [])):
    def __dafnystr__(self) -> str:
        return f'KernelImpl.ApprovalReason.RAlreadyUsed'
    def __eq__(self, __o: object) -> bool:
        return isinstance(__o, ApprovalReason_RAlreadyUsed)
    def __hash__(self) -> int:
        return super().__hash__()


class ApprovalDecision:
    @classmethod
    def default(cls, ):
        return lambda: ApprovalDecision_Approved()
    def __ne__(self, __o: object) -> bool:
        return not self.__eq__(__o)
    @property
    def is_Approved(self) -> bool:
        return isinstance(self, ApprovalDecision_Approved)
    @property
    def is_Refused(self) -> bool:
        return isinstance(self, ApprovalDecision_Refused)

class ApprovalDecision_Approved(ApprovalDecision, NamedTuple('Approved', [])):
    def __dafnystr__(self) -> str:
        return f'KernelImpl.ApprovalDecision.Approved'
    def __eq__(self, __o: object) -> bool:
        return isinstance(__o, ApprovalDecision_Approved)
    def __hash__(self) -> int:
        return super().__hash__()

class ApprovalDecision_Refused(ApprovalDecision, NamedTuple('Refused', [('why', Any)])):
    def __dafnystr__(self) -> str:
        return f'KernelImpl.ApprovalDecision.Refused({_dafny.string_of(self.why)})'
    def __eq__(self, __o: object) -> bool:
        return isinstance(__o, ApprovalDecision_Refused) and self.why == __o.why
    def __hash__(self) -> int:
        return super().__hash__()

