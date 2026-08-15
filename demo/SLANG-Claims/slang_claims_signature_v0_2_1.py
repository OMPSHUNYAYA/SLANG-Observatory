from __future__ import annotations
import argparse
import binascii
import hashlib
import hmac
import json
import re
import sys
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Sequence, Tuple
import slang_claims_v0_2_1 as core
VERSION = '0.2.1'
AUTHENTICITY_CONTRACT_SCHEMA = 'SLANG-CLAIMS-AUTHENTICITY-CONTRACT-1'
VERIFICATION_REPORT_SCHEMA = 'SLANG-CLAIMS-VERIFICATION-REPORT-1'
AUTHENTICITY_CONTRACT_ID_PREFIX = 'slang_claims_authenticity_contract_sha256:'
ENVELOPE_SCHEMA = 'SLANG-CLAIMS-SIGNED-ENVELOPE-1'
SIGNING_STATEMENT_SCHEMA = 'SLANG-CLAIMS-SIGNING-STATEMENT-1'
SIGNATURE_DOMAIN = 'SLANG-CLAIMS-SIGNATURE-1'
SIGNATURE_DOMAIN_TAG = b'SLANG-CLAIMS-SIGNATURE-1\x00'
SIGNING_STATEMENT_ID_PREFIX = 'slang_claims_signing_statement_sha256:'
ENVELOPE_ID_PREFIX = 'slang_claims_signed_envelope_sha256:'
PAYLOAD_HASH_PREFIX = 'sha256:'
PURPOSE_ATTEST = 'ATTEST_STRUCTURE'
SUPPORTED_PURPOSES = {PURPOSE_ATTEST}
ALG_HMAC = 'HMAC-SHA256'
ALG_ED25519 = 'ED25519'
SUPPORTED_ALGS = {ALG_HMAC, ALG_ED25519}
PAYLOAD_KIND_BUNDLE = 'BUNDLE'
PAYLOAD_KIND_RECEIPT = 'RECEIPT'
PAYLOAD_KIND_ATTESTATION = 'ATTESTATION'
SUPPORTED_PAYLOAD_KINDS = {PAYLOAD_KIND_BUNDLE, PAYLOAD_KIND_RECEIPT, PAYLOAD_KIND_ATTESTATION}
MAX_SIGNATURES = 16
SIGNATURE_HEX_PATTERN_LEN_HMAC = 64
SIGNATURE_HEX_LEN_ED25519 = 128
SIGNING_KEY_ID_PREFIX = 'slang_claims_signing_key_sha256:'
KEYSET_SCHEMA = 'SLANG-CLAIMS-KEYSET-1'
KEYSET_ID_PREFIX = 'slang_claims_keyset_sha256:'
KEYSET_KIND_PUBLIC = 'PUBLIC'
KEYSET_KIND_PRIVATE = 'PRIVATE'
SUPPORTED_KEYSET_KINDS = {KEYSET_KIND_PUBLIC, KEYSET_KIND_PRIVATE}
ED25519_SEED_HEX_LEN = 64
ED25519_PUB_HEX_LEN = 64
MIN_HMAC_SECRET_BYTES = 32
MAX_KEYSET_ENTRIES = 64
RFC3339_UTC_PATTERN = re.compile('^[0-9]{4}-[0-9]{2}-[0-9]{2}T[0-9]{2}:[0-9]{2}:[0-9]{2}Z$')

def authenticity_contract_material() -> Dict[str, Any]:
    return {
        'schema': AUTHENTICITY_CONTRACT_SCHEMA,
        'version': VERSION,
        'core_contract_id': core.contract_id(),
        'envelope_schema': ENVELOPE_SCHEMA,
        'signing_statement_schema': SIGNING_STATEMENT_SCHEMA,
        'verification_report_schema': VERIFICATION_REPORT_SCHEMA,
        'signature_domain': SIGNATURE_DOMAIN,
        'supported_algorithms': sorted(SUPPORTED_ALGS),
        'supported_payload_kinds': sorted(SUPPORTED_PAYLOAD_KINDS),
        'hmac_min_secret_bytes': MIN_HMAC_SECRET_BYTES,
        'hmac_secret_requirement': 'CRYPTOGRAPHICALLY_RANDOM_SECRET_MATERIAL_RECOMMENDED',
        'ed25519_private_seed_bytes': ED25519_SEED_HEX_LEN // 2,
        'ed25519_public_key_bytes': ED25519_PUB_HEX_LEN // 2,
        'max_signatures': MAX_SIGNATURES,
        'max_keyset_entries': MAX_KEYSET_ENTRIES,
        'created_at_format': 'RFC3339_UTC_SECONDS',
        'freshness_evaluation': 'OUT_OF_SCOPE',
        'replay_protection': 'EXTERNAL',
        'trust_roots_rotation_revocation': 'EXTERNAL',
        'payment_authority': 'NONE',
        'settlement_authority': 'NONE',
        'legal_authority': 'NONE',
        'policy_interpretation_authority': 'NONE',
        'fraud_determination_authority': 'NONE',
        'money_movement': 'NONE',
    }

def authenticity_contract() -> Dict[str, Any]:
    material = authenticity_contract_material()
    output = core.clone(material)
    output['authenticity_contract_id'] = core.identity(AUTHENTICITY_CONTRACT_ID_PREFIX, material)
    return output

def authenticity_contract_id() -> str:
    return authenticity_contract()['authenticity_contract_id']

class EnvelopeError(ValueError):
    pass
try:
    from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey, Ed25519PublicKey
    from cryptography.hazmat.primitives.serialization import Encoding, NoEncryption, PrivateFormat, PublicFormat
    from cryptography.exceptions import InvalidSignature as _CryptoInvalidSignature
    _HAVE_ED25519 = True
except Exception:
    _HAVE_ED25519 = False

def _as_key_bytes(key: Any) -> bytes:
    if isinstance(key, bytes):
        return key
    if isinstance(key, str):
        return key.encode('utf-8')
    raise EnvelopeError('KEY_MATERIAL_MUST_BE_BYTES_OR_STR')

def _hex_to_bytes(value: str, expected_hex_len: Optional[int]=None) -> bytes:
    if not isinstance(value, str):
        raise EnvelopeError('HEX_STRING_REQUIRED')
    if expected_hex_len is not None and len(value) != expected_hex_len:
        raise EnvelopeError('HEX_LENGTH_MISMATCH')
    try:
        return bytes.fromhex(value)
    except ValueError:
        raise EnvelopeError('INVALID_HEX')

def _is_fingerprint_key_id(value: str) -> bool:
    if not value.startswith(SIGNING_KEY_ID_PREFIX):
        return False
    hexpart = value[len(SIGNING_KEY_ID_PREFIX):]
    return len(hexpart) == 64 and all((c in '0123456789abcdef' for c in hexpart))

def normalize_key_id(value: Any) -> Optional[str]:
    if isinstance(value, str) and _is_fingerprint_key_id(value.strip()):
        return value.strip()
    return core.normalize_identifier(value)

def _require_ed25519() -> None:
    if not _HAVE_ED25519:
        raise EnvelopeError('ED25519_BACKEND_UNAVAILABLE')

def generate_ed25519_keypair() -> Tuple[str, str]:
    _require_ed25519()
    private = Ed25519PrivateKey.generate()
    seed = private.private_bytes(Encoding.Raw, PrivateFormat.Raw, NoEncryption())
    public = private.public_key().public_bytes(Encoding.Raw, PublicFormat.Raw)
    return (seed.hex(), public.hex())

def load_ed25519_private(private_seed_hex: str) -> 'Ed25519PrivateKey':
    _require_ed25519()
    seed = _hex_to_bytes(private_seed_hex, ED25519_SEED_HEX_LEN)
    return Ed25519PrivateKey.from_private_bytes(seed)

def load_ed25519_public(public_key_hex: str) -> 'Ed25519PublicKey':
    _require_ed25519()
    pub = _hex_to_bytes(public_key_hex, ED25519_PUB_HEX_LEN)
    return Ed25519PublicKey.from_public_bytes(pub)

def ed25519_public_hex_from_private(private_seed_hex: str) -> str:
    private = load_ed25519_private(private_seed_hex)
    return private.public_key().public_bytes(Encoding.Raw, PublicFormat.Raw).hex()

def ed25519_key_id(public_key_hex: str) -> str:
    normalized = public_key_hex.strip().lower()
    _hex_to_bytes(normalized, ED25519_PUB_HEX_LEN)
    return core.identity(SIGNING_KEY_ID_PREFIX, {'alg': ALG_ED25519, 'public_key': normalized})
