# Acceptance Checklist

## Scope
- [ ] Objective implemented exactly: Prove in Dafny the five decisions that trust in ForgeMySpec depends on: each obligation's color, each requirement's status, the guards' decision about an edit, the coverage of hypotheses and phrases, and whether an approval counts. The Python of the guards, the gate and the risk box uses only the translation of this kernel for these decisions.
- [ ] No unrequested features were introduced
- [ ] All assumptions are explicit and justified

## Success Criteria
- [ ] `forgemyspec gate forgemyspec-bundle/kernel` passes every stage, with 100% of valid mutants killed and every planted error rejected.
- [ ] Each obligation has a Dafny test with concrete values, including each rule's edge cases.

## Required Evidence
- [ ] Full gate report for the kernel, with mutation and planted errors.
- [ ] Output of the kernel's Dafny tests.

## Decision Rules Compliance
- [ ] If a property cannot be proven as written, stop and amend the contract with the user; never weaken the clause to make the proof pass.
- [ ] If a planted error survives, strengthen the contract or the tests with new approval; never delete the error.
