# Okta SSO

## Prerequisites

- A Workspace that's on an [Enterprise](/pricing) plan
- Admin access to the Workspace you want to configure with Okta Single-Sign-On (SSO)
- Admin privileges for your Okta Organization

## Supported features

- IdP-initiated SSO
- SP-initiated SSO
- Just-In-Time account provisioning

For more information on the listed features, visit the
[Okta Glossary](https://help.okta.com/okta_help.htm?type=oie&id=ext_glossary).

## Configuration

### Read this before you enable "Require SSO"

Enabling "Require SSO" will force all users to sign in via Okta. Ensure that you
have admin access to your Modal Workspace through an Okta account before
enabling.

### Configuration steps

#### Step 1: Add Modal app to Okta Applications

1. Sign in to your Okta admin dashboard
2. Navigate to the Applications tab and click "Browse App Catalog".
   ![Okta browse application](../../assets/docs/okta-browse-applications.png)

3. Select "Modal" and click "Done".
4. Select the "Sign On" tab and click "Edit".
   ![Okta sign on edit](../../assets/docs/okta-sign-on-edit.png)
5. Fill out Workspace field to configure for your specific Modal workspace. See
   [Step 2](/docs/guide/okta-sso#step-2-link-your-workspace-to-okta-modal-application)
   if you're unsure what this is.
   ![Okta add workspace](../../assets/docs/okta-add-workspace-username.png)

#### Step 2: Link your Workspace to Okta Modal application

1. Navigate to your application on the Okta Admin page.
2. Copy the Metadata URL from the Okta Admin Console (It's under the "Sign On"
   tab). ![Okta metadata url](../../assets/docs/okta-metadata-url.png)

3. Sign in to https://modal.com and visit your [Workspace Management](/settings/workspace-management/identity-and-provisioning) page's `Identity and Provisioning` tab.
4. Paste the Metadata URL in the input and click "Save Changes"

#### Step 3: Assign users / groups and test the integration

1. Navigate back to your Okta application on the Okta Admin dashboard.
2. Click on the "Assignments" tab and add the appropriate people or groups.

![Okta Assign Users](../../assets/docs/okta-assign-people.png)

3. To test the integration, sign in as one of the users you assigned in the previous step.
4. Click on the Modal application on the Okta Dashboard to initiate Single Sign-On.

#### Notes

The following SAML attributes are used by the integration:

| Name      | Value          |
| --------- | -------------- |
| email     | user.email     |
| firstName | user.firstName |
| lastName  | user.lastName  |

## SP-initiated SSO

The sign-in process is initiated from https://modal.com/login/sso

1. Enter your workspace name in the input
2. Click "continue with SSO" to authenticate with Okta
