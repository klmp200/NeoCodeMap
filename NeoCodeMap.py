from __future__ import annotations
from typing import Union, List, Optional, Dict, Literal
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


def plugin_unloaded():
    pass


class CodeMapManager:
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
        self._html_sheets: List[int] = []

    @property
    def tab_name(self) -> str:
        return str(settings.get("neocodemap_tab_name"))

    @property
    def layout_position(self) -> Union[Literal["left"], Literal["right"]]:
        desired = str(settings.get("neocodemap_position")).lower()
        if desired in ["left", "right"]:
            return desired

        # Default to auto
        if sublime.active_window().settings().get("sidebar_on_right"):
            return "left"

        return "right"


    def is_code_map(self, sheet: Union[sublime.Sheet, sublime.HtmlSheet]) -> bool:
        return isinstance(sheet, sublime.HtmlSheet) and sheet.id() in self._html_sheets

    def get_sheet(self) -> Union[sublime.HtmlSheet, None]:
        for sheet in sublime.active_window().sheets():
            if self.is_code_map(sheet):
                return sheet
        return None

    def is_visible(self) -> bool:
        sheet = self.get_sheet()
        if not sheet:
            return False
        return sheet == sublime.active_window().active_sheet_in_group(
            sublime.active_window().get_sheet_index(sheet)[0]
        )

    def update_sheet(self, sheet: Optional[sublime.HtmlSheet] = None) -> bool:
        if not sheet:
            sheet = self.get_sheet()
        if not sheet:
            return False
        sheet.set_contents(self.get_html())

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

    def show(self) -> bool:
        if self.is_visible():
            return False

        window = sublime.active_window()
        original_view = window.active_view()

        # Cleanup previous group
        if self.get_sheet():
            self.hide()


        group = self.create_layout(window)

        # Create new sheet
        sheet = sublime.active_window().new_html_sheet(
            self.tab_name, self.get_html(original_view)
        )
        self._html_sheets.append(sheet.id())
        window.move_sheets_to_group([sheet], group, select=False)

        # Restore original focus
        if original_view:
            window.focus_view(original_view)

        return True

    def hide(self) -> bool:
        sheet = self.get_sheet()
        if sheet is None:
            return False

        window = sublime.active_window()
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
        self._html_sheets.remove(sheet.id())

        # Restore original focus
        if original_view:
            window.focus_view(original_view)

        return True

    def toggle(self) -> bool:
        if self.is_visible():
            return self.hide()
        return self.show()

    def get_html(self, view: Optional[sublime.View] = None) -> str:
        window = sublime.active_window()
        if not view:
            view = window.active_view()
        if not view:
            return ""

        html = f"<body><style>{css}</style>"
        for symbol in view.symbol_regions():
            kind_id, short_type, long_type = symbol.kind
            html += f"""
            <p>
                <i class='{self.KIND_CLASS_NAMES.get(kind_id, 'kind kind_ambiguous')}' title='{long_type}'>{short_type}</i>
                <a href='{sublime.command_url('goto_view_region_neo_code_map', {'view_id': view.id(), 'region_a': symbol.region.a})}'>{symbol.name}</a>
            </p>
            """
        html += "</body>"

        return html


class ToggleNeoCodeMap(sublime_plugin.TextCommand):
    def run(self, edit: sublime.Edit):
        map_manager.toggle()

class GotoViewRegionNeoCodeMap(sublime_plugin.ApplicationCommand):
    def run(self, view_id: int, region_a: int):
        view = sublime.View(view_id)
        region = sublime.Region(region_a)
        view.sel().clear()
        view.sel().add(region)
        view.show_at_center(region, animate=True)
        sublime.active_window().focus_view(view)

class NavigationListener(sublime_plugin.EventListener):
    def on_selection_modified_async(self, view: sublime.View):
        map_manager.update_sheet()

    def on_activated(self, view: sublime.View):
        map_manager.update_sheet()
