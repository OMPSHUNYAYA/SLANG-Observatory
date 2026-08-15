# ⭐ **FAQ — SLANG-Observatory**

## **Structural Language (SLANG)**  
**Bounded Deterministic Resolution Across Domains**

SLANG-Observatory contains focused reference demonstrations that resolve
bounded states from declared structure and versioned rules.

The recurring pattern is:

`declared structure + versioned rules -> bounded resolution state`

Where a demo declares order independence:

`same canonical structure + same versioned rules -> same bounded result`

The exact inputs, states, limits, evidence, and claim boundaries are defined by
each demo.

---

## **SECTION A — Core Understanding**

### **A1. What is SLANG-Observatory?**

SLANG-Observatory is a collection of focused structural-resolution
demonstrations.

Each demo applies a shared bounded discipline to a different declared domain
schema, such as invoices, claims, annuity payout admission, cybersecurity
escalation, forecast visibility, examination-form assembly, voting,
password-verification admission, or password-reset admission.

The demos are not presented as separate foundational frameworks merely because
their domain labels differ.

---

### **A2. What does SLANG resolve?**

A SLANG demo resolves a bounded state from declared facts, rules, context, and
admission conditions.

Conceptually:

`outcome = resolve(declared_structure, versioned_rules)`

Depending on the demo, the result may be:

- a visible outcome
- an admitted action or state
- a withheld outcome
- an incomplete state
- a conflict state
- an abstention
- an unsupported-input refusal
- another explicitly declared non-result state

---

### **A3. What is the central idea?**

A named workflow, sequence, arrival order, or operational mechanism does not
have to remain the sole authority over a bounded result when the declared
structure is sufficient to resolve that result.

The practical relation is:

`operational mechanism -> no longer the sole resolution authority`

`complete + consistent + admitted structure -> bounded resolution`

This does not mean that workflows, execution, communication, infrastructure,
or domain operations disappear.

---

### **A4. Is SLANG claiming that correctness always equals structure?**

No.

SLANG-Observatory makes a narrower claim:

within a declared reference model, a bounded resolution can be governed by
explicit structure and versioned rules rather than by a named operational
sequence alone.

Each demo must be judged by its own inputs, rules, limits, evidence, and
documented claim boundary.

---

## **SECTION B — Structural Model**

### **B1. What does “structure” mean?**

Structure is the set of declared facts, relationships, rules, identities,
constraints, authority conditions, and evidence required by a particular demo.

Structure is not a universal object with one fixed schema. Each demo defines
its own supported structure.

---

### **B2. When does an outcome become visible?**

Only when the relevant demo establishes the conditions required by its declared
contract.

A typical relation is:

`complete + consistent + admitted structure -> bounded resolution`

Some demos also require:

- authority
- visibility admission
- release conditions
- uniqueness
- exact resource bounds
- supported evidence identities
- a completed bounded search

---

### **B3. What happens when structure is incomplete?**

The demo should preserve an explicit non-result rather than force an answer.

Depending on the contract, the result may be:

- `INCOMPLETE`
- `ABSTAIN`
- `DENY`
- another declared unresolved state

The exact state names are demo-specific.

---

### **B4. What happens when declarations conflict?**

A conflict should remain visible through the state model declared by the
specific demo.

A resolver may return `CONFLICT` or another explicitly declared non-result state
when supported declarations cannot coexist.

`conflict -> explicit declared non-result state`

A conflicting input is not silently repaired through workflow order unless the
demo contract explicitly defines such behavior.

State meanings remain demo-specific. In particular, `CONFLICT` and `ABSTAIN`
should not be assumed to mean the same thing unless the relevant contract says
so.

---

### **B5. Does missing or conflicting structure always produce silence?**

No.

Some demos return explicit machine-readable states, attestations, receipts,
diagnostics, or reason codes. The important property is that the resolver does
not force a positive outcome when the declared contract does not justify one.

---

## **SECTION C — Determinism and Order Independence**

### **C1. Is SLANG deterministic?**

A demo may claim determinism when identical admitted canonical inputs under the
same versioned rules reproduce the same bounded result.

`same admitted canonical structure + same versioned rules -> same bounded result`

Determinism applies only within the declared implementation and identity
boundary.

---

### **C2. Can two implementations disagree?**

Conforming implementations should reproduce the same declared semantic result when they use the same canonicalization rules, profiles, versioned rules, and supported inputs.

However, exact execution evidence may differ when implementations use different
traversal strategies or operational paths unless the reference contract also
binds those details.

