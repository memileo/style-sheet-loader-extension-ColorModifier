# Style Sheet Loader
# Copyright (C) 2023 Freya Lupen <penguinflyer2222@gmail.com>

# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.

# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.

# modified with chatgpt4o and claude 3.5 sonnet

import re
import os.path
from krita import Extension
from PyQt5.QtWidgets import QFileDialog, QMessageBox, QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QLineEdit, QCheckBox, QApplication, QComboBox
from PyQt5.QtGui import QPalette, QColor
from PyQt5.QtCore import QFile, QIODevice, QMimeDatabase, QFileInfo, QDir, pyqtSignal

EXTENSION_ID = 'pykrita_style_sheet_loader'
MENU_ENTRY = 'Load Style Sheet'

# Constant string for the config group in kritarc
PLUGIN_CONFIG = "plugin/StyleSheetLoader"

# Function to get RGB values from QPalette
def get_palette_rgb_values():
    palette = QApplication.instance().palette()
    return {
        'Window': palette.color(QPalette.Window).getRgb()[:3],
        'WindowText': palette.color(QPalette.WindowText).getRgb()[:3],
        'Base': palette.color(QPalette.Base).getRgb()[:3],
        'Text': palette.color(QPalette.Text).getRgb()[:3],
        'Button': palette.color(QPalette.Button).getRgb()[:3],
        'ButtonText': palette.color(QPalette.ButtonText).getRgb()[:3],
        'Highlight': palette.color(QPalette.Highlight).getRgb()[:3],
        'HighlightedText': palette.color(QPalette.HighlightedText).getRgb()[:3],
        'ToolTipBase': palette.color(QPalette.ToolTipBase).getRgb()[:3],
        'ToolTipText': palette.color(QPalette.ToolTipText).getRgb()[:3],
        'AlternateBase': palette.color(QPalette.AlternateBase).getRgb()[:3],
        'Link': palette.color(QPalette.Link).getRgb()[:3],
        'LinkVisited': palette.color(QPalette.LinkVisited).getRgb()[:3]
    }

def rgb_to_hsl(r, g, b):
    r, g, b = r/255.0, g/255.0, b/255.0
    cmax = max(r, g, b)
    cmin = min(r, g, b)
    delta = cmax - cmin

    # Calculate hue
    if delta == 0:
        h = 0
    elif cmax == r:
        h = 60 * (((g - b) / delta) % 6)
    elif cmax == g:
        h = 60 * ((b - r) / delta + 2)
    else:
        h = 60 * ((r - g) / delta + 4)

    # Calculate lightness
    l = (cmax + cmin) / 2

    # Calculate saturation
    s = 0 if delta == 0 else delta / (1 - abs(2 * l - 1))

    return h, s * 100, l * 100
    
