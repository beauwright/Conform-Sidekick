"""Core operations ported from the davinci-resolve-scripts.

Each operation is UI-agnostic: it takes a :class:`resolve_conn.ResolveConnection`
plus ``log`` / ``pump`` / ``should_cancel`` callbacks, and returns a result dict
of counters. The feature panels (in ``features/``) supply the callbacks and
render the inputs/output around them.
"""