SLANG-Exam v0.7.2 makes this distinction explicit:

- semantic result identity is separated from traversal-dependent evidence
- exact bundle replay reproduces the reference evidence
- semantic-only vector verification does not require identical traversal
  evidence

---

### **C3. Does order always not matter?**

No.

Order independence is claimed only where a demo explicitly normalizes an input
or treats it as a set.

`deterministic != universally order-independent`

`order-independent where declared != every order is semantically equivalent`

Literal submission identity may still preserve the exact submitted form even
when the semantic result is invariant to supported ordering changes.

---

### **C4. Does time never matter?**

No.

Wall-clock time may remain important for operations, validity windows,
scheduling, security, or legal requirements.

A time-independent claim means only that wall-clock time does not govern the
particular bounded admissibility result where the demo explicitly declares that
property.

---

### **C5. What ensures consistency?**

Consistency is established by the validation and resolution rules of the
specific demo.

Structure does not validate itself. The implementation must define:

- supported fields
- canonicalization
- constraints
- conflict rules
- admission rules
- resource limits
- outcome states
- verification behavior

---

## **SECTION D — Execution Clarification**

### **D1. Is software execution removed?**

No.

Execution is still required to evaluate the reference implementation.

The structural claim concerns what determines the bounded result, not whether a
processor executes instructions.

---

### **D2. What is removed from sole authority?**

Depending on the demo, the reference model may remove one of the following from
sole resolution authority:

- workflow sequence
- fragment arrival order
- pipeline order
- premature publication
- a pre-created final artifact
- recount or reset workflow sequence
- continuous connectivity
- traversal or search
- another declared operational mechanism

The mechanism may remain available for operation, discovery, transport,
presentation, audit, or recovery.

---

### **D3. Is this merely delayed execution?**

No.

A structural resolver may still execute, but its bounded result is derived from
the admitted declared structure rather than from the historical order in which
supported fragments happened to arrive.

---

### **D4. Is SLANG just a rules engine?**

SLANG implementations use rules, but the useful distinction is not based on a
label.

The demonstrations make completeness, consistency, admission, refusal,
identity, and evidence boundaries explicit. Rule order must not become an
undeclared source of the bounded outcome where the contract claims canonical
resolution.

---

## **SECTION E — Evidence and Verification**

### **E1. How are results verified?**

Verification varies by demo.

Published evidence may include:

- self-tests
- frozen conformance vectors
- metamorphic relations
- exact replay or reconstruction checks
- semantic-only conformance checks
- reconstruction bundles
- compact receipts
- portable non-result attestations
- machine-readable contracts and schemas
- machine-readable verification reports where published
- artifact-correspondence checks
- optional authenticity envelopes
- tamper tests
- independent semantic verifiers where published

Each verification result applies only to its declared files, profiles, inputs,
schemas, and evidence boundary.

---

### **E2. What does a passing self-test prove?**

It establishes only that the tested implementation satisfies the self-checks
declared by that demo for the covered cases.

It does not by itself establish:

- production safety
- domain completeness
- legal validity
- fairness
- factual truth
- institutional approval
- third-party certification
- superiority over established systems

---

### **E3. What is the difference between semantic and operational evidence?**

Semantic evidence concerns the meaning of the resolved result.

Operational evidence may include details such as:

- search nodes
- traversal counters
- pruning statistics
- execution traces
- reference replay details

A project may bind both, or it may preserve a semantic identity separately from
operational evidence.

---

### **E4. Are integrity, correspondence, authenticity, truth, and authority the same thing?**

No.

Where a demo publishes these layers, they answer different questions.

`structural integrity != correspondence`

`correspondence != authenticity`

`authenticity != trust policy`

`authenticity != real-world truth`

`real-world truth != authorization to act`

`trust policy != authorization to act`

For example:

- structural integrity asks whether an artifact satisfies its own declared contract
- correspondence asks whether it exactly matches the required source or reconstruction
- authenticity asks whether supplied key material cryptographically authenticates the artifact
- trust policy asks whether that key should be trusted in the relevant deployment
- operational authority asks whether an external system may act on the result

A passing result at one layer must not silently be interpreted as a passing
result at a stronger layer.

---

### **E5. What is special about SLANG-Exam v0.7.2?**

SLANG-Exam v0.7.2 is a broader Observatory reference demonstration that
includes:

