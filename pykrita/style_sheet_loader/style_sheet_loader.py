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
DEBUG_MODE = False
PRINT_STYLESHEET = True

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

def normalize_hue(h):
    # Normalize hue value to be within 0-359 range.
    return int(h % 360 if h >= 0 else 360 + (h % 360))

def clip_value(value, min_val=0, max_val=None):
    # Clip value between min and max.
    if value < min_val:
        return min_val
    if max_val is not None and value > max_val:
        return max_val
    return value

def parse_color_params(param_str):
    # Parse the color parameters string and return a dictionary of values.
    # Initialize default values
    params = {'h': 0, 's': 1.0, 'l': 1.0, 'a': 1.0}
    
    if not param_str or not any(x in param_str for x in ['h:', 's:', 'l:', 'a:']):
        return params

    # Remove parentheses and split by any non-alphanumeric character (except . and -)
    parts = re.split(r'[^a-zA-Z0-9\.-]+', param_str.strip('()'))
    
    current_param = None
    for part in parts:
        part = part.strip()
        if not part:
            continue
            
        if part in ['h', 's', 'l', 'a']:
            current_param = part
        elif current_param and part:
            try:
                value = float(part)
                if current_param == 'h':
                    value = normalize_hue(value)
                elif current_param == 'a':
                    value = clip_value(value, 0, 1)
                else:  # s and l
                    value = clip_value(value)
                params[current_param] = value
            except ValueError:
                continue
            current_param = None  # Reset after processing a value
    
    return params

def calculate_color(base_rgb, color_mode="RGB", h_shift=0, s_mult=1.0, l_mult=1.0, alpha=1.0):
    # Calculate the final color based on the color mode and parameters.
    if color_mode == "RGB":
        # In RGB mode, only use lightness multiplier
        rgb_values = tuple(max(0, min(255, int(v * l_mult))) for v in base_rgb)
        return rgb_values, clip_value(alpha, 0, 1)
    else:
        # Convert to HSL, apply modifications, then convert back to RGB
        h, s, l = rgb_to_hsl(*base_rgb)
        
        # Apply modifications
        new_h = normalize_hue(h + h_shift)
        new_s = clip_value(s * s_mult, 0, 100) # Clip to 100%
        new_l = clip_value(l * l_mult, 0 , 100) # Clip to 100%
        
        # Convert back to RGB
        new_rgb = hsl_to_rgb(new_h, new_s, new_l)
        return new_rgb, clip_value(alpha, 0, 1)

def hsl_to_rgb(h, s, l):
    # Convert HSL values to RGB.
    s = s / 100.0
    l = l / 100.0
    
    def hue_to_rgb(p, q, t):
        if t < 0:
            t += 1
        if t > 1:
            t -= 1
        if t < 1/6:
            return p + (q - p) * 6 * t
        if t < 1/2:
            return q
        if t < 2/3:
            return p + (q - p) * (2/3 - t) * 6
        return p

    if s == 0:
        r = g = b = l
    else:
        q = l * (1 + s) if l < 0.5 else l + s - l * s
        p = 2 * l - q
        
        h = h / 360.0
        r = hue_to_rgb(p, q, h + 1/3)
        g = hue_to_rgb(p, q, h)
        b = hue_to_rgb(p, q, h - 1/3)

    return (int(r * 255), int(g * 255), int(b * 255))

    
