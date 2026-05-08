# Traefik Advanced IP Filter
[![Code Coverage](https://codecov.io/gh/PseudoResonance/traefik-advanced-ip-filter/branch/main/graph/badge.svg?token=QFGZS5QJSG)](https://codecov.io/gh/PseudoResonance/traefik-advanced-ip-filter)
[![Code Analysis](https://github.com/PseudoResonance/traefik-advanced-ip-filter/actions/workflows/codeqlAnalysis.yml/badge.svg)](https://github.com/PseudoResonance/traefik-advanced-ip-filter/actions/workflows/codeqlAnalysis.yml)
[![Codacy Security Scan](https://github.com/PseudoResonance/traefik-advanced-ip-filter/actions/workflows/codacyAnalysis.yml/badge.svg)](https://github.com/PseudoResonance/traefik-advanced-ip-filter/actions/workflows/codacyAnalysis.yml)
[![Go Report Card](https://goreportcard.com/badge/github.com/PseudoResonance/traefik-advanced-ip-filter)](https://goreportcard.com/report/github.com/PseudoResonance/traefik-advanced-ip-filter)
[![Build and Test Source](https://github.com/PseudoResonance/traefik-advanced-ip-filter/actions/workflows/buildAndTest.yml/badge.svg)](https://github.com/PseudoResonance/traefik-advanced-ip-filter/actions/workflows/buildAndTest.yml)
[![Static Analysis](https://github.com/PseudoResonance/traefik-advanced-ip-filter/actions/workflows/staticAnalysis.yml/badge.svg)](https://github.com/PseudoResonance/traefik-advanced-ip-filter/actions/workflows/staticAnalysis.yml)
[![Integration Test](https://github.com/PseudoResonance/traefik-advanced-ip-filter/actions/workflows/prodTest.yml/badge.svg)](https://github.com/PseudoResonance/traefik-advanced-ip-filter/actions/workflows/prodTest.yml)

The Traefik built-in IP filter is great, but lacks configuration and sometimes doesn't work with the environment.

This plugin adds extra configuration options to work better with whatever you're already given.

## Configuration

### Configuration documentation

Supported configurations per body

| Setting     | Allowed values | Required | Description                                    |
| :---------- | :------------- | :------- | :--------------------------------------------- |
| sourceRange | []string       | Yes      | List of IPs/CIDRs to match against             |
| denylist    | bool           | No       | Turns sourceRange into a deny list             |
| ipStrategy  | IpStrategy     | No       | Extra strategy for selecting an IP (see below) |
| debug       | bool           | No       | Enables extra debug logging                    |

IpStrategy Configuration

| Setting         | Allowed values | Required | Description                                                               |
| :-------------- | :------------- | :------- | :------------------------------------------------------------------------ |
| depth           | int            | No       | Depth within the configured header to match an IP                         |
| header          | string         | No       | Name of header to search for IPs in                                       |
| isTrustedHeader | string         | No       | Name of header to signal when the IP header should be ignored             |
| sourceFallback  | bool           | No       | Whether to fallback to the source IP if header IP is missing              |
| excludedIPs     | []string       | No       | IPs/CIDRs to exclude from the IP header list                              |
| ipv6Subnet      | int            | No       | Truncates the source IPv6 with the provided subnet size prior to matching |

See the [Traefik ipAllowList documentation](https://doc.traefik.io/traefik/reference/routing-configuration/http/middlewares/ipallowlist/) for additional information on most options.

### Enable the plugin

```yaml
experimental:
  plugins:
    advancedipfilter:
      modulename: github.com/PseudoResonance/traefik-advanced-ip-filter
      version: v1.0.1
```

### Plugin configuration

```yaml
http:
  middlewares:
    advancedipfilter:
      plugin:
        advancedipfilter:
          sourceRange:
          - "10.0.0.0/8"
          - "fd00::/8"
          denylist: false
          ipStrategy:
            depth: 2
            header: "X-Forwarded-For"
            isTrustedHeader: "X-Is-Trusted"
            sourceFallback: true
            excludedIPs: []
            ipv6Subnet: 64

  routers:
    my-router:
      rule: Path(`/whoami`)
      service: service-whoami
      entryPoints:
        - http
      middlewares:
        - advancedipfilter

  services:
    service-whoami:
      loadBalancer:
        servers:
          - url: http://127.0.0.1:5000
```

## Note

Traefik includes some X-Forwarded-For header handling by default, and will process these before the middleware runs. Thus, if you are attempting to use this as access control with headers instead, you may need to trust your source IPs in the Traefik entrypoint config first.

# Testing

[https://github.com/PseudoResonance/traefik-advanced-ip-filter/tree/main/test](https://github.com/PseudoResonance/traefik-advanced-ip-filter/tree/main/test)

We have written the following tests in this repo:

- golang linting
- yaegi tests (validate configuration matches what Traefik expects)
- General GO code coverage
- Dev environment live smoke tests (spin up traefik with comprehensive tests to make sure the plugin actually works in a real environment)
- Production live smoke tests (spin up traefik with the production plugin definition, as it would be for you, and run the same tests again)

These tests allow us to make sure the plugin is always functional with Traefik and Traefik version updates.
