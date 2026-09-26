"""Typed provider wire plans compiled to the existing deterministic executor AST."""
from collections.abc import Collection
from functools import lru_cache
from math import isfinite
from typing import Any

# Bump whenever prompts, AST semantics, schema, or generation settings change.
PLANNER_VERSION = "26"
# Flash Lite needs reasoning for composed predicates; total output includes it.
PLANNER_THINKING_BUDGET = 1024
PLANNER_MAX_OUTPUT_TOKENS = 2048
PLANNER_OPERATORS = frozenset({
    "contains", "equals", "greater_than", "less_than", "west_of", "east_of",
    "greater_than_or_equal", "less_than_or_equal",
    "north_of", "south_of", "exists", "starts_with", "ends_with", "contains_text",
    "has_space", "has_hyphen", "word_count_equals", "word_count_greater_than", "word_count_less_than",
    "char_count_equals", "char_count_greater_than", "char_count_less_than", "and", "or", "not",
})

PLANNER_RULES = """
Plan wire format:
Return only the JSON object, without Markdown fences or surrounding prose.
- plan is a flat ARRAY of nodes, not a nested tree. Generate children before parents; the root is last.
- Every operand is either {"entity":"ENTITY","relation":"RELATION"} or {"value":LITERAL}.
  Use entity "TARGET" for the original hidden target and "item" for a quantifier-bound entity/value.
- Binary predicates use exactly operator, left, right. exists/has_space/has_hyphen use only operator and left.
- and/or use operator and args: node indices counting from zero in the ENTIRE plan array.
  Every args entry must point to an earlier array position, never the current node or a future node.
- not uses operator and args with EXACTLY ONE node index.
- any/all use operator, items (an operand), and args with ONE predicate node index.
  The quantifier binds entity "item" in its predicate subtree.
  The predicate alone tests the required properties; any already requires a matching item.
  Do not add a separate exists node for the same list.
- The root is the ONLY node not referenced by another node. All other nodes must be referenced
  exactly once. No cycles, unused nodes, repeated references, condition/conditions fields,
  or nested operator objects.
- If the same predicate is needed twice, emit two distinct nodes instead of reusing an index.
- A target predicate and an item predicate are distinct even when their relation/value match.
  Never reuse a quantifier's item predicate as a target condition outside that quantifier.

Example for NOT (population > 100000 AND name starts with K):
{"route":"local","plan":[
  {"operator":"greater_than","left":{"entity":"TARGET","relation":"population"},"right":{"value":100000}},
  {"operator":"starts_with","left":{"entity":"TARGET","relation":"name"},"right":{"value":"K"}},
  {"operator":"and","args":[0,1]},
  {"operator":"not","args":[2]}
]}

Meaning:
- Preserve every condition and negation. Resolve the positive predicate using the mode-specific
  notes first, then negate it; negation must not change the underlying relation.
- "A or B" / "A lub B" means or(A, B); "A and B" means and(A, B).
  "Neither A nor B" / "ani A, ani B" means not(or(A, B)), NOT not(and(A, B)).
- exists tests only whether a relation has a value. For "any neighbor/item with property X",
  use any over the list with a predicate on item.X; never replace that condition with exists.
- The game supplies the hidden target; the question does not need to name it. Identity, official
  classifications and stored boolean properties are precise criteria, not vague questions.
- greater_than/less_than are strict. Use less_than_or_equal for "at most", "does not exceed",
  "nie przekracza"; use greater_than_or_equal for "at least", "co najmniej". Include equality.
- Use has_hyphen for whether text contains a hyphen (Polish: łącznik), including its negation.
  It recognizes hyphen-minus and Unicode hyphens, not en/em dashes. Use has_space for spaces.
- For other text substrings use contains_text, not exact list membership. Preserve explicitly
  quoted characters; "-" is a hyphen-minus, "–" is an en dash (półpauza).
- Never invent a threshold, comparison group, event, time period or definition to answer a vague
  question. If its criterion is unspecified (large, famous, important), return route="clarify",
  plan=null and an explanation asking for the missing criterion.
- A precise yes/no question about facts absent from the supported relations needs external facts:
  return route="fallback", plan=null. Do not substitute a loosely related known fact.
""".strip()

