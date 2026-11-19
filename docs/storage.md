# Where your memory lives

Use one private workspace address for each memory you want to keep. Use `--store` before the command to choose it. For a routine or an agent with its own settings, set `MEMORY_PA_STORE` in that agent's environment.

## This computer

Run `memory-pa init`. The default is `~/.memory-pa/workspaces/default`. A separate local workspace can use any new private folder outside the project checkout.

```sh
memory-pa --store ~/club-memory init
memory-pa --store ~/club-memory search "lantern"
```

## Private Git

1. Create an empty **private** repository on your Git host. Check its visibility in its settings and give your agent access if it will run on a different computer.
2. Set up Git to sign in to that host with its credential helper or an SSH key. Copy the repository's clone URL.
3. Add `git+` before the URL and use it as the store. For SSH, use a URL of the form `git+ssh://git@example.com/owner/notes.git`.

```sh
memory-pa --store git+https://github.com/your-account/your-private-notes.git init
```

The adapter uses a dedicated branch in a standard SHA-1 Git repository, `main` by default, containing the workspace files. To choose another branch, set `MEMORY_PA_GIT_BRANCH` or pass `--git-branch` before the command. Each save appends one commit using an exact lease on the expected branch tip. Keep attachments and other repositories in their own locations.

## Private S3

1. Use a general-purpose AWS S3 bucket with Block Public Access enabled. Pick a prefix for your workspace, such as `my-memory`.
2. Give your agent's AWS profile or role `s3:GetObject` and `s3:PutObject` for that prefix and `s3:ListBucket` for the bucket so it can distinguish a new workspace from an access failure. Use your existing AWS sign-in or role.
3. Install the S3 extra and use the address of your bucket and prefix.

```sh
uv tool install --python 3.11 "memory-pa[s3] @ git+https://github.com/anuj-pm-irl/memory-pa.git@v0.1.0"
memory-pa --store s3://your-private-bucket/my-memory init
```

The workspace prefix contains `HEAD.json` and immutable `revisions/<sha256>.zip` files. The adapter writes the archive first, then publishes the head with an S3 conditional write. Set retention for old revisions according to your needs and keep the archive referenced by `HEAD.json` available. Git history and previous local and S3 revisions can retain old source text.

## Move your memory

Export into a new private directory, then use `init --from` against an empty destination. `validate` checks the result. Replace the example paths with yours.

```sh
memory-pa --store ~/club-memory export ~/club-memory-copy
memory-pa --store s3://your-private-bucket/my-memory init --from ~/club-memory-copy
memory-pa --store s3://your-private-bucket/my-memory validate
```

## Add another storage provider

Implement `memory_pa.storage.Storage` and expose a factory taking a target URL as a `memory_pa.storage` entry point named for your URL scheme. The CLI loads the adapter you install in the same Python environment. A provider can also implement the file format independently and exchange workspace exports.

- `read()` returns `Revision(token, files)`. The token is an opaque non-empty string and `files` maps POSIX paths to bytes. The empty-store result is `Revision(None, {})`. Access failures are errors.
- `publish(expected, files)` makes the complete tree visible only if the current token matches `expected`. For an empty store, `expected` is `None`. Return a fresh token after success. Raise `Conflict` for a stale token. Read back the result of an ambiguous write or raise `UncertainWrite`. Both errors and the base `MemoryPAError` are in `memory_pa.errors`. Readers must always see a complete prior or new snapshot.
- Use regular files, preserve paths and bytes, and validate archives before extraction. Credentials, adapter metadata, and private caches live outside the portable tree. Use the conformance tests in `tests/test_storage.py` to check an adapter.
