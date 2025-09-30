# Debian KDE Booster

**Debian KDE Booster** est une application PyQt5 pour gérer et optimiser facilement un système Debian avec KDE. Elle permet de nettoyer le système, ajuster les performances et gérer les services actifs et inactifs via une interface graphique conviviale.

---

## Fonctionnalités

### 1. Nettoyage du système
Permet de supprimer différents types de fichiers et caches pour libérer de l’espace et améliorer la réactivité du système.

- **Corbeille** (`trash`) : vide `~/.local/share/Trash`
- **Documents récents** (`recent`) : supprime `~/.local/share/RecentDocuments`
- **Cache Firefox** (`firefox_cache`) : supprime `~/.cache/mozilla/firefox`
- **Miniatures** (`thumbnails`) : supprime `~/.cache/thumbnails`
- **Cache système** (`system_cache`) : supprime `/var/cache/man`, `/var/cache/ldconfig`, `.cache/fontconfig`, etc.
- **Caches temporaires** (`tmp`, `var_tmp`) : nettoie `/tmp` et `/var/tmp`
- **Journaux systemd** (`journal`, `journal_vacuum`) : nettoie `/var/log/journal` et réduit la rétention à 30 jours
- **Caches mémoire** (`drop_caches`) : libère les caches RAM
- **Swap** (`swap`) : rafraîchit la mémoire swap
- **APT** (`apt_cache`, `apt_autoremove`) : supprime les fichiers temporaires et exécute `autoremove`/`autoclean`
- **Logs KDE/Plasma** (`kde_logs`) : supprime les journaux utilisateurs KDE

Le nettoyage peut être appliqué **à la sélection** ou **à tout le système**.

---

### 2. Optimisation des performances
Permet de modifier différents paramètres système pour améliorer la réactivité et l’usage des ressources.

- **Swappiness** (`vm.swappiness`) : ajustement de la gestion de la mémoire
- **HugePages** (`vm.nr_hugepages`) : configuration des pages mémoire énormes
- **CPU Governor** : ajuste le mode de gestion de la fréquence CPU
- **ZRAM** : activation/désactivation de la mémoire compressée ZRAM
- **Planificateur I/O** : modification du scheduler I/O
- **Services** : activer/désactiver certains services système (ex : Bluetooth, CUPS)

Toutes les modifications peuvent être appliquées ou restaurées à l’état précédent, soit sur les options sélectionnées, soit sur toutes.

---

### 3. Gestion des services
Interface pour visualiser, contrôler et gérer les services système :

- **Services actifs** : liste tous les services en cours d’exécution avec les applications associées
- **Services inactifs** : liste tous les services inactifs ou échoués
- **Actions disponibles** :
  - Redémarrer, démarrer, stopper un service
  - Voir les processus associés à un service et les tuer si nécessaire

---

## Pre-Installation

1. Installer les dépendances :

sudo apt install python3 python3-pyqt5 cpupower systemctl

## Installation

Pour installer Debian KDE Booster sur votre système Debian/KDE, suivez ces étapes :

### 1. Copier les fichiers exécutables

Placez les fichiers `DebianBooster.py` et `DebianBooster.sh` dans `/usr/local/bin/` :

sudo cp DebianBooster.py DebianBooster.sh /usr/local/bin/

### 2. Copier le fichier desktop

cp DebianBooster.desktop ~/.local/share/applications/

### 3. Copier l’icône

cp DebianBooster.png ~/.local/share/icons/

### 4. Donner les permissions d’exécution

sudo chmod +x /usr/local/bin/DebianBooster.py
sudo chmod +x /usr/local/bin/DebianBooster.sh

### 5. Lancer l’application
Vous pouvez maintenant lancer l’application depuis le menu KDE ou directement via le terminal :
Si depuis le terminal utiliser: sudo python3 DebianBooster.py
Sinon si vous avez fais les étapes de 1 à 4 vous pouvez trouver l'application depuis le le menu KDE.
