Adds functionality to Style Sheet Loader Krita plugin: to modify colors based on the current color theme.

Original plugin by Freya Lupen:
https://invent.kde.org/freyalupen/style-sheet-loader-extension

### Installation:

github:
- Code &rarr; Download zip.

Krita:
- Tools &rarr; Scripts &rarr; Import Python Plugin from File...
- Select the zip and click Yes when prompted to activate
- Restart Krita

Select a style sheet to load:
**Tools &rarr; Scripts &rarr; Load Style Sheet**

---

## Syntax:

### QSS:
```css
QPalette.Highlight(h: -10, s: 1.4, l: 0.3, a: 0.8);
```

**HSL mode:** <br>
  h: Int   - Hue shift degrees <br>
  s: Float - Saturation multiplier <br>
  l: Float - Lightness multiplier <br>
  a: Float - Alpha value
  
**RGB mode:** <br>
  l: Float - Multiplier <br>
  a: Float - Alpha value


### SVG:

**QPalette:** <br>
```css
image: url(stylesheet:graphic.svg).QPalette.Highlight(h: 10, s: 2.4, l: 1.80, a: 1.0);
```

#### Override SVG color:
RGB/RGBA:
```css
image: url(stylesheet:graphic.svg).rgb(123, 60, 84);
image: url(stylesheet:graphic.svg).rgba(123, 60, 84, 200);
```
HSL/HSLA:
```css
image: url(stylesheet:graphic.svg).hsl(222, 84%, 60%);
image: url(stylesheet:graphic.svg).hsla(222, 84%, 60%, 100%);
```

(modified svgs are stored in .processed_svg folder where the qss is loaded from)


#### Available color labels:
```css
QPalette.Window
QPalette.WindowText
QPalette.Base
QPalette.Text
QPalette.Button
QPalette.ButtonText
QPalette.Highlight
QPalette.HighlightedText
QPalette.ToolTipBase
QPalette.ToolTipText
QPalette.AlternateBase
QPalette.Link
QPalette.LinkVisited
```
