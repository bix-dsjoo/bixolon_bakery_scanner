# Immutable decision policies

Small calibrated decision and fusion policies are reviewed and stored in Git.
Runtime configs bind them by SHA-256. Changing coefficients, thresholds,
decision rules, artifact hashes, or even canonical serialization produces a
new policy file and a new version; published files are never edited in place.
