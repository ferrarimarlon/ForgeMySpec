// Contract of the ForgeMySpec trust kernel.
// Approved by the user and locked in contract.lock: impl.dfy refines this module and cannot weaken it.
// The guards, the gate and the risk box use only the Python translation of this kernel for these decisions.
abstract module TrustKernel {
  datatype Status = Leaking | Fragile | Proven
  datatype Kind = DafnyObligation | BoundaryObligation
  datatype ObligationReason = ByProof | ByBoundary | ByMutant | ByBlock | ByFailure
  datatype Phase = Draft | Locked | LockInvalid | SpecInvalid
  datatype GateState = NoGate | Stale | Current
  datatype RequirementReason = NotApproved | GateMissing | GateStale | Uncovered | ByObligation(index: nat)
  datatype Category =
    OutsideProject | Protected | Allowed | BundleSpec | BundleContract | BundleImpl
    | BundleDoc | ScopeCovered | NotCovered
  datatype Reason =
    RProtected | ROutsideSpec | RNotApproved | RContractLocked | RFormalLocked | RSpecLocked
    | RImplWithoutLock | RLockInvalid | RSpecInvalid
  datatype Decision = Allow | Deny(reason: Reason)

  // Severity order: Leaking is the worst.
  function Rank(s: Status): nat
  {
    match s
    case Leaking => 0
    case Fragile => 1
    case Proven => 2
  }

  method ClassifyObligation(kind: Kind, failures: nat, survivors: nat, testsOk: bool, blocked: bool)
    returns (s: Status, r: ObligationReason)
    // @obligation failure_means_leaking
    ensures failures > 0 ==> s == Leaking && r == ByFailure
    // @obligation boundary_is_at_most_fragile
    ensures failures == 0 && kind == BoundaryObligation && testsOk ==> s == Fragile && r == ByBoundary
    ensures failures == 0 && kind == BoundaryObligation && !testsOk ==> s == Leaking && r == ByFailure
    // @obligation surviving_mutant_weakens
    ensures failures == 0 && kind == DafnyObligation && survivors > 0 ==> s == Fragile && r == ByMutant
    ensures failures == 0 && kind == DafnyObligation && survivors == 0 && (blocked || !testsOk) ==> s == Fragile && r == ByBlock
    // @obligation proven_requires_full_evidence
    ensures s == Proven <==> (kind == DafnyObligation && failures == 0 && survivors == 0 && testsOk && !blocked)
    ensures s == Proven ==> r == ByProof

  method RequirementStatus(phase: Phase, gate: GateState, coverage: seq<Status>)
    returns (s: Status, r: RequirementReason)
    // @obligation met_requires_approval_and_current_gate
    ensures s != Leaking ==> phase == Locked && gate == Current && |coverage| > 0
    ensures phase != Locked ==> s == Leaking && r == NotApproved
    ensures phase == Locked && gate == NoGate ==> s == Leaking && r == GateMissing
    ensures phase == Locked && gate == Stale ==> s == Leaking && r == GateStale
    ensures phase == Locked && gate == Current && |coverage| == 0 ==> s == Leaking && r == Uncovered
    // @obligation requirement_takes_worst_obligation
    ensures phase == Locked && gate == Current && |coverage| > 0 ==>
              r.ByObligation? && r.index < |coverage| && s == coverage[r.index]
              && forall j :: 0 <= j < |coverage| ==> Rank(s) <= Rank(coverage[j])
    ensures phase == Locked && gate == Current && |coverage| > 0 ==> r.ByObligation? && forall j :: 0 <= j < r.index ==> Rank(coverage[j]) > Rank(s)

  method DecideEdit(c: Category, formal: bool, phase: Phase, changesFormal: bool, coveringApproved: bool)
    returns (d: Decision)
    // @obligation protected_always_denied
    ensures c == Protected ==> d == Deny(RProtected)
    ensures c == OutsideProject ==> d == Allow
    ensures c == Allowed ==> d == Allow
    ensures c == BundleDoc ==> d == Allow
    // @obligation outside_spec_denied
    ensures c == NotCovered ==> d == Deny(ROutsideSpec)
    ensures c == ScopeCovered && coveringApproved ==> d == Allow
    ensures c == ScopeCovered && !coveringApproved ==> d == Deny(RNotApproved)
    // @obligation locked_spec_protected
    ensures c == BundleSpec && (phase == Draft || phase == SpecInvalid) ==> d == Allow
    ensures c == BundleSpec && formal && (phase == Locked || phase == LockInvalid) && changesFormal ==> d == Deny(RFormalLocked)
    ensures c == BundleSpec && formal && (phase == Locked || phase == LockInvalid) && !changesFormal ==> d == Allow
    ensures c == BundleSpec && !formal && (phase == Locked || phase == LockInvalid) ==> d == Deny(RSpecLocked)
    // @obligation locked_contract_protected
    ensures c == BundleContract && phase == Draft ==> d == Allow
    ensures c == BundleContract && (phase == Locked || phase == LockInvalid) ==> d == Deny(RContractLocked)
    ensures c == BundleContract && phase == SpecInvalid ==> d == Deny(RSpecInvalid)
    // @obligation impl_requires_lock
    ensures c == BundleImpl && phase == Locked ==> d == Allow
    ensures c == BundleImpl && phase == Draft && formal ==> d == Deny(RImplWithoutLock)
    ensures c == BundleImpl && phase == Draft && !formal ==> d == Deny(RNotApproved)
    ensures c == BundleImpl && phase == LockInvalid ==> d == Deny(RLockInvalid)
    ensures c == BundleImpl && phase == SpecInvalid ==> d == Deny(RSpecInvalid)

  method Coverage(hypotheses: seq<string>, phrases: seq<string>, refsH: seq<seq<string>>, refsP: seq<seq<string>>)
    returns (missingH: seq<string>, missingP: seq<string>)
    // @obligation exact_coverage
    ensures forall h :: h in missingH <==> (h in hypotheses && forall k :: 0 <= k < |refsH| ==> h !in refsH[k])
    ensures forall p :: p in missingP <==> (p in phrases && forall k :: 0 <= k < |refsP| ==> p !in refsP[k])
}
