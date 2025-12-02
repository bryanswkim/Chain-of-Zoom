# Slack notifications (beta)

You can integrate your Modal Workspace with Slack to receive timely essential notifications.

## Prerequisites

- You are a [Workspace Manager](/docs/guide/workspaces#administrating-workspace-members) in the Modal Workspace you're installing the Slack integration in.
- You have permissions to install apps in your Slack workspace.

## Supported notifications

- Alerts for failed scheduled function runs.
- Alerts for crash-looping containers in a function.
- Alerts when any of your apps have client versions that are out of date.
- Alerts when you hit your GPU resource limits.

## Slack Permissions

The Modal Slack app requests the following permissions to integrate with Slack:

- Start direct messages with people
- Send messages as @modal
- Add shortcuts and/or slash commands that people can use
- View basic information about public channels in a workspace
- View basic information about private channels that Modal has been added to
- View basic information about direct messages that Modal has been added to
- View basic information about group direct messages that Modal has been added to
- View people in a workspace

## Configuration

### Step 1: Install the Slack integration

Visit the _Slack Integration_ section on your [settings](/settings/slack-integration) page in your Modal Workspace and click the **Add to Slack** button.

### Step 2: Invite the Modal app to your Slack channel

Navigate to the Slack channel and `/invite` the Modal app so that the app can post messages to the channel.

![Adding an app to Slack channel](https://modal-cdn.com/cdnbot/slack-invite-app_vpxfskj_f0dc9524.webp)

### Step 3: Add the Modal app to your Slack channel

Navigate to the Slack channel you want to add the Modal app to and click on the channel header. On the integrations tab you can add the Modal app.

![Add Modal app to Slack channel](../../assets/docs/slack-add-modal-app.jpg)

### Step 4: Use `/modal link` to link the Slack channel to your Modal Workspace

You'll be prompted to select the Workspace you want to link to the Slack channel. You can always unlink the Slack channel by visiting the _Slack Integration_ section on your [settings](/settings/slack-integration) page in your Modal Workspace.
