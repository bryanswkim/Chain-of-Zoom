# Managing deployments

Once you've finished using `modal run` or `modal serve` to iterate on your Modal
code, it's time to deploy. A Modal deployment creates and then persists an
application and its objects, providing the following benefits:

- Repeated application function executions will be grouped under the deployment,
  aiding observability and usage tracking. Programmatically triggering lots of
  ephemeral App runs can clutter your web and CLI interfaces.
- Function calls are much faster because deployed functions are persistent and
  reused, not created on-demand by calls. Learn how to trigger deployed
  functions in
  [Invoking deployed functions](/docs/guide/trigger-deployed-functions).
- [Scheduled functions](/docs/guide/cron) will continue scheduling separate from
  any local iteration you do, and will notify you on failure.
- [Web endpoints](/docs/guide/webhooks) keep running when you close your laptop,
  and their URL address matches the deployment name.

## Creating deployments

Deployments are created using the
[`modal deploy` command](/docs/reference/cli/app#modal-app-list).

```
 % modal deploy -m whisper_pod_transcriber.main
✓ Initialized. View app page at https://modal.com/apps/ap-PYc2Tb7JrkskFUI8U5w0KG.
✓ Created objects.
├── 🔨 Created populate_podcast_metadata.
├── 🔨 Mounted /home/ubuntu/whisper_pod_transcriber at /root/whisper_pod_transcriber
├── 🔨 Created fastapi_app => https://modal-labs-whisper-pod-transcriber-fastapi-app.modal.run
├── 🔨 Mounted /home/ubuntu/whisper_pod_transcriber/whisper_frontend/dist at /assets
├── 🔨 Created search_podcast.
├── 🔨 Created refresh_index.
├── 🔨 Created transcribe_segment.
├── 🔨 Created transcribe_episode..
└── 🔨 Created fetch_episodes.
✓ App deployed! 🎉

View Deployment: https://modal.com/apps/modal-labs/whisper-pod-transcriber
```

Running this command on an existing deployment will redeploy the App,
incrementing its version. For detail on how live deployed apps transition
between versions, see the [Updating deployments](#updating-deployments) section.

Deployments can also be created programmatically using Modal's
[Python API](/docs/reference/modal.App#deploy).

## Viewing deployments

Deployments can be viewed either on the [apps](/apps) web page or by using the
[`modal app list` command](/docs/reference/cli/app#modal-app-list).

## Updating deployments

A deployment can deploy a new App or redeploy a new version of an existing
deployed App. It's useful to understand how Modal handles the transition between
versions when an App is redeployed. In general, Modal aims to support
zero-downtime deployments by gradually transitioning traffic to the new version.

If the deployment involves building new versions of the Images used by the App,
the build process will need to complete succcessfully. The existing version of
the App will continue to handle requests during this time. Errors during the
build will abort the deployment with no change to the status of the App.

After the build completes, Modal will start to bring up new containers running
the latest version of the App. The existing containers will continue handling
requests (using the previous version of the App) until the new containers have
completed their cold start.

Once the new containers are ready, old containers will stop accepting new
requests. However, the old containers will continue running any requests they
had previously accepted. The old containers will not terminate until they have
finished processing all ongoing requests.

Any warm pool containers will also be cycled during a deployment, as the
previous version's warm pool are now outdated.

## Deployment rollbacks

To quickly reset an App back to a previous version, you can perform a deployment
_rollback_. Rollbacks can be triggered from either the App dashboard or the CLI.
Rollback deployments look like new deployments: they increment the version number
and are attributed to the user who triggered the rollback. But the App's functions
and metadata will be reset to their previous state independently of your current
App codebase.

Note that deployment rollbacks are supported only on the Team and Enterprise plans.

## Stopping deployments

Deployed apps can be stopped in the web UI by clicking the red "Stop app" button on
the App's "Overview" page, or alternatively from the command line using the
[`modal app stop` command](/docs/reference/cli/app#modal-app-stop).

Stopping an App is a destructive action. Apps cannot be restarted from this state;
a new App will need to be deployed from the same source files. Objects associated
with stopped deployments will eventually be garbage collected.
