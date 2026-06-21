# Developer Agent Guide for octoDNS DigitalOcean Provider

This repository contains the DigitalOcean provider for octoDNS. It enables planning, syncing, and applying DNS record states directly to the DigitalOcean DNS API.

> [!IMPORTANT]
> **Core Workflow and Guidelines**
>
> All agents working on this repository must read and follow the general instructions and workflow guidelines defined in the core octoDNS `AGENTS.md` file.
> - **Local check**: Look for the file at `../octodns/AGENTS.md`.
> - **Remote check**: If the local file is not available, fetch it from GitHub: [octoDNS Core AGENTS.md](https://github.com/octodns/octodns/raw/refs/heads/main/AGENTS.md).
>
> You must align your code structure, style, pull request guidelines, and overall development workflows with the instructions specified there.

## Repository & Module Information

### Key Components

- **Provider Class**: [DigitalOceanProvider](file:///home/ross/octodns/octodns-digitalocean/octodns_digitalocean/__init__.py#L135-L376) (defined in [octodns_digitalocean/__init__.py](file:///home/ross/octodns/octodns-digitalocean/octodns_digitalocean/__init__.py)). Performs conversions between DigitalOcean's JSON API model structures and octoDNS objects.
- **Client Class**: [DigitalOceanClient](file:///home/ross/octodns/octodns-digitalocean/octodns_digitalocean/__init__.py#L33-L133) handles HTTP calls to the DigitalOcean API v2 (`https://api.digitalocean.com/v2`), managing pagination links, and handling common error responses (401 Unauthorized, 404 NotFound).

### Key Workflows & Features

1. **Supported Record Types**: `A`, `AAAA`, `CAA`, `CNAME`, `MX`, `NS`, `SRV`, `TXT`.
2. **Domain Creation Placeholder**: DigitalOcean's API requires specifying an IP address during domain creation. To work around this constraint, `DigitalOceanClient` registers new domains with a placeholder `ip_address` of `192.0.2.1` (documentation TEST-NET-1 IP) and immediately deletes the auto-created root `A` record, leaving the zone clean for octoDNS sync.
3. **Apex Normalization**: The client translates the `@` symbol used by DigitalOcean's API for apex record names and values into empty strings / zone names as expected by octoDNS, and vice versa.
4. **Root Name Server Support**: Fully supported (`SUPPORTS_ROOT_NS=True`).
5. **Dynamic Routing**: Not supported (`SUPPORTS_DYNAMIC=False`, `SUPPORTS_GEO=False`).
6. **Dynamic Subnets**: Not supported (`SUPPORTS_DYNAMIC_SUBNETS=False`).
7. **Pool Value Status**: Not supported (`SUPPORTS_POOL_VALUE_STATUS=False`).

## Development & Testing

- **Setup Script**: Run `./script/bootstrap` to create a virtual environment, install runtime and development dependencies (including `black`, `isort`, `pyflakes`, and `pytest`), and configure pre-commit hooks.
- **Test Suite**: Run unit tests using `pytest` via `./script/test` (or `pytest tests/`). Test files are located in [tests/](file:///home/ross/octodns/octodns-digitalocean/tests).
- **Code Coverage**: Verify code coverage using `./script/coverage`.

## Key Constraints & Behaviors

- **Python Version**: Targets Python `>=3.9`.
- **Formatting**: Code formatting is enforced via `black` (version `>=26.0.0,<27.0.0`) and `isort`.
