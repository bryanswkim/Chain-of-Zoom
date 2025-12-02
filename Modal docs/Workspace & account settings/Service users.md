# Service Users (beta)

Service users are programmatic accounts that allow automated systems to interact with Modal. They're ideal for CI/CD pipelines, automated deployments, and other workflows that need to authenticate.

## Create a Service User

Service users are only available for shared workspaces. You will need workspace owner or manager privileges to create service users.

To create a service user:

1. Go to your workspace [tokens settings page](/settings/tokens/service-users)
2. Click **New Service User**
3. Enter a name for your service user (must be lowercase alphanumeric, can contain hyphens or underscores)
4. Click **Create**

After creation, you'll see the `MODAL_TOKEN_ID` and `MODAL_TOKEN_SECRET`. **This is the only time you can view the token secret** for security reasons.

## Use Service User Tokens

Set the service user credentials as environment variables in your automated environment:

```bash
export MODAL_TOKEN_ID=your-token-id
export MODAL_TOKEN_SECRET=your-token-secret
```

Once configured, you can use Modal's CLI and Python SDK as usual:

```bash
modal deploy your_app.py
```

## Delete a Service User

To remove a service user:

1. Go to the [tokens settings page](/settings/tokens/service-users)
2. Find the service user in the table
3. Click **Delete** when you hover over the row

## Permissions

Service users have the same permissions as workspace members. They cannot do actions that are only permitted for a workspace owner or manager. To learn more about members, managers, and owners, see this [workspace](/docs/guide/workspaces#administrating-workspace-members) section.
