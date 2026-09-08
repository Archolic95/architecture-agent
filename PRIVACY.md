# Data handling

Architecture Agent source runs in the execution environment provided by the user's agent host. It reads modeling inputs supplied for the task and writes source, parameters, model files and previews to the chosen project folder.

The package does not contain telemetry, analytics, a hosted model service or credential collection. Dependency setup downloads Python packages from PyPI. A source rebuild of the browser dependencies downloads pinned packages from npm.

The optional local viewer binds to `127.0.0.1` and serves registered artifacts using a per-session token. No model upload is performed by the viewer. Browser-local file imports remain local to the browser. Native Open dispatches only a registered file when enabled and clicked.

The agent host may send prompts, images and outputs to its model provider under that provider's own terms and controls. This package does not replace those policies. Users control the files retained in their workspace and can delete them there.