class StyleSheetLoader(Extension):
    pathChanged = pyqtSignal(str)

    def __init__(self, parent):
        super().__init__(parent)
        
        self.colorMode = Application.readSetting(PLUGIN_CONFIG, "colorMode", "RGB")

        self.startupStyleSheet = Application.readSetting(PLUGIN_CONFIG, "startupStyleSheet", "")
        self.path = self.startupStyleSheet
        self.useStartup = self.startupStyleSheet != ""

        self.customResourcePrefix = Application.readSetting(PLUGIN_CONFIG, "customResourcePrefix", "stylesheet")
        self.searchInStyleSheetDir = Application.readSetting(PLUGIN_CONFIG, "useStyleSheetDirAsResourcePath", "True") == "True"

    def setup(self):
        appNotifier = Application.instance().notifier()
        appNotifier.setActive(True)

        appNotifier.windowCreated.connect(self.loadOnStartup)

    def createActions(self, window):
        action = window.createAction(EXTENSION_ID, MENU_ENTRY, "tools/scripts")
        action.triggered.connect(self.showDialog)

    def showDialog(self):
        layout = QVBoxLayout()

        pathLayout = QHBoxLayout()
        self.pathEdit = QLineEdit(self.path)
        self.pathChanged.connect(self.pathEdit.setText)
        pathLabel = QLabel("Path:")
        pathLabel.setToolTip("Path to a Qt Style Sheet to load.")
        pathLayout.addWidget(pathLabel)
        pathLayout.addWidget(self.pathEdit)
        self.pathEdit.editingFinished.connect(self.lineEditImport)

        importButton = QPushButton()
        importButton.setIcon(Application.icon("document-open"))
        importButton.setToolTip("Choose a file")
        importButton.pressed.connect(self.showImportDialog)
        pathLayout.addWidget(importButton)

        layout.addLayout(pathLayout)
        
        colorModeLayout = QHBoxLayout()
        colorModeLabel = QLabel("Multiply colors:")
        self.colorModeCombo = QComboBox()
        self.colorModeCombo.addItems(["RGB", "Lightness (HSL)"])
        self.colorModeCombo.setCurrentText(self.colorMode)
        self.colorModeCombo.currentTextChanged.connect(self.setColorMode)
        colorModeLayout.addWidget(colorModeLabel)
        colorModeLayout.addWidget(self.colorModeCombo)
        layout.addLayout(colorModeLayout)

        self.startupCheckbox = QCheckBox("Load on startup")
        self.startupCheckbox.setToolTip("Whether to remember this style sheet path and load it on startup.")
        self.startupCheckbox.setChecked(self.useStartup)
        self.startupCheckbox.clicked.connect(self.toggleLoadOnStartup)
        layout.addWidget(self.startupCheckbox)

        resPrefixLayout = QHBoxLayout()
        self.resPrefixEdit = QLineEdit(self.customResourcePrefix)
        resPrefixLabel = QLabel("Use folder resource prefix:")
        resPrefixLabel.setToolTip("Prefix used by the style sheet to look for resources such as images in the same folder")
        self.useAsResourcePathCheckbox = QCheckBox()
        self.useAsResourcePathCheckbox.setToolTip("Whether to add the style sheet's folder as a resource path")
        self.useAsResourcePathCheckbox.setChecked(self.searchInStyleSheetDir)
        self.useAsResourcePathCheckbox.clicked.connect(self.toggleResPath)
        resPrefixLayout.addWidget(self.useAsResourcePathCheckbox)
        resPrefixLayout.addWidget(resPrefixLabel)
        resPrefixLayout.addWidget(self.resPrefixEdit)
        self.resPrefixEdit.editingFinished.connect(self.setResPrefix)
        layout.addLayout(resPrefixLayout)

        self.dialog = QDialog(Application.activeWindow().qwindow())

        closeButton = QPushButton("Close")
        closeButton.setDefault(True)
        closeButton.clicked.connect(self.dialog.accept)
        layout.addWidget(closeButton)

        self.dialog.setLayout(layout)
        self.dialog.setWindowTitle("Style Sheet Loader")
        self.dialog.show()

    # Things that call the loader --
    def showImportDialog(self):
        path, _filter = QFileDialog.getOpenFileName(None, "Open a Qt Style Sheet", filter="Qt Style Sheets (*.qss *.txt)")
        self.importStylesheet(path)

    def lineEditImport(self):
        self.importStylesheet(self.pathEdit.text())

    def loadOnStartup(self):
        if not self.startupStyleSheet:
            return
        # Notify what we're doing, in case the user forgets it's active or something.
        print("Style Sheet Loader Extension: Loading %s." % self.startupStyleSheet)
        # If the file is changed, we could get errors, so add context to those error dialogs as to where they're coming from.
        self.importStylesheet(self.startupStyleSheet, addContext=True)

    def importStylesheet(self, path, addContext=False):
        if not path:
            return

        if not QFileInfo(path).exists():
            self.showWarningMessage("\"%s\" does not exist!" % (path), addContext)
            return

        mimeType = QMimeDatabase().mimeTypeForFile(path)
        if not mimeType.inherits("text/plain"):
            self.showWarningMessage("\"%s\" does not appear to be a text file!" % (path), addContext)
            return

        file = QFile(path)
        if file.open(QIODevice.ReadOnly):
            data = file.readAll()
            file.close()

            self.updateResPath()

            stylesheet = str(data, 'utf-8')
            # Replace placeholders with RGB values
            stylesheet = self.replace_placeholders(stylesheet)
            # Correct image paths
            stylesheet = self.correct_image_paths(stylesheet, os.path.dirname(path))
            # Debugging: Print the stylesheet after replacing placeholders and correcting image paths
            print("Stylesheet after processing:\n", stylesheet)
            
            # Apply the stylesheet
            # Add safety check for active window
            active_window = Application.activeWindow()
            if active_window is not None and hasattr(active_window, 'qwindow'):
                try:
                    active_window.qwindow().setStyleSheet(stylesheet)
                except Exception as e:
                    print(f"Failed to set stylesheet: {e}")
            else:
                print("No active window available to apply stylesheet")

            self.setPath(path)
        else:
            self.showWarningMessage("Failed to open \"%s\"." % (path), addContext)
            
            
    def showWarningMessage(self, warning, addContext):
        if addContext:
            warning = "Style Sheet Loader Extension: " + warning
        # Add safety check here too
        active_window = Application.activeWindow()
        if active_window is not None and hasattr(active_window, 'qwindow'):
            resultBox = QMessageBox(active_window.qwindow())
            resultBox.setText(warning)
            resultBox.setIcon(QMessageBox.Warning)
            resultBox.show()
        else:
            print(f"Warning: {warning}")

    # Variable setters --
    def toggleLoadOnStartup(self, isChecked):
        self.useStartup = isChecked
        self.startupStyleSheet = self.path if isChecked else ""
        Krita.writeSetting(PLUGIN_CONFIG, "startupStyleSheet", self.startupStyleSheet)

    def setPath(self, path):
        self.path = path
        # Use a signal and not pathEdit directly, in case we are doing this on startup, where pathEdit doesn't exist.
        self.pathChanged.emit(path)
        # Just changing the path here, not toggling
        self.toggleLoadOnStartup(self.useStartup)

    def toggleResPath(self, isChecked):
        self.searchInStyleSheetDir = isChecked
        valString = "True" if self.searchInStyleSheetDir else "False"
        Application.writeSetting(PLUGIN_CONFIG, "useStyleSheetDirAsResourcePath", valString)

        self.resPrefixEdit.setEnabled(self.searchInStyleSheetDir)

        # Update the resource path and reload the stylesheet
        self.lineEditImport()

    def setResPrefix(self):
        self.customResourcePrefix = self.resPrefixEdit.text()
        # Update the resource path and reload the stylesheet
        self.lineEditImport()

    def updateResPath(self):
        if self.searchInStyleSheetDir:
            QDir.setSearchPaths(self.customResourcePrefix, [os.path.dirname(self.startupStyleSheet)])
        else:
            QDir.setSearchPaths(self.customResourcePrefix, [])

    def setColorMode(self, mode):
        self.colorMode = mode
        Application.writeSetting(PLUGIN_CONFIG, "colorMode", mode)
        # Reload stylesheet if path exists
        if self.path:
            self.lineEditImport()

    def replace_placeholders(self, stylesheet):
        palette_rgb_values = get_palette_rgb_values()

        def calculate_color(base_value, multiplier, alpha_multiplier):
            if self.colorMode == "RGB":
                # Existing RGB calculation
                rgb_values = tuple(max(0, min(255, int(base_value[i] * multiplier))) for i in range(3))
                return rgb_values, alpha_multiplier
            else:
                # HSL calculation
                h, s, l = rgb_to_hsl(*base_value)
                # Only modify lightness with multiplier
                new_l = max(0, min(100, l * multiplier))
                return (h, s, new_l), alpha_multiplier

        def replace_match(match):
            base_name = match.group(1)
            multiplier = float(match.group(2)) if match.group(2) else 1.0
            alpha_multiplier = float(match.group(3)) if match.group(3) else 1.0
            
            if base_name in palette_rgb_values:
                color_values, alpha = calculate_color(palette_rgb_values[base_name], multiplier, alpha_multiplier)
                
                if self.colorMode == "RGB":
                    # Use RGB format
                    if abs(alpha - 1.0) < 0.001:
                        return f"rgb({color_values[0]}, {color_values[1]}, {color_values[2]})"
                    else:
                        return f"rgba({color_values[0]}, {color_values[1]}, {color_values[2]}, {alpha:.2f})"
                else:
                    # Use HSL format
                    if abs(alpha - 1.0) < 0.001:
                        return f"hsl({int(color_values[0])}, {int(color_values[1])}%, {int(color_values[2])}%)"
                    else:
                        return f"hsla({int(color_values[0])}, {int(color_values[1])}%, {int(color_values[2])}%, {alpha:.2f})"
                    
            return match.group(0)
        
        pattern = re.compile(r'QPalette\.(\w+)(?:\s*?\(\s*?([\d\.]+)\s*?(?:,\s*?([\d\.]+))?\s*?\))?')
        return pattern.sub(replace_match, stylesheet)

    def correct_image_paths(self, stylesheet, base_path):
        """
        Ensures that any relative paths in the stylesheet are converted to absolute paths
        based on the base path of the stylesheet file.
        """
        pattern = re.compile(r'url\(([^)]+)\)')

        def replace_url(match):
            url = match.group(1).strip('\'"')
            if not os.path.isabs(url):
                url = os.path.join(base_path, url)
            # Remove 'stylesheet:' prefix if present
            url = url.replace('stylesheet:', '')
            return f"url('{url}')"

        return pattern.sub(replace_url, stylesheet)

# Example QSS content to test
qss_content = """
QWidget {
    background-color: QPalette.Window;
    color: QPalette.WindowText(0.95, 0.3);
    border: 1px solid QPalette.Link(0.95);
    image: url('images/test.png');
}
"""

# Test the replace_placeholders function
loader = StyleSheetLoader(None)
processed_content = loader.replace_placeholders(qss_content)
print("Processed QSS content:\n", processed_content)
