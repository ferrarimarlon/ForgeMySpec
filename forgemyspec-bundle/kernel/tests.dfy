include "impl.dfy"

module KernelTests {
  import opened KernelImpl

  // @obligation failure_means_leaking
  method {:test} FailureMeansLeaking() {
    var s, r := ClassifyObligation(DafnyObligation, 1, 0, true, false);
    expect s == Leaking && r == ByFailure;
    var s2, r2 := ClassifyObligation(BoundaryObligation, 2, 0, true, false);
    expect s2 == Leaking && r2 == ByFailure;
  }

  // @obligation boundary_is_at_most_fragile
  method {:test} BoundaryIsAtMostFragile() {
    var s, r := ClassifyObligation(BoundaryObligation, 0, 0, true, false);
    expect s == Fragile && r == ByBoundary;
    var s2, r2 := ClassifyObligation(BoundaryObligation, 0, 0, false, false);
    expect s2 == Leaking && r2 == ByFailure;
  }

  // @obligation surviving_mutant_weakens
  method {:test} SurvivingMutantWeakens() {
    var s, r := ClassifyObligation(DafnyObligation, 0, 2, true, false);
    expect s == Fragile && r == ByMutant;
  }

  // @obligation proven_requires_full_evidence
  method {:test} ProvenRequiresFullEvidence() {
    var s, r := ClassifyObligation(DafnyObligation, 0, 0, true, false);
    expect s == Proven && r == ByProof;
    var s2, r2 := ClassifyObligation(DafnyObligation, 0, 0, false, false);
    expect s2 == Fragile && r2 == ByBlock;
    var s3, r3 := ClassifyObligation(DafnyObligation, 0, 0, true, true);
    expect s3 == Fragile && r3 == ByBlock;
  }

  // @obligation met_requires_approval_and_current_gate
  method {:test} MetRequiresApprovalAndCurrentGate() {
    var s, r := RequirementStatus(Draft, Current, [Proven]);
    expect s == Leaking && r == NotApproved;
    var s2, r2 := RequirementStatus(Locked, NoGate, [Proven]);
    expect s2 == Leaking && r2 == GateMissing;
    var s3, r3 := RequirementStatus(Locked, Stale, [Proven]);
    expect s3 == Leaking && r3 == GateStale;
    var s4, r4 := RequirementStatus(Locked, Current, []);
    expect s4 == Leaking && r4 == Uncovered;
    var s5, r5 := RequirementStatus(LockInvalid, Current, [Proven]);
    expect s5 == Leaking && r5 == NotApproved;
  }

  // @obligation requirement_takes_worst_obligation
  method {:test} RequirementTakesWorstObligation() {
    var s, r := RequirementStatus(Locked, Current, [Proven, Fragile, Proven]);
    expect s == Fragile && r == ByObligation(1);
    var s2, r2 := RequirementStatus(Locked, Current, [Proven, Proven]);
    expect s2 == Proven && r2.ByObligation?;
    var s3, r3 := RequirementStatus(Locked, Current, [Fragile, Leaking]);
    expect s3 == Leaking && r3 == ByObligation(1);
    var s4, r4 := RequirementStatus(Locked, Current, [Proven, Fragile, Fragile]);
    expect s4 == Fragile && r4 == ByObligation(1);
  }

  // @obligation protected_always_denied
  method {:test} ProtectedAlwaysDenied() {
    var d := DecideEdit(Protected, true, Locked, false, true);
    expect d == Deny(RProtected);
    var d2 := DecideEdit(Protected, false, Draft, false, true);
    expect d2 == Deny(RProtected);
    var d3 := DecideEdit(OutsideProject, true, Draft, false, false);
    expect d3 == Allow;
    var d4 := DecideEdit(Allowed, false, Draft, false, false);
    expect d4 == Allow;
    var d5 := DecideEdit(BundleDoc, true, Locked, false, false);
    expect d5 == Allow;
  }

  // @obligation outside_spec_denied
  method {:test} OutsideSpecDenied() {
    var d := DecideEdit(NotCovered, false, Draft, false, true);
    expect d == Deny(ROutsideSpec);
    var d2 := DecideEdit(ScopeCovered, false, Draft, false, false);
    expect d2 == Deny(RNotApproved);
    var d3 := DecideEdit(ScopeCovered, false, Draft, false, true);
    expect d3 == Allow;
  }

  // @obligation locked_spec_protected
  method {:test} LockedSpecProtected() {
    var d := DecideEdit(BundleSpec, true, Locked, true, false);
    expect d == Deny(RFormalLocked);
    var d2 := DecideEdit(BundleSpec, true, Locked, false, false);
    expect d2 == Allow;
    var d3 := DecideEdit(BundleSpec, false, Locked, false, false);
    expect d3 == Deny(RSpecLocked);
    var d4 := DecideEdit(BundleSpec, true, Draft, true, false);
    expect d4 == Allow;
    var d5 := DecideEdit(BundleSpec, false, SpecInvalid, false, false);
    expect d5 == Allow;
  }

  // @obligation locked_contract_protected
  method {:test} LockedContractProtected() {
    var d := DecideEdit(BundleContract, true, Draft, false, false);
    expect d == Allow;
    var d2 := DecideEdit(BundleContract, true, Locked, false, false);
    expect d2 == Deny(RContractLocked);
    var d3 := DecideEdit(BundleContract, true, LockInvalid, false, false);
    expect d3 == Deny(RContractLocked);
  }

  // @obligation impl_requires_lock
  method {:test} ImplRequiresLock() {
    var d := DecideEdit(BundleImpl, true, Locked, false, false);
    expect d == Allow;
    var d2 := DecideEdit(BundleImpl, true, Draft, false, false);
    expect d2 == Deny(RImplWithoutLock);
    var d3 := DecideEdit(BundleImpl, false, Draft, false, false);
    expect d3 == Deny(RNotApproved);
    var d4 := DecideEdit(BundleImpl, true, LockInvalid, false, false);
    expect d4 == Deny(RLockInvalid);
  }

  // @obligation exact_coverage
  method {:test} ExactCoverage() {
    var mh, mp := Coverage(["h1", "h2"], ["a", "b"], [["h1"]], [["a", "b"]]);
    expect mh == ["h2"] && mp == [];
    var mh2, mp2 := Coverage(["h1"], ["a"], [], []);
    expect mh2 == ["h1"] && mp2 == ["a"];
    var mh3, mp3 := Coverage([], [], [["x"]], [["y"]]);
    expect mh3 == [] && mp3 == [];
  }
}