- bounded examination-form assembly
- canonical ranking
- abstention under unresolved multiplicity
- single-party commit-reveal ranking
- multi-party commit-reveal ranking
- scope-sensitive authority
- release and visibility separation
- bounded exact-marks feasibility
- explicit JSON, marks, and search limits
- reconstruction bundles
- compact receipts
- frozen semantic vectors
- exact reference-evidence vectors
- metamorphic relations
- bounded-search probes

Its current published checks report:

- `127/127 PASS` reference self-test
- `56/56` semantic vectors reproduced
- `56/56` reference-evidence vectors reproduced
- `10/10` metamorphic relations reproduced
- `3/3` bounded-search probes reproduced

These results apply only to the declared v0.7.2 contract and its published
artifacts.

---

### **E6. What is special about SLANG-Claims v0.2.1?**

SLANG-Claims v0.2.1 is a bounded claim-payability admission reference.

It resolves declared claim context and bound claim-authority evidence under an
identified profile, ruleset, canonicalization contract, and bounded arithmetic
profile.

Its published verification surface includes:

- frozen conformance vectors
- reconstruction bundles
- compact receipts
- portable non-result attestations
- machine-readable contracts and schemas
- separate integrity and correspondence checks
- machine-readable authenticity verification reports
- an optional outer authenticity envelope

The central boundary remains:

`PAYABLE != PAYMENT_AUTHORIZED`

SLANG-Claims does not authenticate claimants or evidence sources, interpret
policy or law, determine fraud, settle claims, authorize payment, or move money.

---

### **E7. What is special about SLANG-Annuity v1.1.1?**

SLANG-Annuity v1.1.1 is a bounded annuitant periodic-payout admission reference.

It resolves declared annuity context and bound authority evidence under an
identified profile, ruleset, canonicalization contract, and declared
periodic-benefit pass-through profile.

Its published verification surface includes:

- `102/102 PASS` core self-test
- `79/79 PASS` frozen conformance corpus
- `34/34 PASS` independent semantic verifier
- reconstruction bundles
- compact receipts
- portable non-result attestations
- machine-readable contracts and schemas
- separate integrity and correspondence checks
- deterministic binding-maintenance commands
- precise library-path diagnostics
- dependency-aware evidence-set identity checking

The central deterministic relation is:

`same admitted canonical annuity structure + same versioned contract -> same bounded result`

The operational boundary remains:

`PAYABLE != PAYMENT_AUTHORIZED`

The declared payout amount is admitted rather than actuarially calculated:

`payout_amount_minor = declared_periodic_payout_minor`

when the payout is admitted.

SLANG-Annuity does not authenticate evidence sources, interpret annuity
contracts, establish legal entitlement, perform actuarial valuation, determine
tax treatment, authorize payment, or move money.

---

## **SECTION F — Safety and Failure Behavior**

### **F1. What prevents a forced positive result?**

A demo may use:

- input validation
- completeness checks
- conflict checks
- authority gates
- visibility gates
- exact capacity checks
- bounded search
- explicit abstention
- unsupported-input refusal

The purpose is not to guarantee universal correctness. It is to make the
reference model refuse outcomes that its own contract does not justify.

---

### **F2. Can incorrect declarations still produce a result?**

Yes.

A deterministic resolver can consistently resolve incorrect or misleading
declared facts if those facts satisfy the supported structure.

Therefore, source authenticity, factual validation, authorization, and domain
review remain separate responsibilities unless a specific demo explicitly
implements them.

---

### **F3. Does a verified result establish factual truth?**

No.

A verification result establishes only the scope claimed by that verifier,
such as satisfaction of declared self-checks, reproduction of a frozen corpus,
or exact artifact correspondence. It does not automatically establish:

- authenticity of the source
- truth of the submitted facts
- legal authority
- policy approval
- safety
- fairness
- execution authority

---

### **F4. Can resource limits affect a result?**

Yes.

A bounded resolver may return `UNSUPPORTED`, `ABSTAIN`, or another non-result
state when declared limits are exceeded or a required conclusion cannot be
established within its search boundary.

Resource exhaustion is not proof that no admissible result exists outside the
declared bound.

---

## **SECTION G — Practical Meaning**

### **G1. Where can this pattern be useful?**

Potential uses include:

- bounded validation layers
- eligibility and admission checks
- deterministic reference models
- evidence reconstruction
- explicit refusal handling
- order-independent reconciliation where declared
- visibility and release gating
- conformance testing
- structural diagnostics

Operational use requires domain-specific validation and appropriate controls.

---

### **G2. Is SLANG-Observatory replacing existing systems?**

No.

A demo may act as:

