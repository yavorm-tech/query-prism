"""
Fitness functions for the modular monolith.

1. A context may import another context only through its public `api` module.
   (Layer direction is checked separately by `lint-imports`, see pyproject.toml.)
2. Each table is written (INSERT/UPDATE/DELETE) only by the context that owns
   its schema.
3. Cross-context *reads* (SQL joins into another schema) are a ratchet: the
   current ones are listed in ALLOWED_CROSS_READS. New ones fail the build;
   removing one without updating the list also fails, so the list only shrinks.
"""
import ast
import importlib.util
import pathlib
import re

APP = pathlib.Path(__file__).resolve().parents[2] / "app"
MIGRATIONS = APP.parent / "migrations" / "versions"

CONTEXTS = ["identity", "audit", "metering", "notification", "workspace", "knowledge", "retrieval"]
COMPOSITION_ROOTS = {"main.py", "bootstrap.py", "worker.py"}


def _load_ownership() -> dict[str, str]:
    spec = importlib.util.spec_from_file_location("m0003", MIGRATIONS / "0003_context_schemas.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    table_schema = {t: schema for schema, tables in module.OWNERSHIP.items() for t in tables}
    table_schema["subscriptions"] = "metering"  # revision 0004
    return table_schema


TABLE_SCHEMA = _load_ownership()

# (reading context, table) pairs that exist today. Shrink this list; never grow it.
ALLOWED_CROSS_READS = {
    ("audit", "teams"),           # audit log shows team names
    ("workspace", "users"),       # topic list shows creator username
    ("workspace", "teams"),       # admin topic list shows team names
    ("workspace", "documents"),   # topic list shows document counts
    ("knowledge", "users"),       # document lists show uploader username
    ("knowledge", "teams"),       # document lists show team names
    ("knowledge", "topics"),      # document lists show topic names
    ("retrieval", "documents"),   # retrieval searches knowledge's index
    ("retrieval", "chunks"),
    ("retrieval", "users"),       # question history shows usernames
}


def _python_files(context: str):
    return sorted((APP / context).rglob("*.py"))


def _context_of(module: str) -> str | None:
    parts = module.split(".")
    return parts[1] if len(parts) > 1 and parts[0] == "app" and parts[1] in CONTEXTS else None


# ── 1. Imports go through api modules ───────────────────────────────────────

def test_contexts_import_each_other_only_through_api():
    violations = []
    for context in CONTEXTS:
        for path in _python_files(context):
            tree = ast.parse(path.read_text())
            for node in ast.walk(tree):
                if isinstance(node, ast.ImportFrom) and node.module:
                    # "from app.x.api import f" and "from app.x import api" are the only allowed forms
                    if node.module == f"app.{_context_of(node.module)}":
                        targets = [f"{node.module}.{a.name}" for a in node.names]
                    else:
                        targets = [node.module]
                elif isinstance(node, ast.Import):
                    targets = [a.name for a in node.names]
                else:
                    continue
                for target in targets:
                    other = _context_of(target)
                    if other and other != context and target.split(".")[2:3] != ["api"]:
                        violations.append(f"{path.relative_to(APP)}:{node.lineno} imports {target}")
    assert not violations, "Import another context only via its api module:\n" + "\n".join(violations)


# ── 2 & 3. SQL ownership ────────────────────────────────────────────────────

WRITE_RE = re.compile(r"\b(?:INSERT\s+INTO|DELETE\s+FROM)\s+(?:\w+\.)?(\w+)|\bUPDATE\s+(?:\w+\.)?(\w+)\s+(?:\w+\s+)?SET\b", re.I)
READ_RE = re.compile(r"\b(?:FROM|JOIN)\s+(?:\w+\.)?(\w+)", re.I)


def _sql_strings(path: pathlib.Path) -> list[tuple[int, str]]:
    out = []
    for node in ast.walk(ast.parse(path.read_text())):
        if isinstance(node, ast.Constant) and isinstance(node.value, str) and re.search(r"\b(SELECT|INSERT|UPDATE|DELETE)\b", node.value):
            out.append((node.lineno, node.value))
        elif isinstance(node, ast.JoinedStr):
            text = "".join(v.value for v in node.values if isinstance(v, ast.Constant) and isinstance(v.value, str))
            if re.search(r"\b(SELECT|INSERT|UPDATE|DELETE)\b", text):
                out.append((node.lineno, text))
    return out


def _scan():
    writes, reads = [], set()
    for context in CONTEXTS:
        for path in _python_files(context):
            for lineno, sql in _sql_strings(path):
                for m in WRITE_RE.finditer(sql):
                    table = m.group(1) or m.group(2)
                    if table in TABLE_SCHEMA and TABLE_SCHEMA[table] != context:
                        writes.append(f"{path.relative_to(APP)}:{lineno} writes {TABLE_SCHEMA[table]}.{table}")
                for m in READ_RE.finditer(sql):
                    table = m.group(1)
                    if table in TABLE_SCHEMA and TABLE_SCHEMA[table] != context:
                        reads.add((context, table))
    return writes, reads


def test_each_table_is_written_only_by_its_owning_context():
    writes, _ = _scan()
    assert not writes, "Write through the owning context's api instead:\n" + "\n".join(writes)


def test_cross_context_reads_do_not_grow():
    _, reads = _scan()
    new = sorted(reads - ALLOWED_CROSS_READS)
    gone = sorted(ALLOWED_CROSS_READS - reads)
    assert not new, f"New cross-context SQL reads (use the owning context's api): {new}"
    assert not gone, f"These cross-context reads no longer exist; remove them from ALLOWED_CROSS_READS: {gone}"


def test_every_table_has_an_owner():
    init_sql = (APP.parents[1] / "postgres" / "init.sql").read_text()
    tables = set(re.findall(r"CREATE TABLE IF NOT EXISTS (\w+)", init_sql))
    assert tables <= set(TABLE_SCHEMA), f"Tables without an owning context: {sorted(tables - set(TABLE_SCHEMA))}"
