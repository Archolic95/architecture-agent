# Distribution

The quickest public release is a clean GitHub repository containing this plugin marketplace and a downloadable source archive. A user can add the repository as a custom marketplace and install the skill. The package is source-based; it does not require a separately installed Rhino MCP plug-in.

This local skill requires a host that can execute Python and open local files. A cloud ChatGPT session can run the modeling source if its workspace provides compatible execution and libraries, but a cloud process's `127.0.0.1` URL is not the user's computer. Deliver downloadable artifacts in that case; do not promise the local viewer or Rhino button works across that boundary.

GitHub publication and the universal Plugins Directory are separate distribution steps. The latter accepts skills-only plugins but requires publisher identity, listing URLs, reviewer test cases and review before publication. This source beta does not claim that approval. [Official plugin packaging](https://developers.openai.com/plugins/build/plugins), [submission process](https://developers.openai.com/plugins/deploy/submission).

No hosted server is required for this release. The browser viewer serves only explicitly registered files from loopback and has no telemetry. The host application's model execution, input handling and account limits remain governed by that host.