_KEYSET_TOP_KEYS = {'schema', 'version', 'keyset_kind', 'keys', 'keyset_id'}
_ENTRY_COMMON_KEYS = {'signer_id', 'alg', 'key_id'}
_ENTRY_ED25519_KEYS = _ENTRY_COMMON_KEYS | {'public_key', 'private_key'}
_ENTRY_HMAC_KEYS = _ENTRY_COMMON_KEYS | {'secret'}

def _keyset_entry_sort_key(entry: Dict[str, Any]) -> Tuple[str, str, str]:
    return (str(entry.get('signer_id', '')), str(entry.get('alg', '')), str(entry.get('key_id', '')))

def _canonical_keyset_entries(entries: Sequence[Dict[str, Any]]) -> List[Dict[str, Any]]:
    return sorted([core.clone(e) for e in entries], key=_keyset_entry_sort_key)

def _keyset_material(schema_kind: str, entries: List[Dict[str, Any]]) -> Dict[str, Any]:
    return {'schema': KEYSET_SCHEMA, 'version': VERSION, 'keyset_kind': schema_kind, 'keys': entries}

def build_keyset(entries: List[Dict[str, Any]], keyset_kind: str) -> Dict[str, Any]:
    if keyset_kind not in SUPPORTED_KEYSET_KINDS:
        raise EnvelopeError('UNSUPPORTED_KEYSET_KIND:' + str(keyset_kind))
    if len(entries) > MAX_KEYSET_ENTRIES:
        raise EnvelopeError('TOO_MANY_KEYSET_ENTRIES')
    material = _keyset_material(keyset_kind, _canonical_keyset_entries(entries))
    keyset = core.clone(material)
    keyset['keyset_id'] = core.identity(KEYSET_ID_PREFIX, material)
    ok, detail = verify_keyset(keyset)
    if not ok:
        raise EnvelopeError('KEYSET_SELF_CHECK_FAILED:' + detail)
    return keyset

def make_ed25519_entry(signer_id: str, private_seed_hex: Optional[str]=None, public_key_hex: Optional[str]=None, include_private: bool=False) -> Dict[str, Any]:
    normalized_signer = core.normalize_identifier(signer_id)
    if normalized_signer is None:
        raise EnvelopeError('INVALID_SIGNER_ID')
    if public_key_hex is None:
        if private_seed_hex is None:
            raise EnvelopeError('ED25519_ENTRY_REQUIRES_KEY_MATERIAL')
        public_key_hex = ed25519_public_hex_from_private(private_seed_hex)
    public_key_hex = public_key_hex.strip().lower()
    entry: Dict[str, Any] = {'signer_id': normalized_signer, 'alg': ALG_ED25519, 'key_id': ed25519_key_id(public_key_hex), 'public_key': public_key_hex}
    if include_private:
        if private_seed_hex is None:
            raise EnvelopeError('ED25519_PRIVATE_ENTRY_REQUIRES_SEED')
        entry['private_key'] = private_seed_hex.strip().lower()
    return entry

def make_hmac_entry(signer_id: str, key_id: str, secret: Any) -> Dict[str, Any]:
    normalized_signer = core.normalize_identifier(signer_id)
    normalized_key_id = core.normalize_identifier(key_id)
    if normalized_signer is None:
        raise EnvelopeError('INVALID_SIGNER_ID')
    if normalized_key_id is None:
        raise EnvelopeError('INVALID_KEY_ID')
    secret_bytes = _as_key_bytes(secret)
    if len(secret_bytes) < MIN_HMAC_SECRET_BYTES:
        raise EnvelopeError('HMAC_SECRET_TOO_SHORT')
    return {'signer_id': normalized_signer, 'alg': ALG_HMAC, 'key_id': normalized_key_id, 'secret': secret_bytes.hex()}

def verify_keyset(keyset: Any) -> Tuple[bool, str]:
    if not isinstance(keyset, dict):
        return (False, 'KEYSET_OBJECT_REQUIRED')
    if set(keyset.keys()) != _KEYSET_TOP_KEYS:
        return (False, 'KEYSET_KEYS_MISMATCH')
    if keyset.get('schema') != KEYSET_SCHEMA or keyset.get('version') != VERSION:
        return (False, 'KEYSET_VERSION_MISMATCH')
    kind = keyset.get('keyset_kind')
    if kind not in SUPPORTED_KEYSET_KINDS:
        return (False, 'KEYSET_KIND_UNSUPPORTED')
    entries = keyset.get('keys')
    if not isinstance(entries, list) or not entries:
        return (False, 'KEYSET_ENTRIES_REQUIRED')
    if len(entries) > MAX_KEYSET_ENTRIES:
        return (False, 'KEYSET_TOO_MANY_ENTRIES')
    if entries != _canonical_keyset_entries(entries):
        return (False, 'KEYSET_ENTRY_ORDER_NONCANONICAL')
    seen: set = set()
    for entry in entries:
        if not isinstance(entry, dict):
            return (False, 'KEYSET_ENTRY_OBJECT_REQUIRED')
        signer = entry.get('signer_id')
        if core.normalize_identifier(signer) != signer:
            return (False, 'KEYSET_ENTRY_SIGNER_ID_INVALID')
        if signer in seen:
            return (False, 'KEYSET_DUPLICATE_SIGNER:' + str(signer))
        seen.add(signer)
        alg = entry.get('alg')
        if alg == ALG_ED25519:
            if set(entry.keys()) - _ENTRY_ED25519_KEYS:
                return (False, 'KEYSET_ENTRY_UNKNOWN_FIELD')
            pub = entry.get('public_key')
            try:
                _hex_to_bytes(pub, ED25519_PUB_HEX_LEN)
            except EnvelopeError:
                return (False, 'KEYSET_ENTRY_PUBLIC_KEY_INVALID')
            if entry.get('key_id') != ed25519_key_id(pub):
                return (False, 'KEYSET_ENTRY_KEY_ID_FINGERPRINT_MISMATCH')
            if 'private_key' in entry:
                if kind != KEYSET_KIND_PRIVATE:
                    return (False, 'PUBLIC_KEYSET_CONTAINS_PRIVATE_KEY')
                try:
                    derived = ed25519_public_hex_from_private(entry['private_key'])
                except EnvelopeError:
                    return (False, 'KEYSET_ENTRY_PRIVATE_KEY_INVALID')
                if derived != pub:
                    return (False, 'KEYSET_ENTRY_PRIVATE_PUBLIC_DISAGREE')
        elif alg == ALG_HMAC:
            if set(entry.keys()) - _ENTRY_HMAC_KEYS:
                return (False, 'KEYSET_ENTRY_UNKNOWN_FIELD')
            if core.normalize_identifier(entry.get('key_id')) != entry.get('key_id'):
                return (False, 'KEYSET_ENTRY_KEY_ID_INVALID')
            if kind == KEYSET_KIND_PUBLIC:
                return (False, 'PUBLIC_KEYSET_CONTAINS_SYMMETRIC_SECRET')
            try:
                secret = _hex_to_bytes(entry.get('secret'))
            except EnvelopeError:
                return (False, 'KEYSET_ENTRY_SECRET_INVALID')
            if len(secret) < MIN_HMAC_SECRET_BYTES:
                return (False, 'KEYSET_ENTRY_SECRET_TOO_SHORT')
        else:
            return (False, 'KEYSET_ENTRY_ALG_UNSUPPORTED')
    expected_id = core.identity(KEYSET_ID_PREFIX, _keyset_material(kind, [{k: v for k, v in e.items()} for e in entries]))
    if keyset.get('keyset_id') != expected_id:
        return (False, 'KEYSET_ID_MISMATCH')
    return (True, 'PASS')

def keyset_public_view(private_keyset: Dict[str, Any], drop_symmetric: bool=False) -> Dict[str, Any]:
    ok, detail = verify_keyset(private_keyset)
    if not ok:
        raise EnvelopeError('SOURCE_KEYSET_INVALID:' + detail)
    public_entries: List[Dict[str, Any]] = []
    for entry in private_keyset['keys']:
        if entry['alg'] == ALG_ED25519:
            public_entries.append({'signer_id': entry['signer_id'], 'alg': ALG_ED25519, 'key_id': entry['key_id'], 'public_key': entry['public_key']})
        elif entry['alg'] == ALG_HMAC:
            if not drop_symmetric:
                raise EnvelopeError('CANNOT_PUBLISH_SYMMETRIC_ENTRY:' + entry['signer_id'])
        else:
            raise EnvelopeError('UNSUPPORTED_ALG_IN_KEYSET')
    if not public_entries:
        raise EnvelopeError('NO_PUBLISHABLE_ENTRIES')
    return build_keyset(public_entries, KEYSET_KIND_PUBLIC)

