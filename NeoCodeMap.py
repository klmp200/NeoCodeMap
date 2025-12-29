from __future__ import annotations
from json.decoder import JSONDecodeError
import json
from pathlib import Path
from typing import Union, List, Optional, Dict, Literal, Any
import sublime
import sublime_plugin

map_manager: CodeMapManager = None
settings: sublime.Settings = None
css: str = ""


def plugin_loaded():
    global settings, css, map_manager
    map_manager = CodeMapManager()
    settings = sublime.load_settings("NeoCodeMap.sublime-settings")
    css = sublime.load_resource("Packages/NeoCodeMap/NeoCodeMap.css")

    for window in sublime.windows():
        map_manager.restore_sheet(window)

class SheetManager:
    def __init__(self):
        self._sheets: Dict[sublime.Window, sublime.HtmlSheet] = {}

    def create(self, window: sublime.Window, content: str) -> sublime.HtmlSheet:
        """Create a new html sheet in a provided window"""
        self._sheets[window] = window.new_html_sheet(
            "", content, flags=sublime.NewFileFlags.TRANSIENT
        )
        return self._sheets[window]

    def get(self, window: Optional[sublime.Window] = None) -> Optional[sublime.HtmlSheet]:
        """Get a sheet from a specified window. Get from active window if unspecified"""
        if not window:
            window = sublime.active_window()

        sheet = self._sheets.get(window)

        # Test if the sheet has been destroyed
        if sheet and not sheet.group():
            del self._sheets[window]
            return None

        return sheet

    def remove(self, window: sublime.Window):
        """Remove a sheet from a specific window"""
        if self.get(window):
            del self._sheets[window]


