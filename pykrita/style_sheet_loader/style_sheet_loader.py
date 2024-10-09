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

from krita import Extension
from PyQt5.QtWidgets import QFileDialog, QMessageBox, QDialog, \
                            QVBoxLayout, QHBoxLayout, \
                            QWidget, QLabel, QPushButton, QLineEdit, QCheckBox
from PyQt5.QtCore import QFile, QIODevice, QMimeDatabase, QFileInfo, QDir, pyqtSignal

import os.path

EXTENSION_ID = 'pykrita_style_sheet_loader'
MENU_ENTRY = 'Load Style Sheet'

# Constant string for the config group in kritarc
PLUGIN_CONFIG = "plugin/StyleSheetLoader"

class StyleSheetLoader(Extension):
    pathChanged = pyqtSignal(str)

    def __init__(self, parent):
        super().__init__(parent)

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
        path, _filter = QFileDialog.getOpenFileName(None, "Open a Qt Style Sheet", \
                                    filter="Qt Style Sheets (*.qss *.txt)")
        self.importStylesheet(path)

    def lineEditImport(self):
        self.importStylesheet(self.pathEdit.text())

    def loadOnStartup(self):
        if not self.startupStyleSheet:
            return
        # Notify what we're doing, in case the user forgets it's active or something.
        print("Style Sheet Loader Extension: Loading %s." % self.startupStyleSheet)
        # If the file is changed, we could get errors,
        # so add context to those error dialogs as to where they're coming from.
        self.importStylesheet(self.startupStyleSheet, addContext=True)

    # Do the actual loading.
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

            styleSheet = f"{str(data, 'utf-8')}"
            # There's not really a way to validate the stylesheet,
            # so just let it try to apply whatever's there.
            Application.activeWindow().qwindow().setStyleSheet(styleSheet)

            self.setPath(path)
        else:
            self.showWarningMessage("Failed to open \"%s\"." % (path), addContext)

    def showWarningMessage(self, warning, addContext):
            if addContext:
                warning = "Style Sheet Loader Extension: " + warning
            resultBox = QMessageBox(Application.activeWindow().qwindow())
            resultBox.setText(warning)
            resultBox.setIcon(QMessageBox.Warning)
            resultBox.show()

    # Variable setters --
    def toggleLoadOnStartup(self, isChecked):
        self.useStartup = isChecked
        self.startupStyleSheet = self.path if isChecked else ""
        Krita.writeSetting(PLUGIN_CONFIG, "startupStyleSheet", self.startupStyleSheet)

    def setPath(self, path):
        self.path = path
        # Use a signal and not pathEdit directly, in case we are
        # doing this on startup, where pathEdit doesn't exist.
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
