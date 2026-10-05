import ast

from vllm_hust_utility_victim import plugin


def test_empty_type_params_do_not_change_fingerprint(monkeypatch):
    source = "def choose(x):\n    return x + 1\n"
    expected = plugin.fingerprint(source)
    original = ast.parse

    def newer_ast(text):
        tree = original(text)
        for node in ast.walk(tree):
            if isinstance(node, (ast.FunctionDef, ast.ClassDef)):
                if "type_params" not in node._fields:
                    node._fields = (*node._fields, "type_params")
                node.type_params = []
        return tree

    monkeypatch.setattr(plugin.ast, "parse", newer_ast)
    assert plugin.fingerprint(source) == expected


def test_changed_behavior_is_still_rejected():
    assert plugin.fingerprint("def f(x): return x + 1") != plugin.fingerprint(
        "def f(x): return x + 2")


def test_formatting_and_line_endings_are_ignored():
    assert plugin.fingerprint("def f(x):\n    return x + 1\n") == plugin.fingerprint(
        "# comment\r\ndef f(x):\r\n  return x+1\r\n")