- a bounded reference resolver
- a validation layer
- an admissibility layer
- an evidence layer
- a comparison surface
- a reproducibility demonstration

Existing domain infrastructure may still be required for authentication,
transport, execution, settlement, security, legal authority, monitoring, or
human judgment.

---

### **G3. Why are some demos very small?**

Small demonstrations help isolate one structural contract and make it easier to
inspect.

Small size is not itself evidence of correctness, novelty, security, or
generality.

The stronger demos may therefore include larger verification and evidence
surfaces even when the core relation remains compact.

---

### **G4. Are all demos equally mature?**

No.

The repository contains demonstrations with different levels of:

- implementation depth
- documentation
- verification
- adversarial testing
- reconstruction evidence
- domain specificity

Each demo should be evaluated independently.

---

## **SECTION H — Repository Relationships**

### **H1. Where does SLANG fit in the wider Shunyaya ecosystem?**

SLANG is one structural-resolution family within the broader Shunyaya
ecosystem.

Related families and systems explore different bounded questions, including:

- ORL — orderless reconciliation
- STIME — structural progress through accepted transitions
- STINT-Money — financial-state resolution without continuous connectivity
  as sole authority
- STRAL-Path — path validity without traversal as sole authority
- STILE — delivery admission separated from transport observation
- SVARE — exact mathematical resolution for supported expressions

These are related systems, not interchangeable labels.

---

### **H2. Are the Observatory demos separate frameworks?**

No.

They intentionally reuse a common bounded structural-resolution discipline
across different domain schemas.

`shared SLANG discipline + different bounded domain contract -> domain demonstration`

A domain adaptation does not automatically create a separate architectural or
novelty claim.

---

### **H3. What are the standalone SLANG repositories?**

Selected SLANG domains have dedicated repositories with broader documentation
and verification surfaces:

- SLANG-Computation
- SLANG-Audit
- SLANG-Money

Those repositories define their own current contracts, evidence, and limits.

---

## **SECTION I — Common Skeptic Questions**

### **I1. Is something still running?**

Yes.

Software executes. The narrower claim is that the admitted structure and
versioned rules determine the bounded resolution rather than an undeclared
historical workflow path.

---

### **I2. Do real systems still need workflows?**

Often, yes.

Workflows may remain necessary for:

- user interaction
- responsibility assignment
- review
- scheduling
- escalation
- audit
- transport
- settlement
- security
- legal or institutional processes

SLANG asks whether those workflows must also remain the sole authority over a
specific bounded result.

---

### **I3. Is the same result guaranteed on every machine?**

Only within the supported runtime, input, canonicalization, and implementation
contract.

Projects may publish replay or conformance evidence to demonstrate the intended
boundary. Environment-independent behavior must not be assumed beyond what is
tested and documented.

---

### **I4. Can a demo fail?**

Yes.

It can reject malformed or unsupported input, expose a conflict, remain
incomplete, abstain, or fail verification.

Clean refusal is part of the reference behavior.

---

### **I5. Does dependency elimination mean dependency removal?**

Not necessarily.

In this framework, dependency elimination means that a named operational
mechanism no longer governs the bounded admissible resolution as its sole
authority.

The mechanism may remain operational.

---

### **I6. Does the repository claim to be a formal standard?**

No.

SLANG-Observatory does not claim recognition as a formal technical standard,
security certification, production qualification, or third-party verification.

---

## **SECTION J — License and Use**

### **J1. Can the implementations be used and modified?**

The reference implementations and associated verification artifacts may be
used, copied, modified, tested, studied, and redistributed without a license
fee, subject to the repository LICENSE.

---

### **J2. What license applies to documentation and diagrams?**

Unless a file states otherwise, documentation, architecture materials,
specifications, diagrams, and explanatory content are subject to the separate
terms stated in the repository LICENSE, including the declared CC BY-NC 4.0
terms.

---

### **J3. Can a modified implementation be presented as verified?**

Not on the basis of the original verification results.

Modified files, rules, profiles, schemas, vectors, contexts, or evidence require
their own verification. Modified artifacts must not imply endorsement,
certification, or authorship by the original maintainers.

---

## ⭐ **Final Summary**

SLANG-Observatory demonstrates that bounded outcomes can be resolved
deterministically from admitted declared structure and versioned rules, while a
named workflow, sequence, or operational mechanism may remain available without
serving as the sole resolution authority.

Each claim is limited to the code, evidence, inputs, rules, limits, and
documented boundary of the relevant demo.
