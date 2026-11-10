<div align="center">

# Campus Copilot brand

Bone and olive, one mark, one typeface.

</div>

## Idea

Campus Copilot answers questions and proposes actions, but the student always has the final say. The brand is calm and plain: it should feel like a reliable person at the next desk, not a gadget.

## The mark

A bold letter C with a solid dot in its opening. The C is the product. The dot is the action the assistant has proposed and is holding until you confirm it. It reads clearly at 32 px, so the same shape works as the app icon, the browser tab icon and the one-colour notification badge.

## Colour

The palette is the one the app already uses (`frontend/app/globals.css`).

| Name | Hex | Use |
|---|---|---|
| Bone | `#ecebe7` | Page ground, the mark on olive |
| Olive | `#38450f` | Text, buttons, icon tile |
| Muted olive | `#5d683a` | Secondary text |

Bone on olive has a contrast ratio of 8.69:1, above the 4.5:1 minimum for text.

## Type

Hanken Grotesk, medium weight, with tight letter spacing for the wordmark (`-0.03em`). The wordmark is set in text, not drawn.

## Files

| File | What it is |
|---|---|
| `icon.svg` | App icon: bone mark on an olive rounded tile. Source for the 192 and 512 px PNGs and the favicon |
| `icon-maskable.svg` | Same icon, full square with no rounded corners, so the phone can crop it to any shape. The mark stays inside the central 80% |
| `mark.svg` | The mark alone in olive, for the header |
| `badge.svg` | White mark on a transparent background, for notification badges, which the phone recolours |
| `banner.svg` | The README banner: the mark, the name and the tagline. The text is drawn from the typeface's outlines, so it looks right with no font installed |

Exported files are in `frontend/public/icons/` (`icon-192.png`, `icon-512.png`, `icon-maskable-512.png`, `badge-96.png`), plus `frontend/app/favicon.ico` and `frontend/app/apple-icon.png`. To rebuild them, run `rsvg-convert -w <size> -h <size> assets/brand/<file>.svg -o <output>.png`.

## Rules

- Use the mark only in bone on olive, olive on bone, or white on transparent for the badge.
- Do not stretch, rotate, outline or recolour it, and do not add effects.
- Keep clear space around it of at least the dot's diameter.
- Do not use it smaller than 32 px; below that, use the favicon.
