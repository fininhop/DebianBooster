#!/bin/bash
# Wrapper pour lancer DebianBooster.py avec droits root via pkexec
SELF="$(readlink -f "$0")"
BASEDIR="$(dirname "$SELF")"
SCRIPT="$BASEDIR/DebianBooster.py"

if [ ! -f "$SCRIPT" ]; then
  zenity --error --text="Script introuvable : $SCRIPT"
  exit 1
fi

# Fonction pour récupérer le thème KDE courant
get_kde_theme() {
    local cfg="$HOME/.config/kdeglobals"
    if [ -f "$cfg" ]; then
        grep '^ColorScheme=' "$cfg" | cut -d= -f2
    else
        echo "BreezeDark"  # Valeur par défaut
    fi
}

KDE_THEME=$(get_kde_theme)

# Variables communes pour KDE
THEME_VARS="XDG_CURRENT_DESKTOP=KDE KDE_FULL_SESSION=true QT_STYLE_OVERRIDE=$KDE_THEME"

# Détection de la session (X11 ou Wayland)
if [ -n "$WAYLAND_DISPLAY" ]; then
    # Wayland
    SESSION_VARS="WAYLAND_DISPLAY=$WAYLAND_DISPLAY XDG_RUNTIME_DIR=$XDG_RUNTIME_DIR"
else
    # X11
    SESSION_VARS="DISPLAY=$DISPLAY XAUTHORITY=$XAUTHORITY"
fi

if [ "$(id -u)" -ne 0 ]; then
    exec pkexec env HOME="$HOME" $SESSION_VARS $THEME_VARS python3 "$SCRIPT"
else
    exec env $SESSION_VARS $THEME_VARS python3 "$SCRIPT"
fi