def resolver_from_keyset(keyset: Dict[str, Any]) -> 'KeyResolver':
    ok, detail = verify_keyset(keyset)
    if not ok:
        raise EnvelopeError('KEYSET_INVALID:' + detail)
    by_signer = {e['signer_id']: e for e in keyset['keys']}

    def resolve(signer_id: str, key_id: str, alg: str) -> Any:
        entry = by_signer.get(signer_id)
        if entry is None:
            raise EnvelopeError('NO_KEY_FOR_SIGNER:' + str(signer_id))
        if entry['alg'] != alg:
            raise EnvelopeError('KEYSET_ALG_MISMATCH:' + str(signer_id))
        if alg == ALG_ED25519:
            if key_id != entry['key_id']:
                raise EnvelopeError('KEYSET_KEY_ID_MISMATCH:' + str(signer_id))
            return load_ed25519_public(entry['public_key'])
        if alg == ALG_HMAC:
            if key_id != entry['key_id']:
                raise EnvelopeError('KEYSET_KEY_ID_MISMATCH:' + str(signer_id))
            return _hex_to_bytes(entry['secret'])
        raise EnvelopeError('KEYSET_ALG_UNSUPPORTED:' + str(alg))
    return resolve

def _signing_material_from_keyset(private_keyset: Dict[str, Any], signer_id: str) -> Tuple[str, Any, str]:
    ok, detail = verify_keyset(private_keyset)
    if not ok:
        raise EnvelopeError('KEYSET_INVALID:' + detail)
    normalized = core.normalize_identifier(signer_id)
    entry = next((e for e in private_keyset['keys'] if e['signer_id'] == normalized), None)
    if entry is None:
        raise EnvelopeError('NO_SIGNING_KEY_FOR_SIGNER:' + str(signer_id))
    if entry['alg'] == ALG_ED25519:
        if 'private_key' not in entry:
            raise EnvelopeError('KEYSET_ENTRY_HAS_NO_PRIVATE_KEY:' + str(signer_id))
        return (ALG_ED25519, load_ed25519_private(entry['private_key']), entry['key_id'])
    if entry['alg'] == ALG_HMAC:
        return (ALG_HMAC, _hex_to_bytes(entry['secret']), entry['key_id'])
    raise EnvelopeError('KEYSET_ENTRY_ALG_UNSUPPORTED')

def sign_with_keyset(payload: Dict[str, Any], payload_kind: str, private_keyset: Dict[str, Any], signer_id: str, created_at: Optional[str]=None, bundle_for_receipt: Optional[Dict[str, Any]]=None, input_for_attestation: Any=None) -> Dict[str, Any]:
    alg, key, key_id = _signing_material_from_keyset(private_keyset, signer_id)
    return sign_envelope(payload, payload_kind, alg, key, signer_id, key_id, created_at=created_at, bundle_for_receipt=bundle_for_receipt, input_for_attestation=input_for_attestation)

def add_signature_with_keyset(envelope: Dict[str, Any], private_keyset: Dict[str, Any], signer_id: str, created_at: Optional[str]=None, bundle_for_receipt: Optional[Dict[str, Any]]=None, input_for_attestation: Any=None) -> Dict[str, Any]:
    alg, key, key_id = _signing_material_from_keyset(private_keyset, signer_id)
    return add_signature(envelope, alg, key, signer_id, key_id, created_at=created_at, bundle_for_receipt=bundle_for_receipt, input_for_attestation=input_for_attestation)

def payload_declared_id(payload_kind: str, payload: Dict[str, Any]) -> str:
    if payload_kind == PAYLOAD_KIND_BUNDLE:
        return payload['bundle_id']
    if payload_kind == PAYLOAD_KIND_RECEIPT:
        return payload['receipt_id']
    if payload_kind == PAYLOAD_KIND_ATTESTATION:
        return payload['attestation_id']
    raise EnvelopeError('UNSUPPORTED_PAYLOAD_KIND:' + str(payload_kind))

def _require_valid_payload(payload_kind: str, payload: Any) -> None:
    if not isinstance(payload, dict):
        raise EnvelopeError('PAYLOAD_OBJECT_REQUIRED')
    if payload_kind == PAYLOAD_KIND_BUNDLE:
        ok, detail = core.verify_bundle(payload)
        if not ok:
            raise EnvelopeError('PAYLOAD_BUNDLE_INVALID:' + detail)
        return
    if payload_kind == PAYLOAD_KIND_RECEIPT:
        ok, detail = core.check_receipt_integrity(payload)
        if not ok:
            raise EnvelopeError('PAYLOAD_RECEIPT_INVALID:' + detail)
        return
    if payload_kind == PAYLOAD_KIND_ATTESTATION:
        ok, detail = core.check_attestation_integrity(payload)
        if not ok:
            raise EnvelopeError('PAYLOAD_ATTESTATION_INVALID:' + detail)
        return
    raise EnvelopeError('UNSUPPORTED_PAYLOAD_KIND:' + str(payload_kind))

def _require_payload_correspondence(payload_kind: str, payload: Dict[str, Any], bundle_for_receipt: Optional[Dict[str, Any]]=None, input_for_attestation: Any=None) -> None:
    if payload_kind == PAYLOAD_KIND_BUNDLE:
        return
    if payload_kind == PAYLOAD_KIND_RECEIPT:
        if bundle_for_receipt is None:
            raise EnvelopeError('RECEIPT_REQUIRES_BUNDLE_FOR_CORRESPONDENCE')
        ok, detail = core.verify_receipt_against_bundle(payload, bundle_for_receipt)
        if not ok:
            raise EnvelopeError('RECEIPT_BUNDLE_CORRESPONDENCE_FAILED:' + detail)
        return
    if payload_kind == PAYLOAD_KIND_ATTESTATION:
        if input_for_attestation is None:
            raise EnvelopeError('ATTESTATION_REQUIRES_INPUT_FOR_CORRESPONDENCE')
        ok, detail = core.verify_attestation_against_input(payload, input_for_attestation)
        if not ok:
            raise EnvelopeError('ATTESTATION_INPUT_CORRESPONDENCE_FAILED:' + detail)
        return
    raise EnvelopeError('UNSUPPORTED_PAYLOAD_KIND:' + str(payload_kind))

def signing_statement(payload_kind: str, payload: Dict[str, Any], signer_id: str, key_id: str, created_at: Optional[str]=None) -> Dict[str, Any]:
    normalized_signer = core.normalize_identifier(signer_id)
    normalized_key_id = normalize_key_id(key_id)
    if normalized_signer is None:
        raise EnvelopeError('INVALID_SIGNER_ID')
    if normalized_key_id is None:
        raise EnvelopeError('INVALID_KEY_ID')
    statement: Dict[str, Any] = {'schema': SIGNING_STATEMENT_SCHEMA, 'signing_domain': SIGNATURE_DOMAIN, 'version': VERSION, 'core_version': core.CORE_VERSION, 'identity_domain_id': core.identity_domain_id(), 'contract_id': core.contract_id(), 'payload_kind': payload_kind, 'payload_schema': payload.get('schema'), 'payload_id': payload_declared_id(payload_kind, payload), 'payload_hash': PAYLOAD_HASH_PREFIX + core.sha256_hex(payload), 'purpose': PURPOSE_ATTEST, 'signer_id': normalized_signer, 'key_id': normalized_key_id}
    if created_at is not None:
        if not isinstance(created_at, str) or not RFC3339_UTC_PATTERN.fullmatch(created_at):
            raise EnvelopeError('INVALID_CREATED_AT')
        statement['created_at'] = created_at
    return statement

def _statement_message(statement: Dict[str, Any]) -> bytes:
    return SIGNATURE_DOMAIN_TAG + core.canonical_json(statement).encode('utf-8')

def _sign_message(alg: str, key: Any, message: bytes) -> str:
    if alg == ALG_HMAC:
        key_bytes = _as_key_bytes(key)
        if len(key_bytes) < MIN_HMAC_SECRET_BYTES:
            raise EnvelopeError('HMAC_SECRET_TOO_SHORT')
        return hmac.new(key_bytes, message, hashlib.sha256).hexdigest()
    if alg == ALG_ED25519:
        if not _HAVE_ED25519:
            raise EnvelopeError('ED25519_BACKEND_UNAVAILABLE')
        private = key
        if not isinstance(private, Ed25519PrivateKey):
            raise EnvelopeError('ED25519_PRIVATE_KEY_REQUIRED')
        return private.sign(message).hex()
    raise EnvelopeError('UNSUPPORTED_SIGNATURE_ALG:' + str(alg))