class StyleSheetLoader(Extension):
    pathChanged = pyqtSignal(str)

    def __init__(self, parent):
        super().__init__(parent)

        self.colorMode = Application.readSetting(PLUGIN_CONFIG, "colorMode", "HSL")

        self.startupStyleSheet = Application.readSetting(PLUGIN_CONFIG, "startupStyleSheet", "")
        self.path = self.startupStyleSheet
        self.useStartup = self.startupStyleSheet != ""

        self.customResourcePrefix = Application.readSetting(PLUGIN_CONFIG, "customResourcePrefix", "stylesheet")
        self.searchInStyleSheetDir = Application.readSetting(PLUGIN_CONFIG, "useStyleSheetDirAsResourcePath", "True") == "True"
        
        # Initialize the checkbox as a class variable
        self.useAsResourcePathCheckbox = QCheckBox()
        # Update resource path on initialization
        self.updateResPath()

    def setup(self):
        appNotifier = Application.instance().notifier()
        appNotifier.setActive(True)
        appNotifier.windowCreated.connect(self.loadOnStartup)

    def initialSetup(self):
        print("Performing initial setup...")
        self.updateResPath()
        if self.startupStyleSheet:
            print(f"Loading startup stylesheet: {self.startupStyleSheet}")
            self.importStylesheet(self.startupStyleSheet, addContext=True)
        
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
        colorModeLabel = QLabel("Modify palette colors using:")
        self.colorModeToolTipString = """
                <table cellpadding="2" cellspacing="4" cellspacing="0" width="100%" border="0">
                    <tr>
                        <td>If present in stylesheet. Syntax:</td>
                    </tr>
                    <tr style="background: palette(button); color: palette(button-text)">
                        <td><center><code>color: QPalette.Highlight(h: -10, s: 1.4, l: 0.3, a: 0.8);</code></center></td>
                    </tr>
                    <tr>
                        <td>
                            &nbsp;&nbsp;<b>HSL:</b> <br>
                            <code>&nbsp;&nbsp;&nbsp;&nbsp;h: Int&nbsp;&nbsp; - Hue shift degrees <br>
                            &nbsp;&nbsp;&nbsp;&nbsp;s: Float - Saturation multiplier <br>
                            &nbsp;&nbsp;&nbsp;&nbsp;l: Float - Lightness multiplier <br>
                            &nbsp;&nbsp;&nbsp;&nbsp;a: Float - Alpha value</code><br>
                            &nbsp;&nbsp;<b>RGB:</b> <br>
                            <code>&nbsp;&nbsp;&nbsp;&nbsp;l: Float - Multiplier <br>
                            &nbsp;&nbsp;&nbsp;&nbsp;a: Float - Alpha value</code>
                        </td>
                    </tr>
                </table>
            """
        self.colorModeToolTipStylesheet = """QToolTip {padding: 2px; min-width: 474px; font-size: 13px;}"""
        colorModeLabel.setToolTip(self.colorModeToolTipString)
        colorModeLabel.setStyleSheet(self.colorModeToolTipStylesheet)
        self.colorModeCombo = QComboBox()
        self.colorModeCombo.addItems(["HSL", "RGB"])
        self.colorModeCombo.setCurrentText(self.colorMode)
        self.colorModeCombo.currentTextChanged.connect(self.setColorMode)
        self.colorModeCombo.setToolTip(self.colorModeToolTipString)
        self.colorModeCombo.setStyleSheet(self.colorModeToolTipStylesheet)
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

        try:
            # Force update resource path before loading stylesheet
            self.updateResPath()
            
            if not QFileInfo(path).exists():
                self.showWarningMessage(f"\"{path}\" does not exist!", addContext)
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
                if PRINT_STYLESHEET:
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
                
             # Add debug information
            if DEBUG_MODE:
                print(f"Resource paths for prefix '{self.customResourcePrefix}': {QDir.searchPaths(self.customResourcePrefix)}")
            
        except Exception as e:
            print(f"Error importing stylesheet: {e}")
            self.showWarningMessage(f"Error loading stylesheet: {str(e)}", addContext)
            
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
        
    def updateResPath(self):
        try:
            if self.searchInStyleSheetDir and self.startupStyleSheet:
                resource_path = os.path.dirname(self.startupStyleSheet)
                if os.path.exists(resource_path):
                    QDir.setSearchPaths(self.customResourcePrefix, [resource_path])
                    if DEBUG_MODE:
                        print(f"Resource path set to: {resource_path}")
                        # Verify the search paths were set
                        current_paths = QDir.searchPaths(self.customResourcePrefix)
                        print(f"Verified search paths: {current_paths}")
                        # Verify if specific image files exist
                        for img in ['close-light.svg', 'normal-light.svg', 'minimize-light.svg', 'maximize-light.svg']:
                            full_path = os.path.join(resource_path, 'images', img)
                            print(f"Checking image file: {full_path} - Exists: {os.path.exists(full_path)}")
                elif DEBUG_MODE:
                    print(f"Warning: Resource path does not exist: {resource_path}")
            else:
                QDir.setSearchPaths(self.customResourcePrefix, [])
                if DEBUG_MODE:
                    print("Resource paths cleared")
        except Exception as e:
            if DEBUG_MODE:
                print(f"Error updating resource path: {e}")
            
    def setResPrefix(self):
        self.customResourcePrefix = self.resPrefixEdit.text()
        # Write the updated resource prefix to settings
        Application.writeSetting(PLUGIN_CONFIG, "customResourcePrefix", self.customResourcePrefix)
        # Update the resource path and reload the stylesheet
        self.updateResPath()
        if self.path:
            self.lineEditImport()


    def setColorMode(self, mode):
        self.colorMode = mode
        Application.writeSetting(PLUGIN_CONFIG, "colorMode", mode)
        # Reload stylesheet if path exists
        if self.path:
            self.lineEditImport()

    def replace_placeholders(self, stylesheet):
        palette_rgb_values = get_palette_rgb_values()
        
        # Pattern to match QPalette.Color with optional parameters
        pattern = re.compile(r'QPalette\.(\w+)(?:\((.*?)\))?')
        
        def replace_match(match):
            base_name = match.group(1)
            param_str = match.group(2)  # This will be None if no parentheses
            
            if base_name not in palette_rgb_values:
                return match.group(0)
                
            # Parse parameters if they exist, otherwise use defaults
            params = parse_color_params(param_str) if param_str is not None else {'h': 0, 's': 1.0, 'l': 1.0, 'a': 1.0}
            
            # Calculate new color
            color_values, alpha = calculate_color(
                palette_rgb_values[base_name],
                self.colorMode,
                params['h'],
                params['s'],
                params['l'],
                params['a']
            )
            
            # Format output string
            if self.colorMode == "RGB":
                if abs(alpha - 1.0) < 0.001:
                    return f"rgb({color_values[0]}, {color_values[1]}, {color_values[2]})"
                else:
                    return f"rgba({color_values[0]}, {color_values[1]}, {color_values[2]}, {alpha:.2f})"
            else:
                h, s, l = rgb_to_hsl(*color_values)
                if abs(alpha - 1.0) < 0.001:
                    return f"hsl({int(h)}, {int(s)}%, {int(l)}%)"
                else:
                    return f"hsla({int(h)}, {int(s)}%, {int(l)}%, {alpha:.2f})"
        
        return pattern.sub(replace_match, stylesheet)

    def correct_image_paths(self, stylesheet, base_path):
        
        # Ensures that any relative paths in the stylesheet are converted to the correct format
        # using the resource prefix system.
        
        if DEBUG_MODE:
            print(f"Processing stylesheet paths with base_path: {base_path}")
            print(f"Current resource prefix: {self.customResourcePrefix}")
            print(f"Search paths before correction: {QDir.searchPaths(self.customResourcePrefix)}")

        pattern = re.compile(r'url\(([^)]+)\)')

        def replace_url(match):
            url = match.group(1).strip('\'"')
            
            # If the URL already starts with the resource prefix, leave it as is
            if url.startswith(f'{self.customResourcePrefix}:'):
                if DEBUG_MODE:
                    print(f"URL already has prefix: {url}")
                return f"url('{url}')"
                
            # If it's a relative path and we're using resource paths
            if not os.path.isabs(url) and self.useAsResourcePathCheckbox.isChecked():
                # Just add the resource prefix
                url = f"{self.customResourcePrefix}:{url}"
            else:
                # For absolute paths or when not using resource system
                url = os.path.join(base_path, url).replace('\\', '/')
            
            if DEBUG_MODE:
                print(f"Corrected URL: {url}")
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
def test_replace_placeholders():
    loader = StyleSheetLoader(None)
    processed_content = loader.replace_placeholders(qss_content)
    print("Processed QSS content:\n", processed_content)


