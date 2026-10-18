"""Schema-only checks; does NOT imply runtime conformance to CAAIF."""
import json
from pathlib import Path
try:
    from jsonschema import Draft202012Validator, FormatChecker
except ImportError as exc:
    raise SystemExit("Install dependency: python3 -m pip install jsonschema") from exc

ROOT=Path(__file__).resolve().parents[1]
PAIRS={
    'contract.json':'interaction-contract.schema.json',
    'request_ref.json':'interaction-request.schema.json',
    'request_inline.json':'interaction-request.schema.json',
    'decision.json':'interaction-decision.schema.json',
    'result.json':'interaction-result.schema.json',
    'three-agent/profile.json':'three-agent-profile.schema.json',
}
for example, schema_name in PAIRS.items():
    schema=json.loads((ROOT/'schemas'/schema_name).read_text())
    Draft202012Validator.check_schema(schema)
    instance=json.loads((ROOT/'examples'/example).read_text())
    Draft202012Validator(schema, format_checker=FormatChecker()).validate(instance)
# Basic cross-object consistency check (schema validity is not contract enforcement)
req=json.loads((ROOT/'examples'/'request_ref.json').read_text())
contract=json.loads((ROOT/'examples'/'contract.json').read_text())
assert (req['caller_id'],req['recipient_id'],req['capability'],req['contract_id'],req['contract_version']) == (contract['caller_id'],contract['recipient_id'],contract['capability'],contract['contract_id'],contract['version'])
assert all(ref['scope'] in contract['context_policy']['allowed_scopes'] for ref in req['context_refs'])
for role_a,role_b in [('conversational','reasoning'),('reasoning','task'),('task','reasoning'),('reasoning','conversational')]:
    for typ in ('contracts','requests'):
        filename=f'three-agent/{typ}/{role_a}_to_{role_b}.json'
        schema_name='interaction-contract.schema.json' if typ=='contracts' else 'interaction-request.schema.json'
        schema=json.loads((ROOT/'schemas'/schema_name).read_text())
        instance=json.loads((ROOT/'examples'/filename).read_text())
        Draft202012Validator(schema,format_checker=FormatChecker()).validate(instance)
print('CAAIF Core draft schemas and examples: PASS (14 objects)')