def _verify_message(alg: str, key: Any, message: bytes, signature_hex: str) -> bool:
    if alg == ALG_HMAC:
        key_bytes = _as_key_bytes(key)
        if len(key_bytes) < MIN_HMAC_SECRET_BYTES:
            raise EnvelopeError('HMAC_SECRET_TOO_SHORT')
        if not isinstance(signature_hex, str) or len(signature_hex) != SIGNATURE_HEX_PATTERN_LEN_HMAC:
            return False
        if any((ch not in '0123456789abcdef' for ch in signature_hex)):
            return False
        expected = hmac.new(key_bytes, message, hashlib.sha256).hexdigest()
        return hmac.compare_digest(expected, signature_hex)
    if alg == ALG_ED25519:
        if not _HAVE_ED25519:
            raise EnvelopeError('ED25519_BACKEND_UNAVAILABLE')
        if not isinstance(signature_hex, str) or len(signature_hex) != SIGNATURE_HEX_LEN_ED25519:
            return False
        if any((ch not in '0123456789abcdef' for ch in signature_hex)):
            return False
        public = key
        if not isinstance(public, Ed25519PublicKey):
            raise EnvelopeError('ED25519_PUBLIC_KEY_REQUIRED')
        try:
            public.verify(binascii.unhexlify(signature_hex), message)
            return True
        except (_CryptoInvalidSignature, binascii.Error, ValueError):
            return False
    raise EnvelopeError('UNSUPPORTED_SIGNATURE_ALG:' + str(alg))

def _build_signature_block(payload_kind: str, payload: Dict[str, Any], alg: str, key: Any, signer_id: str, key_id: str, created_at: Optional[str]) -> Dict[str, Any]:
    if alg not in SUPPORTED_ALGS:
        raise EnvelopeError('UNSUPPORTED_SIGNATURE_ALG:' + str(alg))
    statement = signing_statement(payload_kind, payload, signer_id, key_id, created_at)
    message = _statement_message(statement)
    signature_hex = _sign_message(alg, key, message)
    block: Dict[str, Any] = {'alg': alg, 'signer_id': statement['signer_id'], 'key_id': statement['key_id'], 'purpose': PURPOSE_ATTEST, 'tbs_id': core.identity(SIGNING_STATEMENT_ID_PREFIX, statement), 'signature': signature_hex}
    if created_at is not None:
        block['created_at'] = created_at
    return block

def _signature_sort_key(block: Dict[str, Any]) -> Tuple[str, str, str, str, str]:
    return (str(block.get('signer_id', '')), str(block.get('alg', '')), str(block.get('key_id', '')), str(block.get('tbs_id', '')), str(block.get('signature', '')))

def _canonical_signature_blocks(blocks: Sequence[Dict[str, Any]]) -> List[Dict[str, Any]]:
    return sorted([core.clone(block) for block in blocks], key=_signature_sort_key)

def _finalize_envelope(envelope: Dict[str, Any]) -> Dict[str, Any]:
    envelope.pop('envelope_id', None)
    envelope['envelope_id'] = core.identity(ENVELOPE_ID_PREFIX, envelope)
    return envelope

def sign_envelope(payload: Dict[str, Any], payload_kind: str, alg: str, key: Any, signer_id: str, key_id: str, created_at: Optional[str]=None, bundle_for_receipt: Optional[Dict[str, Any]]=None, input_for_attestation: Any=None) -> Dict[str, Any]:
    _require_valid_payload(payload_kind, payload)
    _require_payload_correspondence(payload_kind, payload, bundle_for_receipt=bundle_for_receipt, input_for_attestation=input_for_attestation)
    block = _build_signature_block(payload_kind, payload, alg, key, signer_id, key_id, created_at)
    envelope: Dict[str, Any] = {'schema': ENVELOPE_SCHEMA, 'version': VERSION, 'core_version': core.CORE_VERSION, 'identity_domain_id': core.identity_domain_id(), 'contract_id': core.contract_id(), 'payload_kind': payload_kind, 'payload_id': payload_declared_id(payload_kind, payload), 'payload': core.clone(payload), 'signatures': _canonical_signature_blocks([block])}
    return _finalize_envelope(envelope)

def add_signature(envelope: Dict[str, Any], alg: str, key: Any, signer_id: str, key_id: str, created_at: Optional[str]=None, bundle_for_receipt: Optional[Dict[str, Any]]=None, input_for_attestation: Any=None) -> Dict[str, Any]:
    _require_envelope_shape(envelope)
    payload_kind = envelope['payload_kind']
    payload = envelope['payload']
    _require_valid_payload(payload_kind, payload)
    _require_payload_correspondence(payload_kind, payload, bundle_for_receipt=bundle_for_receipt, input_for_attestation=input_for_attestation)
    existing = {sig.get('signer_id') for sig in envelope['signatures']}
    normalized_signer = core.normalize_identifier(signer_id)
    if normalized_signer is None:
        raise EnvelopeError('INVALID_SIGNER_ID')
    if normalized_signer in existing:
        raise EnvelopeError('DUPLICATE_SIGNER:' + normalized_signer)
    if len(envelope['signatures']) >= MAX_SIGNATURES:
        raise EnvelopeError('TOO_MANY_SIGNATURES')
    block = _build_signature_block(payload_kind, payload, alg, key, signer_id, key_id, created_at)
    new_envelope = core.clone(envelope)
    new_envelope['signatures'] = _canonical_signature_blocks(envelope['signatures'] + [block])
    return _finalize_envelope(new_envelope)

def strip_envelope(envelope: Dict[str, Any]) -> Dict[str, Any]:
    _require_envelope_shape(envelope)
    return core.clone(envelope['payload'])
ENVELOPE_KEYS = {'schema', 'version', 'core_version', 'identity_domain_id', 'contract_id', 'payload_kind', 'payload_id', 'payload', 'signatures', 'envelope_id'}
SIGNATURE_BLOCK_KEYS = {'alg', 'signer_id', 'key_id', 'purpose', 'tbs_id', 'signature', 'created_at'}
SIGNATURE_BLOCK_REQUIRED = {'alg', 'signer_id', 'key_id', 'purpose', 'tbs_id', 'signature'}

def _require_envelope_shape(envelope: Any) -> None:
    if not isinstance(envelope, dict):
        raise EnvelopeError('ENVELOPE_OBJECT_REQUIRED')
    if set(envelope.keys()) != ENVELOPE_KEYS:
        raise EnvelopeError('ENVELOPE_KEYS_MISMATCH')
    if envelope.get('schema') != ENVELOPE_SCHEMA:
        raise EnvelopeError('ENVELOPE_SCHEMA_MISMATCH')
    if envelope.get('version') != VERSION:
        raise EnvelopeError('ENVELOPE_VERSION_MISMATCH')
    if envelope.get('core_version') != core.CORE_VERSION:
        raise EnvelopeError('ENVELOPE_CORE_VERSION_MISMATCH')
    if envelope.get('identity_domain_id') != core.identity_domain_id():
        raise EnvelopeError('ENVELOPE_IDENTITY_DOMAIN_MISMATCH')
    if envelope.get('contract_id') != core.contract_id():
        raise EnvelopeError('ENVELOPE_CONTRACT_MISMATCH')
    if envelope.get('payload_kind') not in SUPPORTED_PAYLOAD_KINDS:
        raise EnvelopeError('ENVELOPE_PAYLOAD_KIND_UNSUPPORTED')
    if not isinstance(envelope.get('signatures'), list) or not envelope['signatures']:
        raise EnvelopeError('ENVELOPE_SIGNATURES_REQUIRED')
    if len(envelope['signatures']) > MAX_SIGNATURES:
        raise EnvelopeError('ENVELOPE_TOO_MANY_SIGNATURES')
    if envelope['signatures'] != _canonical_signature_blocks(envelope['signatures']):
        raise EnvelopeError('ENVELOPE_SIGNATURE_ORDER_NONCANONICAL')
    envelope_id = envelope.get('envelope_id')
    if not isinstance(envelope_id, str):
        raise EnvelopeError('ENVELOPE_ID_MISSING')
    material = core.clone(envelope)
    material.pop('envelope_id', None)
    if envelope_id != core.identity(ENVELOPE_ID_PREFIX, material):
        raise EnvelopeError('ENVELOPE_ID_MISMATCH')
