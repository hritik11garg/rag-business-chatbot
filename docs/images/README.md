# Screenshots & demo media

The README references these files. Drop them here with these exact
names and they render automatically — no README edits needed.

| File | What to capture |
|---|---|
| `demo.gif` | The money shot: upload a PDF → ask a question → answer streams in token by token → sources + confidence badge appear. Keep it under ~15s and ~5 MB. |
| `login.png` | The login / create-organization screen. |
| `upload.png` | The sidebar with several documents listed, mid-upload notice visible. |
| `chat.png` | A completed answer showing the confidence badge and source filenames. |

## Capturing

Run the stack (`docker compose --profile app up`, or the host-dev flow
in [SETUP.md](../../SETUP.md)), then open the demo UI at
http://localhost:5173.

- **Windows:** Win+Shift+S for stills; [ScreenToGif](https://www.screentogif.com/)
  for the GIF (free, exports optimised GIF/MP4 directly).
- Use a narrow browser window (~1200px) so text stays legible when the
  image is scaled down in the README.
- Seed a couple of realistic documents first — an empty knowledge base
  makes a weak screenshot.

> Use non-sensitive sample PDFs. These images end up in a public
> repository, so avoid anything with real customer or personal data.
