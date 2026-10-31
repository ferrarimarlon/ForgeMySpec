// @target boundary_is_at_most_fragile
// Planted error: Treats a passing boundary test as proof.
include "contract.dfy"

module KernelImpl refines TrustKernel {
  method ClassifyObligation(kind: Kind, failures: nat, survivors: nat, testsOk: bool, blocked: bool)
    returns (s: Status, r: ObligationReason)
  {
    if failures > 0 {
      s, r := Leaking, ByFailure;
    } else if kind == BoundaryObligation {
      if testsOk {
        s, r := Proven, ByProof;
      } else {
        s, r := Leaking, ByFailure;
      }
    } else if survivors > 0 {
      s, r := Fragile, ByMutant;
    } else if blocked || !testsOk {
      s, r := Fragile, ByBlock;
    } else {
      s, r := Proven, ByProof;
    }
  }

  method RequirementStatus(phase: Phase, gate: GateState, coverage: seq<Status>)
    returns (s: Status, r: RequirementReason)
  {
    if phase != Locked {
      return Leaking, NotApproved;
    }
    if gate == NoGate {
      return Leaking, GateMissing;
    }
    if gate == Stale {
      return Leaking, GateStale;
    }
    if |coverage| == 0 {
      return Leaking, Uncovered;
    }
    var idx := 0;
    var i := 1;
    while i < |coverage|
      invariant 1 <= i <= |coverage|
      invariant 0 <= idx < i
      invariant forall j :: 0 <= j < i ==> Rank(coverage[idx]) <= Rank(coverage[j])
      invariant forall j :: 0 <= j < idx ==> Rank(coverage[j]) > Rank(coverage[idx])
    {
      if Rank(coverage[i]) < Rank(coverage[idx]) {
        idx := i;
      }
      i := i + 1;
    }
    s := coverage[idx];
    r := ByObligation(idx);
  }

  method DecideEdit(c: Category, formal: bool, phase: Phase, changesFormal: bool, coveringApproved: bool)
    returns (d: Decision)
  {
    match c {
      case OutsideProject => d := Allow;
      case Protected => d := Deny(RProtected);
      case Allowed => d := Allow;
      case BundleDoc => d := Allow;
      case NotCovered => d := Deny(ROutsideSpec);
      case ScopeCovered =>
        d := if coveringApproved then Allow else Deny(RNotApproved);
      case BundleSpec =>
        if phase == Draft || phase == SpecInvalid {
          d := Allow;
        } else if !formal {
          d := Deny(RSpecLocked);
        } else if changesFormal {
          d := Deny(RFormalLocked);
        } else {
          d := Allow;
        }
      case BundleContract =>
        match phase {
          case Draft => d := Allow;
          case Locked => d := Deny(RContractLocked);
          case LockInvalid => d := Deny(RContractLocked);
          case SpecInvalid => d := Deny(RSpecInvalid);
        }
      case BundleImpl =>
        match phase {
          case Locked => d := Allow;
          case Draft => d := if formal then Deny(RImplWithoutLock) else Deny(RNotApproved);
          case LockInvalid => d := Deny(RLockInvalid);
          case SpecInvalid => d := Deny(RSpecInvalid);
        }
    }
  }

  method DecideApproval(terminal: bool, typedCode: bool, contentMatches: bool, used: bool)
    returns (a: ApprovalDecision)
  {
    if terminal {
      a := Approved;
    } else if !typedCode {
      a := Refused(RNoTypedCode);
    } else if !contentMatches {
      a := Refused(RContentChanged);
    } else if used {
      a := Refused(RAlreadyUsed);
    } else {
      a := Approved;
    }
  }

  method Coverage(hypotheses: seq<string>, phrases: seq<string>, refsH: seq<seq<string>>, refsP: seq<seq<string>>)
    returns (missingH: seq<string>, missingP: seq<string>)
  {
    missingH := Missing(hypotheses, refsH);
    missingP := Missing(phrases, refsP);
  }

  method Missing(xs: seq<string>, refs: seq<seq<string>>) returns (r: seq<string>)
    ensures forall h :: h in r <==> (h in xs && forall k :: 0 <= k < |refs| ==> h !in refs[k])
  {
    r := [];
    var i := 0;
    while i < |xs|
      invariant 0 <= i <= |xs|
      invariant forall h :: h in r <==> (h in xs[..i] && forall k :: 0 <= k < |refs| ==> h !in refs[k])
    {
      var covered := Covered(xs[i], refs);
      if !covered {
        r := r + [xs[i]];
      }
      assert xs[..i + 1] == xs[..i] + [xs[i]];
      i := i + 1;
    }
    assert xs[..i] == xs;
  }

  method Covered(x: string, refs: seq<seq<string>>) returns (b: bool)
    ensures b <==> exists k :: 0 <= k < |refs| && x in refs[k]
  {
    b := false;
    var k := 0;
    while k < |refs|
      invariant 0 <= k <= |refs|
      invariant b <==> exists j :: 0 <= j < k && x in refs[j]
    {
      if x in refs[k] {
        b := true;
      }
      k := k + 1;
    }
  }
}
