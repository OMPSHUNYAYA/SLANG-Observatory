# ⭐ **SLANG-Observatory — Quickstart**

## **Structural Language (SLANG)**  
**Bounded Deterministic Resolution Across Domains**

SLANG-Observatory contains focused reference demonstrations that resolve
bounded states from declared structure and versioned rules.

The recurring relation is:

`declared structure + versioned rules -> bounded resolution state`

Where a demo declares canonical order independence:

`same admitted canonical structure + same versioned rules -> same bounded result`

Each demo defines its own inputs, state model, limits, evidence, and claim
boundary.

---

## ⚡ **30-Second Start**

From the repository root, run a selected Python demonstration with bytecode
generation disabled:

```text
python -B demo/<demo_folder>/<script_name>.py
```

Example:

```text
python -B demo/SLANG-Invoice/slang_invoice.py
```

Then inspect:

- the submitted declarations
- the resolved state
- any reason or refusal state
- any published identity, bundle, receipt, attestation, or evidence output
- the demo-specific README

No installation step is required for reference demos that use only the Python
standard library.

---

## **1. Minimum Requirements**

- Python 3.9-compatible syntax where declared; use a currently supported Python release for operational testing unless a demo states otherwise
- a terminal or command prompt
- the repository downloaded or cloned locally
- no network connection for demos documented as offline
- no third-party packages unless a particular demo states otherwise

Check the relevant demo folder before assuming that every demonstration has the
same runtime requirements.

---

## **2. Open the Repository**

### Windows Command Prompt

```text
cd /d D:\PATH\TO\SLANG-Observatory
```

### PowerShell

```text
Set-Location "D:\PATH\TO\SLANG-Observatory"
```

### Linux or macOS

```text
cd /path/to/SLANG-Observatory
```

Confirm that the repository root contains files such as:

```text
README.md
LICENSE
demo/
docs/
```

---

## **3. Choose a Demonstration**

Each folder under `demo/` represents a bounded domain adaptation.

Representative folders may include:

- `SLANG-Invoice`
- `SLANG-Claims`
- `SLANG-Cybersecurity`
- `SLANG-Password`
- `SLANG-ResetPassword`
- `SLANG-Exam`

The exact folders and artifacts present in the repository remain the governing
reference.

Before running a demonstration, read its local README when available.

---

## **4. Run a Basic Demo**

Example:

```text
python -B demo/SLANG-Invoice/slang_invoice.py
```

A basic reference demo commonly shows:

1. declared input structure
2. validation or admission
3. a bounded resolution state
4. an explicit reason or visible result

The exact output and state names are demo-specific.

---

## **5. What to Observe**

Look for the following questions rather than assuming one universal behavior:

- What input fields are supported?
- Which fields are required?
- Which collections are ordered or set-like?
- What makes the structure complete?
- What constitutes a conflict?
- Which authority or visibility conditions apply?
- What explicit non-result states are available?
- What resource limits are declared?
- What evidence is produced?
- Which properties are actually tested?

A typical bounded relation is:

`complete + consistent + admitted structure -> bounded resolution`

When the declared contract is not satisfied, the demo may return a declared
resolution or non-result state such as:

- `INCOMPLETE`
- `CONFLICT`
- `ABSTAIN`
- `FORBIDDEN`
- `UNSUPPORTED`
- another declared non-result state

Some demos separately define admission states such as `ADMIT`, `DENY`, or
`WITHHOLD`, visibility states, or authority states.

`resolution state != admission state != visibility state != operational authority`

where the relevant demo defines those dimensions separately.

---

## **6. Determinism Check**

Run the same demonstration twice with the same supported input and unchanged
versioned rules:

```text
python -B demo/SLANG-Invoice/slang_invoice.py
python -B demo/SLANG-Invoice/slang_invoice.py
```

At the declared semantic level, expect:

`same admitted canonical input + same versioned rules -> same bounded result`

Operational details may differ only when the implementation or contract permits
them to differ.

Examples of operational details include:

- timing
- diagnostics
- traversal counters
- search-node counts
- execution traces

Do not treat operational equality as guaranteed unless the demo binds it.

---

## **7. Order-Independence Check — Where Declared**

Order independence applies only when the demo explicitly treats a collection as
set-like or canonicalizes supported permutations.

For a supported permutation `pi`:

`C(S) = C(pi(S))`

therefore:

`F_R(C(S)) = F_R(C(pi(S)))`

This does not mean that every sequence is irrelevant.

Ordered structures may include:

- ranked lists
- event histories
- dependency chains
- literal submissions
- traces
- replay evidence

Accordingly:

`deterministic != universally order-independent`

---

## **8. Incomplete and Conflicting Inputs**

A reference demo should not force a positive result when its own contract is not
satisfied.

Typical behavior:

| Condition | Representative behavior |
|---|---|
| Supported and complete | Evaluate the declared bounded resolution rules |
| Missing required structure | Return the explicit non-result state defined by the demo, such as `INCOMPLETE` |
| Accepted declarations conflict | Expose `CONFLICT` or another explicitly declared non-result state |
| Input lies outside the supported boundary | Return `UNSUPPORTED` or another declared refusal state |
| Admission conditions are not satisfied | Preserve the declared admission state, such as `DENY` or `WITHHOLD`, where separately defined |
| Authority is absent | Do not infer operational authorization where the contract requires authority |
| Visibility or release is absent | Keep an otherwise resolved or assembled result hidden where declared |

State names and precedence differ across demos.

---

## **9. Unsupported Inputs**

Unsupported input should be refused before the bounded resolver is treated as
though it covers that input.

Conceptually:

`x -> admit_R(x) -> C(x) -> F_R(C(x))`

If the supported-input predicate fails:

`admit_R(x) = UNSUPPORTED`

The resolver is then not invoked over an input outside its declared domain.

---

## **10. SLANG-Exam v0.7.2**

SLANG-Exam provides a broader reference demonstration with:

- bounded examination-form assembly
- canonical ranking
- explicit abstention
- single-party commit-reveal ranking
- multi-party commit-reveal ranking
- scope-sensitive authority
- release and visibility separation
- exact-marks feasibility checks
- bounded search
- reconstruction bundles
- compact receipts
- frozen vectors
- metamorphic relations

### Run the reference self-test

```text
python -B demo/SLANG-Exam/slang_exam_v0_7_2.py --self-test
```

Expected published result:

```text
TOTAL                127/127 PASS
```

### Run the vector verifier

```text
python -B demo/SLANG-Exam/slang_exam_vectors_v0_7_2.py --verify demo/SLANG-Exam/SLANG_Exam_Vectors_v0_7_2.json
```

Expected published checks:

```text
semantic vectors: 56/56 reproduced
reference evidence: 56/56 reproduced
relations: 10/10 reproduced
search probes: 3/3 reproduced
VERIFY: PASS
```

These results apply only to the declared SLANG-Exam v0.7.2 contract and its
published artifacts.

---

## **11. SLANG-Exam Artifact Set**

The SLANG-Exam folder includes the following reference artifacts:

```text
slang_exam_v0_7_2.py
slang_exam_vectors_v0_7_2.py
SLANG_Exam_Vectors_v0_7_2.json
SLANG_Exam_Bundle_v0_7_2.json
SLANG_Exam_Receipt_v0_7_2.json
SLANG_Exam_MPCR_Example_Input_v0_7_2.json
SLANG_Exam_MPCR_Bundle_v0_7_2.json
SLANG_Exam_MPCR_Receipt_v0_7_2.json
SLANG_Exam_MPCR_Profile_v0_7_2.txt
SLANG-Exam-Reference-Diagram.png
README.md
```

Use the local SLANG-Exam README as the detailed operating guide.

---

## **11A. SLANG-Claims v0.2.1 Quick Verification**

SLANG-Claims provides a deterministic claim-payability admission reference from
declared claim context and bound claim-authority evidence.

The central relation is:

`same admitted canonical claim structure + same versioned contract -> same bounded claim result`

The operational boundary remains:

`PAYABLE != PAYMENT_AUTHORIZED`

### Run the core self-test

From the repository root:

```text
python -B demo/SLANG-Claims/slang_claims_v0_2_1.py --self-test
```

Expected published result:

```text
TOTAL 101/101 PASS
```

### Verify the frozen conformance vectors

```text
python -B demo/SLANG-Claims/slang_claims_vectors_v0_2_1.py --verify demo/SLANG-Claims/SLANG_Claims_Vectors_v0_2_1.json
```

Expected published summary:

```text
TOTAL: 154/154 PASS
VERIFY: PASS
```

The SLANG-Claims folder additionally publishes reconstruction bundles, compact
receipts, portable non-result attestations, machine-readable contracts and
schemas, and an optional outer authenticity envelope.

The authenticity layer may optionally use the `cryptography` package for
Ed25519. The core resolver uses only the Python standard library.

Use the local SLANG-Claims README for bundle, receipt, attestation,
correspondence, authenticity, and machine-readable verification-report commands.

These results apply only to the declared SLANG-Claims v0.2.1 contract and its
published artifacts.

---

## **12. Semantic Conformance and Exact Replay**

Some demos distinguish two evidence levels.

### Semantic conformance

Confirms that the declared semantic result is reproduced:

`semantic_verify(F_R(C(x))) = PASS`

### Exact reference replay

Confirms the complete reference artifact, including operational evidence where
the contract binds it:

`exact_verify(reference_bundle) = PASS`

Two conforming implementations may agree semantically while producing different
operational evidence unless the contract fixes both.

---

## **13. Bounded Search**

