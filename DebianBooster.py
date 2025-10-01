#!/usr/bin/env python3
import os, pwd, shutil, signal, subprocess, sys, time
from pathlib import Path
from functools import partial
from PyQt5 import QtCore, QtWidgets
from PyQt5.QtGui import QIcon
from PyQt5.QtWidgets import QProgressDialog

HOME = Path(pwd.getpwnam(os.environ["SUDO_USER"]).pw_dir) if "SUDO_USER" in os.environ else Path.home()

def run(cmd, use_sudo=False):
    if isinstance(cmd, str): cmd = cmd.split()
    if use_sudo and os.geteuid() != 0: cmd = ["sudo"] + cmd
    r = subprocess.run(cmd, text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    return r.returncode, r.stdout.strip(), r.stderr.strip()

def get_sysctl_param(param):
    rc, out, _ = run(["sysctl", "-n", param])
    return out if rc == 0 else "inconnu"

def set_sysctl_param(param, value, use_sudo=True):
    cmd = (
        f"/bin/grep -q '^{param}' /etc/sysctl.conf && "
        f"/bin/sed -i 's|^{param}=.*|{param}={value}|' /etc/sysctl.conf || "
        f"/bin/echo '{param}={value}' >> /etc/sysctl.conf"
    )
    run(cmd, use_sudo)
    run(["sysctl", "-p"], use_sudo)

def remove_sysctl_param(param, use_sudo=True):
    run(f"/bin/sed -i '/{param}/d' /etc/sysctl.conf", use_sudo)
    run(["sysctl", "-p"], use_sudo)

def get_cpu_governor():
    try:
        govs = {p.read_text().strip() for p in Path('/sys/devices/system/cpu').glob('cpu[0-9]*/cpufreq/scaling_governor')}
        return ','.join(sorted(govs)) if govs else 'inconnu'
    except: return 'inconnu'

def set_cpu_governor(gov, use_sudo=True): run(["cpupower","frequency-set","-g",gov], use_sudo)
def zram_enabled(): return run(["systemctl","is-enabled","zramswap"])[0] == 0
def enable_zram(use_sudo=True): run(["systemctl","enable","--now","zramswap"], use_sudo)
def disable_zram(use_sudo=True): run(["systemctl","disable","--now","zramswap"], use_sudo)

def get_io_schedulers():
    scheds = {}
    for d in Path('/sys/block').glob('sd*'):
        try: scheds[d.name] = (d/'queue'/'scheduler').read_text().strip()
        except: scheds[d.name] = 'inconnu'
    return scheds

def set_io_scheduler(scheduler, use_sudo=True):
    for d in Path('/sys/block').glob('sd*'):
        run(f"echo {scheduler} | sudo tee /sys/block/{d.name}/queue/scheduler", use_sudo)

def service_enabled(name): return run(["systemctl","is-enabled",name])[0] == 0
def set_service(name, enable=True, use_sudo=True):
    run(["systemctl", "enable" if enable else "disable", "--now", name], use_sudo)

def confirm_action(parent, text):
    return QtWidgets.QMessageBox.question(parent, "Confirmation", text,
        QtWidgets.QMessageBox.Yes | QtWidgets.QMessageBox.No) == QtWidgets.QMessageBox.Yes

DIR_MAP = {
    "trash":[HOME/".local/share/Trash/files", HOME/".local/share/Trash/info"],
    "recent":[HOME/".local/share/RecentDocuments"],
    "firefox_cache":[HOME/".cache/mozilla/firefox"],
    "thumbnails":[HOME/".cache/thumbnails"],
    "apt_cache":[Path("/var/cache/apt")],
    "system_cache":[HOME/".cache/fontconfig", Path("/var/cache/man"), Path("/var/cache/ldconfig"), Path("/var/cache/misc")],
    "tmp":[Path("/tmp"), Path("/var/tmp")],
    "journal":[Path("/var/log/journal")]  
}

def safe_rmtree(path):
    try: shutil.rmtree(path); return True
    except: return False

def clean_caches(actions):
    results = []
    for a in actions:
        try:
            if a == "drop_caches":
                run(["sync"], True)
                run(["sh", "-c", "echo 3 > /proc/sys/vm/drop_caches"], True)
                results.append((a, "[✓] Caches mémoire libérées"))
            elif a == "swap":
                run(["swapoff", "-a"], True)
                run(["swapon", "-a"], True)
                results.append((a, "[✓] Swap rafraîchi"))
            elif a == "apt_autoremove":
                run(["apt-get", "-y", "autoremove"], True)
                run(["apt-get", "-y", "autoclean"], True)
                results.append((a, "[✓] APT autoremove/autoclean effectués"))
            elif a == "journal_vacuum":
                run(["journalctl", "--vacuum-time=30d"], True)
                results.append((a, "[✓] Journaux systemd réduits à 30 jours"))
            elif a == "kde_logs":
                count = 0
                kde_paths = [HOME / ".xsession-errors", HOME / ".local/share/sddm"]
                for p in kde_paths:
                    if p.exists():
                        if p.is_file():
                            p.unlink(); count += 1
                        else:
                            count += safe_rmtree(p)
                results.append((a, f"[✓] {count} fichiers journaux KDE supprimés"))
            elif a == "tmp":
                count = 0
                for p in DIR_MAP.get("tmp", []):
                    if p.exists():
                        if p.is_file():
                            p.unlink(); count += 1
                        else:
                            count += safe_rmtree(p)
                results.append((a, f"[✓] {count} fichiers/dossiers supprimés dans /tmp"))
            elif a == "var_tmp":
                cutoff = time.time() - 30*86400
                count = 0
                for p in Path("/var/tmp").iterdir():
                    if p.is_file() and p.stat().st_mtime < cutoff:
                        p.unlink(); count += 1
                    elif p.is_dir() and safe_rmtree(p):
                        count += 1
                results.append((a, f"[✓] {count} fichiers/dossiers anciens supprimés dans /var/tmp"))
            elif a == "var_tmp_aggressive":
                count = 0
                for p in Path("/var/tmp").iterdir():
                    if p.is_file():
                        p.unlink(); count += 1
                    elif p.is_dir() and safe_rmtree(p):
                        count += 1
                results.append((a, f"[✓] purge agressive : {count} fichiers/dossiers supprimés dans /var/tmp"))
            else:
                count = 0
                for p in DIR_MAP.get(a, []):
                    if p.exists():
                        if p.is_file():
                            p.unlink(); count += 1
                        else:
                            count += safe_rmtree(p)
                results.append((a, f"[✓] {count} éléments supprimés ({a})"))
        except Exception as e:
            results.append((a, f"[Erreur] {e}"))
    return results

class Signals(QtCore.QObject):
    result = QtCore.pyqtSignal(object)
    error = QtCore.pyqtSignal(str)
    finished = QtCore.pyqtSignal()

class Worker(QtCore.QRunnable):
    def __init__(self, fn, *args):
        super().__init__()
        self.fn, self.args = fn, args
        self.signals = Signals()
    @QtCore.pyqtSlot()
    def run(self):
        try: self.signals.result.emit(self.fn(*self.args))
        except Exception as e: self.signals.error.emit(str(e))
        finally: self.signals.finished.emit()

class MainWindow(QtWidgets.QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Debian KDE Booster")
        self.setWindowIcon(QIcon("/home/cattac/.local/share/icons/DebianBoosterIcon.png"))
        self.resize(1000,800)
        self.pool = QtCore.QThreadPool(); self.pool.setMaxThreadCount(2)
        self.tabs = QtWidgets.QTabWidget(); self.setCentralWidget(self.tabs)

        # ---- setup onglets ----
        self.setup_clean_tab()
        self.setup_perf_tab()
        self.setup_services_tab()
        self.setup_inactive_services_tab()
        self.refresh_perf()

        # Timer services
        self.services_timer = QtCore.QTimer(); self.services_timer.setInterval(5000)
        self.services_timer.timeout.connect(self.refresh_active_service_tab)
        self.tabs.currentChanged.connect(self.on_tab_changed)

    # ---------------- LOG UTILS ----------------
    def log_safe(self, widget, msg):
        clean_msg = msg.strip()
        if clean_msg:
            QtCore.QTimer.singleShot(0, lambda: widget.appendPlainText(clean_msg))

    def start_with_loader(self, fn, *args, log_widget=None):
        loader = QtWidgets.QProgressDialog("Opération en cours...", None, 0, 0, self)
        loader.setWindowModality(QtCore.Qt.ApplicationModal)
        loader.setCancelButton(None)
        loader.show()
        worker = Worker(fn, *args)
        if log_widget:
            worker.signals.result.connect(lambda res: [self.log_safe(log_widget, m) for _, m in res])
        worker.signals.finished.connect(loader.close)
        self.pool.start(worker)
        
    # --- Onglet Performance avec séparateur ---
    def refresh_perf_with_log(self):
        if self.log_perf.toPlainText().strip():
            self.log_perf.appendPlainText("\n" + "-"*40 + "\n")
        self.start_with_loader(self.refresh_perf, log_widget=self.log_perf)
        
    def apply_perf(self, apply, selected):
        results = []
        keys = self.options.keys() if not selected else [k for k,(cb,_) in self.options.items() if cb.isChecked()]
        if not keys:
            results.append(("info","Aucune option sélectionnée"))
            return results

        results.append(("info", f"{'Application' if apply else 'Restauration'} : {', '.join(keys)}"))

        for k in keys:
            try:
                if k == "governor":
                    # appliquer/restaurer dans le thread principal
                    gov_value = "performance" if apply else "powersave"
                    QtCore.QTimer.singleShot(0, lambda val=gov_value: set_cpu_governor(val))

                # Autres options (swappiness, hugepages, zram, iosched, services…) restent inchangées
                results.append((k, f"{k} -> {'appliqué' if apply else 'restauré'}"))
            except Exception as e:
                results.append((k, f"{k} erreur : {e}"))

        # Vérifier que le governor a bien changé avant de rafraîchir l'UI
        def refresh_after_governor():
            max_tries = 5
            interval = 0.2
            for _ in range(max_tries):
                if "governor" in keys and get_cpu_governor() != ("performance" if apply else "powersave"):
                    time.sleep(interval)
                else:
                    break
            self.refresh_perf()  # refresh de l’UI dans le thread principal

        QtCore.QTimer.singleShot(100, refresh_after_governor)  # petit délai avant vérif
        return results
        
    # ---- Nettoyage ----
    def setup_clean_tab(self):
        self.clean_options = {}
        self.tab_clean = QtWidgets.QWidget()
        self.tabs.addTab(self.tab_clean, "Nettoyage")
        clean_items = ["trash", "recent", "thumbnails", "firefox_cache", "journal_vacuum", "journal", "tmp", "var_tmp","var_tmp_aggressive", "system_cache", "drop_caches","apt_cache", "apt_autoremove", "kde_logs", "swap"]
        clean_titles = {"trash":"Corbeille","recent":"Documents récents","firefox_cache":"Cache Firefox","thumbnails":"Miniatures","apt_cache":"Cache APT","system_cache":"Cache système","tmp":"Mémoire temporaire","journal":"Journaux systemd","drop_caches":"Caches mémoire","swap":"Mémoire swap","apt_autoremove":"APT autoremove/autoclean","journal_vacuum":"Journalctl (vacuum 30j)","kde_logs":"Logs KDE/Plasma","var_tmp":"Mémoire temporaire (/var/tmp) - standard","var_tmp_aggressive":"Mémoire temporaire (/var/tmp) - purge agressive"}
        clean_desc = {"trash":"~/.local/share/Trash","recent":"~/.local/share/RecentDocuments","firefox_cache":"~/.cache/mozilla/firefox","thumbnails":"~/.cache/thumbnails","apt_cache":"/var/cache/apt","system_cache":"~/.cache/fontconfig, /var/cache/man, /var/cache/ldconfig, /var/cache/misc","tmp":"/tmp","journal":"/var/log/journal","drop_caches":"Caches mémoire du système","swap":"Mémoire swap","apt_autoremove":"apt-get autoremove & autoclean","journal_vacuum":"Réduit journaux systemd à 30 jours","kde_logs":"~/.xsession-errors et ~/.local/share/sddm","var_tmp":"Supprime uniquement les fichiers vieux de plus de 30 jours","var_tmp_aggressive":"Supprime tous les fichiers, attention risque d’impacter certains programmes"}
        layout = QtWidgets.QGridLayout(); layout.setSpacing(10)
        n = len(clean_items); n_rows = (n + 1) // 2
        for row in range(n_rows):
            for col in range(2):
                idx = row + col * n_rows
                if idx >= n: continue
                key = clean_items[idx]
                container = QtWidgets.QWidget(); v_layout = QtWidgets.QVBoxLayout(container)
                v_layout.setContentsMargins(0,0,0,0); v_layout.setSpacing(2)
                cb = QtWidgets.QCheckBox(clean_titles.get(key,key))
                cb.setChecked(key in ["trash","recent","thumbnails","firefox_cache","journal_vacuum","drop_caches","swap"])
                self.clean_options[key] = cb; v_layout.addWidget(cb)
                label = QtWidgets.QLabel(f"({clean_desc.get(key,'')})")
                font = label.font(); font.setPointSize(9); label.setFont(font); label.setStyleSheet("color:#555"); label.setWordWrap(True)
                v_layout.addWidget(label); layout.addWidget(container,row,col)
        btn_layout = QtWidgets.QHBoxLayout(); self.btn_clean_sel = QtWidgets.QPushButton("Appliquer sélection"); self.btn_clean_all = QtWidgets.QPushButton("Appliquer tout"); btn_layout.addWidget(self.btn_clean_sel); btn_layout.addWidget(self.btn_clean_all); layout.addLayout(btn_layout,n_rows,0,1,2)
        self.log_clean = QtWidgets.QPlainTextEdit(); self.log_clean.setReadOnly(True); layout.addWidget(self.log_clean,n_rows+1,0,1,2)
        self.tab_clean.setLayout(layout)
        # Boutons et log
        self.btn_clean_sel.clicked.connect(lambda: self.confirmed_start_clean(True))
        self.btn_clean_all.clicked.connect(lambda: self.confirmed_start_clean(False))

    def confirmed_start_clean(self, selected):
        if confirm_action(self, "Confirmer le nettoyage ?"):
            self.start_clean(selected)

    def start_clean(self, selected):
        keys = [k for k, cb in self.clean_options.items() if cb.isChecked()] if selected else list(self.clean_options.keys())
        if not keys:
            self.log_clean.appendPlainText("Aucune action sélectionnée")
            return
        # Ne plus ajouter de séparateur ici
        self.start_with_loader(clean_caches, keys, log_widget=self.log_clean)


    def on_clean_done(self, results, loader):
        loader.close()
        for a, msg in results: self.log_clean.appendPlainText(msg)
        self.log_clean.appendPlainText("[✓] Nettoyage terminé\n")

    # ---------------- Onglet Performance ----------------
    def setup_perf_tab(self):
        self.options = {}
        self.tab_perf = QtWidgets.QWidget()
        self.tabs.addTab(self.tab_perf, "Performance")
        opts = [("swappiness","vm.swappiness"),("hugepages","vm.nr_hugepages"),
                ("governor","Gouverneur CPU"),("zram","ZRAM"),
                ("iosched","Planificateur I/O"),("bluetooth","Service Bluetooth"),
                ("cups","Service CUPS")]
        layout = QtWidgets.QVBoxLayout()
        opts_group = QtWidgets.QGroupBox("Options")
        opts_layout = QtWidgets.QGridLayout()
        opts_group.setLayout(opts_layout)
        for i,(k,lbl) in enumerate(opts):
            cb = QtWidgets.QCheckBox(lbl); val = QtWidgets.QLabel("...")
            opts_layout.addWidget(cb,i,0); opts_layout.addWidget(val,i,1)
            self.options[k] = (cb,val)
        layout.addWidget(opts_group)

        # boutons
        btn_layout = QtWidgets.QHBoxLayout()
        self.btn_refresh = QtWidgets.QPushButton("Rafraîchir")
        self.btn_apply_sel = QtWidgets.QPushButton("Appliquer sélection")
        self.btn_revert_sel = QtWidgets.QPushButton("Revert sélection")
        self.btn_apply_all = QtWidgets.QPushButton("Appliquer tout")
        self.btn_revert_all = QtWidgets.QPushButton("Revert tout")
        for b in [self.btn_refresh,self.btn_apply_sel,self.btn_revert_sel,self.btn_apply_all,self.btn_revert_all]: btn_layout.addWidget(b)
        layout.addLayout(btn_layout)

        # log
        self.log_perf = QtWidgets.QPlainTextEdit(); self.log_perf.setReadOnly(True)
        layout.addWidget(self.log_perf)
        self.tab_perf.setLayout(layout)

        # connections
        self.btn_refresh.clicked.connect(lambda: self.confirmed_refresh_perf())
        self.btn_apply_sel.clicked.connect(lambda: self.confirmed_apply_perf(True, True))
        self.btn_revert_sel.clicked.connect(lambda: self.confirmed_apply_perf(False, True))
        self.btn_apply_all.clicked.connect(lambda: self.confirmed_apply_perf(True, False))
        self.btn_revert_all.clicked.connect(lambda: self.confirmed_apply_perf(False, False))

    def confirmed_refresh_perf(self):
        if confirm_action(self,"Confirmer le rafraîchissement ?"):
            self.refresh_perf()

    def confirmed_apply_perf(self, apply, selected):
        if confirm_action(self, f"Confirmer {'application' if apply else 'restauration'} ?"):
            self.apply_perf(apply, selected)

    # ------------------ refresh_perf thread-safe ------------------
    def refresh_perf(self):
        def worker_fn():
            try:
                return {
                    "swappiness": get_sysctl_param("vm.swappiness"),
                    "hugepages": get_sysctl_param("vm.nr_hugepages"),
                    "governor": get_cpu_governor(),
                    "zram": "activé" if zram_enabled() else "désactivé",
                    "iosched": ",".join(f"{k}:{v}" for k,v in get_io_schedulers().items()),
                    "bluetooth": "activé" if service_enabled("bluetooth") else "désactivé",
                    "cups": "activé" if service_enabled("cups") else "désactivé"
                }
            except Exception as e:
                return {"error": str(e)}

        def update_ui(res):
            if "error" in res:
                self.log_safe(self.log_perf, f"[Erreur] {res['error']}")
                return
            for k, v in res.items():
                if k in self.options:
                    self.options[k][1].setText(v)
            self.log_safe(self.log_perf, "-"*40)
            self.log_safe(self.log_perf, "[✓] Statut rafraîchi")

        worker = Worker(worker_fn)
        worker.signals.result.connect(update_ui)
        self.pool.start(worker)

    # ------------------ apply_perf thread-safe ------------------
    def apply_perf(self, apply, selected):
        keys = self.options.keys() if not selected else [k for k,(cb,_) in self.options.items() if cb.isChecked()]
        if not keys:
            self.log_safe(self.log_perf, "Aucune option sélectionnée")
            return

        self.log_safe(self.log_perf, "-"*40)
        self.log_safe(self.log_perf, f"{'Application' if apply else 'Restauration'} : {', '.join(keys)}")

        for k in keys:
            try:
                if k == "governor":
                    set_cpu_governor("performance" if apply else "powersave")
                elif k == "swappiness":
                    set_sysctl_param("vm.swappiness","10" if apply else "60")
                elif k == "hugepages":
                    set_sysctl_param("vm.nr_hugepages","128" if apply else "0")
                elif k == "zram":
                    enable_zram() if apply else disable_zram()
                elif k == "bluetooth":
                    set_service("bluetooth", enable=not apply)
                elif k == "cups":
                    set_service("cups", enable=not apply)
                self.log_safe(self.log_perf, f"{k} -> {'appliqué' if apply else 'restauré'}")
            except Exception as e:
                self.log_safe(self.log_perf, f"{k} erreur : {e}")

        # refresh UI après application
        QtCore.QTimer.singleShot(200, self.refresh_perf)

    def setup_services_tab(self):
        self.tab_services = QtWidgets.QWidget()
        self.tabs.addTab(self.tab_services,"Services actifs")
        layout = QtWidgets.QVBoxLayout()
        self.tab_services.setLayout(layout)
        self.services_table = QtWidgets.QTableWidget()
        layout.addWidget(self.services_table)
        self.services_table.setColumnCount(3)
        self.services_table.setHorizontalHeaderLabels(["Service","Statut","Applications"])
        self.services_table.horizontalHeader().setStretchLastSection(True)
        self.services_table.setContextMenuPolicy(QtCore.Qt.CustomContextMenu)
        self.services_table.customContextMenuRequested.connect(self.on_service_context)
        self.log_services = QtWidgets.QPlainTextEdit()
        self.log_services.setReadOnly(True)
        self.log_services.setMaximumHeight(120)
        layout.addWidget(self.log_services)
        self.proc_cache = {}
        self.ppid_cache = {}

    def setup_inactive_services_tab(self):
        self.tab_inactive = QtWidgets.QWidget()
        self.tabs.insertTab(self.tabs.indexOf(self.tab_services)+1, self.tab_inactive, "Services inactifs")
        layout = QtWidgets.QVBoxLayout()
        self.tab_inactive.setLayout(layout)
        self.inactive_table = QtWidgets.QTableWidget()
        layout.addWidget(self.inactive_table)
        self.inactive_table.setColumnCount(3)
        self.inactive_table.setHorizontalHeaderLabels(["Service","Statut","Applications"])
        self.inactive_table.horizontalHeader().setStretchLastSection(True)
        self.inactive_table.setContextMenuPolicy(QtCore.Qt.CustomContextMenu)
        self.inactive_table.customContextMenuRequested.connect(self.on_inactive_context)
        self.log_inactive = QtWidgets.QPlainTextEdit()
        self.log_inactive.setReadOnly(True)
        self.log_inactive.setMaximumHeight(120)
        layout.addWidget(self.log_inactive)

    def on_tab_changed(self, index):
        widget = self.tabs.widget(index)
        if widget in (getattr(self, 'tab_services', None), getattr(self, 'tab_inactive', None)):
            self.services_timer.start()
            if widget == self.tab_services: self.refresh_services()
            else: self.refresh_inactive_services()
        else:
            self.services_timer.stop()

    def refresh_active_service_tab(self):
        current = self.tabs.currentWidget()
        if current == self.tab_services: self.refresh_services()
        elif current == self.tab_inactive: self.refresh_inactive_services()

    def refresh_services(self):
        self.build_proc_cache()
        rc, out, _ = run("systemctl list-units --type=service --state=running --no-legend --no-pager")
        services = [l.split()[0] for l in out.splitlines() if l.strip() and l.split()[0].endswith(".service")]
        self.services_table.setUpdatesEnabled(False)
        self.services_table.setRowCount(len(services))
        for row, svc in enumerate(sorted(services)):
            self.services_table.setItem(row,0,QtWidgets.QTableWidgetItem(svc))
            self.services_table.setItem(row,1,QtWidgets.QTableWidgetItem("running"))
            pids = self.get_service_pids(svc)
            apps = set(self.proc_cache.get(pid,"?") for pid in pids)
            self.services_table.setItem(row,2,QtWidgets.QTableWidgetItem(",".join(sorted(apps))))
        self.services_table.resizeColumnToContents(0)
        self.services_table.setSortingEnabled(True)
        self.services_table.setUpdatesEnabled(True)

    def refresh_inactive_services(self):
        rc, out, _ = run("systemctl list-unit-files --type=service --no-legend")
        services = []
        for line in out.splitlines():
            svc_name = line.split()[0]
            rc2, state, _ = run(["systemctl", "is-active", svc_name])
            if state in ("inactive", "failed"):
                services.append(svc_name)
        self.inactive_table.setUpdatesEnabled(False)
        self.inactive_table.setRowCount(len(services))
        for row, svc in enumerate(sorted(services)):
            self.inactive_table.setItem(row,0,QtWidgets.QTableWidgetItem(svc))
            self.inactive_table.setItem(row,1,QtWidgets.QTableWidgetItem("inactive"))
            self.inactive_table.setItem(row,2,QtWidgets.QTableWidgetItem(""))
        self.inactive_table.resizeColumnToContents(0)
        self.inactive_table.setSortingEnabled(True)
        self.inactive_table.setUpdatesEnabled(True)

    def on_service_context(self,pos):
        item=self.services_table.itemAt(pos)
        if not item: return
        row=item.row(); svc=self.services_table.item(row,0).text()
        menu=QtWidgets.QMenu()
        menu.addAction("Redémarrer", lambda: self.confirmed_control_service(svc,"restart"))
        menu.addAction("Stopper", lambda: self.confirmed_control_service(svc,"stop"))
        menu.addAction("Voir processus", lambda: self.show_service_processes(svc))
        menu.exec_(self.services_table.viewport().mapToGlobal(pos))

    def on_inactive_context(self,pos):
        item=self.inactive_table.itemAt(pos)
        if not item: return
        row=item.row(); svc=self.inactive_table.item(row,0).text()
        menu=QtWidgets.QMenu()
        menu.addAction("Démarrer", lambda: self.confirmed_control_service(svc,"start"))
        menu.exec_(self.inactive_table.viewport().mapToGlobal(pos))

    def confirmed_control_service(self,svc,action):
        if confirm_action(self,f"Confirmer {action} pour {svc} ?"): self.control_service(svc,action)

    def control_service(self, svc, action):
        def fn():
            rc,out,err = run(["sudo","systemctl",action,svc])
            return f"{action} {svc}: {'OK' if rc==0 else 'Erreur '+err}"
        w = Worker(fn)
        w.signals.result.connect(lambda msg: self.log_inactive.appendPlainText(msg) if action=="start" else self.log_services.appendPlainText(msg))
        w.signals.finished.connect(lambda: self.refresh_inactive_services() if action=="start" else self.refresh_services())
        self.pool.start(w)

    def build_proc_cache(self):
        self.proc_cache.clear()
        self.ppid_cache.clear()
        for pid in os.listdir("/proc"):
            if not pid.isdigit(): continue
            try:
                with open(f"/proc/{pid}/comm") as f: self.proc_cache[pid]=f.read().strip()
                with open(f"/proc/{pid}/status") as f:
                    for l in f:
                        if l.startswith("PPid:"):
                            ppid = l.split()[1]; self.ppid_cache.setdefault(ppid,set()).add(pid)
            except: continue

    def get_service_pids(self,service):
        pids=set(); svc_name=service.replace('.service','')
        for pid in os.listdir("/proc"):
            if not pid.isdigit(): continue
            try:
                with open(f"/proc/{pid}/cgroup") as f:
                    if any(svc_name in line for line in f): pids.add(pid)
            except: pass
        return pids

    def kill_pid_safe(self,pid):
        if not confirm_action(self,f"Voulez-vous tuer le processus PID {pid} ?"): return
        try: os.kill(int(pid), signal.SIGKILL); self.log_services.appendPlainText(f"PID {pid} tué")
        except ProcessLookupError: self.log_services.appendPlainText(f"PID {pid} inexistant")
        except PermissionError: self.log_services.appendPlainText(f"PID {pid} — permission refusée")

    def show_service_processes(self, svc):
        dlg = QtWidgets.QDialog(self)
        dlg.setWindowTitle(f"Processus de {svc}")
        layout = QtWidgets.QVBoxLayout(dlg)

        table = QtWidgets.QTableWidget()
        table.setColumnCount(3)
        table.setHorizontalHeaderLabels(["PID", "Nom", "Action"])
        layout.addWidget(table)
        pid_rows = {}

        def refresh_table():
            self.build_proc_cache()
            pids = sorted(self.get_service_pids(svc))
            for pid in pids:
                if pid in pid_rows:
                    row = pid_rows[pid]
                    item = table.item(row, 1)
                    if item is None:
                        item = QtWidgets.QTableWidgetItem(self.proc_cache.get(pid, "?"))
                        table.setItem(row, 1, item)
                    else:
                        item.setText(self.proc_cache.get(pid, "?"))
                else:
                    row = table.rowCount()
                    table.insertRow(row)
                    table.setItem(row, 0, QtWidgets.QTableWidgetItem(pid))
                    table.setItem(row, 1, QtWidgets.QTableWidgetItem(self.proc_cache.get(pid, "?")))
                    btn = QtWidgets.QPushButton("Tuer")
                    btn.clicked.connect(lambda _, p=pid: self.kill_pid_safe(p))
                    table.setCellWidget(row, 2, btn)
                    pid_rows[pid] = row

            # Supprimer les PID disparus
            removals = [(pid, pid_rows[pid]) for pid in pid_rows if pid not in pids]
            removals.sort(key=lambda x: x[1], reverse=True)
            for pid, row in removals:
                table.removeRow(row)
                del pid_rows[pid]

        timer = QtCore.QTimer(dlg)
        timer.setInterval(2000)
        timer.timeout.connect(refresh_table)
        timer.start()
        refresh_table()

        table.resizeColumnsToContents()
        table.resizeRowsToContents()
        table.setSortingEnabled(True)
        v_scroll_width = table.verticalScrollBar().sizeHint().width()
        dlg.resize(table.horizontalHeader().length() + v_scroll_width + 50,
                table.verticalHeader().length() + 50)
        dlg.exec_()

    def start_with_loader(self, fn, *args, log_widget=None):
        dlg = QtWidgets.QProgressDialog("Opération en cours...", None, 0, 0, self)
        dlg.setWindowModality(QtCore.Qt.ApplicationModal)
        dlg.setCancelButton(None)
        dlg.setMinimumDuration(0)
        dlg.show()
        worker = Worker(fn, *args)

        if log_widget:
            def handle_result(res):
                if res is None:
                    return
                if isinstance(res, dict):
                    if "error" in res:
                        self.log_safe(log_widget, f"[Erreur] {res['error']}")
                    else:
                        self.log_safe(log_widget, "-"*40)
                        self.log_safe(log_widget, "[✓] Statut rafraîchi")
                else:
                    self.log_safe(log_widget, "-"*40)  # séparateur avant chaque série
                    for item in res:
                        if item is None: continue
                        try:
                            _, msg = item
                            self.log_safe(log_widget, msg)
                        except Exception:
                            pass

            worker.signals.result.connect(handle_result)

        worker.signals.finished.connect(dlg.close)
        self.pool.start(worker)


def main():
    app = QtWidgets.QApplication(sys.argv)
    win = MainWindow()
    win.show()
    if os.geteuid() != 0: win.statusBar().showMessage("Non root — certaines actions nécessitent sudo")
    sys.exit(app.exec_())

if __name__=="__main__":
    app = QtWidgets.QApplication(sys.argv)
    win = MainWindow(); win.show()
    sys.exit(app.exec_())
