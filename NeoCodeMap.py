from typing import Union, List, Optional
import sublime
import sublime_plugin

settings: sublime.Settings = None


def plugin_loaded():
    global settings
    settings = sublime.load_settings("NeoCodeMap.sublime-settings")


def plugin_unloaded():
    pass


class CodeMapManager:
    _html_sheets: List[int] = []

    @staticmethod
    def tab_name() -> str:
        return str(settings.get("neocodemap_tab_name"))

    @classmethod
    def is_code_map(cls, sheet: Union[sublime.Sheet, sublime.HtmlSheet]) -> bool:
        return isinstance(sheet, sublime.HtmlSheet) and sheet.id() in cls._html_sheets

    @classmethod
    def get_sheet(cls) -> Union[sublime.HtmlSheet, None]:
        for sheet in sublime.active_window().sheets():
            if cls.is_code_map(sheet):
                return sheet
        return None

    @classmethod
    def is_visible(cls) -> bool:
        sheet = cls.get_sheet()
        if not sheet:
            return False
        return sheet == sublime.active_window().active_sheet_in_group(
            sublime.active_window().get_sheet_index(sheet)[0]
        )

    @classmethod
    def show(cls) -> bool:
        if cls.is_visible():
            return False

        window = sublime.active_window()
        original_view = window.active_view()

        # Cleanup previous group
        if cls.get_sheet():
            cls.hide()

        # Create new layout
        layout = window.get_layout()
        columns = layout["cols"]
        cells = layout["cells"]
        last_column = len(columns) - 1
        last_row = len(layout["rows"]) - 1
        width = 1 - float(settings.get("neocodemap_width"))

        for i, column in enumerate(columns):
            if column > 0:
                columns[i] = column * width

        columns.append(1)
        cells.append([last_column, 0, last_column + 1, last_row])
        window.run_command("set_layout", layout)

        group = window.num_groups()

        # Create new sheet
        sheet = sublime.active_window().new_html_sheet(
            cls.tab_name(), cls.get_html(original_view)
        )
        cls._html_sheets.append(sheet.id())
        window.move_sheets_to_group([sheet], group, select=False)

        # Restore original focus
        if original_view:
            window.focus_view(original_view)

        return True

    @classmethod
    def hide(cls) -> bool:
        sheet = cls.get_sheet()
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
        cls._html_sheets.remove(sheet.id())

        # Restore original focus
        if original_view:
            window.focus_view(original_view)

        return True

    @classmethod
    def toggle(cls) -> bool:
        if cls.is_visible():
            return cls.hide()
        return cls.show()

    @classmethod
    def get_html(cls, view: Optional[sublime.View] = None) -> str:
        window = sublime.active_window()
        if not view:
            view = window.active_view()
        if not view:
            return ""

        html = "<body>"
        for symbol in view.get_symbols():
            region, sym = symbol
            html += f"<p>{sym}: {str(region)}</p>"
        html += "</body>"
        print(html)

        return html


class ToggleNeoCodeMap(sublime_plugin.TextCommand):
    def run(self, edit: sublime.Edit):
        CodeMapManager.toggle()


class SheetListener(sublime_plugin.EventListener):
    def on_modified(self, view):
        pass
