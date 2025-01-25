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
import hashlib
import xml.etree.ElementTree as ET
from krita import Extension
from PyQt5.QtWidgets import QFileDialog, QMessageBox, QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QLineEdit, QCheckBox, QApplication, QComboBox
from PyQt5.QtGui import QPalette, QColor
from PyQt5.QtCore import QFile, QIODevice, QMimeDatabase, QFileInfo, QDir, pyqtSignal

EXTENSION_ID = 'pykrita_style_sheet_loader'
MENU_ENTRY = 'Load Style Sheet'
DEBUG_MODE = False
PRINT_STYLESHEET = False

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
    """Clip value between min and max."""
    try:
        value = float(value)
        if value < min_val:
            return min_val
        if max_val is not None and value > max_val:
            return max_val
        return value
    except (TypeError, ValueError):
        return min_val

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
        return rgb_values, clip_value(alpha, 0, 1)  # Ensure alpha is clipped between 0 and 1
    else:
        # Convert to HSL, apply modifications, then convert back to RGB
        h, s, l = rgb_to_hsl(*base_rgb)
        
        # Apply modifications
        new_h = normalize_hue(h + h_shift)
        new_s = clip_value(s * s_mult, 0, 100)
        new_l = clip_value(l * l_mult, 0, 100)
        
        # Convert back to RGB
        new_rgb = hsl_to_rgb(new_h, new_s, new_l)
        return new_rgb, clip_value(alpha, 0, 1)  # Ensure alpha is clipped between 0 and 1

def clip_color_value(value, min_val=0, max_val=255):
    """Clip color values to valid range"""
    return max(min_val, min(max_val, int(round(value))))

def hsl_to_rgb(h, s, l):
    """
    Convert HSL to RGB with value clipping
    h: 0-360
    s: 0-100
    l: 0-100
    Returns: tuple (r, g, b) where r, g, b are 0-255
    """
    # Normalize values
    h = float(h % 360)  # Ensure hue is 0-360
    s = max(0, min(100, float(s))) / 100  # Convert to 0-1
    l = max(0, min(100, float(l))) / 100  # Convert to 0-1

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
        # Achromatic (grey)
        rgb = l, l, l
    else:
        q = l * (1 + s) if l < 0.5 else l + s - l * s
        p = 2 * l - q
        
        h /= 360  # Normalize hue to 0-1
        r = hue_to_rgb(p, q, h + 1/3)
        g = hue_to_rgb(p, q, h)
        b = hue_to_rgb(p, q, h - 1/3)
        rgb = (r, g, b)

    # Convert to 8-bit values with clipping
    return tuple(clip_color_value(x * 255) for x in rgb)


