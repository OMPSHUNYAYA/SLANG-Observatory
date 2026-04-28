rules = [
    ("po_match", "true", lambda s: s.get("invoice_po") == s.get("po_number") and s.get("receipt_po") == s.get("po_number")),
    ("amount_match", "true", lambda s: s.get("po_match") == "true" and s.get("po_amount") == s.get("invoice_amount")),
    ("qty_match", "true", lambda s: s.get("po_match") == "true" and s.get("po_qty") == s.get("receipt_qty")),
    ("payable", "approved", lambda s: s.get("amount_match") == "true" and s.get("qty_match") == "true"),
]

state = {
    "po_number": "PO-2025-7841",
    "po_amount": "12500",
    "po_qty": "250",
    "invoice_po": "PO-2025-7841",
    "invoice_amount": "12500",
    "receipt_po": "PO-2025-7841",
    "receipt_qty": "250"
}

changed = True
while changed:
    changed = False
    for key, value, cond in rules:
        if cond(state) and state.get(key) != value:
            state[key] = value
            changed = True

print(state)
