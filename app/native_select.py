from nicegui import ui


class NativeSelect(ui.select, component="native_select.js"):
    """Drop-in `ui.select` that renders the browser's own <select> (the iOS wheel picker on iPhone).

    Same API as ui.select (value, options, set_options, on_change...). There is no type-to-search.
    """