def test_style_sheet_parser():
    print("\nRunning style sheet parser tests...")
    # Test cases for the stylesheet parser
    test_cases = [
        # Basic syntax tests
        ("QPalette.Highlight(h: -2, s: 1.4, l: 1.04, a: 0.8)",
         "Valid basic syntax with all parameters"),
        
        # Spacing variations
        ("QPalette.Highlight(h:-2,s:1.4,l:1.04,a:0.8)",
         "No spaces"),
        ("QPalette.Highlight( h: -2  s: 1.4  l: 1.04  a: 0.8 )",
         "Extra spaces"),
        ("QPalette.Highlight(   h: -2, s: 1.4, l:1.04 , a:0.8   )",
         "Irregular spaces"),
        
        # Parameter order variations
        ("QPalette.Highlight(s: 1.4, h: -2, a: 0.8, l: 1.04)",
         "Different parameter order"),
        
        # Optional parameters
        ("QPalette.Highlight(h: -2)",
         "Single parameter"),
        ("QPalette.Highlight(s: 1.4, l: 1.04)",
         "Two parameters"),
        ("QPalette.Highlight()",
         "No parameters"),
        
        # Value range tests
        ("QPalette.Highlight(h: 850)",
         "Hue > 359"),
        ("QPalette.Highlight(h: -900)",
         "Negative hue"),
        ("QPalette.Highlight(s: 2.5)",
         "Saturation > 1"),
        ("QPalette.Highlight(s: -0.5)",
         "Negative saturation"),
        ("QPalette.Highlight(a: 1.5)",
         "Alpha > 1"),
        
        # Edge cases
        ("QPalette.Highlight(h: 0, s: 0, l: 0, a: 0)",
         "Zero values"),
        ("QPalette.Highlight(h:,s:,l:,a:)",
         "Empty values"),
        ("QPalette.Highlight(invalid)",
         "Invalid content"),
    ]

    test_qss = """
    QWidget {
        background-color: %s;
    }
    """

    for test_case, description in test_cases:
        print(f"\nTesting: {description}")
        print(f"Input: {test_case}")
        qss = test_qss % test_case
        # Create a StyleSheetLoader instance and process the stylesheet
        # loader = StyleSheetLoader(None)
        # result = loader.replace_placeholders(qss)
        # print(f"Output: {result}")

