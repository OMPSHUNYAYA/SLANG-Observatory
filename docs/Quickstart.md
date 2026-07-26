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
- any published identity, receipt, or evidence output
- the demo-specific README

No installation step is required for reference demos that use only the Python
standard library.

---

## **1. Minimum Requirements**

- Python 3.9 or later
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

The exact folders and artifacts present in the repository remain authoritative.

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

When the declared contract is not satisfied, the demo may return:

- `INCOMPLETE`
- `CONFLICT`
- `ABSTAIN`
- `DENY`
- `FORBIDDEN`
- `UNSUPPORTED`
- another declared non-result state

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
| Supported and complete | Evaluate the declared resolution rules |
| Missing required structure | Return `INCOMPLETE`, `ABSTAIN`, `DENY`, or another declared non-result |
| Accepted declarations conflict | Return `CONFLICT`, `ABSTAIN`, `DENY`, or another declared refusal |
| Input lies outside the supported boundary | Return `UNSUPPORTED` or another declared refusal |
| Authority is absent | Withhold or deny the action where the contract requires authority |
| Visibility or release is absent | Keep an otherwise assembled result hidden where declared |

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
127/127 PASS
```

### Run the vector verifier

```text
python -B demo/SLANG-Exam/slang_exam_vectors_v0_7_2.py
```

Expected published checks:

```text
56/56 semantic vectors reproduced
56/56 reference-evidence vectors reproduced
10/10 metamorphic relations reproduced
3/3 bounded-search probes reproduced
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

## **14. Evidence and Receipts**

Depending on the demonstration, published evidence may include:

- result identities
- ruleset identities
- input or canonical-structure identities
- bundles
- receipts
- vector files
- self-tests
- metamorphic checks
- tamper checks
- exact replay evidence

Verification establishes agreement with the declared reference contract.

It does not automatically establish:

- factual truth
- source authenticity
- legal authority
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
profiles, vectors, and evidence remain authoritative for each demo.

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