KeyResolver = Callable[[str, str, str], Any]

def _ed25519_public_hex(public_obj: Any) -> str:
    return public_obj.public_bytes(Encoding.Raw, PublicFormat.Raw).hex()

def _make_resolver(key: Any, keys_by_signer: Optional[Dict[str, Any]], key_resolver: Optional[KeyResolver], keyset: Optional[Dict[str, Any]]) -> KeyResolver:
    if keyset is not None:
        return resolver_from_keyset(keyset)

    def resolve(signer_id: str, key_id: str, alg: str) -> Any:
        if key_resolver is not None:
            return key_resolver(signer_id, key_id, alg)
        if keys_by_signer is not None and signer_id in keys_by_signer:
            return keys_by_signer[signer_id]
        if key is not None:
            return key
        raise EnvelopeError('NO_KEY_FOR_SIGNER:' + str(signer_id))
    return resolve

def verify_envelope(envelope: Any, key: Any=None, keys_by_signer: Optional[Dict[str, Any]]=None, key_resolver: Optional[KeyResolver]=None, keyset: Optional[Dict[str, Any]]=None, require_signers: Optional[Sequence[str]]=None, exact_signer_set: bool=False, bundle_for_receipt: Optional[Dict[str, Any]]=None, input_for_attestation: Any=None, require_correspondence: bool=False) -> Tuple[bool, str, Dict[str, Any]]:
    report: Dict[str, Any] = {'payload_kind': None, 'payload_integrity': 'FAIL', 'correspondence_status': 'NOT_CHECKED', 'authenticity_status': 'NOT_CHECKED', 'signer_policy_status': 'NOT_APPLIED', 'valid_signers': [], 'invalid_signers': [], 'freshness_status': 'NOT_EVALUATED', 'replay_protection_status': 'EXTERNAL', 'trust_policy_status': 'EXTERNAL', 'core_contract_id': core.contract_id(), 'authenticity_contract_id': authenticity_contract_id(), 'payment_authority': 'NONE', 'settlement_authority': 'NONE', 'legal_authority': 'NONE', 'policy_interpretation_authority': 'NONE', 'fraud_determination_authority': 'NONE', 'money_movement': 'NONE', 'operational_authority': 'NONE'}
    try:
        _require_envelope_shape(envelope)
    except EnvelopeError as exc:
        return (False, str(exc), report)
    payload_kind = envelope['payload_kind']
    payload = envelope['payload']
    report['payload_kind'] = payload_kind
    try:
        _require_valid_payload(payload_kind, payload)
    except EnvelopeError as exc:
        return (False, str(exc), report)
    report['payload_integrity'] = 'PASS'
    if envelope['payload_id'] != payload_declared_id(payload_kind, payload):
        return (False, 'ENVELOPE_PAYLOAD_ID_MISMATCH', report)
    if payload_kind == PAYLOAD_KIND_BUNDLE:
        report['correspondence_status'] = 'INTRINSIC_RECONSTRUCTION_PASS'
    elif payload_kind == PAYLOAD_KIND_RECEIPT:
        if bundle_for_receipt is not None:
            ok, detail = core.verify_receipt_against_bundle(payload, bundle_for_receipt)
            if not ok:
                report['correspondence_status'] = 'FAIL'
                return (False, 'RECEIPT_BUNDLE_CORRESPONDENCE_FAILED:' + detail, report)
            report['correspondence_status'] = 'PASS'
        elif require_correspondence:
            return (False, 'RECEIPT_BUNDLE_REQUIRED_FOR_VERIFICATION', report)
    elif payload_kind == PAYLOAD_KIND_ATTESTATION:
        if input_for_attestation is not None:
            ok, detail = core.verify_attestation_against_input(payload, input_for_attestation)
            if not ok:
                report['correspondence_status'] = 'FAIL'
                return (False, 'ATTESTATION_INPUT_CORRESPONDENCE_FAILED:' + detail, report)
            report['correspondence_status'] = 'PASS'
        elif require_correspondence:
            return (False, 'ATTESTATION_INPUT_REQUIRED_FOR_VERIFICATION', report)
    if exact_signer_set and require_signers is None:
        report['signer_policy_status'] = 'FAIL'
        return (False, 'EXACT_SIGNER_SET_REQUIRES_REQUIRED_SIGNERS', report)
    resolver = _make_resolver(key, keys_by_signer, key_resolver, keyset)
    seen_declared: Set[str] = set()
    for index, block in enumerate(envelope['signatures']):
        if not isinstance(block, dict):
            report['invalid_signers'].append({'index': index, 'reason': 'SIGNATURE_BLOCK_OBJECT_REQUIRED'})
            continue
        allowed_keys = set(SIGNATURE_BLOCK_REQUIRED)
        if 'created_at' in block:
            allowed_keys.add('created_at')
        if set(block.keys()) != allowed_keys:
            report['invalid_signers'].append({'index': index, 'reason': 'SIGNATURE_BLOCK_KEYS_MISMATCH'})
            continue
        signer = block.get('signer_id')
        if core.normalize_identifier(signer) != signer:
            report['invalid_signers'].append({'index': index, 'reason': 'SIGNER_ID_INVALID'})
            continue
        if signer in seen_declared:
            report['invalid_signers'].append({'signer_id': signer, 'reason': 'DUPLICATE_SIGNER'})
            continue
        seen_declared.add(signer)
        alg = block.get('alg')
        if alg not in SUPPORTED_ALGS:
            report['invalid_signers'].append({'signer_id': signer, 'reason': 'UNSUPPORTED_ALG'})
            continue
        if block.get('purpose') != PURPOSE_ATTEST:
            report['invalid_signers'].append({'signer_id': signer, 'reason': 'UNSUPPORTED_PURPOSE'})
            continue
        if normalize_key_id(block.get('key_id')) != block.get('key_id'):
            report['invalid_signers'].append({'signer_id': signer, 'reason': 'KEY_ID_INVALID'})
            continue
        created_at = block.get('created_at')
        if created_at is not None and (not isinstance(created_at, str) or not RFC3339_UTC_PATTERN.fullmatch(created_at)):
            report['invalid_signers'].append({'signer_id': signer, 'reason': 'CREATED_AT_INVALID'})
            continue
        try:
            statement = signing_statement(payload_kind, payload, signer, block['key_id'], created_at)
        except EnvelopeError as exc:
            report['invalid_signers'].append({'signer_id': signer, 'reason': str(exc)})
            continue
        recomputed_tbs = core.identity(SIGNING_STATEMENT_ID_PREFIX, statement)
        if recomputed_tbs != block.get('tbs_id'):
            report['invalid_signers'].append({'signer_id': signer, 'reason': 'TBS_ID_MISMATCH'})
            continue
        try:
            resolved_key = resolver(statement['signer_id'], statement['key_id'], alg)
        except EnvelopeError as exc:
            report['invalid_signers'].append({'signer_id': signer, 'reason': str(exc)})
            continue
        if alg == ALG_ED25519:
            try:
                resolved_fpr = ed25519_key_id(_ed25519_public_hex(resolved_key))
            except Exception:
                report['invalid_signers'].append({'signer_id': signer, 'reason': 'ED25519_PUBLIC_KEY_UNUSABLE'})
                continue
            if resolved_fpr != statement['key_id']:
                report['invalid_signers'].append({'signer_id': signer, 'reason': 'ED25519_KEY_ID_FINGERPRINT_MISMATCH'})
                continue
        try:
            valid = _verify_message(alg, resolved_key, _statement_message(statement), block['signature'])
        except EnvelopeError as exc:
            report['invalid_signers'].append({'signer_id': signer, 'reason': str(exc)})
            continue
        if not valid:
            report['invalid_signers'].append({'signer_id': signer, 'reason': 'SIGNATURE_INVALID'})
            continue
        report['valid_signers'].append(signer)
    if report['invalid_signers']:
        report['authenticity_status'] = 'FAIL'
        return (False, 'SIGNATURE_SET_INVALID', report)
    if not report['valid_signers']:
        report['authenticity_status'] = 'FAIL'
        return (False, 'NO_VALID_SIGNATURE', report)
    report['authenticity_status'] = 'PASS'
    if require_signers is not None:
        required: List[str] = []
        for signer in require_signers:
            normalized = core.normalize_identifier(signer)
            if normalized is None:
                report['signer_policy_status'] = 'FAIL'
                return (False, 'INVALID_REQUIRED_SIGNER_ID', report)
            required.append(normalized)
        if len(required) != len(set(required)):
            report['signer_policy_status'] = 'FAIL'
            return (False, 'DUPLICATE_REQUIRED_SIGNER_ID', report)
        required_set = set(required)
        valid_set = set(report['valid_signers'])
        missing = sorted(required_set - valid_set)
        if missing:
            report['missing_required_signers'] = missing
            report['signer_policy_status'] = 'FAIL'
            return (False, 'REQUIRED_SIGNER_MISSING', report)
        if exact_signer_set:
            extra = sorted(valid_set - required_set)
            if extra:
                report['unexpected_signers'] = extra
                report['signer_policy_status'] = 'FAIL'
                return (False, 'UNEXPECTED_SIGNER_PRESENT', report)
        report['signer_policy_status'] = 'PASS'
    return (True, 'PASS', report)

