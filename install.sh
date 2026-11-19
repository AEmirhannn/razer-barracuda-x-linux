#!/bin/sh
set -eu
cd "$(dirname "$0")"
data="$HOME/.local/share/razer-barracuda-x"
bin="$HOME/.local/bin"
units="${XDG_CONFIG_HOME:-$HOME/.config}/systemd/user"
install -d "$data/barracuda" "$bin" "$units"
install -m 644 barracuda/*.py "$data/barracuda/"
install -m 644 packaging/razer-barracuda-x.service "$units/"
cat > "$bin/barracudactl" <<'LAUNCHER'
#!/bin/sh
cd "$HOME/.local/share/razer-barracuda-x" || exit 1
exec /usr/bin/python3 -m barracuda "$@"
LAUNCHER
chmod 755 "$bin/barracudactl"
systemctl --user daemon-reload
systemctl --user enable --now razer-barracuda-x.service
systemctl --user restart razer-barracuda-x.service
