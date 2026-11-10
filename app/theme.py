from nicegui import ui


def apply_app_theme() -> None:
    ui.add_head_html("""
        <meta name="apple-mobile-web-app-capable" content="yes">
        <meta name="apple-mobile-web-app-status-bar-style" content="default">
        <meta name="apple-mobile-web-app-status-bar-style" content="black-translucent">
        <meta name="theme-color" content="#ffffff">
        <script>
        window.casaTheme = {
            current() {
                const saved = localStorage.getItem("casa-theme");
                if (saved) return saved;
                return window.matchMedia("(prefers-color-scheme: dark)").matches ? "dark" : "light";
            },
            apply(theme) {
                const currentTheme = theme || window.casaTheme.current();
                document.documentElement.dataset.theme = currentTheme;
                // Browser UI color (Chrome/Brave on Android) follows the chosen theme, not only the OS one.
                const meta = document.querySelector('meta[name="theme-color"]');
                if (meta) meta.content = currentTheme === "dark" ? "#16222f" : "#ffffff";
                // Quasar's plugin is `Dark` (capital D); it is missing until Quasar has loaded.
                if (window.Quasar && Quasar.Dark) Quasar.Dark.set(currentTheme === "dark");
            },
            toggle() {
                localStorage.setItem("casa-theme", window.casaTheme.current() === "dark" ? "light" : "dark");
                window.casaTheme.apply();
            }
        };
        window.casaTheme.apply();
        window.addEventListener("load", () => window.casaTheme.apply());
        window.matchMedia("(prefers-color-scheme: dark)").addEventListener("change", () => window.casaTheme.apply());
        </script>
        <style>
        :root {
            --color-scheme: light;
            --casa-bg: #f8fafc;
            --casa-surface: #ffffff;
            --casa-surface-soft: #f2f3f5;
            --casa-border: #d0d7de;
            --casa-text: #1f2328;
            --casa-muted: #656d76;
            --casa-accent: #0969da;
            --casa-accent-soft: #ddf4ff;
        }

        /* Makes native controls (date picker, scrollbars, autofill) follow the theme in Chrome/Brave. */
        html { color-scheme: var(--color-scheme); }

        html[data-theme="dark"] {
            --color-scheme: dark;
            --casa-bg: #0f141b;
            --casa-surface: #16222f;
            --casa-surface-soft: #26303f;
            --casa-border: #465260;
            --casa-text: #f3f6f4;
            --casa-muted: #91a8c0;
            --casa-accent: #378ccf;
            --casa-accent-soft: #193644;
        }

        body {
            background: var(--casa-bg);
            color: var(--casa-text);
            font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", "Noto Sans", Helvetica, Arial, sans-serif, "Apple Color Emoji", "Segoe UI Emoji";
            -webkit-font-smoothing: antialiased;
            -webkit-tap-highlight-color: transparent;
        }

        .casa-header {
            background: color-mix(in srgb, var(--casa-surface) 92%, transparent);
            color: var(--casa-text);
            border-bottom: 1px solid var(--casa-border);
            backdrop-filter: blur(14px);
            -webkit-backdrop-filter: blur(14px);
            padding-top: env(safe-area-inset-top);
            padding-left: max(12px, env(safe-area-inset-left));
            padding-right: max(12px, env(safe-area-inset-right));
        }

        .casa-tabbar {
            display: none;
            background: color-mix(in srgb, var(--casa-surface) 92%, transparent);
            color: var(--casa-text);
            border-top: 1px solid var(--casa-border);
            backdrop-filter: blur(14px);
            -webkit-backdrop-filter: blur(14px);
            padding: max(4px, env(safe-area-inset-right)) max(env(safe-area-inset-right)) max(env(safe-area-inset-bottom)) max(4px, env(safe-area-inset-left));
        }

        .casa-tabbar .q-tab {
            flex: 1;
            color: var(--casa-muted);
            font-size: 11px;
            min-height: 52px;
        }

        .casa-tabbar .q-tab--active {
            color: var(--casa-accent);
        }

        @media (max-width: 767px) {
            .casa-nav { display: none !important; }
            .casa-tabbar { display: flex !important; }
            .chart-view .q-btn { flex: 1 1 0; min-width: 0; padding-inline: 2px; }
            .chart-view .q-btn__content { white-space: normal; text-align: center; }
        }

        .q-page {
            padding-left: max(0px, env(safe-area-inset-left));
            padding-right: max(0px, env(safe-area-inset-right));
        }

        .casa-month {
            scroll-margin-top: calc(72px + env(safe-area-inset-top));
        }

        .casa-clickable {
            cursor: pointer;
        }

        .casa-clickable:active {
            background: var(--casa-surface-soft);
        }

        .casa-positive { color: #16a34a; }
        .casa-negative { color: #dc2626; }
        html[data-theme="dark"] .casa-positive { color: #4ade80; }
        html[data-theme="dark"] .casa-negative { color: #f87171; }

        .casa-scroll-x {
            overflow-x: auto;
            -webkit-overflow-scrolling: touch;
        }

        /* iOS Safari zoom into inputs with font-size below 16px */
        @supports (-webkit-touch-callout: none) {
            input, select, textarea, .q-field__native, .q-field__input {
                font-size: 16px !important;
            }
        }

        @media (pointer: coarse) {
            .q-btn { min-height: 44px; }
            .q-btn.q-btn-round { min-width: 44px; }
        }

        .casa-nav {
            background: var(--casa-surface-soft);
            border: 1px solid var(--casa-border);
            border-radius: 8px;
            padding: 3px;
        }

        .casa-nav-q-btn {
            border-radius: 6px;
            min-height: 34px;
            color: var(--casa-muted);
        }

        .casa-nav-is-active {
            background: var(--casa-surface);
            color: var(--casa-accent);
            box-shadow: 0 1px 3px rgba(15, 23, 42, 0.14);
        }

        .casa-card {
            background: var(--casa-surface);
            color: var(--casa-text);
            border: 1px solid var(--casa-border);
            border-radius: 8px;
            box-shadow: none;
        }

        .casa-muted {
            color: var(--casa-muted);
        }

        .casa-page-title {
            color: var(--casa-text);
            font-size: 20px;
            letter-spacing: 0;
        }

        .casa-filter {
            background: var(--casa-surface);
            color: var(--casa-text);
            border: 1px solid var(--casa-border);
            border-radius: 8px;
            padding: 10px 12px;
        }

        html[data-theme="dark"] .q-page,
        html[data-theme="dark"] .q-layout,
        html[data-theme="dark"] .q-drawer,
        html[data-theme="dark"] .q-menu,
        html[data-theme="dark"] .q-dialog_inner > div {
            background: var(--casa-bg);
            color: var(--casa-text);
        }

        html[data-theme="dark"] .q-card,
        html[data-theme="dark"] .q-menu,
        html[data-theme="dark"] .q-list,
        html[data-theme="dark"] .q-item {
            background: var(--casa-surface);
            color: var(--casa-text);
        }

        html[data-theme="dark"] .q-item.q-manual-focusable--focused,
        html[data-theme="dark"] .q-item--active,
        html[data-theme="dark"] .q-item:hover {
            background: var(--casa-surface-soft);
            color: var(--casa-text);
        }

        html[data-theme="dark"] .q-field,
        html[data-theme="dark"] .q-field__native,
        html[data-theme="dark"] .q-field__input,
        html[data-theme="dark"] .q-field__label,
        html[data-theme="dark"] .q-field__prefix,
        html[data-theme="dark"] .q-field__suffix,
        html[data-theme="dark"] .q-field__append,
        html[data-theme="dark"] .q-field__prepend {
            color: var(--casa-text);
        }

        html[data-theme="dark"] .q-field__label {
            color: var(--casa-muted);
        }

        html[data-theme="dark"] .q-field--focused .q-field__label,
        html[data-theme="dark"] .q-field--highlighted .q-field__label {
            color: var(--casa-accent);
        }

        html[data-theme="dark"] .q-field__control::before {
            border-color: var(--casa-border);
        }

        html[data-theme="dark"] .q-field__control::after {
            background: var(--casa-accent);
        }

        html[data-theme="dark"] .q-field__marginal,
        html[data-theme="dark"] .q-select__dropdown-icon {
            color: var(--casa-muted);
            opacity: 1;
        }

        html[data-theme="dark"] .q-btn--flat,
        html[data-theme="dark"] .q-btn--outline {
            color: var(--casa-accent);
        }

        html[data-theme="dark"] .q-btn--flat.text-grey-7,
        html[data-theme="dark"] .text-grey-7 {
            color: var(--casa-muted) !important;
        }

        html[data-theme="dark"] .text-blue-600,
        html[data-theme="dark"] .text-blue-700 {
            color: var(--casa-accent) !important;
        }

        html[data-theme="dark"] .border-b{
          border-color: var(--casa-border);
        }
      </style>
      """
    )

def page_container():
    return ui.column().classes("w-full max-w-4xl mx-auto p-3 sm:p-4 gap-4")

def card_classes(extra: str = ""):
    return f"casa-card {extra}".strip()
