"""macOS notifications via the UserNotifications framework.

Needs to run inside an app bundle (dist/Stumpbar.app). When run from source,
falls back to rumps' older notification API, which may not show on newer macOS.
"""

import sys
import uuid

import objc
import rumps
from Foundation import NSBundle, NSObject

try:
    import UserNotifications as UN
except ImportError:  # pragma: no cover
    UN = None


def log(msg):
    print(f"[notify] {msg}", file=sys.stderr, flush=True)


class _Delegate(NSObject, protocols=[objc.protocolNamed("UNUserNotificationCenterDelegate")]):
    # Show banners even while the app is active (e.g. its menu is open).
    def userNotificationCenter_willPresentNotification_withCompletionHandler_(self, center, n, handler):
        handler(UN.UNNotificationPresentationOptionBanner
                | UN.UNNotificationPresentationOptionList
                | UN.UNNotificationPresentationOptionSound)


SETTINGS_URL = "x-apple.systempreferences:com.apple.Notifications-Settings.extension"


class Notifier:
    def __init__(self):
        self.center = None
        self.allowed = None  # None until macOS answers the permission request
        if UN is not None and NSBundle.mainBundle().bundleIdentifier():
            self.center = UN.UNUserNotificationCenter.currentNotificationCenter()
            self.delegate = _Delegate.alloc().init()
            self.center.setDelegate_(self.delegate)
            options = UN.UNAuthorizationOptionAlert | UN.UNAuthorizationOptionSound
            self.center.requestAuthorizationWithOptions_completionHandler_(options, self._on_permission)
        else:
            log("not running from an app bundle; using rumps.notification")

    def _on_permission(self, granted, err):
        self.allowed = bool(granted)
        log(f"permission granted={self.allowed} error={err}")

    def send(self, title, subtitle="", body=""):
        if self.center is None:
            rumps.notification(title, subtitle, body, sound=True)
            return
        content = UN.UNMutableNotificationContent.alloc().init()
        content.setTitle_(title)
        content.setSubtitle_(subtitle)
        content.setBody_(body)
        content.setSound_(UN.UNNotificationSound.defaultSound())
        request = UN.UNNotificationRequest.requestWithIdentifier_content_trigger_(
            str(uuid.uuid4()), content, None)
        self.center.addNotificationRequest_withCompletionHandler_(
            request, lambda err: log(f"sent {title!r} error={err}"))

    def log_delivered(self):
        """Log what Notification Center is currently showing from this app (for testing)."""
        if self.center is not None:
            self.center.getDeliveredNotificationsWithCompletionHandler_(
                lambda ns: log("delivered:\n" + "\n".join(
                    f"  {n.request().content().title()} | {n.request().content().subtitle()}" for n in ns)))