_RESPONSE_FIELDS = frozenset({
    "route", "improved_question", "explanation", "plan", "fallback_reason",
})
_ROUTES = ("local", "fallback", "clarify")
_UNARY = frozenset({"exists", "has_space", "has_hyphen"})
_LOGICAL = frozenset({"and", "or", "not", "any", "all"})
_BINARY_FIELDS = frozenset({"operator", "left", "right"})
_UNARY_FIELDS = frozenset({"operator", "left"})
_LOGICAL_FIELDS = frozenset({"operator", "args"})
_QUANTIFIER_FIELDS = frozenset({"operator", "items", "args"})


def planner_response_schema(
    *, relations: Collection[str], operators: Collection[str], target_entity: str,
    allow_named_entities: bool = False,
) -> dict[str, Any]:
    return _response_schema(
        tuple(sorted(relations)), tuple(sorted(operators)), target_entity, allow_named_entities,
    )


@lru_cache(maxsize=16)
def _response_schema(
    relations: tuple[str, ...], operators: tuple[str, ...], target_entity: str,
    allow_named_entities: bool,
) -> dict[str, Any]:
    entity = {"type": "string", "minLength": 1}
    if not allow_named_entities:
        entity["enum"] = [target_entity, "item"]
    operand = {"$ref": "#/$defs/operand"}
    args = {"type": "array", "items": {"type": "integer", "minimum": 0}, "minItems": 1}
    properties = {"left": operand, "right": operand, "items": operand, "args": args}
    branches = []
    for names, fields, single_argument in (
        (set(operators) - _UNARY - _LOGICAL, _BINARY_FIELDS, False),
        (set(operators) & _UNARY, _UNARY_FIELDS, False),
        (set(operators) & {"and", "or"}, _LOGICAL_FIELDS, False),
        (set(operators) & {"not"}, _LOGICAL_FIELDS, True),
        (set(operators) & {"any", "all"}, _QUANTIFIER_FIELDS, True),
    ):
        if not names:
            continue
        fields_schema = {field: properties[field] for field in sorted(fields - {"operator"})}
        if single_argument:
            fields_schema["args"] = {**args, "maxItems": 1}
        branches.append({
            "type": "object",
            "properties": {"operator": {"type": "string", "enum": sorted(names)}, **fields_schema},
            "required": sorted(fields),
            "additionalProperties": False,
        })
    return {
        "type": "object",
        "properties": {
            "improved_question": {"type": ["string", "null"]},
            "explanation": {"type": ["string", "null"]},
            "fallback_reason": {"type": ["string", "null"]},
            "route": {
                "type": "string",
                "enum": list(_ROUTES),
                "description": "local: clear predicate expressible with local facts and operators. fallback: clear predicate requiring unavailable local facts or operations. clarify: missing criterion, relation or polarity, or an unrelated/open-ended question. Unsupported facts or operations require fallback, never clarify.",
            },
            "plan": {"anyOf": [
                {"type": "array", "items": {"anyOf": branches}, "minItems": 1},
                {"type": "null"},
            ]},
        },
        "required": ["route", "plan"],
        "additionalProperties": False,
        "$defs": {"operand": {"anyOf": [
            {
                "type": "object",
                "properties": {"entity": entity, "relation": {"type": "string", "enum": list(relations)}},
                "required": ["entity", "relation"],
                "additionalProperties": False,
            },
            {
                "type": "object",
                "properties": {"value": {
                    "type": ["string", "number", "boolean", "array"],
                    "items": {"type": ["string", "number", "boolean"]},
                }},
                "required": ["value"],
                "additionalProperties": False,
            },
        ]}},
    }