def self_test() -> Tuple[int, int, List[str]]:
    checks: List[Tuple[str, bool]] = []

    def check(name: str, condition: bool) -> None:
        checks.append((name, bool(condition)))
    key_a = 'reference-hmac-key-alpha-32-bytes-minimum'
    key_b = 'reference-hmac-key-bravo-32-bytes-minimum'
    wrong = 'reference-hmac-key-wrong-32-bytes-minimum'
    auth_contract = authenticity_contract()
    check('authenticity_contract_core_binding', auth_contract['core_contract_id'] == core.contract_id())
    check('authenticity_contract_hmac_floor', auth_contract['hmac_min_secret_bytes'] == MIN_HMAC_SECRET_BYTES == 32)
    check('authenticity_contract_replay_external', auth_contract['replay_protection'] == 'EXTERNAL' and auth_contract['freshness_evaluation'] == 'OUT_OF_SCOPE')
    reference_input = core.build_reference_input(False, True)
    bundle = core.build_bundle(reference_input)
    receipt = core.make_receipt(bundle)
    env = sign_envelope(bundle, PAYLOAD_KIND_BUNDLE, ALG_HMAC, key_a, 'SIGNER-A', 'KEY-A')
    stripped = strip_envelope(env)
    check('bundle_roundtrip_identical', core.canonical_json(stripped) == core.canonical_json(bundle))
    ok, detail, report = verify_envelope(env, key=key_a)
    check('bundle_signature_verifies', ok and detail == 'PASS')
    check('bundle_reports_signer', report['valid_signers'] == ['SIGNER-A'])
    check('bundle_authenticity_scope', report['authenticity_status'] == 'PASS' and report['signer_policy_status'] == 'NOT_APPLIED')
    check('bundle_replay_boundary_explicit', report['replay_protection_status'] == 'EXTERNAL' and report['freshness_status'] == 'NOT_EVALUATED')
    check('bundle_authority_none', report['payment_authority'] == 'NONE' and report['money_movement'] == 'NONE')
    ok, detail, _ = verify_envelope(env, key=wrong)
    check('wrong_key_rejected', not ok and detail == 'SIGNATURE_SET_INVALID')
    tampered_payload = core.clone(env)
    tampered_payload['payload']['result']['payable_amount_minor'] += 1
    ok, detail, _ = verify_envelope(tampered_payload, key=key_a)
    check('tampered_payload_rejected', not ok)
    other_input = core.clone(reference_input)
    other_input['context']['remaining_limit_minor'] = 200000
    other_input = core.refresh_declared_ids(other_input)
    other_bundle = core.build_bundle(other_input)
    swapped = core.clone(env)
    swapped['payload'] = other_bundle
    swapped['payload_id'] = other_bundle['bundle_id']
    swapped = _finalize_envelope(swapped)
    ok, detail, _ = verify_envelope(swapped, key=key_a)
    check('payload_swap_rejected', not ok)
    envelope_id_tamper = core.clone(env)
    envelope_id_tamper['envelope_id'] = ENVELOPE_ID_PREFIX + '0' * 64
    ok, detail, _ = verify_envelope(envelope_id_tamper, key=key_a)
    check('envelope_id_tamper_rejected', not ok and detail == 'ENVELOPE_ID_MISMATCH')
    invalid_extra = core.clone(env)
    invalid_extra['signatures'].append(core.clone(env['signatures'][0]))
    invalid_extra['signatures'][1]['signer_id'] = 'SIGNER-X'
    invalid_extra = _finalize_envelope(invalid_extra)
    ok, detail, _ = verify_envelope(invalid_extra, key=key_a)
    check('invalid_extra_signature_rejects_envelope', not ok and detail == 'SIGNATURE_SET_INVALID')
    forged = core.clone(receipt)
    forged['payable_amount_minor'] = 999999999
    forged.pop('receipt_id')
    forged['receipt_id'] = core.identity(core.RECEIPT_ID_PREFIX, forged)
    forged_wrap_rejected = False
    try:
        sign_envelope(forged, PAYLOAD_KIND_RECEIPT, ALG_HMAC, key_a, 'SIGNER-A', 'KEY-A', bundle_for_receipt=bundle)
    except EnvelopeError:
        forged_wrap_rejected = True
    check('forged_receipt_unsignable', forged_wrap_rejected)
    unbound_refused = False
    try:
        sign_envelope(receipt, PAYLOAD_KIND_RECEIPT, ALG_HMAC, key_a, 'SIGNER-A', 'KEY-A')
    except EnvelopeError:
        unbound_refused = True
    check('unbound_receipt_refused', unbound_refused)
    renv = sign_envelope(receipt, PAYLOAD_KIND_RECEIPT, ALG_HMAC, key_a, 'SIGNER-A', 'KEY-A', bundle_for_receipt=bundle)
    ok, detail, receipt_report = verify_envelope(renv, key=key_a, bundle_for_receipt=bundle, require_correspondence=True)
    check('receipt_signature_verifies', ok and detail == 'PASS')
    check('receipt_correspondence_verified', receipt_report['correspondence_status'] == 'PASS')
    ok_missing, detail_missing, missing_report = verify_envelope(renv, key=key_a, require_correspondence=True)
    check('receipt_missing_bundle_keeps_authenticity_unchecked', not ok_missing and detail_missing == 'RECEIPT_BUNDLE_REQUIRED_FOR_VERIFICATION' and missing_report['authenticity_status'] == 'NOT_CHECKED')
    abstain_input = core.clone(reference_input)
    abstain_input['context']['evaluation_authorized'] = False
    abstain_input = core.refresh_declared_ids(abstain_input)
    attestation = core.make_attestation(abstain_input)
    attestation_unbound_refused = False
    try:
        sign_envelope(attestation, PAYLOAD_KIND_ATTESTATION, ALG_HMAC, key_a, 'SIGNER-A', 'KEY-A')
    except EnvelopeError:
        attestation_unbound_refused = True
    check('unbound_attestation_refused', attestation_unbound_refused)
    aenv = sign_envelope(attestation, PAYLOAD_KIND_ATTESTATION, ALG_HMAC, key_a, 'SIGNER-A', 'KEY-A', input_for_attestation=abstain_input)
    ok, detail, attestation_report = verify_envelope(aenv, key=key_a, input_for_attestation=abstain_input, require_correspondence=True)
    check('attestation_signature_verifies', ok and detail == 'PASS')
    check('attestation_correspondence_verified', attestation_report['correspondence_status'] == 'PASS')
    replay = core.clone(renv)
    replay['signatures'] = env['signatures']
    replay = _finalize_envelope(replay)
    ok, detail, _ = verify_envelope(replay, key=key_a)
    check('cross_kind_replay_rejected', not ok)
    multi = add_signature(env, ALG_HMAC, key_b, 'SIGNER-B', 'KEY-B')
    keys = {'SIGNER-A': key_a, 'SIGNER-B': key_b}
    ok, detail, report = verify_envelope(multi, keys_by_signer=keys, require_signers=['SIGNER-A', 'SIGNER-B'], exact_signer_set=True)
    check('multi_signature_exact_set', ok and set(report['valid_signers']) == {'SIGNER-A', 'SIGNER-B'} and report['signer_policy_status'] == 'PASS')
    policy_ok, policy_detail, policy_report = verify_envelope(env, key=key_a, require_signers=['SIGNER-B'])
    check('signer_policy_failure_preserves_authenticity_result', not policy_ok and policy_detail == 'REQUIRED_SIGNER_MISSING' and policy_report['authenticity_status'] == 'PASS' and policy_report['signer_policy_status'] == 'FAIL')
    ok, detail, report = verify_envelope(multi, keys_by_signer={'SIGNER-A': key_a, 'SIGNER-B': wrong}, require_signers=['SIGNER-A', 'SIGNER-B'])
    check('multi_partial_key_fails_policy', not ok and detail == 'SIGNATURE_SET_INVALID')
    check('multi_partial_reports_valid_a', report['valid_signers'] == ['SIGNER-A'])
    dup_refused = False
    try:
        add_signature(env, ALG_HMAC, key_a, 'SIGNER-A', 'KEY-A')
    except EnvelopeError:
        dup_refused = True
    check('duplicate_signer_refused', dup_refused)
    e1 = sign_envelope(bundle, PAYLOAD_KIND_BUNDLE, ALG_HMAC, key_a, 'SIGNER-A', 'KEY-A', created_at='2026-08-15T00:00:00Z')
    e2 = sign_envelope(bundle, PAYLOAD_KIND_BUNDLE, ALG_HMAC, key_a, 'SIGNER-A', 'KEY-A', created_at='2026-08-15T00:00:00Z')
    check('deterministic_given_timestamp', core.canonical_json(e1) == core.canonical_json(e2))
    hmac_secret = b'reference-hmac-secret-min-16-bytes!!'
    hmac_entry = make_hmac_entry('SIGNER-H', 'KEY-H', hmac_secret)
    private_hmac_keyset = build_keyset([hmac_entry], KEYSET_KIND_PRIVATE)
    check('keyset_hmac_builds_and_verifies', verify_keyset(private_hmac_keyset)[0])
    env_h = sign_with_keyset(bundle, PAYLOAD_KIND_BUNDLE, private_hmac_keyset, 'SIGNER-H')
    ok, detail, _ = verify_envelope(env_h, keyset=private_hmac_keyset)
    check('keyset_hmac_sign_verify', ok and detail == 'PASS')
    public_from_hmac_rejected = False
    try:
        build_keyset([{**hmac_entry}], KEYSET_KIND_PUBLIC)
    except EnvelopeError:
        public_from_hmac_rejected = True
    check('public_keyset_rejects_hmac_secret', public_from_hmac_rejected)
    cannot_publish_hmac = False
    try:
        keyset_public_view(private_hmac_keyset)
    except EnvelopeError:
        cannot_publish_hmac = True
    check('hmac_not_publishable', cannot_publish_hmac)
    ed_checks_ran = False
    if _HAVE_ED25519:
        ed_checks_ran = True
        seed, pub = generate_ed25519_keypair()
        ed_entry = make_ed25519_entry('SIGNER-E', private_seed_hex=seed, include_private=True)
        check('ed25519_key_id_is_fingerprint', ed_entry['key_id'] == ed25519_key_id(pub))
        private_ed_keyset = build_keyset([ed_entry], KEYSET_KIND_PRIVATE)
        check('ed25519_private_keyset_verifies', verify_keyset(private_ed_keyset)[0])
        public_ed_keyset = keyset_public_view(private_ed_keyset)
        check('ed25519_public_view_has_no_private', all(('private_key' not in e for e in public_ed_keyset['keys'])))
        check('ed25519_public_keyset_verifies', verify_keyset(public_ed_keyset)[0])
        env_e = sign_with_keyset(bundle, PAYLOAD_KIND_BUNDLE, private_ed_keyset, 'SIGNER-E', created_at='2026-08-15T00:00:00Z')
        ok, detail, report = verify_envelope(env_e, keyset=public_ed_keyset)
        check('ed25519_sign_verify_with_public_keyset', ok and report['valid_signers'] == ['SIGNER-E'])
        env_e2 = sign_with_keyset(bundle, PAYLOAD_KIND_BUNDLE, private_ed_keyset, 'SIGNER-E', created_at='2026-08-15T00:00:00Z')
        check('ed25519_deterministic', core.canonical_json(env_e) == core.canonical_json(env_e2))
        tampered_e = core.clone(env_e)
        tampered_e['payload']['result']['payable_amount_minor'] += 1
        ok, _, _ = verify_envelope(tampered_e, keyset=public_ed_keyset)
        check('ed25519_tamper_rejected', not ok)
        seed2, pub2 = generate_ed25519_keypair()
        wrong_entry = make_ed25519_entry('SIGNER-E', private_seed_hex=seed2)
        wrong_keyset = build_keyset([wrong_entry], KEYSET_KIND_PUBLIC)
        ok, detail, _ = verify_envelope(env_e, keyset=wrong_keyset)
        check('ed25519_wrong_key_rejected', not ok)
        mixed = build_keyset([ed_entry, hmac_entry], KEYSET_KIND_PRIVATE)
        env_mix_e = sign_with_keyset(bundle, PAYLOAD_KIND_BUNDLE, mixed, 'SIGNER-E')
        env_mix_h = sign_with_keyset(bundle, PAYLOAD_KIND_BUNDLE, mixed, 'SIGNER-H')
        ok_e = verify_envelope(env_mix_e, keyset=mixed)[0]
        ok_h = verify_envelope(env_mix_h, keyset=mixed)[0]
        check('mixed_keyset_ed25519', ok_e)
        check('mixed_keyset_hmac', ok_h)
        co = add_signature_with_keyset(env_mix_e, mixed, 'SIGNER-H')
        ok, detail, report = verify_envelope(co, keyset=mixed, require_signers=['SIGNER-E', 'SIGNER-H'], exact_signer_set=True)
        check('cross_alg_multisig', ok and set(report['valid_signers']) == {'SIGNER-E', 'SIGNER-H'})
    hentry_a = make_hmac_entry('SIGNER-A', 'KEY-A', b'aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa')
    hentry_b = make_hmac_entry('SIGNER-B', 'KEY-B', b'bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb')
    keyset_ab = build_keyset([hentry_a, hentry_b], KEYSET_KIND_PRIVATE)
    keyset_ba = build_keyset([hentry_b, hentry_a], KEYSET_KIND_PRIVATE)
    check('keyset_order_invariant', keyset_ab == keyset_ba)
    env_ab = sign_envelope(bundle, PAYLOAD_KIND_BUNDLE, ALG_HMAC, key_a, 'SIGNER-A', 'KEY-A')
    env_ab = add_signature(env_ab, ALG_HMAC, key_b, 'SIGNER-B', 'KEY-B')
    env_ba = sign_envelope(bundle, PAYLOAD_KIND_BUNDLE, ALG_HMAC, key_b, 'SIGNER-B', 'KEY-B')
    env_ba = add_signature(env_ba, ALG_HMAC, key_a, 'SIGNER-A', 'KEY-A')
    check('cosignature_order_invariant', env_ab == env_ba)
    failures = [name for name, ok in checks if not ok]
    skipped = 0 if ed_checks_ran else 1
    return (len(checks), len(checks) - len(failures), failures, skipped)

