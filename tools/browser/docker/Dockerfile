# Browser container image: Edge for Linux under Xvfb, behind a token-checking
# CDP relay and an entrypoint firewall. The guest of browser-tool's docker
# backend (refdocs/research/docker-browser.md); see README.md in this folder.
#
# Build: docker build --pull --no-cache -t signal-browser:latest tools/browser/docker
#
# The base is pinned by digest for a reproducible start, and `apt-get upgrade`
# brings in Debian's security fixes released since that digest. Bump the digest
# by hand now and then so the upgrade step stays small.
FROM debian:trixie-slim@sha256:a29215f6a35e51e22adffa17f89e9d2ef06214e64a2bad10d765c46aea49f11f

# Microsoft's release signing key, committed next to this file. apt trusts it
# for the Edge repo only (signed-by), and only if its fingerprint matches.
ARG MICROSOFT_SIGNER_FINGERPRINT=BC528686B50D79E339D3721CEB3E94ADBE1229CF
ARG EDGE_KEYRING=/usr/share/keyrings/microsoft-edge.asc
COPY --chmod=0644 microsoft.asc ${EDGE_KEYRING}

# Edge's postinst rewrites the apt source into its own microsoft-edge.sources
# (repos/edge-stable, with a keyring it installs) and adds a cron job that keeps
# it. The image never runs apt again, so the step below deletes all of that: the
# only key the build trusted is the pinned one.
RUN set -eu; \
    export DEBIAN_FRONTEND=noninteractive; \
    apt-get update; \
    apt-get upgrade -y; \
    apt-get install -y --no-install-recommends ca-certificates gpg; \
    fingerprints=$(gpg --show-keys --with-colons "$EDGE_KEYRING" | awk -F: '$1 == "pub" { want = 1; next } $1 == "fpr" && want { print $10; want = 0 }'); \
    if [ "$fingerprints" != "$MICROSOFT_SIGNER_FINGERPRINT" ]; then \
        echo "Microsoft key fingerprint mismatch: got '$fingerprints'" >&2; exit 1; \
    fi; \
    echo "deb [arch=amd64 signed-by=$EDGE_KEYRING] https://packages.microsoft.com/repos/edge stable main" \
        > /etc/apt/sources.list.d/microsoft-edge.list; \
    apt-get update; \
    apt-get install -y --no-install-recommends \
        microsoft-edge-stable xvfb python3 iptables iproute2; \
    apt-get purge -y --auto-remove gpg; \
    rm -rf /var/lib/apt/lists/* /root/.gnupg /etc/cron.daily/microsoft-edge \
        /etc/apt/sources.list.d/microsoft-edge.* /usr/share/keyrings/microsoft-edge.*

# The policy folder is made here because COPY --chmod would give the folders it
# creates the file's mode (0644), and Edge couldn't enter them.
RUN useradd --create-home --uid 1000 --shell /usr/sbin/nologin edge \
    && install -d -o edge -g edge -m 0700 /run/signal \
    && install -d -m 0755 /etc/opt/edge/policies/managed /opt/signal \
    && install -d -m 1777 /tmp/.X11-unix

# Managed policies: root-owned, so "edge" can't change them.
COPY --chmod=0644 guest/edge_policy.json /etc/opt/edge/policies/managed/signal.json
COPY --chmod=0755 guest/entrypoint.sh /opt/signal/entrypoint.sh
COPY --chmod=0644 guest/main.py guest/relay.py guest/processes.py guest/edge_switches.py /opt/signal/

EXPOSE 9333
ENTRYPOINT ["/opt/signal/entrypoint.sh"]
