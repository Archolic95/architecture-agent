# Downloadable interactive preview

Use this delivery when the user needs an interactive preview that can travel
with the model files. The packager uses Python's standard library and the
bundled viewer. It generates no geometry and needs no server, installation,
API key or repository path.

After checking the model, paired preview and generator validation report, run
this command from the skill folder (or use the packager's absolute path):

```sh
python scripts/portable/build_portable.py \
  --model /path/to/revision/model.3dm \
  --preview /path/to/revision/model.preview.json \
  --validation /path/to/revision/validation.json \
  --output /path/to/new-viewer-folder \
  --title "Project title"
```

Use a new output folder. The command refuses an existing destination and checks
the native/preview hashes, component IDs and successful geometry checks in the
generator report before writing output. This binds the existing files to their
report; it does not independently prove native/preview geometric equivalence.
Keep the native model and preview filenames used by that report.

Deliver `model-portable.html` plus the original `.3dm`, retained source,
parameters and validation. Only the HTML is needed to open its embedded
interactive preview; `receipt.json`, `payload.json`, `modules/` and
`bootstrap.runtime.mjs` are build evidence. The HTML embeds the paired files,
viewer modules and license notices. Its runtime uses Blob modules, WebCrypto
SHA-256 and WebGL in the user's desktop browser.

Tell the user to download the HTML and open it in a desktop browser. Do not
present a sandbox or cloud loopback URL as a local viewer. Attachment delivery
and inline execution depend on the host and are not established ChatGPT or
Claude capabilities of this package. If the host cannot provide an HTML
attachment, deliver the ordinary model files and verified static previews.

The portable viewer includes perspective/axonometric cameras, layers,
selection, orbit/zoom, fit, edges and uncapped section cuts. Native model
download is available after file verification. It contains one model and its
paired preview; arbitrary `.3dm` import, native Rhino/Grasshopper dispatch and
live generation are unavailable. Download the native file and open it manually
when further editing is needed.

Inspect the generated result with available tools and report what was actually
checked. Prior Chrome evidence covers a bounded fixture, not every host or
browser. Actual pan, file-drop refusal, WebGL-unavailable download fallback,
browser-saved native-file identity and ChatGPT/Claude attachment delivery remain
unverified; do not turn an implementation path or a unit check into a browser
acceptance claim. Report unsupported display data or failed verification, and
retain the original native files even when an interactive preview cannot open.
