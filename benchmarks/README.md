# XMem Benchmarks

This directory contains benchmark harnesses for XMem.

- `longmemeval/`: Python-only LongMemEval benchmark runner targeting the XMem HTTP API.

Benchmark runs can create large dataset and result artifacts. Keep those files under
`benchmarks/longmemeval/data`, `benchmarks/longmemeval/results`, or
`benchmarks/longmemeval/outputs`; those paths are intentionally ignored by git.