def _read_json(path: str) -> Any:
    return core.load_json_file(Path(path))

def _read_key(path: str) -> bytes:
    data = Path(path).read_bytes()
    if len(data) < MIN_HMAC_SECRET_BYTES:
        raise EnvelopeError('HMAC_SECRET_TOO_SHORT')
    return data

def _write_json(path: str, value: Any) -> None:
    Path(path).write_text(json.dumps(value, ensure_ascii=False, sort_keys=True, indent=2) + '\n', encoding='utf-8')

def parse_args(argv: Optional[Sequence[str]]=None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(prog='slang_claims_signature_v0_2_1.py')
    group = parser.add_mutually_exclusive_group()
    group.add_argument('--self-test', action='store_true')
    group.add_argument('--version', action='store_true')
    group.add_argument('--describe-authenticity-contract', action='store_true')
    group.add_argument('--gen-ed25519', action='store_true')
    group.add_argument('--public-view', metavar='PRIVATE_KEYSET_JSON')
    group.add_argument('--sign-bundle', metavar='BUNDLE_JSON')
    group.add_argument('--sign-receipt', metavar='RECEIPT_JSON')
    group.add_argument('--sign-attestation', metavar='ATTESTATION_JSON')
    group.add_argument('--add-signature', metavar='ENVELOPE_JSON')
    group.add_argument('--verify-envelope', metavar='ENVELOPE_JSON', help='verify payload, correspondence where required, and signatures; freshness, replay prevention, trust roots, rotation and revocation remain external')
    group.add_argument('--check-envelope-authenticity', metavar='ENVELOPE_JSON', help='check payload integrity and signatures without requiring receipt or attestation correspondence; freshness and replay prevention remain external')
    group.add_argument('--strip-envelope', metavar='ENVELOPE_JSON')
    parser.add_argument('--key', metavar='KEY_FILE')
    parser.add_argument('--private-keyset', metavar='KEYSET_JSON')
    parser.add_argument('--keyset', metavar='KEYSET_JSON')
    parser.add_argument('--against-bundle', metavar='BUNDLE_JSON')
    parser.add_argument('--against-input', metavar='INPUT_JSON')
    parser.add_argument('--signer-id', metavar='ID')
    parser.add_argument('--key-id', metavar='ID')
    parser.add_argument('--created-at', metavar='YYYY-MM-DDTHH:MM:SSZ', help='optional signed timestamp; freshness, expiry and replay prevention are not evaluated by this reference')
    parser.add_argument('--require-signers', metavar='ID,ID')
    parser.add_argument('--exact-signer-set', action='store_true')
    parser.add_argument('--output', metavar='PATH')
    parser.add_argument('--report-json', metavar='PATH', help='write a machine-readable verification report for envelope verification commands')
    return parser.parse_args(argv)

def _signing_material_from_args(args: argparse.Namespace) -> Tuple[Optional[Dict[str, Any]], Optional[bytes]]:
    if args.private_keyset:
        return (_read_json(args.private_keyset), None)
    if args.key:
        return (None, _read_key(args.key))
    raise EnvelopeError('SIGNING_KEY_MATERIAL_REQUIRED')

def _verification_material_from_args(args: argparse.Namespace) -> Tuple[Optional[Dict[str, Any]], Optional[bytes]]:
    if args.keyset:
        return (_read_json(args.keyset), None)
    if args.key:
        return (None, _read_key(args.key))
    raise EnvelopeError('VERIFICATION_KEY_MATERIAL_REQUIRED')

def _payload_for_signing(args: argparse.Namespace) -> Tuple[str, Dict[str, Any], Optional[Dict[str, Any]], Any]:
    if args.sign_bundle:
        return (PAYLOAD_KIND_BUNDLE, _read_json(args.sign_bundle), None, None)
    if args.sign_receipt:
        if not args.against_bundle:
            raise EnvelopeError('--sign-receipt requires --against-bundle')
        return (PAYLOAD_KIND_RECEIPT, _read_json(args.sign_receipt), _read_json(args.against_bundle), None)
    if args.sign_attestation:
        if not args.against_input:
            raise EnvelopeError('--sign-attestation requires --against-input')
        return (PAYLOAD_KIND_ATTESTATION, _read_json(args.sign_attestation), None, _read_json(args.against_input))
    raise EnvelopeError('SIGNING_PAYLOAD_REQUIRED')

def _write_or_print(args: argparse.Namespace, value: Any) -> None:
    if args.output:
        _write_json(args.output, value)
    else:
        print(json.dumps(value, ensure_ascii=False, sort_keys=True, indent=2))

def _print_verification(ok: bool, detail: str, report: Dict[str, Any]) -> None:
    if ok:
        print('ENVELOPE_VERIFICATION: PASS')
    else:
        print('ENVELOPE_VERIFICATION: FAIL ' + detail)
    print('PAYLOAD_INTEGRITY: ' + str(report.get('payload_integrity')))
    print('CORRESPONDENCE: ' + str(report.get('correspondence_status')))
    print('AUTHENTICITY: ' + str(report.get('authenticity_status')))
    print('SIGNER_POLICY: ' + str(report.get('signer_policy_status')))
    print('VALID_SIGNERS: ' + ','.join(report.get('valid_signers', [])))
    print('FRESHNESS: ' + str(report.get('freshness_status')))
    print('REPLAY_PROTECTION: ' + str(report.get('replay_protection_status')))
    print('TRUST_POLICY: ' + str(report.get('trust_policy_status')))
    print('OPERATIONAL_AUTHORITY: NONE')

def main(argv: Optional[Sequence[str]]=None) -> int:
    args = parse_args(argv)
    try:
        if args.self_test:
            total, passed, failures, skipped = self_test()
            print('SLANG-Claims authenticity envelope v' + VERSION + ' self-test')
            print('ED25519_BACKEND: ' + ('AVAILABLE' if _HAVE_ED25519 else 'UNAVAILABLE'))
            print('TOTAL ' + str(passed) + '/' + str(total) + ' PASS')
            if skipped:
                print('ED25519_GROUP: SKIPPED')
            for name in failures:
                print('FAIL ' + name)
            return 0 if not failures else 1
        if args.version:
            print('SLANG-Claims authenticity envelope ' + VERSION)
            return 0
        if args.describe_authenticity_contract:
            print(json.dumps(authenticity_contract(), ensure_ascii=False, sort_keys=True, indent=2))
            return 0
        if args.gen_ed25519:
            if not args.signer_id:
                raise EnvelopeError('--gen-ed25519 requires --signer-id')
            seed, _ = generate_ed25519_keypair()
            entry = make_ed25519_entry(args.signer_id, private_seed_hex=seed, include_private=True)
            private_keyset = build_keyset([entry], KEYSET_KIND_PRIVATE)
            _write_or_print(args, private_keyset)
            return 0
        if args.public_view:
            public_keyset = keyset_public_view(_read_json(args.public_view))
            _write_or_print(args, public_keyset)
            return 0
        if args.sign_bundle or args.sign_receipt or args.sign_attestation:
            kind, payload, bundle_for_receipt, input_for_attestation = _payload_for_signing(args)
            private_keyset, direct_key = _signing_material_from_args(args)
            if not args.signer_id:
                raise EnvelopeError('--signer-id is required')
            if private_keyset is not None:
                envelope = sign_with_keyset(payload, kind, private_keyset, args.signer_id, created_at=args.created_at, bundle_for_receipt=bundle_for_receipt, input_for_attestation=input_for_attestation)
            else:
                if not args.key_id:
                    raise EnvelopeError('--key-id is required with --key')
                envelope = sign_envelope(payload, kind, ALG_HMAC, direct_key, args.signer_id, args.key_id, created_at=args.created_at, bundle_for_receipt=bundle_for_receipt, input_for_attestation=input_for_attestation)
            _write_or_print(args, envelope)
            return 0
        if args.add_signature:
            envelope = _read_json(args.add_signature)
            private_keyset, direct_key = _signing_material_from_args(args)
            if not args.signer_id:
                raise EnvelopeError('--signer-id is required')
            bundle_for_receipt = _read_json(args.against_bundle) if args.against_bundle else None
            input_for_attestation = _read_json(args.against_input) if args.against_input else None
            if private_keyset is not None:
                envelope_out = add_signature_with_keyset(envelope, private_keyset, args.signer_id, created_at=args.created_at, bundle_for_receipt=bundle_for_receipt, input_for_attestation=input_for_attestation)
            else:
                if not args.key_id:
                    raise EnvelopeError('--key-id is required with --key')
                envelope_out = add_signature(envelope, ALG_HMAC, direct_key, args.signer_id, args.key_id, created_at=args.created_at, bundle_for_receipt=bundle_for_receipt, input_for_attestation=input_for_attestation)
            _write_or_print(args, envelope_out)
            return 0
        if args.verify_envelope or args.check_envelope_authenticity:
            envelope_path = args.verify_envelope or args.check_envelope_authenticity
            envelope = _read_json(envelope_path)
            keyset, direct_key = _verification_material_from_args(args)
            require = args.require_signers.split(',') if args.require_signers else None
            bundle_for_receipt = _read_json(args.against_bundle) if args.against_bundle else None
            input_for_attestation = _read_json(args.against_input) if args.against_input else None
            require_correspondence = bool(args.verify_envelope)
            kwargs = {'require_signers': require, 'exact_signer_set': args.exact_signer_set, 'bundle_for_receipt': bundle_for_receipt, 'input_for_attestation': input_for_attestation, 'require_correspondence': require_correspondence}
            if keyset is not None:
                ok, detail, report = verify_envelope(envelope, keyset=keyset, **kwargs)
            else:
                ok, detail, report = verify_envelope(envelope, key=direct_key, **kwargs)
            _print_verification(ok, detail, report)
            if args.report_json:
                report_document = {'schema': VERIFICATION_REPORT_SCHEMA, 'version': VERSION, 'verification_ok': bool(ok), 'detail': detail}
                report_document.update(core.clone(report))
                _write_json(args.report_json, report_document)
            return 0 if ok else 1
        if args.strip_envelope:
            payload = strip_envelope(_read_json(args.strip_envelope))
            _write_or_print(args, payload)
            return 0
        raise EnvelopeError('NO_OPERATION_SELECTED')
    except Exception as exc:
        print('ERROR: ' + str(exc), file=sys.stderr)
        return 2
if __name__ == '__main__':
    raise SystemExit(main())