class CodeMapManager:
    """Main logic of the code map"""

    SETTINGS_GROUP_KEY = "neo_code_map_group"

    KIND_CLASS_NAMES: Dict[int, str] = {
        sublime.KindId.KEYWORD: 'kind kind_keyword',
        sublime.KindId.TYPE: 'kind kind_type',
        sublime.KindId.FUNCTION: 'kind kind_function',
        sublime.KindId.NAMESPACE: 'kind kind_namespace',
        sublime.KindId.NAVIGATION: 'kind kind_navigation',
        sublime.KindId.MARKUP: 'kind kind_markup',
        sublime.KindId.VARIABLE: 'kind kind_variable',
        sublime.KindId.SNIPPET: 'kind kind_snippet',
    }

    def __init__(self):
        self._sheets = SheetManager()

    def restore_sheet(self, window: sublime.Window):
        """Restore code map sheet on a given window if it exists"""
        try:
            group = int(window.settings().get(self.SETTINGS_GROUP_KEY))
        except (ValueError, TypeError):
            return

        # Check that the group still exists
        if group >= window.num_groups():
            return

        # Check that the group is empty
        if window.sheets_in_group(group) or window.views_in_group(group):
            return

        # For some reason, showing the sheet promotes it when restoring
        # The workaround is to restore the sheet, remove it and then show it again
        # This is why I show it twice here. One low level show and one high level
        self._show(window, group, window.active_view(), window)
        self.show(window)


    @property
    def layout_position(self) -> Union[Literal["left"], Literal["right"]]:
        """Get preferred layout position from settings"""
        desired = str(settings.get("neocodemap_position")).lower()
        if desired in ["left", "right"]:
            return desired

        # Default to auto
        if sublime.active_window().settings().get("sidebar_on_right"):
            return "left"

        return "right"

    def clear(self):
        """Delete all html sheets on all windows"""
        for window in sublime.windows():
            self.hide(self._sheets.get(window), window)

    def update_sheet(self, sheet: Optional[sublime.HtmlSheet] = None) -> bool:
        """Update the html content of a provided sheet"""
        if not sheet:
            sheet = self._sheets.get()
        if not sheet:
            return False
        sheet.set_contents(self.get_html())
        return True

    def create_layout(self, window: sublime.Window) -> int:
        """Create the layout and return the newly created group"""
        layout = window.layout()
        columns: List[float] = layout["cols"]
        cells: List[List[int]] = layout["cells"]
        rows: List[float] = layout["rows"]

        width = float(settings.get("neocodemap_width"))
        last_column = len(columns) - 1
        last_row = len(rows) - 1

        for i, column in enumerate(columns):
            if column > 0:
                columns[i] = column * (1 - width)

        if self.layout_position == "right":
            columns.append(1)
            cells.append([last_column, 0, last_column + 1, last_row])

        else:
            columns[-1] = 1
            columns.insert(1, width)
            # Move everything right
            for i, cell in enumerate(cells):
                cells[i] = [cell[0] + 1, cell[1], cell[2] + 1, cell[3]]
            cells.append([0, 0, 1, last_row])

        window.run_command("set_layout", layout)
        return window.num_groups()

    def _show(self,
            window: sublime.Window,
            group: int,
            rendered_view: Optional[sublime.View] = None,
            active_window: Optional[sublime.Window] = None,
        ) -> sublime.HtmlSheet:
        """Low level function that does the showing logic on a group"""

        # Create new sheet
        sheet = self._sheets.create(window, self.get_html(rendered_view))
        window.move_sheets_to_group([sheet], group)

        # Restore original focus
        if active_window and rendered_view:
            active_window.focus_view(rendered_view)

        return sheet


    def show(self, window: Optional[sublime.Window] = None) -> bool:
        """Show the html sheet on the specified window. Use the active window if unspecified"""
        if not window:
            window = sublime.active_window()

        if not window:
            return False

        active_view = window.active_view()
        if not active_view:
            return False

        # Cleanup previous group
        self.hide(self._sheets.get(window), window)

        sheet = self._show(window, self.create_layout(window), active_view, window)
        window.settings().set(self.SETTINGS_GROUP_KEY, sheet.group())

        return True

    def hide(self, sheet: Optional[sublime.HtmlSheet] = None, window: Optional[sublime.Window] = None) -> bool:
        """Hide the specified sheet on the specified window.
        Get the sheet from the specified window if unspecified.
        Get the active window if unspecified"""

        if not window:
            window = sublime.active_window()

        if not sheet:
            sheet = self._sheets.get(window)

        if not sheet:
            return False

        original_view = window.active_view()

        group = sheet.group()
        if not group:
            return False

        # Remove sheet
        group, index = window.get_sheet_index(sheet)
        window.run_command("close_by_index", {"group": group, "index": index})

        # Restore layout if group is empty
        if not window.views_in_group(group) and not window.sheets_in_group(group):
            window.run_command("close_pane", {"group": group})

        # Cleanup
        self._sheets.remove(window)
        window.settings().erase(self.SETTINGS_GROUP_KEY)

        # Restore original focus
        if original_view:
            window.focus_view(original_view)

        return True

    def toggle(self, window: Optional[sublime.Window] = None) -> bool:
        """Toggle the display of the sheet from the specified window.
        Get the active window if unspecified"""

        if self._sheets.get(window):
            return self.hide(window=window)
        return self.show(window)

    def get_selected_lines(self, view: Optional[sublime.View] = None) -> List[int]:
        """Get all selected lines on a provided view. Use the current active view if unspecified"""
        if not view:
            view = sublime.active_window().active_view()

        if not view:
            return []

        return [view.rowcol(region.a)[0] for region in view.sel()]

    def _is_symbol_active(self, view: sublime.View, selected_lines: List[int], symbol: sublime.SymbolRegion, next_symbol: Optional[sublime.SymbolRegion]) -> bool:
        """Test if the provided symbol is active in the provided view
        view: view to test the symbol on
        selected_lines: list of line numbers that are currently selected by the user on that view
        symbol: symbol region to test
        next_symbol: next symbol region in the document. Used to test symbol boundaries. Leave to None if you're testing the last symbol in the view"""

        current_line = view.rowcol(symbol.region.a)[0]
        next_line = view.rowcol(next_symbol.region.a)[0] if next_symbol else len(view.lines(sublime.Region(0, view.size())))

        for line in selected_lines:
            if line >= current_line and line < next_line:
                return True

        return False

    def _get_around_active_symbol(self, default_index: int, offset: int, view: Optional[sublime.View] = None) -> Optional[sublime.SymbolRegion]:
        """Get a symbol around the active one on the specified view
        default_index: index of the list to get if the symbol list isn't empty but no active symbol exists
        offset: symbol offset to get in the list around the active symbol
        view: view to search symbols on. Get the current active list if unspecified"""

        if not view:
            view = sublime.active_window().active_view()

        if not view:
            return None

        symbol_regions = view.symbol_regions()
        selected_lines = self.get_selected_lines(view)

        if len(symbol_regions) == 0:
            return None

        for i, symbol in enumerate(symbol_regions):
            next_symbol = symbol_regions[i+1] if i+1 < len(symbol_regions) else None
            if self._is_symbol_active(view, selected_lines, symbol, next_symbol):
                return symbol_regions[(i + offset) % len(symbol_regions)]

        # If no symbol is active in the view, we get the default index
        return symbol_regions[default_index]

    def get_next_symbol(self, view: Optional[sublime.View] = None) -> Optional[sublime.SymbolRegion]:
        """Get the next symbol region on the provided view. Use the current active view if unspecified"""
        return self._get_around_active_symbol(0, 1, view)

    def get_previous_symbol(self, view: Optional[sublime.View] = None) -> Optional[sublime.SymbolRegion]:
        """Get the previous symbol region on the provided view. Use the current active view if unspecified"""
        return self._get_around_active_symbol(-1, -1, view)

    def get_html(self, view: Optional[sublime.View] = None) -> str:
        """Build the HTML content for a sheet based on the content of the specified view.
        Get the current active view from the current active window if unspecified"""

        window = sublime.active_window()
        if not view:
            view = window.active_view()

        if not view:
            return ""

        html = f"<body><style>{css}</style>"
        selected_lines = [view.rowcol(region.a)[0] for region in view.sel()]

        def indent_css(symbol: sublime.SymbolRegion) -> str:
            if not settings.get("neocodemap_enable_indent"):
                return ""

            level = view.indentation_level(symbol.region.a)
            if level == 0:
                return ""
            return f"margin-left: {0.5 + level * 1.6}rem;"
            
        symbol_regions = view.symbol_regions()
        for i, symbol in enumerate(symbol_regions):
            kind_id, short_type, long_type = symbol.kind
            next_symbol = symbol_regions[i+1] if i+1 < len(symbol_regions) else None

            html += f"""
            <div
                class='item {'active' if self._is_symbol_active(view, selected_lines, symbol, next_symbol) else ''}'
                style='{indent_css(symbol)}'
            >
                <i
                    class='{self.KIND_CLASS_NAMES.get(kind_id, 'kind kind_ambiguous')}'
                    title='{long_type}'
                >{short_type}</i>
                <a
                    href='{sublime.command_url('neo_code_map_goto_view_region', {'view_id': view.id(), 'region_begin': symbol.region.a})}'
                    title='{view.rowcol(symbol.region.begin())}'
                >{symbol.name}</a>
                <a href='{sublime.command_url('neo_code_map_goto_reference', {'view_id': view.id(), 'symbol': symbol.name})}'>⧉</a>
            </div>
            """
        html += "</body>"

        return html

    def move_to_region(self, view: sublime.View, region: sublime.Region):
        """Move the cursor to a specified region on the specified view"""
        if (window := view.window()):
            window.focus_view(view)


        # Avoid selection bug when moving after jump
        view.sel().clear()

        # Needed to avoid selection bug and properly trigger the history
        # This also fires the correct event for the html redraw
        # +1 is needed because rowcol is 0 based but goto_line is 1 based
        view.run_command("goto_line", {"line": view.rowcol(region.begin())[0] + 1})

        # Move the cursor to the beginning of the symbol
        view.sel().clear()
        view.sel().add(region.begin())