class SVGProcessor:
    def __init__(self, base_path, resource_prefix="stylesheet", search_in_stylesheet_dir=True):
        self.base_path = base_path
        self.resource_prefix = resource_prefix
        self.search_in_stylesheet_dir = search_in_stylesheet_dir
        # Create temp directory for processed SVGs
        self.temp_dir = os.path.join(self.base_path, '.processed_svg')
        os.makedirs(self.temp_dir, exist_ok=True)

    def get_or_process_svg(self, svg_path, palette_color, color_params):
        """Get processed SVG path or create new processed version"""
        # Remove any existing prefix from the path
        if svg_path.startswith(f'{self.resource_prefix}:'):
            svg_path = svg_path[len(f'{self.resource_prefix}:'):]
        
        input_path = os.path.join(self.base_path, svg_path)
        
        # Create unique filename based on parameters
        params_hash = hashlib.md5(f"{palette_color}:{color_params}".encode()).hexdigest()[:8]
        base_name = os.path.splitext(os.path.basename(svg_path))[0]
        output_filename = f"{base_name}_{params_hash}.svg"
        output_path = os.path.join(self.temp_dir, output_filename)
        
        if not os.path.exists(output_path):
            self.process_svg(input_path, output_path, palette_color, color_params)
        
        relative_path = os.path.relpath(output_path, self.base_path).replace("\\","/")
        
        if DEBUG_MODE:
            print(f"[SVG] Processed SVG path: {relative_path}")
            
        return relative_path
        

    def process_svg(self, input_path, output_path, palette_color, color_params):
        """Process SVG file and save with modified colors"""
        try:
            if DEBUG_MODE:
                print(f"[SVG] Processing SVG file:")
                print(f"[SVG]   Input: {input_path}")
                print(f"[SVG]   Output: {output_path}")
                print(f"[SVG]   Palette Color: {palette_color}")
                if palette_color:
                    print(f"[SVG]   Base RGB: {get_palette_rgb_values()[palette_color]}")
                print(f"[SVG]   Color Params: {color_params}")

            tree = ET.parse(input_path)
            root = tree.getroot()
            
            base_rgb = get_palette_rgb_values()[palette_color] if palette_color else None
            
            for elem in root.iter():
                if 'style' in elem.attrib:
                    orig_style = elem.attrib['style']
                    if DEBUG_MODE:
                        print(f"[SVG]   Original style: {orig_style}")
                    elem.attrib['style'] = self.transform_style_colors(orig_style, base_rgb, color_params)
                    if DEBUG_MODE:
                        print(f"[SVG]   Modified style: {elem.attrib['style']}")

            tree.write(output_path, encoding='utf-8', xml_declaration=True)
            
        except Exception as e:
            print(f"[SVG] Error: {e}")
            raise

    def transform_style_colors(self, style, base_rgb, params):
        """Transform colors and opacity in SVG style attribute"""
        # Early debug to verify inputs
        print(f"[SVG Color] Starting transformation:")
        print(f"[SVG Color] Input style: {style}")
        print(f"[SVG Color] Base RGB: {base_rgb}")
        print(f"[SVG Color] Parameters: {params}")

        if not style:
            return style

        # Split into properties
        properties = [p.strip() for p in style.split(';') if p.strip()]
        modified_properties = []

        try:
            # Calculate final color
            if base_rgb:
                # Convert base color to HSL
                base_h, base_s, base_l = rgb_to_hsl(*base_rgb)
                print(f"[SVG Color] Base HSL: h={base_h:.1f}, s={base_s:.1f}, l={base_l:.1f}")

                if params:
                    # Get modifiers
                    h_mod = float(params.get('h', 0))
                    s_mod = float(params.get('s', 1.0))
                    l_mod = float(params.get('l', 1.0))
                    
                    # Apply modifiers
                    h = normalize_hue(base_h + h_mod)
                    s = base_s * s_mod  # Multiply base saturation
                    l = base_l * l_mod  # Multiply base lightness
                    
                    # Ensure valid ranges
                    s = clip_value(s, 0, 100)
                    l = clip_value(l, 0, 100)
                    
                    print(f"[SVG Color] Modified HSL: h={h:.1f}, s={s:.1f}, l={l:.1f}")
                    print(f"[SVG Color] Applied modifiers: h+={h_mod}, s*={s_mod}, l*={l_mod}")
                else:
                    h, s, l = base_h, base_s, base_l

                # Convert back to RGB
                final_rgb = [int(x) for x in hsl_to_rgb(h, s, l)]
                alpha = float(params.get('a', 1.0)) if params else 1.0
                
                print(f"[SVG Color] Final RGB: {final_rgb}, Alpha: {alpha}")
            else:
                # Direct color mode (RGB or HSL)
                if isinstance(params, dict):
                    if 'rgb' in params:
                        final_rgb = params['rgb']
                        alpha = params.get('a', 1.0)
                    else:
                        h = float(params.get('h', 0))
                        s = float(params.get('s', 100))
                        l = float(params.get('l', 50))
                        final_rgb = [int(x) for x in hsl_to_rgb(h, s, l)]
                        alpha = float(params.get('a', 1.0))

            # Apply colors to style properties
            for prop in properties:
                if ':' not in prop:
                    modified_properties.append(prop)
                    continue

                name, value = [x.strip() for x in prop.split(':', 1)]
                
                if name in ['fill', 'color', 'stroke'] and value.lower() != 'none':
                    modified_properties.append(f"{name}: rgb({final_rgb[0]}, {final_rgb[1]}, {final_rgb[2]})")
                    if abs(alpha - 1.0) > 0.001:
                        modified_properties.append(f"{name}-opacity: {alpha:.3f}")
                elif not name.endswith('-opacity'):
                    modified_properties.append(f"{name}: {value}")

            result = '; '.join(modified_properties)
            print(f"[SVG Color] Final style: {result}")
            return result

        except Exception as e:
            print(f"[SVG Color] Error during transformation: {e}")
            return style


        
    def normalize_color_params(self, params):
        """Normalize color parameters to ensure proper ranges"""
        if not isinstance(params, dict):
            return {'h': 0, 's': 100, 'l': 50, 'a': 1.0}
            
        normalized = {}
        
        # Handle hue (0-360)
        normalized['h'] = normalize_hue(float(params.get('h', 0)))
        
        # Handle saturation (0-100%)
        s_val = float(params.get('s', 1.0))
        if s_val <= 2.0:  # Assuming multiplier format
            normalized['s'] = clip_value(s_val * 100, 0, 100)
        else:  # Assuming percentage format
            normalized['s'] = clip_value(s_val, 0, 100)
        
        # Handle lightness (0-100%)
        l_val = float(params.get('l', 1.0))
        if l_val <= 2.0:  # Assuming multiplier format
            normalized['l'] = clip_value(l_val * 100, 0, 100)
        else:  # Assuming percentage format
            normalized['l'] = clip_value(l_val, 0, 100)
        
        # Handle alpha (0-1)
        a_val = float(params.get('a', 1.0))
        if a_val > 1:  # Assuming 0-255 format
            normalized['a'] = clip_value(a_val / 255, 0, 1)
        else:  # Assuming 0-1 format
            normalized['a'] = clip_value(a_val, 0, 1)
        
        if DEBUG_MODE:
            print(f"[SVG] Normalizing params: {params}")
            print(f"[SVG] Normalized result: {normalized}")
        
        return normalized

        
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
        self.base_path = None
        self.useAsResourcePathCheckbox = QCheckBox()
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
                        <td><code>&nbsp;&nbsp;&nbsp;&nbsp;color: QPalette.Highlight(h: -10, s: 1.4, l: 0.3, a: 0.8);</code></td>
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
                            &nbsp;&nbsp;&nbsp;&nbsp;a: Float - Alpha value</code><br>
                        </td>
                    </tr>
                    <tr>
                        <td><h3>SVG coloring</h3></td>
                    </tr>
                    <tr>
                        <td>&nbsp;&nbsp;<b>QPalette:</b></td>
                    </tr>            
                    <tr  style="background: palette(button); color: palette(button-text)">
                        <td><code>&nbsp;image: url(stylesheet:graphic.svg).QPalette.Highlight(h: 10, s: 2.4, l: 1.80, a: 1.0);</code></td>
                    </tr>
                    <tr>
                        <td><br>Override SVG color:<br>
                        &nbsp;&nbsp;<b>RGB/RGBA:</b></td>
                    </tr>
                    <tr  style="background: palette(button); color: palette(button-text)">
                        <td><code>&nbsp;&nbsp;&nbsp;&nbsp;image: url(stylesheet:graphic.svg).rgb(123, 60, 84);</code></td>
                    </tr>
                    <tr  style="background: palette(button); color: palette(button-text)">
                        <td><code>&nbsp;&nbsp;&nbsp;&nbsp;image: url(stylesheet:graphic.svg).rgba(123, 60, 84, 200);</code></td>
                    </tr>
                    <tr>
                        <td>&nbsp;&nbsp;<b>HSL/HSLA:</b></td>
                    </tr>
                    <tr  style="background: palette(button); color: palette(button-text)">
                        <td><code>&nbsp;&nbsp;&nbsp;&nbsp;image: url(stylesheet:graphic.svg).hsl(222, 84%, 60%);</code></td>
                    </tr>
                    <tr  style="background: palette(button); color: palette(button-text)">
                        <td><code>&nbsp;&nbsp;&nbsp;&nbsp;image: url(stylesheet:graphic.svg).hsla(222, 84%, 60%, 100%);</code></td>
                    </tr>
                </table>
            """
        self.colorModeToolTipStylesheet = """QToolTip {padding: 2px; min-width: 690px; font-size: 13px;}"""
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
        """Import and apply a stylesheet"""
        if not path:
            return

        try:
            self.updateResPath()
            
            if not QFileInfo(path).exists():
                self.showWarningMessage(f"\"{path}\" does not exist!", addContext)
                return
                    
            mimeType = QMimeDatabase().mimeTypeForFile(path)
            if not mimeType.inherits("text/plain"):
                self.showWarningMessage("\"%s\" does not appear to be a text file!" % (path), addContext)
                return

            file = QFile(path)
            if file.open(QIODevice.ReadOnly | QIODevice.Text):
                try:
                    # Read QByteArray data
                    qbytearray = file.readAll()
                    
                    if DEBUG_MODE:
                        print(f"[DEBUG] Raw data type: {type(qbytearray)}")
                    
                    # Convert QByteArray to Python string
                    try:
                        stylesheet = str(qbytearray, encoding='utf-8')
                    except UnicodeDecodeError:
                        # Fallback to system default encoding if UTF-8 fails
                        stylesheet = str(qbytearray, encoding='ascii', errors='ignore')
                    
                    if DEBUG_MODE:
                        print(f"[DEBUG] Base path: {os.path.dirname(os.path.abspath(path))}")
                        print(f"[DEBUG] Stylesheet length: {len(stylesheet)}")
                        print(f"[DEBUG] Stylesheet type: {type(stylesheet)}")
                    
                    if PRINT_STYLESHEET and DEBUG_MODE:
                        print("\nOriginal stylesheet:")
                        print(stylesheet[:800])  # Print first 800 chars
                    
                    # Update base path for SVG processing
                    self.base_path = os.path.dirname(os.path.abspath(path))
                    
                    # Process SVG URLs first
                    processed_stylesheet = self.process_svg_urls(stylesheet, self.base_path)
                    
                    # Then replace color placeholders
                    final_stylesheet = self.replace_placeholders(processed_stylesheet)
                    
                    if PRINT_STYLESHEET:
                        print("\nProcessed stylesheet:\n", final_stylesheet)
                        #print(final_stylesheet[:500])  # Print first 500 chars
                    
                    # Apply the stylesheet
                    active_window = Application.activeWindow()
                    if active_window is not None and hasattr(active_window, 'qwindow'):
                        try:
                            active_window.qwindow().setStyleSheet(final_stylesheet)
                        except Exception as e:
                            print(f"Failed to set stylesheet: {e}")
                            raise
                    else:
                        print("No active window available to apply stylesheet")

                    self.setPath(path)
                    
                except Exception as e:
                    print(f"Error processing stylesheet: {e}")
                    raise
                finally:
                    file.close()
            else:
                self.showWarningMessage("Failed to open \"%s\"." % (path), addContext)
                
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
        
    def process_svg(self, input_path, output_path, palette_color, color_params):
        """Process SVG file and save with modified colors"""
        if DEBUG_MODE:
            print(f"[SVG] Processing SVG:")
            print(f"[SVG]   Input: {input_path}")
            print(f"[SVG]   Output: {output_path}")
            print(f"[SVG]   Palette Color: {palette_color}")
            print(f"[SVG]   Color Params: {color_params}")

        try:
            # Parse SVG content
            tree = ET.parse(input_path)
            root = tree.getroot()
            
            if palette_color:
                # Handle QPalette colors
                base_rgb = get_palette_rgb_values()[palette_color]
                params = parse_color_params(color_params)
            else:
                # Handle direct HSL/HSLA values
                try:
                    if isinstance(color_params, dict):
                        params = color_params
                        base_rgb = None  # Not needed for direct HSL values
                    else:
                        # Parse "h,s%,l%[,a]" format
                        parts = [x.strip() for x in color_params.split(',')]
                        params = {}
                        
                        # Parse hue
                        params['h'] = float(parts[0].rstrip('°'))
                        
                        # Parse saturation
                        s_val = parts[1].rstrip('%')
                        params['s'] = float(s_val)
                        
                        # Parse lightness
                        l_val = parts[2].rstrip('%')
                        params['l'] = float(l_val)
                        
                        # Parse alpha if present
                        if len(parts) >= 4:
                            a_val = parts[3].rstrip('%')
                            params['a'] = float(a_val) / 100.0 if '%' in parts[3] else float(a_val)
                        else:
                            params['a'] = 1.0
                        
                        base_rgb = None  # Not needed for direct HSL values
                        
                except Exception as e:
                    print(f"[SVG] Error parsing color params: {e}")
                    print(f"[SVG] Color params received: {color_params}")
                    raise
            
            # Process all elements with style attributes
            for elem in root.iter():
                if 'style' in elem.attrib:
                    style = elem.attrib['style']
                    modified_style = self.transform_style_colors(style, base_rgb, params)
                    elem.attrib['style'] = modified_style

            # Create output directory if needed
            os.makedirs(os.path.dirname(output_path), exist_ok=True)
                    
            # Save processed SVG
            tree.write(output_path, encoding='utf-8', xml_declaration=True)
            
            if DEBUG_MODE:
                print(f"[SVG] Successfully saved processed SVG to: {output_path}")

        except Exception as e:
            print(f"[SVG] Error processing SVG: {e}")
            raise
            
    def process_svg_urls(self, stylesheet, base_path):
        """Process SVG URLs in stylesheet"""
        if not isinstance(stylesheet, str):
            print(f"[DEBUG] Invalid stylesheet type in process_svg_urls: {type(stylesheet)}")
            return stylesheet
            
        if not base_path:
            return stylesheet
            
        try:
            if DEBUG_MODE:
                print(f"[DEBUG] Processing SVG URLs with base path: {base_path}")
                
            self.base_path = base_path
            svg_processor = SVGProcessor(
                base_path, 
                self.customResourcePrefix, 
                self.searchInStyleSheetDir
            )
            
            # Updated pattern to support all color formats
            svg_pattern = re.compile(
                r'(url\([\'"]?([^\'"\)]+\.svg)[\'"]?\))'  # Full URL and path
                r'\s*\.\s*'  # Dot with optional whitespace
                r'(?:'  # Non-capturing group for alternatives
                r'QPalette\.(\w+)(?:\((.*?)\))?|'  # QPalette.Color(params)
                r'hsla?\((.*?)\)|'  # hsl(params) or hsla(params)
                r'rgba?\((.*?)\)'   # rgb(params) or rgba(params)
                r')'
            )
            
            def handle_svg_match(match):
                if DEBUG_MODE:
                    print("\n[SVG] Processing match:")
                    print(f"[SVG] Full match: {match.group(0)}")
                
                url = match.group(2)
                if not url:
                    return match.group(0)
                
                try:
                    # QPalette case
                    if match.group(3):
                        return self.process_qpalette(url, match.group(3), match.group(4))
                    # HSL/HSLA case
                    elif match.group(5):
                        params = match.group(5)
                        with_alpha = 'hsla' in match.group(0).lower()
                        return self.process_hsl(url, params, with_alpha)
                    # RGB/RGBA case
                    elif match.group(6):
                        params = match.group(6)
                        with_alpha = 'rgba' in match.group(0).lower()
                        return self.process_rgb(url, params, with_alpha)
                except Exception as e:
                    print(f"[SVG] Error processing match: {e}")
                    return match.group(0)
                
                return match.group(0)
            
            return svg_pattern.sub(handle_svg_match, stylesheet)
            
        except Exception as e:
            print(f"[DEBUG] Error in process_svg_urls: {e}")
            return stylesheet


    def process_qpalette(self, url, color, params):
        """Process QPalette colors"""
        try:
            if DEBUG_MODE:
                print(f"[QPalette] Processing: color={color}, params={params}")
                print(f"[QPalette] Using color mode: {self.colorMode}")
            
            # Remove any existing prefix from the path
            if url.startswith(f'{self.customResourcePrefix}:'):
                url = url[len(f'{self.customResourcePrefix}:'):]
            
            # Get the base RGB values from the palette
            base_rgb = get_palette_rgb_values()[color]
            
            if DEBUG_MODE:
                print(f"[QPalette] Base RGB from palette: {base_rgb}")
            
            # Parse parameters if provided
            if params:
                try:
                    # Parse parameters into a dict
                    param_parts = re.findall(r'([hsla])\s*:\s*([-+]?\d*\.?\d+)', params)
                    color_params = {}
                    for key, value in param_parts:
                        color_params[key] = float(value)
                    
                    if DEBUG_MODE:
                        print(f"[QPalette] Parsed parameters: {color_params}")
                    
                    # Use the existing colorMode setting
                    modified_rgb = list(base_rgb)  # Start with base RGB
                    alpha = color_params.get('a', 1.0)  # Get alpha value early
                    
                    if self.colorMode == 'HSL': # HSL mode processing   
                        h, s, l = rgb_to_hsl(*base_rgb)
                        
                        if 'h' in color_params:
                            h = normalize_hue(h + color_params['h'])
                        if 's' in color_params:
                            s = clip_value(s * color_params['s'], 0, 100)
                        if 'l' in color_params:
                            l = clip_value(l * color_params['l'], 0, 100)
                        
                        modified_rgb = [int(x) for x in hsl_to_rgb(h, s, l)]
                        
                        if DEBUG_MODE:
                            print(f"[QPalette] HSL mode - Modified HSL: h={h:.1f}, s={s:.1f}, l={l:.1f}")
                            print(f"[QPalette] HSL mode - Modified RGB: {modified_rgb}, Alpha: {alpha}")
                    
                    else:  # RGB mode
                        r, g, b = base_rgb

                        if 'l' in color_params:
                            l_multiplier = color_params.pop('l')  # Remove 'l' after getting its value
                            r = clip_color_value(r * l_multiplier)
                            g = clip_color_value(g * l_multiplier)
                            b = clip_color_value(b * l_multiplier)
                            modified_rgb = [r, g, b]
                        else:
                            modified_rgb = list(base_rgb)
                        
                                            
                        if 'h' in color_params:
                            color_params.pop("h")
                        
                        if 's' in color_params:
                            color_params.pop("s")
                        
                        if DEBUG_MODE:
                            print(f"[QPalette] RGB mode - Modified RGB: {modified_rgb}, Alpha: {alpha}")

                        modified_rgb = [int(x) for x in modified_rgb]  # Ensure integer values
                    
                    color_params = {
                        'rgb': [int(x) for x in modified_rgb],
                        'a': alpha
                    }
                    
                except Exception as e:
                    if DEBUG_MODE:
                        print(f"[QPalette] Error during color processing: {e}")
                        import traceback
                        traceback.print_exc()
                    # Don't reset to base_rgb on error, keep any successful modifications
                    color_params = {
                        'rgb': [int(x) for x in modified_rgb],
                        'a': alpha
                    }
            else:
                color_params = {'rgb': base_rgb, 'a': 1.0}
                
            if DEBUG_MODE:
                print(f"[QPalette] Final color parameters: {color_params}")
            
            svg_processor = SVGProcessor(
                self.base_path,
                self.customResourcePrefix,
                self.searchInStyleSheetDir
            )
            new_path = svg_processor.get_or_process_svg(url, None, color_params)
            
            if self.searchInStyleSheetDir:
                new_path = f"{self.customResourcePrefix}:{new_path}"
            
            return f"url('{new_path}')"
            
        except Exception as e:
            print(f"Error in process_qpalette: {e}")
            if not url.startswith(f"{self.customResourcePrefix}:"):
                url = f"{self.customResourcePrefix}:{url}"
            return f"url('{url}')"


    def adjust_rgb_saturation(r, g, b, s_multiplier):
        """Adjust RGB saturation without converting to HSL"""
        # Find the average value
        avg = (r + g + b) / 3
        
        # Apply saturation multiplier
        r = clip_color_value(avg + (r - avg) * s_multiplier)
        g = clip_color_value(avg + (g - avg) * s_multiplier)
        b = clip_color_value(avg + (b - avg) * s_multiplier)
        
        return [int(r), int(g), int(b)]


    def process_hsl(self, url, params, with_alpha=False):
        """Process HSL/HSLA colors"""
        try:
            # Handle both space and comma separated values
            parts = [p.strip() for p in re.split(r'[,\s]+', params)]
            
            if DEBUG_MODE:
                print(f"[HSL] Processing parts: {parts}")
            
            # Extract HSL and alpha values
            if len(parts) >= 4:  # HSLA format
                h, s, l, a = parts[:4]
                with_alpha = True
            elif len(parts) >= 3:  # HSL format
                h, s, l = parts[:3]
                a = "100%"
            else:
                raise ValueError(f"Not enough values in HSL/HSLA: {params}")
            
            # Parse color values
            h = float(h.rstrip('°'))
            s = float(s.rstrip('%'))
            l = float(l.rstrip('%'))
            
            # Parse alpha
            if '%' in str(a):
                a = float(a.rstrip('%')) / 100.0
            else:
                a = float(a)
            
            color_params = {
                'h': h,
                's': s,
                'l': l,
                'a': clip_value(a, 0, 1)
            }
            
            if DEBUG_MODE:
                print(f"[HSL] Processing with params: {color_params}")
            
            svg_processor = SVGProcessor(
                self.base_path,
                self.customResourcePrefix,
                self.searchInStyleSheetDir
            )
            new_path = svg_processor.get_or_process_svg(url, None, color_params)
            
            if self.searchInStyleSheetDir and not new_path.startswith(f"{self.customResourcePrefix}:"):
                new_path = f"{self.customResourcePrefix}:{new_path}"
            
            return f"url('{new_path}')"
        except Exception as e:
            print(f"Error processing HSL/HSLA: {e}")
            if not url.startswith(f"{self.customResourcePrefix}:"):
                url = f"{self.customResourcePrefix}:{url}"
            return f"url('{url}')"


    def process_rgb(self, url, params, with_alpha=False):
        """Process RGB/RGBA colors"""
        try:
            parts = [p.strip() for p in re.split(r'[,\s]+', params)]
            
            if DEBUG_MODE:
                print(f"[RGB] Processing parts: {parts}")
            
            # Extract RGB and alpha values
            if len(parts) >= 4:  # RGBA format
                r, g, b, a = [float(x) for x in parts[:4]]
                with_alpha = True
            elif len(parts) >= 3:  # RGB format
                r, g, b = [float(x) for x in parts[:3]]
                a = 255.0
            else:
                raise ValueError(f"Not enough values in RGB/RGBA: {params}")
            
            # Ensure RGB values are in 0-255 range
            r = clip_color_value(r)
            g = clip_color_value(g)
            b = clip_color_value(b)
            
            # Convert alpha to 0-1 range
            alpha = clip_value(a / 255.0, 0, 1) if a > 1 else clip_value(a, 0, 1)
            
            color_params = {
                'rgb': (int(r), int(g), int(b)),
                'a': alpha
            }
            
            if DEBUG_MODE:
                print(f"[RGB] Processing with params: {color_params}")
            
            svg_processor = SVGProcessor(
                self.base_path,
                self.customResourcePrefix,
                self.searchInStyleSheetDir
            )
            new_path = svg_processor.get_or_process_svg(url, None, color_params)
            
            if self.searchInStyleSheetDir:
                new_path = f"{self.customResourcePrefix}:{new_path}"
            
            return f"url('{new_path}')"
        except Exception as e:
            print(f"Error processing RGB/RGBA: {e}")
            if not url.startswith(f"{self.customResourcePrefix}:"):
                url = f"{self.customResourcePrefix}:{url}"
            return f"url('{url}')"


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
if __name__ == '__main__' and DEBUG_MODE:
    test_replace_placeholders()
    test_style_sheet_parser()
    test_color_transformations()
