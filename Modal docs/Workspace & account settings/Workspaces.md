# Workspaces

A **workspace** is an area where a user can deploy Modal apps and other
resources. There are two types of workspaces: personal and shared. After a new
user has signed up to Modal, a personal workspace is automatically created for
them. The name of the personal workspace is based on your GitHub username, but
it might be randomly generated if already taken or invalid.

To collaborate with others, a new shared workspace needs to be created.

## Create a Workspace

All additional workspaces are shared workspaces, meaning you can invite others
by email to collaborate with you. There are two ways to create a Modal workspace
on the [settings](/settings/workspaces) page.

![view of workspaces creation interface](https://modal-cdn.com/cdnbot/create-new-workspace-viewk0ka46_7_800f2053.webp)

1. Create from [GitHub organization](https://docs.github.com/en/organizations). Allows members in GitHub organization to auto-join the workspace.

2. Create from scratch. You can invite anyone to your workspace.

If you're interested in having a workspace associated with your Okta
organization, then check out our [Okta SSO docs](/docs/guide/okta-sso).

If you're interested in using SSO through Google or other providers, then please reach out to us at [support@modal.com](mailto:support@modal.com).

## Auto-joining a Workspace associated with a GitHub organization

Note: This is only relevant for Workspaces created from a GitHub organization.

Users can automatically join a Workspace on their [Workspace settings page](/settings/workspaces) if they are a member of the GitHub organization associated with the Workspace.

To turn off this functionality a Workspace Manager can disable it on the **Workspace Management** tab of their Workspace's settings page.

## Inviting new Workspace members

To invite a new Workspace member, you can visit the [settings](/settings) page
and navigate to the members tab for the appropriate workspace.

You can either send an email invite or share an invite link. Both existing Modal
users and non-existing users can use the links to join your workspace. If they
are a new user a Modal account will be created for them.

![invite member section](../../assets/screenshots/invite-member.png)

## Create a token for a Workspace

To interact with a Workspace's resources programmatically, you need to add an
API token for that Workspace. Your existing API tokens are displayed on
[the settings page](/settings/tokens) and new API tokens can be added for a
particular Workspace.

After adding a token for a Workspace to your Modal config file you can activate
that Workspace's profile using the CLI (see below).

As an manager or workspace owner you can manage active tokens for a workspace on
[the member tokens page](/settings/tokens/member-tokens). For more information on API
token management see the
[documentation about configuration](/docs/reference/modal.config).

## Switching active Workspace

When on the dashboard or using the CLI, the active profile determines which
personal or organizational Workspace is associated with your actions.

### Dashboard

You can switch between organization Workspaces and your Personal Workspace by
using the workspace selector at the top of [the dashboard](/home).

### CLI

To switch the Workspace associated with CLI commands, use
`modal profile activate`.

## Administrating workspace members

Workspaces have three different levels of access privileges:

- Owner
- Manager
- Member

The user that creates a workspace is automatically set as the **Owner** for that
workspace. The owner can assign any other roles within the workspace, as well as
remove other members of the workspace.

A **Manager** within a workspace can assign all roles except **Owner** and can
also remove other members of the workspace.

A **Member** of a workspace can not assign any access privileges within the
workspace but can otherwise perform any action like running and deploying apps
and modify Secrets.

As an Owner or Manager you can administrate the access privileges of other
members on the `Workspace Management` tab in [settings](/settings/workspace-management).

## Leaving a Workspace

To leave a workspace, navigate to [the settings page](/settings/workspaces) and
click "Leave" on a listed Workspace. There must be at least one owner assigned
to a workspace.