class NeoCodeMapToggleCommand(sublime_plugin.WindowCommand):
    """Toggle the code map"""
    def name(self) -> str:
        return "neo_code_map_toggle"

    def run(self):
        map_manager.toggle(self.window)

class NeoCodeMapCloseAllCommand(sublime_plugin.ApplicationCommand):
    """Close all code maps from all windows"""
    def name(self) -> str:
        return "neo_code_map_close_all"

    def run(self):
        map_manager.clear()

class NeoCodeMapMoveCommand(sublime_plugin.WindowCommand):
    """Move up or down symbols on the code map"""
    def name(self) -> str:
        return "neo_code_map_move"

    def run(self, direction: Union[Literal["up"], Literal["down"]]):
        view = self.window.active_view()

        if not view:
            return

        symbol = map_manager.get_next_symbol(view) if direction == "down" else map_manager.get_previous_symbol(view)

        if not symbol:
            return

        map_manager.move_to_region(view, symbol.region)


class NeoCodeMapGotoViewRegionCommand(sublime_plugin.ApplicationCommand):
    """Unexposed: used as a callback when clicking on html links in the code map"""
    def name(self) -> str:
        return "neo_code_map_goto_view_region"

    def run(self, view_id: int, region_begin: int):
        view = sublime.View(view_id)
        region = sublime.Region(region_begin)
        map_manager.move_to_region(view, region)

class NoCodeMapGotoReferenceCommand(sublime_plugin.ApplicationCommand):
    """Unexposed: goto reference of a symbol on the current active view"""

    def name(self) -> str:
        return "neo_code_map_goto_reference"

    def run(self, view_id: int, symbol: str):
        view = sublime.View(view_id)
        window = view.window()

        if not window:
            return

        window.focus_view(view)
        window.run_command("goto_reference", {"symbol": symbol})

class NavigationListener(sublime_plugin.EventListener):
    """Synchronize codemap with user activity"""
    def on_selection_modified_async(self, view: sublime.View):
        map_manager.update_sheet()

    def on_activated(self, view: sublime.View):
        map_manager.update_sheet()

    def on_new_window_async(self, window: sublime.Window):
        map_manager.restore_sheet(window)
