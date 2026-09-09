"""Conservative SQL AST gate. The OS/database privileges remain the boundary."""
import sqlglot
from sqlglot import exp
from sqlglot.optimizer.scope import traverse_scope

ALLOWED_FUNCTIONS = frozenset({
    "SUM", "AVG", "MIN", "MAX", "COUNT", "ROUND", "ABS", "CAST", "TRY_CAST", "COALESCE", "NULLIF",
    "EXTRACT", "DATE_TRUNC", "TIME_TO_STR", "STR_TO_TIME", "STRPTIME", "STRFTIME", "LOWER", "UPPER",
    "TRIM", "LENGTH", "CHAR_LENGTH", "SUBSTRING", "CONCAT", "CASE", "IF", "GREATEST", "LEAST",
    "ROW_NUMBER", "RANK", "DENSE_RANK", "LAG", "LEAD", "FIRST_VALUE", "LAST_VALUE", "STDDEV",
    "STDDEV_SAMP", "STDDEV_POP", "VARIANCE", "VAR_POP", "VAR_SAMP", "PERCENTILE_CONT", "MEDIAN",
    "DATE", "YEAR", "MONTH", "DAY", "DATE_PART", "DATE_DIFF", "DATEDIFF", "COUNT_IF", "ISNAN",
})

def validate_sql(sql, allowed_sources, dialect="duckdb"):
    statements = sqlglot.parse(sql, read=dialect)
    if len(statements) != 1 or not isinstance(statements[0], (exp.Select, exp.Union, exp.Intersect, exp.Except)):
        raise ValueError("Exactly one SELECT query is required.")
    tree = statements[0]
    forbidden = {"Insert", "Update", "Delete", "Create", "Drop", "Alter", "Command", "Copy", "Into", "Lock", "Set", "Transaction"}
    for node in tree.walk():
        if isinstance(node, exp.Dot) and isinstance(node.expression, exp.Func):
            raise ValueError("Qualified function calls are forbidden.")
        if isinstance(node, exp.DataType) and node.this == exp.DataType.Type.USERDEFINED:
            raise ValueError("User-defined type casts are forbidden.")
        if type(node).__name__ in forbidden:
            raise ValueError("SQL mutation/control statements are forbidden.")
        if isinstance(node, exp.Func):
            name = node.name.upper() if isinstance(node, exp.Anonymous) else node.sql_name().upper()
            if name not in ALLOWED_FUNCTIONS:
                raise ValueError(f"SQL function is not allowed: {name}")
    for scope in traverse_scope(tree):
        for source in scope.sources.values():
            if isinstance(source, exp.Table):
                if not isinstance(source.this, exp.Identifier) or source.db or source.catalog or source.name not in allowed_sources:
                    raise ValueError("SQL references an undeclared source.")
    return tree
