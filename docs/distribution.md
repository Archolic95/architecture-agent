# Distribution

The quickest public release is a clean GitHub repository containing this plugin marketplace and a downloadable source archive. A user can add the repository as a custom marketplace and install the skill. The package is source-based; it does not require a separately installed Rhino MCP plug-in.

Model generation requires a host that can execute compatible Python and inspect files. A cloud execution host's `127.0.0.1` URL is not the user's computer. The portable packager can instead create a self-contained HTML file for the user to download and open in a desktop browser. The recipient needs no Python or local server for that file. Actual attachment delivery and inline execution depend on the host and remain unverified for ChatGPT/Claude.

GitHub publication and the universal Plugins Directory are separate distribution steps. Public directory submissions require verified publisher identity, applicable package/listing checks, policy attestations and review. Listing URLs and the exact five-positive/three-negative test-case requirement apply to remote MCP submissions; they are not universal requirements for skills-only ZIP uploads. This source beta does not claim directory approval. [Submission process](https://developers.openai.com/plugins/deploy/submission), [requirements by submission type](https://developers.openai.com/plugins/deploy/submission-errors).

No hosted server is required. The local viewer serves only explicitly registered files from loopback; the portable viewer embeds its files and uses no external requests. Neither adds telemetry. The host application's model execution, input handling and account limits remain governed by that host.
