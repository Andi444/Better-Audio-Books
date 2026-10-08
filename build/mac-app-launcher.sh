#!/bin/sh
set -eu
BAB_RESOURCES=$(CDPATH= cd -P "$(dirname "$0")/../Resources" && pwd)
case "$(uname -m)" in
  arm64) BAB_ARCH=arm64 ;;
  x86_64) BAB_ARCH=x86_64 ;;
  *) /usr/bin/osascript -e 'display alert "BAB kunde inte starta" message "Den här versionen stöder Apple-chip och Intel-Mac."'; exit 1 ;;
esac
export BAB_MAC_PACKAGES="$BAB_RESOURCES/mac-$BAB_ARCH/packages"
BAB_LOGDIR="${BAB_DATA_DIR:-$HOME/Library/Application Support/Better Audio Books}"
mkdir -p "$BAB_LOGDIR"
exec "$BAB_RESOURCES/mac-$BAB_ARCH/runtime/bin/python3.12" -I "$BAB_RESOURCES/app/mac_launcher.py" >>"$BAB_LOGDIR/launcher.log" 2>&1
