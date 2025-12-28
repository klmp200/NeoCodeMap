# NeoCodeMap

This plugin is inspired by [sublime-codemap](https://github.com/oleg-shilo/sublime-codemap/tree/master) but using Sublime Text 4 capabilities.

It displays on the side of the editor. You can jump to symbol definition and references to it.

It supports all languages through native Sublime indexing.

![preview](preview.png)

# Command Palette

Press `cmd+shift+p`. Type `neocodemap` to see the available commands:

* **Toggle**: Toggle the code map view
* **Close All**: Close all code maps on all windows
* **Move Up**: Move to the next symbol on the current view
* **Move Down**: Move to the previous symbol on the current view
* **Preferences**: Edit preferences (see below)

# Preferences

You can configure the plugin to use:

* A custom name for the code map tab
* The default width of the code map
* The position of the code map (right or left)
* Indentation of methods