def compile_planner_response(
    data: Any, *, relations: Collection[str], operators: Collection[str],
    target_entity: str, allow_named_entities: bool = False,
) -> dict[str, Any] | None:
    """Validate a single-root indexed tree and compile it in O(nodes), before caching."""
    if not isinstance(data, dict) or data.get("route") not in _ROUTES:
        raise RuntimeError("Planner returned an invalid response schema")
    if "plan" not in data or data.keys() - _RESPONSE_FIELDS:
        raise RuntimeError("Planner returned an invalid response schema")
    for key in ("improved_question", "explanation", "fallback_reason"):
        if data.get(key) is not None and not isinstance(data[key], str):
            raise RuntimeError("Planner returned an invalid response schema")
    if data["route"] != "local":
        if data["plan"] is not None:
            raise RuntimeError("Planner returned a plan for a non-local route")
        return None
    wire = data["plan"]
    if not isinstance(wire, list) or not wire:
        raise RuntimeError("Planner returned an invalid node list")

    def scalar(value: Any) -> bool:
        return isinstance(value, (str, bool, int)) or isinstance(value, float) and isfinite(value)

    def operand(value: Any, item_bound: bool) -> None:
        if not isinstance(value, dict):
            raise RuntimeError("Planner returned an invalid operand")
        if value.keys() == {"value"}:
            literal = value["value"]
            if not scalar(literal) and not (
                isinstance(literal, list) and all(scalar(item) for item in literal)
            ):
                raise RuntimeError("Planner returned an invalid literal")
            return
        if value.keys() != {"entity", "relation"}:
            raise RuntimeError("Planner returned an invalid reference")
        if not isinstance(value["relation"], str) or value["relation"] not in relations:
            raise RuntimeError("Planner returned an unsupported relation")
        entity = value["entity"]
        if not isinstance(entity, str) or not entity:
            raise RuntimeError("Planner returned an invalid entity")
        if entity == "item":
            if not item_bound:
                raise RuntimeError("Planner returned an unbound item reference")
            return
        if entity != target_entity and (not allow_named_entities or entity.startswith("target_")):
            raise RuntimeError("Planner returned an unsupported entity")
    consumed: set[int] = set()
    for index, node in enumerate(wire):
        if not isinstance(node, dict) or not isinstance(node.get("operator"), str) or node["operator"] not in operators:
            raise RuntimeError("Planner returned an unsupported operator")
        op = node["operator"]
        if op in _LOGICAL:
            fields = _QUANTIFIER_FIELDS if op in {"any", "all"} else _LOGICAL_FIELDS
            if node.keys() != fields:
                raise RuntimeError("Planner returned invalid operator fields")
            args = node["args"]
            if not isinstance(args, list) or not args or op in {"not", "any", "all"} and len(args) != 1:
                raise RuntimeError("Planner returned invalid operator arity")
            for child in args:
                if type(child) is not int or not 0 <= child < len(wire) or child == index or child in consumed:
                    raise RuntimeError("Planner returned an invalid or reused node reference")
                consumed.add(child)
        elif node.keys() != (_UNARY_FIELDS if op in _UNARY else _BINARY_FIELDS):
            raise RuntimeError("Planner returned invalid operator fields")
    if len(consumed) != len(wire) - 1:
        raise RuntimeError("Planner returned multiple or missing roots")
    root = next(index for index in range(len(wire)) if index not in consumed)
    visited: set[int] = set()

    def build(index: int, item_bound: bool = False) -> dict[str, Any]:
        if index in visited:
            raise RuntimeError("Planner returned a cyclic plan")
        visited.add(index)
        node = wire[index]
        op = node["operator"]
        if op in {"and", "or"}:
            return {"operator": op, "conditions": [build(child, item_bound) for child in node["args"]]}
        if op == "not":
            return {"operator": op, "condition": build(node["args"][0], item_bound)}
        if op in {"any", "all"}:
            operand(node["items"], item_bound)
            return {"operator": op, "items": node["items"], "condition": build(node["args"][0], True)}
        operand(node["left"], item_bound)
        if op not in _UNARY:
            operand(node["right"], item_bound)
        return node

    tree = build(root)
    if len(visited) != len(wire):
        raise RuntimeError("Planner returned disconnected nodes")
    return tree
