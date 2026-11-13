#!/bin/sh
# Browser container entrypoint (docker backend guest, refdocs/research/docker-browser.md section 5).
# Runs as root under docker-init. It blocks outbound traffic to the host and the
# private ranges in SIGNAL_BLOCK_CIDRS, checks the rules are really in place,
# then drops to user "edge" with no capabilities and execs the relay (main.py).
# Any failure exits non-zero, so the container dies instead of running open.
set -eu

RELAY_MAIN=/opt/signal/main.py
DNS_PORT=53

# Validate SIGNAL_BLOCK_CIDRS (comma-separated IPv4 CIDRs, at least one) and print
# them normalised, one per line. iptables would resolve a hostname, so validate first.
cidrs=$(python3 -I -c '
import ipaddress, sys
entries = [entry.strip() for entry in sys.argv[1].split(",") if entry.strip()]
if not entries:
    sys.exit("SIGNAL_BLOCK_CIDRS is empty")
for entry in entries:
    try:
        print(ipaddress.IPv4Network(entry))
    except ValueError:
        sys.exit(f"SIGNAL_BLOCK_CIDRS has a bad entry: {entry!r}")
' "${SIGNAL_BLOCK_CIDRS:?SIGNAL_BLOCK_CIDRS is required}")

# Docker's DNS server, which may sit inside a blocked range, stays reachable on port 53.
nameservers=$(awk '$1 == "nameserver" && $2 ~ /^[0-9]+\.[0-9]+\.[0-9]+\.[0-9]+$/ { print $2 }' /etc/resolv.conf)
if [ -z "$nameservers" ]; then
    echo "entrypoint: no IPv4 nameserver in /etc/resolv.conf" >&2
    exit 1
fi

# Every OUTPUT rule, in order. $1 is -A to append it or -C to check it exists.
# The nat table, where Docker keeps its DNS rules, is never touched.
output_rules() {
    op=$1
    iptables "$op" OUTPUT -o lo -j ACCEPT
    iptables "$op" OUTPUT -m conntrack --ctstate ESTABLISHED,RELATED -j ACCEPT
    for nameserver in $nameservers; do
        iptables "$op" OUTPUT -d "$nameserver" -p udp --dport "$DNS_PORT" -j ACCEPT
        iptables "$op" OUTPUT -d "$nameserver" -p tcp --dport "$DNS_PORT" -j ACCEPT
    done
    for cidr in $cidrs; do
        iptables "$op" OUTPUT -d "$cidr" -j REJECT
    done
}

output_rules -A
# Backstop to the disable_ipv6 sysctl.
ip6tables -P OUTPUT DROP

# Re-read the rules: each must exist, there must be no others, and IPv6 must drop.
output_rules -C
expected_count=$((2 + 2 * $(echo "$nameservers" | wc -l) + $(echo "$cidrs" | wc -l)))
actual_count=$(iptables -S OUTPUT | grep -c '^-A OUTPUT ')
if [ "$actual_count" -ne "$expected_count" ]; then
    echo "entrypoint: expected $expected_count OUTPUT rules, found $actual_count" >&2
    exit 1
fi
if ! ip6tables -S OUTPUT | grep -qx -- '-P OUTPUT DROP'; then
    echo "entrypoint: ip6tables OUTPUT policy isn't DROP" >&2
    exit 1
fi
echo "entrypoint: firewall in place ($actual_count rules, $(iptables -V))" >&2

# setuid clears the remaining capabilities; the empty bounding set and
# no-new-privileges (from docker run) stop them coming back.
exec setpriv --reuid=edge --regid=edge --init-groups --inh-caps=-all --bounding-set=-all \
    -- python3 -E -s "$RELAY_MAIN"
