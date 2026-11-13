# browser_tool.policy

Decides which URLs the browser may load. Pure Python with no Playwright import. `browser_tool.session` applies the decisions to the browser in two layers: request routing, plus Chromium host-resolver rules for redirect hops.

## Public API (`from browser_tool.policy import ...`)

- `HostPolicy.from_strings(allow, deny, *, is_allow_all=False, guest_block=None)` builds a policy from config patterns. It raises `ValueError` on a bad pattern.
  - `check_url(url) -> PolicyDecision(is_allowed, reason, host)`
  - `check_host(host)`
  - `is_allow_all` is True only when switched on explicitly (`[policy] allow_all = true`)
- Patterns come in two forms. `"example.com"` matches that host exactly. `"*.example.com"` matches its subdomains but not the apex. Hosts are IDNA-normalized.
- Decision order:
  1. Opaque origins are refused with `opaque_origin`. These are `about:blank`, `about:srcdoc`, `data:` and `blob:`.
  2. Other non-network schemes are refused with `unsupported_scheme`.
  3. With a guest block (docker jobs only), a host it lists is refused with `guest_blocked`, whatever the lists say.
  4. A host on the denylist is refused with `denylisted`. The denylist always wins.
  5. With allow-all on, everything else is allowed (`allow_all`).
  6. Otherwise the host must be on the allowlist: `allowlisted` or `not_allowlisted`. An empty allowlist blocks everything.
- Userinfo is ignored: `https://good.com@evil.com` is checked as `evil.com`.
- `GuestBlock(host_ips)` is Layer 1 of the docker jobs' host and LAN block (`refdocs/research/docker-browser.md` section 5). It refuses `docker.internal`, `localhost` and their subdomains, any IP literal that isn't globally routable (after unwrapping an IPv4-mapped IPv6 address, so CGNAT `100.64/10` counts; short, decimal, hex and octal IPv4 forms such as `127.1` and `2130706433` are read too), and the host's own IPv4 addresses, which `host_ips()` returns live on every check. Its names and the host IPs also go into the resolver rules.
  - `BLOCKED_GUEST_CIDRS` is the one list of private ranges. The guest's iptables (Layer 2, the real boundary) rejects it plus the host addresses.
- `build_host_resolver_rules(policy)` / `build_resolver_args(policy)` produce the Chromium `--host-resolver-rules` flag. It blocks redirect hops, which Playwright routing can't see. The known gaps are in the module docstring.
- `origin_of(url)` returns a loggable `scheme://host:port` with no path or query. `display_url(url)` returns origin plus path, for the model. `scheme_of(url)` returns the lowercased scheme. `host_of(url)` returns a network URL's host, lower-cased with no trailing dot, or None.

## Files

- `host_patterns.py`: pattern parsing, matching and host normalization.
- `guest_block.py`: `GuestBlock` and `BLOCKED_GUEST_CIDRS`.
- `host_policy.py`: `HostPolicy` and `PolicyDecision`.
- `resolver_rules.py`: the Chromium flag builder.
- `urls.py`: scheme sets, `scheme_of`, `origin_of`, `display_url`, `host_of`.

## Dependencies

Standard library only.
