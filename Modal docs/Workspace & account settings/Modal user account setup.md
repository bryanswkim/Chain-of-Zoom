# Modal user account setup

To run and deploy applications on Modal you'll need to sign up and create a user
account.

You can visit the [signup](/signup) page to begin the process or execute
[`modal setup`](/docs/reference/cli/setup#modal-setup) on the command line.

Users can also be provisioned through [Okta SSO](/docs/guide/okta-sso), which is
an enterprise feature that you can request. For the typical user you'll sign-up
using an existing GitHub account. If you're interested in authenticating with
other identity providers let us know at <support@modal.com>.

## What GitHub permissions does signing up require?

- `user:email` — gives us the emails associated with the GitHub account.
- `read:org` (invites only) — needed for Modal workspace invites. Note: this
  only allows us to see what organization memberships you have
  ([GitHub docs](https://docs.github.com/en/apps/oauth-apps/building-oauth-apps/scopes-for-oauth-apps)).
  We won't be able to access any code repositories or other details.

## How can I change my email?

You can change your email on the [settings](/settings) page.
