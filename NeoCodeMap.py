from typing import Union, List, Optional, Dict
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
    def update_sheet(cls, sheet: Optional[sublime.HtmlSheet] = None) -> bool:
        if not sheet:
            sheet = cls.get_sheet()
        if not sheet:
            return False
        sheet.set_contents(cls.get_html())

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

        html = """
        <style>
        html {
                padding: 0;
        }
         .kind {
                font-weight: bold;
                font-style: italic;
                width: 1.5rem;
                display: inline-block;
                text-align: center;
                font-family: system;
                line-height: 1.3;
                border-radius: 2px;
                position: relative;
                top: 1px;
                margin-left: 6px;
                margin-right: 6px;
            }
            .kind_ambiguous {
                display: none;
            }
            .kind_keyword {
                background-color: color(var(--pinkish) a(0.2));
                color: var(--pinkish);
            }
            .kind_type {
                background-color: color(var(--purplish) a(0.2));
                color: var(--purplish);
            }
            .kind_function {
                background-color: color(var(--redish) a(0.2));
                color: var(--redish);
            }
            .kind_namespace {
                background-color: color(var(--bluish) a(0.2));
                color: var(--bluish);
            }
            .kind_navigation {
                background-color: color(var(--yellowish) a(0.2));
                color: var(--yellowish);
            }
            .kind_markup {
                background-color: color(var(--orangish) a(0.2));
                color: var(--orangish);
            }
            .kind_variable {
                background-color: color(var(--cyanish) a(0.2));
                color: var(--cyanish);
            }
            .kind_snippet {
                background-color: color(var(--greenish) a(0.2));
                color: var(--greenish);
            }
        </style>
        <body>
        """
        for symbol in view.symbol_regions():
            kind_id, short_type, long_type = symbol.kind
            html += f"""
            <p>
                <i class='{cls.KIND_CLASS_NAMES.get(kind_id, 'kind kind_ambiguous')}' title='{long_type}'>{short_type}</i>
                <a href='{sublime.command_url('goto_view_region_neo_code_map', {'view_id': view.id(), 'region_a': symbol.region.a, 'region_b': symbol.region.b})}'>{symbol.name}</a>
            </p>
            """
        html += "</body>"

        return html


class ToggleNeoCodeMap(sublime_plugin.TextCommand):
    def run(self, edit: sublime.Edit):
        CodeMapManager.toggle()

class GotoViewRegionNeoCodeMap(sublime_plugin.ApplicationCommand):
    def run(self, view_id: int, region_a: int, region_b: int):
        view = sublime.View(view_id)
        region = sublime.Region(region_a, region_b)
        view.sel().clear()
        view.sel().add(region)
        view.show_at_center(region, animate=True)
        sublime.active_window().focus_view(view)



class SheetListener(sublime_plugin.EventListener):
    def on_modified_async(self, view: sublime.View):
        CodeMapManager.update_sheet()

