# Contributing

Create one branch per issue from the latest `dev` branch:

```bash
git switch dev
git pull
git switch -c <initials>/<issue>-<short-name>
```

Commit in small steps, push the work branch, and open a pull request into
`dev`. The pull request must explain what changed, how it was tested, and which
Raspberry Pi was used when hardware is involved.

Another developer must review the pull request. Resolve every comment before
squash-merging. Do not push directly to `main` or `dev`, and do not commit on a
Pi directly to either protected branch.

`main` is the deployable branch. Releases move from `dev` to `main` through a
reviewed pull request. Urgent field fixes branch from `main`, merge back into
`main` through review, and are then merged into `dev`.