A demo that performs search may declare a maximum search limit `L`.

The implementation should preserve:

`evaluated_nodes <= L`

When the required conclusion is established within the limit, the resolver may
return the corresponding result.

When the limit is reached without establishing the conclusion, the result may
be:

- `ABSTAIN`
- `UNSUPPORTED`
- another declared bounded non-result state

Search exhaustion means:

`conclusion not established within the declared bound`

It does not prove that no solution exists outside the bound.

---

## **14. Evidence and Verification Scope**

Depending on the demonstration, published evidence may include:

- result identities
- ruleset or contract identities
- input or canonical-structure identities
- reconstruction bundles
- compact receipts
- portable non-result attestations
- frozen conformance vectors
- machine-readable contracts and schemas
- machine-readable verification reports
- self-tests
- metamorphic checks
- correspondence checks
- optional authenticity envelopes
- tamper checks
- exact replay evidence

Different verification operations may establish different properties.

`structural integrity != correspondence`

`correspondence != authenticity`

`authenticity != trust policy`

`authenticity != real-world truth`

`real-world truth != authorization to act`

`trust policy != authorization to act`

A passing verification establishes only the scope actually checked by the
relevant verifier.

It does not automatically establish:

- factual truth
- authenticity of underlying source declarations
- institutional trust in supplied key material
- legal authority
- operational authorization
- production safety
- fairness
- institutional approval
- independent certification

---

## **15. Representative Repository Paths**

The repository may be navigated through paths such as:

```text
SLANG-Observatory/
├── README.md
├── LICENSE
├── demo/
│   ├── SLANG-Invoice/
│   ├── SLANG-Claims/
│   ├── SLANG-Cybersecurity/
│   ├── SLANG-Password/
│   ├── SLANG-ResetPassword/
│   ├── SLANG-Exam/
│   └── ...
└── docs/
    ├── Quickstart.md
    ├── FAQ.md
    ├── Proof-Sketch.md
    ├── Dependency-Elimination-Framework.png
    ├── Shunyaya-Structural-Stack.png
    └── archive/
```

This is a representative navigation view, not a claim that every checkout has
exactly the same folders.

---

## **16. Visual Context**

The following diagrams provide repository-level context:

```text
docs/Dependency-Elimination-Framework.png
docs/Shunyaya-Structural-Stack.png
```

The diagrams are explanatory summaries. The code, local documentation, rules,
profiles, vectors, and evidence remain the governing reference for each demo.

---

## **17. Common Commands**

### Run a demonstration

```text
python -B demo/<demo_folder>/<script_name>.py
```

### Display command help where supported

```text
python -B demo/<demo_folder>/<script_name>.py --help
```

### Run a self-test where supported

```text
python -B demo/<demo_folder>/<script_name>.py --self-test
```

### Run an audit where supported

```text
python -B demo/<demo_folder>/<script_name>.py --audit
```

Not every demonstration supports every command-line option.

---

## **18. Common Issues**

### Python is not recognized

Install a supported Python version and ensure that it is available on `PATH`.

On some Windows systems, use:

```text
py -3 -B demo/<demo_folder>/<script_name>.py
```

### The script path is not found

Confirm that the terminal is at the repository root:

```text
dir
```

or:

```text
ls
```

Then inspect the actual folder and file names under `demo/`.

### An option is rejected

The selected demo may not implement that command-line option. Read its local
README or run `--help` where supported.

### The output differs after editing a file

A code, rule, profile, vector, input, or evidence change may create a different
contract or artifact identity. Earlier verification results do not automatically
apply to modified files.

---

## **19. What SLANG-Observatory Demonstrates**

SLANG-Observatory demonstrates that a class of bounded reference models can
resolve explicit states deterministically from admitted declared structure and
versioned rules.

A named workflow, sequence, arrival order, or operational mechanism may remain
available without serving as the sole authority over the bounded result.

---

## **20. What SLANG-Observatory Does Not Claim**

The repository does not claim:

- elimination of software execution
- elimination of every workflow
- universal order independence
- universal time independence
- universal applicability
- production qualification
- security certification
- legal validity
- performance superiority
- third-party verification
- factual correctness of submitted declarations

Each claim remains limited to the relevant implementation, supported inputs,
versioned rules, profiles, limits, evidence, and documented boundary.

---

## **21. Recommended Reading Order**

For a first review:

1. `README.md`
2. `docs/Quickstart.md`
3. one selected demo README
4. the selected Python script
5. its vectors, bundles, receipts, or tests
6. `docs/FAQ.md`
7. `docs/Proof-Sketch.md`
8. the repository diagrams

This order moves from repository context to implementation-specific evidence.

---

## ⭐ **One-Line Summary**

`same admitted canonical structure + same versioned rules -> same bounded semantic result`

Operations may remain; they need not be the sole authority over that bounded
resolution.
