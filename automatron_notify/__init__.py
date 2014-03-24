from automatron.controller.plugin import IAutomatronEventHandler


class IAutomatronNotifyHandler(IAutomatronEventHandler):
    def on_notify(server, username, title, body, body_as_html=None):
        """
        Called when a notification is triggered.
        """
