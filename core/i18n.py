from core.settings import Settings

SUPPORTED_LANGUAGES = [("de", "Deutsch"), ("en", "English")]
DEFAULT_LANGUAGE = "de"

_TRANSLATIONS = {
    "de": {
        # ---------- Allgemein ----------
        "app.title": "GuideOSBookHub",
        "common.ok": "OK",
        "common.cancel": "Abbrechen",
        "common.close": "Schließen",
        "common.yes": "Ja",
        "common.no": "Nein",
        "common.error_title": "Fehler",
        "common.error_prefix": "Fehler: ",
        "common.ok_prefix": "OK: ",

        # ---------- Startseite (home_window.py) ----------
        "home.settings_button": "Einstellungen",
        "home.tagline": (
            "Deine Browser-Lesezeichen, sicher synchronisiert über eine Cloud oder "
            "einen USB-Stick deiner Wahl."
        ),
        "home.subtitle": (
            "Lesezeichen anlegen, ändern und löschen erledigst du weiterhin in deinem "
            "Browser. GuideOSBookHub übernimmt den Import, die Cloud-/Stick-Synchronisation "
            "und den Rück-Export."
        ),
        "home.import_card.title": "📥  Aus Browser in den Hub importieren",
        "home.import_card.subtitle": "Lesezeichen aus Vivaldi, Chrome & Co. übernehmen",
        "home.cloud_card.title": "☁️  Cloud-/Stick-Sync einrichten",
        "home.cloud_card.subtitle": (
            "Verbinde GuideOSBookHub mit einer Cloud, einem USB-Stick oder einem "
            "anderen Anbieter deiner Wahl"
        ),
        "home.export_card.title": "📤  Aus Hub in neuen Browser importieren",
        "home.export_card.subtitle": (
            "Lesezeichen in einen Browser deiner Wahl auf diesem Rechner schreiben"
        ),
        "home.sync_button": "Jetzt synchronisieren",
        "home.status_ready": "Bereit.",
        "home.status_syncing": "Synchronisiere...",
        "home.status_profile_error": "{profile}: Fehler – {error}",
        "home.status_profile_result": (
            "{profile}: {created} neu, {updated} aktualisiert, "
            "{deleted} gelöscht, {conflicts} Konflikte gelöst"
        ),

        # ---------- Browser-Import (browser_import_dialog.py) ----------
        "import.window_title": "Lesezeichen aus Browser importieren",
        "import.intro_first_run": (
            "Willkommen bei GuideOSBookHub! Welchen Browser nutzt du? "
            "Deine Lesezeichen werden automatisch gefunden und importiert."
        ),
        "import.intro": "Welchen Browser möchtest du importieren?",
        "import.other_file_item": "Andere Datei auswählen (z.B. Firefox-Export) …",
        "import.skip_button": "Überspringen",
        "import.cancel_button": "Abbrechen",
        "import.import_button": "Importieren",
        "import.not_found_title": "Nicht gefunden",
        "import.not_found_text": (
            "Die Lesezeichen-Datei von {browser} wurde nicht am erwarteten Ort gefunden. "
            "Bitte stattdessen manuell exportieren und auswählen."
        ),
        "import.file_dialog_title": "Lesezeichen-Datei auswählen",
        "import.file_dialog_filter": "HTML-Dateien (*.html *.htm)",
        "import.failed_title": "Import fehlgeschlagen",
        "import.done_title": "Import abgeschlossen",
        "import.done_text": (
            "{groups} Ordner und {bookmarks} Lesezeichen importiert, "
            "{skipped} Duplikate übersprungen."
        ),

        # ---------- Cloud-/Stick-Sync einrichten (cloud_setup_dialog.py) ----------
        "cloud.window_title": "Cloud-/Stick-Sync einrichten",
        "cloud.intro_first_run": (
            "Möchtest du deine Lesezeichen jetzt mit einer Cloud oder einem "
            "USB-Stick synchronisieren?"
        ),
        "cloud.intro": "Wähle einen Anbieter für die Synchronisation.",
        "cloud.step_label": "Schritt {step} von 2 — {title}",
        "cloud.step_title.provider": "Anbieter wählen",
        "cloud.step_title.details": "Zugangsdaten",
        "cloud.back_button": "Zurück",
        "cloud.next_button": "Weiter",
        "cloud.provider.webdav": "Nextcloud / ownCloud / WebDAV",
        "cloud.provider.protondrive": "Proton Drive",
        "cloud.provider.drive": "Google Drive",
        "cloud.provider.onedrive": "Microsoft OneDrive",
        "cloud.provider.dropbox": "Dropbox",
        "cloud.provider.pcloud": "pCloud",
        "cloud.provider.local": "USB-Stick / Lokaler Ordner",
        "cloud.oauth_intro": (
            "Melde dich im Browser an, um {provider} mit GuideOSBookHub zu verbinden."
        ),
        "cloud.oauth_button": "Im Browser anmelden",
        "cloud.oauth_waiting": "Warte auf Anmeldung im Browser...",
        "cloud.local_intro": (
            "Wähle einen Ordner auf einem USB-Stick oder einer lokalen Festplatte, "
            "in dem die Lesezeichen gespeichert werden sollen."
        ),
        "cloud.local_choose_button": "Ordner auswählen",
        "cloud.local_selected_path_label": "Gewählter Ordner:",
        "cloud.local_no_folder_title": "Kein Ordner ausgewählt",
        "cloud.local_no_folder_text": "Bitte zuerst einen Ordner auswählen.",
        "cloud.local_not_writable_title": "Ordner nicht beschreibbar",
        "cloud.local_not_writable_text": (
            "In diesen Ordner kann nicht geschrieben werden. Bitte einen anderen "
            "Ordner wählen (z.B. auf dem USB-Stick)."
        ),
        "cloud.protondrive_twofa_field": "2FA-Code (optional)",
        "cloud.protondrive_mailbox_password_field": "Mailbox-Passwort (optional)",
        "cloud.protondrive_hint": (
            "Falls dein Proton-Konto Zwei-Faktor-Authentifizierung nutzt, trage hier "
            "den aktuellen Code ein."
        ),
        "cloud.vendor.nextcloud": "Nextcloud",
        "cloud.vendor.owncloud": "ownCloud",
        "cloud.vendor.other": "Generisches WebDAV",
        "cloud.field.name": "Verbindungsname",
        "cloud.field.vendor": "Anbieter",
        "cloud.field.url": "Server-URL",
        "cloud.field.user": "Benutzername",
        "cloud.field.password": "Passwort",
        "cloud.url_placeholder": "https://deine-domain.tld/remote.php/dav/files/BENUTZERNAME/",
        "cloud.hint": (
            "Tipp bei Nextcloud: Nicht das normale Passwort verwenden, sondern unter "
            "Einstellungen → Sicherheit ein App-Passwort erzeugen."
        ),
        "cloud.skip_button": "Überspringen",
        "cloud.cancel_button": "Abbrechen",
        "cloud.setup_button": "Einrichten",
        "cloud.connecting": "Verbinde...",
        "cloud.step_create": "Lege Verbindung an...",
        "cloud.step_test": "Teste Verbindung...",
        "cloud.step_done": "Verbindung erfolgreich eingerichtet.",
        "cloud.missing_fields_title": "Angaben fehlen",
        "cloud.missing_fields_text": "Bitte alle Felder ausfüllen.",
        "cloud.rclone_missing_title": "rclone fehlt",
        "cloud.rclone_missing_text": (
            "rclone wurde nicht gefunden. Ohne rclone kann keine Cloud-Verbindung "
            "eingerichtet werden."
        ),
        "cloud.name_taken_title": "Verbindung existiert bereits",
        "cloud.name_taken_text": (
            "Es gibt bereits eine Verbindung namens '{name}'. Soll sie mit diesen "
            "Zugangsdaten aktualisiert werden?"
        ),
        "cloud.done_title": "Fertig",
        "cloud.done_text": (
            "'{name}' ist eingerichtet. Deine Lesezeichen werden ab jetzt automatisch "
            "synchronisiert (weitere Einstellungen dazu findest du unter 'Einstellungen')."
        ),

        # ---------- Rück-Export (export_to_browser_dialog.py) ----------
        "export.window_title": "Lesezeichen in Browser zurückschreiben",
        "export.step_title.browser": "Browser wählen",
        "export.step_title.strategy": "Strategie wählen",
        "export.step_title.confirm": "Bestätigen",
        "export.strategy.merge.title": "Zusammenführen",
        "export.strategy.merge.hint": (
            "Bestehende Lesezeichen im Browser bleiben erhalten, GuideOSBookHub ergänzt "
            "nur neue (keine doppelten Links)."
        ),
        "export.strategy.separate_folder.title": "In eigenen Ordner",
        "export.strategy.separate_folder.hint": (
            "Alle GuideOSBookHub-Lesezeichen landen gesammelt in einem neuen Ordner, "
            "der Rest bleibt unverändert."
        ),
        "export.strategy.replace.title": "Ersetzen",
        "export.strategy.replace.hint": (
            "Die Lesezeichenleiste des Browsers wird komplett durch den "
            "GuideOSBookHub-Bestand ersetzt. Vorherige Lesezeichen dort gehen verloren."
        ),
        "export.back_button": "Zurück",
        "export.cancel_button": "Abbrechen",
        "export.next_button": "Weiter",
        "export.write_button": "Jetzt schreiben",
        "export.browser_step_label": "Welchen Browser möchtest du aktualisieren?",
        "export.found": "✓ gefunden",
        "export.not_found": "✗ nicht gefunden",
        "export.strategy_step_label": "Wie sollen die Lesezeichen im Browser aktualisiert werden?",
        "export.step_label": "Schritt {step} von 3 — {title}",
        "export.warning_text": (
            "⚠️ Wichtiger Hinweis\n\n{browser} muss vollständig geschlossen sein, bevor "
            "fortgefahren wird. Andernfalls überschreibt der Browser die Änderung beim "
            "nächsten eigenen Speichern wieder."
        ),
        "export.selection_missing_title": "Auswahl fehlt",
        "export.selection_missing_text": "Bitte einen gefundenen Browser auswählen.",
        "export.browser_running_title": "Browser läuft noch",
        "export.browser_running_text": (
            "{browser} läuft noch. Bitte vollständig schließen und erneut versuchen."
        ),
        "export.not_found_title": "Nicht gefunden",
        "export.not_found_text": "Lesezeichen-Datei von {browser} nicht gefunden.",
        "export.failed_title": "Fehlgeschlagen",
        "export.done_title": "Fertig",
        "export.done_text": (
            "Lesezeichen wurden in {browser} geschrieben. Starte den Browser neu, "
            "um die Änderungen zu sehen."
        ),

        # ---------- Einstellungen (settings_dialog.py) ----------
        "settings.window_title": "Einstellungen",
        "settings.rclone_missing_label": (
            "rclone wurde nicht gefunden. Ohne rclone kann kein Sync-Profil "
            "angelegt werden."
        ),
        "settings.install_rclone_button": "rclone installieren",
        "settings.refresh_remotes_button": "Remotes aktualisieren",
        "settings.add_cloud_remote_button": "Cloud-/Stick-Verbindung einrichten…",
        "settings.field.name": "Name",
        "settings.field.remote": "Remote",
        "settings.field.path": "Pfad/Dateiname",
        "settings.field.interval": "Sync-Intervall",
        "settings.field.language": "Sprache",
        "settings.interval_suffix": " min",
        "settings.auto_sync_checkbox": "Automatisch synchronisieren",
        "settings.test_button": "Verbindung testen",
        "settings.add_profile_button": "Neues Profil",
        "settings.remove_profile_button": "Profil entfernen",
        "settings.save_button": "Speichern",
        "settings.new_profile_default_name": "Neues Profil",
        "settings.unnamed_profile": "Unbenanntes Profil",
        "settings.remove_confirm_title": "Profil entfernen",
        "settings.remove_confirm_text": (
            "Profil wirklich entfernen? Bereits synchronisierte Lesezeichen bleiben lokal "
            "erhalten, werden aber nicht mehr mit diesem Ziel abgeglichen."
        ),
        "settings.testing_connection": "Teste Verbindung...",
        "settings.no_remote_title": "Kein Remote konfiguriert",
        "settings.no_remote_text": (
            "Bitte zuerst per 'rclone config' im Terminal mindestens ein Remote "
            "einrichten, dann hier auf 'Remotes aktualisieren' klicken."
        ),

        # ---------- rclone-Installation (rclone_install_dialog.py) ----------
        "rclone_install.window_title": "rclone wird benötigt",
        "rclone_install.info": (
            "GuideOSBookHub synchronisiert Lesezeichen über rclone, das auf "
            "diesem System nicht gefunden wurde.\n\n"
            "Ohne rclone funktioniert die App weiter als lokaler "
            "Lesezeichen-Manager, aber ohne Cloud-/Stick-Synchronisation.\n\n"
            "Soll rclone jetzt installiert werden? Es erscheint eine "
            "grafische Rechte-Abfrage (PolicyKit), da dafür "
            "Administratorrechte nötig sind."
        ),
        "rclone_install.later_button": "Später",
        "rclone_install.install_button": "Installieren",
        "rclone_install.installing": "Installation läuft, bitte die Rechte-Abfrage bestätigen...",
        "rclone_install.success": "rclone wurde erfolgreich installiert.",
        "rclone_install.done_button": "Fertig",
        "rclone_install.retry_button": "Erneut versuchen",
    },
    "en": {
        # ---------- General ----------
        "app.title": "GuideOSBookHub",
        "common.ok": "OK",
        "common.cancel": "Cancel",
        "common.close": "Close",
        "common.yes": "Yes",
        "common.no": "No",
        "common.error_title": "Error",
        "common.error_prefix": "Error: ",
        "common.ok_prefix": "OK: ",

        # ---------- Home screen (home_window.py) ----------
        "home.settings_button": "Settings",
        "home.tagline": (
            "Your browser bookmarks, securely synced via a cloud or a USB drive "
            "of your choice."
        ),
        "home.subtitle": (
            "You'll keep adding, editing, and deleting bookmarks in your browser as "
            "usual. GuideOSBookHub handles the import, cloud/USB sync, and writing back "
            "to your browser."
        ),
        "home.import_card.title": "📥  Import from browser into the Hub",
        "home.import_card.subtitle": "Bring in bookmarks from Vivaldi, Chrome & more",
        "home.cloud_card.title": "☁️  Set up cloud/USB sync",
        "home.cloud_card.subtitle": (
            "Connect GuideOSBookHub to a cloud, a USB drive, or another provider "
            "of your choice"
        ),
        "home.export_card.title": "📤  Import from the Hub into a new browser",
        "home.export_card.subtitle": (
            "Write bookmarks into a browser of your choice on this computer"
        ),
        "home.sync_button": "Sync now",
        "home.status_ready": "Ready.",
        "home.status_syncing": "Syncing...",
        "home.status_profile_error": "{profile}: Error – {error}",
        "home.status_profile_result": (
            "{profile}: {created} new, {updated} updated, "
            "{deleted} deleted, {conflicts} conflicts resolved"
        ),

        # ---------- Browser import (browser_import_dialog.py) ----------
        "import.window_title": "Import bookmarks from browser",
        "import.intro_first_run": (
            "Welcome to GuideOSBookHub! Which browser do you use? "
            "Your bookmarks will be found and imported automatically."
        ),
        "import.intro": "Which browser would you like to import?",
        "import.other_file_item": "Choose another file (e.g. Firefox export) …",
        "import.skip_button": "Skip",
        "import.cancel_button": "Cancel",
        "import.import_button": "Import",
        "import.not_found_title": "Not found",
        "import.not_found_text": (
            "The bookmarks file for {browser} wasn't found at the expected location. "
            "Please export manually and select the file instead."
        ),
        "import.file_dialog_title": "Select bookmarks file",
        "import.file_dialog_filter": "HTML files (*.html *.htm)",
        "import.failed_title": "Import failed",
        "import.done_title": "Import complete",
        "import.done_text": (
            "{groups} folders and {bookmarks} bookmarks imported, "
            "{skipped} duplicates skipped."
        ),

        # ---------- Cloud/USB sync setup (cloud_setup_dialog.py) ----------
        "cloud.window_title": "Set up cloud/USB sync",
        "cloud.intro_first_run": (
            "Would you like to sync your bookmarks now with a cloud or a USB drive?"
        ),
        "cloud.intro": "Choose a provider for syncing.",
        "cloud.step_label": "Step {step} of 2 — {title}",
        "cloud.step_title.provider": "Choose provider",
        "cloud.step_title.details": "Credentials",
        "cloud.back_button": "Back",
        "cloud.next_button": "Next",
        "cloud.provider.webdav": "Nextcloud / ownCloud / WebDAV",
        "cloud.provider.protondrive": "Proton Drive",
        "cloud.provider.drive": "Google Drive",
        "cloud.provider.onedrive": "Microsoft OneDrive",
        "cloud.provider.dropbox": "Dropbox",
        "cloud.provider.pcloud": "pCloud",
        "cloud.provider.local": "USB drive / local folder",
        "cloud.oauth_intro": (
            "Sign in in your browser to connect {provider} with GuideOSBookHub."
        ),
        "cloud.oauth_button": "Sign in in browser",
        "cloud.oauth_waiting": "Waiting for sign-in in browser...",
        "cloud.local_intro": (
            "Choose a folder on a USB drive or a local disk where the bookmarks "
            "should be stored."
        ),
        "cloud.local_choose_button": "Choose folder",
        "cloud.local_selected_path_label": "Selected folder:",
        "cloud.local_no_folder_title": "No folder selected",
        "cloud.local_no_folder_text": "Please choose a folder first.",
        "cloud.local_not_writable_title": "Folder not writable",
        "cloud.local_not_writable_text": (
            "This folder can't be written to. Please choose a different folder "
            "(e.g. on the USB drive)."
        ),
        "cloud.protondrive_twofa_field": "2FA code (optional)",
        "cloud.protondrive_mailbox_password_field": "Mailbox password (optional)",
        "cloud.protondrive_hint": (
            "If your Proton account uses two-factor authentication, enter the "
            "current code here."
        ),
        "cloud.vendor.nextcloud": "Nextcloud",
        "cloud.vendor.owncloud": "ownCloud",
        "cloud.vendor.other": "Generic WebDAV",
        "cloud.field.name": "Connection name",
        "cloud.field.vendor": "Provider",
        "cloud.field.url": "Server URL",
        "cloud.field.user": "Username",
        "cloud.field.password": "Password",
        "cloud.url_placeholder": "https://your-domain.tld/remote.php/dav/files/USERNAME/",
        "cloud.hint": (
            "Tip for Nextcloud: Don't use your regular password — create an app "
            "password under Settings → Security instead."
        ),
        "cloud.skip_button": "Skip",
        "cloud.cancel_button": "Cancel",
        "cloud.setup_button": "Set up",
        "cloud.connecting": "Connecting...",
        "cloud.step_create": "Creating connection...",
        "cloud.step_test": "Testing connection...",
        "cloud.step_done": "Connection set up successfully.",
        "cloud.missing_fields_title": "Missing information",
        "cloud.missing_fields_text": "Please fill in all fields.",
        "cloud.rclone_missing_title": "rclone missing",
        "cloud.rclone_missing_text": (
            "rclone wasn't found. A cloud connection can't be set up without rclone."
        ),
        "cloud.name_taken_title": "Connection already exists",
        "cloud.name_taken_text": (
            "There's already a connection named '{name}'. Update it with these "
            "credentials?"
        ),
        "cloud.done_title": "Done",
        "cloud.done_text": (
            "'{name}' is set up. Your bookmarks will now sync automatically "
            "(more options are available under 'Settings')."
        ),

        # ---------- Write back to browser (export_to_browser_dialog.py) ----------
        "export.window_title": "Write bookmarks back to browser",
        "export.step_title.browser": "Choose browser",
        "export.step_title.strategy": "Choose strategy",
        "export.step_title.confirm": "Confirm",
        "export.strategy.merge.title": "Merge",
        "export.strategy.merge.hint": (
            "Existing bookmarks in the browser are kept, GuideOSBookHub only adds "
            "new ones (no duplicate links)."
        ),
        "export.strategy.separate_folder.title": "Into its own folder",
        "export.strategy.separate_folder.hint": (
            "All GuideOSBookHub bookmarks are collected into a new folder, "
            "everything else stays unchanged."
        ),
        "export.strategy.replace.title": "Replace",
        "export.strategy.replace.hint": (
            "The browser's bookmark bar is completely replaced by GuideOSBookHub's "
            "bookmarks. Previous bookmarks there will be lost."
        ),
        "export.back_button": "Back",
        "export.cancel_button": "Cancel",
        "export.next_button": "Next",
        "export.write_button": "Write now",
        "export.browser_step_label": "Which browser would you like to update?",
        "export.found": "✓ found",
        "export.not_found": "✗ not found",
        "export.strategy_step_label": "How should the bookmarks in the browser be updated?",
        "export.step_label": "Step {step} of 3 — {title}",
        "export.warning_text": (
            "⚠️ Important\n\n{browser} must be completely closed before continuing. "
            "Otherwise the browser will overwrite the change the next time it saves."
        ),
        "export.selection_missing_title": "Selection missing",
        "export.selection_missing_text": "Please select a browser that was found.",
        "export.browser_running_title": "Browser still running",
        "export.browser_running_text": (
            "{browser} is still running. Please close it completely and try again."
        ),
        "export.not_found_title": "Not found",
        "export.not_found_text": "Bookmarks file for {browser} not found.",
        "export.failed_title": "Failed",
        "export.done_title": "Done",
        "export.done_text": (
            "Bookmarks were written to {browser}. Restart the browser to see "
            "the changes."
        ),

        # ---------- Settings (settings_dialog.py) ----------
        "settings.window_title": "Settings",
        "settings.rclone_missing_label": (
            "rclone wasn't found. A sync profile can't be created without rclone."
        ),
        "settings.install_rclone_button": "Install rclone",
        "settings.refresh_remotes_button": "Refresh remotes",
        "settings.add_cloud_remote_button": "Set up cloud/USB connection…",
        "settings.field.name": "Name",
        "settings.field.remote": "Remote",
        "settings.field.path": "Path/filename",
        "settings.field.interval": "Sync interval",
        "settings.field.language": "Language",
        "settings.interval_suffix": " min",
        "settings.auto_sync_checkbox": "Sync automatically",
        "settings.test_button": "Test connection",
        "settings.add_profile_button": "New profile",
        "settings.remove_profile_button": "Remove profile",
        "settings.save_button": "Save",
        "settings.new_profile_default_name": "New profile",
        "settings.unnamed_profile": "Unnamed profile",
        "settings.remove_confirm_title": "Remove profile",
        "settings.remove_confirm_text": (
            "Really remove this profile? Already-synced bookmarks stay on this "
            "device but will no longer be matched against this destination."
        ),
        "settings.testing_connection": "Testing connection...",
        "settings.no_remote_title": "No remote configured",
        "settings.no_remote_text": (
            "Please first set up at least one remote via 'rclone config' in the "
            "terminal, then click 'Refresh remotes' here."
        ),

        # ---------- rclone installation (rclone_install_dialog.py) ----------
        "rclone_install.window_title": "rclone is required",
        "rclone_install.info": (
            "GuideOSBookHub syncs bookmarks via rclone, which wasn't found on "
            "this system.\n\n"
            "Without rclone the app still works as a local bookmark manager, "
            "just without cloud/USB sync.\n\n"
            "Install rclone now? A graphical permission prompt (PolicyKit) will "
            "appear, since administrator rights are needed."
        ),
        "rclone_install.later_button": "Later",
        "rclone_install.install_button": "Install",
        "rclone_install.installing": "Installing, please confirm the permission prompt...",
        "rclone_install.success": "rclone was installed successfully.",
        "rclone_install.done_button": "Done",
        "rclone_install.retry_button": "Try again",
    },
}


def t(key: str, **kwargs) -> str:
    language = Settings.get_language()
    table = _TRANSLATIONS.get(language) or _TRANSLATIONS[DEFAULT_LANGUAGE]
    text = table.get(key)
    if text is None:
        text = _TRANSLATIONS[DEFAULT_LANGUAGE].get(key, key)
    return text.format(**kwargs) if kwargs else text
