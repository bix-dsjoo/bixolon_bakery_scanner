"""Compatibility CLI for hash-bound RPC few-shot scoring."""

from bakery_scanner.experiments import rpc_scoring as _rpc_scoring

globals().update(
    {
        name: value
        for name, value in vars(_rpc_scoring).items()
        if not name.startswith("__")
    }
)


if __name__ == "__main__":
    raise SystemExit(_rpc_scoring.main())
