# Continuous deployment

It's a common pattern to auto-deploy your Modal App as part of a CI/CD pipeline.
To get you started, below is a guide to doing continuous deployment of a Modal
App in GitHub.

## GitHub Actions

Here's a sample GitHub Actions workflow that deploys your App on every push to
the `main` branch.

This requires you to create a [Modal token](/settings/tokens) and add it as a
[secret for your Github Actions workflow](https://docs.github.com/en/actions/how-tos/write-workflows/choose-what-workflows-do/use-secrets).

After setting up secrets, create a new workflow file in your repository at
`.github/workflows/ci-cd.yml` with the following contents:

```yaml
name: CI/CD

on:
  push:
    branches:
      - main

jobs:
  deploy:
    name: Deploy
    runs-on: ubuntu-latest
    env:
      MODAL_TOKEN_ID: ${{ secrets.MODAL_TOKEN_ID }}
      MODAL_TOKEN_SECRET: ${{ secrets.MODAL_TOKEN_SECRET }}

    steps:
      - name: Checkout Repository
        uses: actions/checkout@v4

      - name: Install Python
        uses: actions/setup-python@v5
        with:
          python-version: "3.10"

      - name: Install Modal
        run: |
          python -m pip install --upgrade pip
          pip install modal

      - name: Deploy job
        run: |
          modal deploy -m my_package.my_file
```

Be sure to replace `my_package.my_file` with your actual entrypoint.

If you use multiple Modal [Environments](/docs/guide/environments), you can
additionally specify the target environment in the YAML using
`MODAL_ENVIRONMENT=xyz`.
