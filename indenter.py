from typing import Callable, NewType, Optional
import sublime

Indenter = NewType("Indenter", Callable[[sublime.View, sublime.SymbolRegion], int])
Scope = NewType("Scope", Optional[str])

class IndenterError(Exception):
    ...

_indenters = {}

def scope_from_syntax(syntax: Optional[sublime.Syntax]) -> Scope:
    if not syntax:
        return None
    return syntax.scope

def register_indenter(scope: Scope, indenter: Indenter):
    global _indenters
    _indenters[scope] = indenter

def _default_indenter(
    view: sublime.View, symbol: sublime.SymbolRegion
) -> int:
    return view.indentation_level(symbol.region.a)

def get_default_indenter() -> Indenter:
    global _indenters
    return _indenters[None]

def get_indent(
    view: sublime.View, symbol: sublime.SymbolRegion
) -> int:
    global _indenters
    try:
        return _indenters.get(scope_from_syntax(view.syntax()), _indenters[None])(view, symbol)
    except IndenterError:
        # Force overridable default indenter if indentation error happens
        try:
            return _indenters[None](view, symbol)
        except IndenterError:
            # Force non-overriden default indenter if indentation error happens
            return _default_indenter(view, symbol)

def _markdown_indenter(view: sublime.View, symbol: sublime.SymbolRegion) -> int:
    headings = [scope for scope in view.scope_name(symbol.region.a).split(" ") if scope.startswith("markup.heading")]
    if len(headings) < 1:
        raise IndenterError
    heading = headings[0].split(".")
    try:
        print(int(heading[2]))
        return int(heading[2]) - 1
    except ValueError as e:
        raise IndenterError from e
    return 0

register_indenter(None, _default_indenter)
register_indenter('text.html.markdown', _markdown_indenter)