# Function to test specific color transformations
def test_color_transformations():
    print("\nRunning color transformation tests...")
    test_colors = [
        # Test extreme hue wrapping
        {"h": 720, "s": 1.0, "l": 1.0},  # Should wrap to 0
        {"h": -180, "s": 1.0, "l": 1.0}, # Should become 180
        
        # Test saturation clipping
        {"h": 0, "s": 2.0, "l": 1.0},    # Should clip to 100%
        {"h": 0, "s": -0.5, "l": 1.0},   # Should clip to 0%
        
        # Test lightness variations
        {"h": 0, "s": 1.0, "l": 1.5},    # 150% lightness
        {"h": 0, "s": 1.0, "l": 0.5},    # 50% lightness
        
        # Test alpha variations
        {"h": 0, "s": 1.0, "l": 1.0, "a": 0.5},  # 50% opacity
        {"h": 0, "s": 1.0, "l": 1.0, "a": 1.5},  # Should clip to 1.0
    ]

    base_color = (255, 0, 0)  # Pure red as base color
    for params in test_colors:
        print("\nTesting color transformation:")
        print(f"Input parameters: {params}")
        h_shift = params.get("h", 0)
        s_mult = params.get("s", 1.0)
        l_mult = params.get("l", 1.0)
        alpha = params.get("a", 1.0)
        
        # Test both RGB and HSL modes
        for mode in ["HSL", "RGB"]:
            result = calculate_color(base_color, mode, h_shift, s_mult, l_mult, alpha)
            print(f"{mode} mode result: {result}")

# Run the tests
if DEBUG_MODE:
    test_replace_placeholders()
    test_style_sheet_parser()
    test_color_transformations()
