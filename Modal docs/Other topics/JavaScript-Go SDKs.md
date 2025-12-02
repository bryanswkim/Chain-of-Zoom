# Modal SDKs for JavaScript and Go

Modal also provides SDKs (currently in beta) that enable using Modal Functions and Sandboxes from JavaScript/TypeScript and Go projects.

While Python is the primary language for building Modal applications and implementing Modal Functions, these SDKs enable use cases like:

- Using Sandboxes in JS/Go projects, to safely execute arbitrary commands, run untrusted user code, or as a safe environment for AI agents.
- Directly calling Modal Functions without having to go through a web endpoint.
- Interacting with Modal resources like Volumes, Secrets, Queues, etc. directly from JS/Go.

We're working towards feature parity with the main Modal Python SDK, although defining Modal Functions will likely remain exclusive to Python.

## Installation

For installation instructions, see the READMEs for [JavaScript](https://github.com/modal-labs/libmodal/tree/main/modal-js) and [Go](https://github.com/modal-labs/libmodal/tree/main/modal-go) on GitHub.

## JavaScript/TypeScript

The `modal` package is [distributed via npm](https://www.npmjs.org/package/modal). See the [JS API reference documentation](https://modal-labs.github.io/libmodal/) for details.

### Simple JavaScript Example

```ts
import { ModalClient } from "modal";

const modal = new ModalClient();

const app = await modal.apps.fromName("libmodal-example", {
  createIfMissing: true,
});

// Create a Sandbox with the specified Image, and mount a Volume
const volume = await modal.volumes.fromName("libmodal-example-volume", {
  createIfMissing: true,
});
const image = modal.images.fromRegistry("alpine:3.21");
const sb = await modal.sandboxes.create(app, image, {
  volumes: { "/mnt/volume": volume },
});
const p = await sb.exec(["cat", "/mnt/volume/message.txt"]);
console.log(`Message: ${await p.stdout.readText()}`);
await sb.terminate();

// Call a previously deployed Modal Function
const echo = await modal.functions.fromName("libmodal-example", "echo");
console.log(await echo.remote(["Hello world!"]));
```

There are [many more examples available on GitHub](https://github.com/modal-labs/libmodal/blob/main/modal-js/README.md#documentation).

## Go

The `modal-go` package is [installed via go get](https://pkg.go.dev/github.com/modal-labs/libmodal/modal-go). See the [Go API reference documentation](https://pkg.go.dev/github.com/modal-labs/libmodal/modal-go#section-documentation) for details.

### Simple Go Example

```go
package main

import (
	"context"
	"fmt"
	"io"

	"github.com/modal-labs/libmodal/modal-go"
)

func main() {
	// Skipping err handling throughout for brevity
	ctx := context.Background()

	mc, _ := modal.NewClient()

	app, _err := mc.Apps.FromName(ctx, "libmodal-example", &modal.AppFromNameParams{CreateIfMissing: true})

	// Create a Sandbox with the specified Image, and mount a Volume
	volume, _ := mc.Volumes.FromName(ctx, "libmodal-example-volume", &modal.VolumeFromNameParams{CreateIfMissing: true})
	image := mc.Images.FromRegistry("alpine:3.21", nil)
	sb, _ := mc.Sandboxes.Create(ctx, app, image, &modal.SandboxCreateParams{
		Volumes: map[string]*modal.Volume{"/mnt/volume": volume},
	})
	defer sb.Terminate(context.Background())
	p, _ := sb.Exec(ctx, []string{"cat", "/mnt/volume/message.txt"}, nil)
	stdout, _ := io.ReadAll(p.Stdout)
	fmt.Printf("Message: %s\n", stdout)

	// Call a previously deployed Modal Function
	echo, _ := mc.Functions.FromName(ctx, "libmodal-example", "echo", nil)
	result, _ := echo.Remote(ctx, []any{"Hello world!"}, nil)
	fmt.Println(result)
}
```

There are [many more examples available on GitHub](https://github.com/modal-labs/libmodal/blob/main/modal-go/README.md#documentation).

## Support

The JS and Go Modal SDKs are in active development, and we love to hear your feedback. If you have questions or suggestions, please reach out on the [Modal Community Slack](https://modal.com/slack).
