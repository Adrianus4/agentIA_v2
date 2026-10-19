# Tooling Verification Spikes

## SC-1 official Quarkus tooling

The repository environment used for this implementation does not have `mvn` on
`PATH` (`mvn: command not found`). Therefore the live Quarkus Maven command has
not been enabled or claimed as verified.

The implementation records the profile-owned command as an argv template and
requires a future environment check of:

```text
mvn -version
mvn io.quarkus.platform:quarkus-maven-plugin:<version>:help
```

The networked scaffolder is opt-in and fails explicitly when its tool is absent.
The offline verifier remains a separate `mvn -o -q test-compile` request through
the existing hermetic runner.
