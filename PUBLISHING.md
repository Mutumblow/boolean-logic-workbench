# Public release checklist

This checklist is a practical preflight, not legal advice or a guarantee that
a release complies with every law or license.

## Before making the repository public

- Confirm you have the right to publish every source file, test, image, font,
  icon, and other asset. Check any employment, school, client, or contributor
  agreements that may affect ownership.
- Review `LICENSE` and confirm its copyright holder and year are correct for
  the code being released. The MIT license covers this project's code, not its
  dependencies.
- Review `THIRD_PARTY_NOTICES.md` and verify the license information for the
  exact dependency versions you intend to use or distribute.
- Scan the files to be uploaded for credentials, private keys, personal data,
  and local machine paths. Do not upload generated exports, build output, or
  virtual environments.
- Confirm the README's install, usage, platform, and feature claims match the
  release. Test from a clean environment if practical.
- Remember that a public repository may be cloned and forked. Removing a file
  later does not remove copies already made by others.

## Before distributing a packaged application

- Re-check the licenses of all included Qt modules, plugins, and other
  dependencies for the exact build.
- Follow the applicable PySide6/Qt license terms, including any required
  license texts, notices, source availability, relinking, and installation
  information. See `THIRD_PARTY_NOTICES.md` and consult qualified counsel if
  the distribution model or obligations are unclear.
- Do not describe the whole packaged application as MIT-licensed unless the
  license rights for every included component support that statement.

## GitHub repository setup

Create an empty repository named `boolean-logic-workbench` under
`Mutumblow`, select **Public**, and do not initialize it with a README,
license, or `.gitignore` because those files are already in this project.
Then install Git for Windows, open PowerShell in the project folder, and run:

```powershell
git init -b main
git add .
git status
git commit -m "Initial public release"
git remote add origin https://github.com/Mutumblow/boolean-logic-workbench.git
git push -u origin main
```

Review the `git status` output before committing to ensure only intended files
will be published. Enable two-factor authentication on the GitHub account and
use GitHub's recommended authentication method; do not put credentials in the
repository or remote URL.
