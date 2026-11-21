# Contributing

After installing this checkout, try `memory-pa demo`. It opens the [complete fictional Avengers workspace](examples/workspace/index.md) without using your configured store. If you're reporting a bug, describe the behavior using made-up notes and test credentials. This project uses fictional fixtures for examples, tests, screenshots, and release artifacts.

For development, use Python 3.11 or newer and Git.

```sh
python -m pip install -e '.[test]'
python -m unittest discover -s tests -v
```

The test extra enables S3 tests using the AWS SDK and an emulator. To run the same tests against an AWS test prefix, set `MEMORY_PA_TEST_S3` to a private `s3://bucket/prefix` and use credentials that can read and write under it. Tests create unique subprefixes containing fictional data. The bucket owner controls their cleanup.

Build and test both the wheel and source distribution before a release. Review the exact tracked tree, history, and release files using synthetic demo output. Check that personal workspaces and credentials live outside the code checkout.
