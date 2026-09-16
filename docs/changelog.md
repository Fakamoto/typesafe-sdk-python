---
title: Changelog
icon: lucide/history
---

# Changelog

## Unreleased

### Features

- accept Pydantic v2 output models through `response_model` in both clients, with the optional `pydantic` extra
- accept `input` as an alias for `state`, preserving existing calls

## v0.6.0 (2026-09-15)

### Breaking Changes

- accept `Score.criteria` as an ordered sequence instead of a dictionary keyed by integers

### Features

- improve type annotations on SDK inputs to accept abstract types like `Mapping` and `Sequence`
- improve error messages to include http details and metadata

### Bug fixes

- handle invalid values in `RetryPolicy`
- make exceptions and responses picklable

### Documentation

- link more concepts from main [docs](https://docs.typesafe.ai/)

## v0.5.7 (2026-09-14)

This is the initial public release of TypeSafe Python SDK. Learn more in the [documentation](https://docs.typesafe.ai/sdk/python).
